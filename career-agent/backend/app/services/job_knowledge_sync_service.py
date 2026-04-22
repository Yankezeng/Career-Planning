from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.career import SystemConfig
from app.models.job import Job, JobCertificate, JobSkill
from app.services.graph.job_graph_neo4j import JobGraphNeo4jService
from app.services.graph.neo4j_service import get_neo4j_service
from app.services.vector_search_service import VectorSearchService


COURSE_LIBRARY = {
    "python": ["Python 基础编程", "Python 数据处理实战"],
    "java": ["Java 面向对象开发", "Spring Boot 企业应用开发"],
    "springboot": ["Spring Boot 企业应用开发"],
    "vue": ["Vue 3 前端开发", "前端工程化实践"],
    "react": ["React 前端组件开发", "前端工程化实践"],
    "javascript": ["JavaScript 交互开发", "前端工程化实践"],
    "typescript": ["TypeScript 工程化开发"],
    "sql": ["SQL 查询基础", "数据库建模与优化"],
    "mysql": ["MySQL 数据库实战", "数据库建模与优化"],
    "数据分析": ["数据分析方法", "Excel 与 BI 数据实战"],
    "excel": ["Excel 数据分析"],
    "产品": ["产品需求分析", "产品原型设计"],
    "原型": ["Axure 原型设计"],
    "运营": ["新媒体运营实战", "内容增长策略"],
    "设计": ["UI 视觉设计", "Figma 界面设计"],
    "测试": ["软件测试基础", "接口自动化测试"],
    "运维": ["Linux 运维基础", "云平台部署与监控"],
}

CERTIFICATE_LIBRARY = {
    "python": ["Python 程序设计证书"],
    "java": ["Java 软件开发工程师证书"],
    "sql": ["数据库系统工程师"],
    "mysql": ["数据库系统工程师"],
    "数据分析": ["数据分析师证书"],
    "产品": ["NPDP 产品经理认证"],
    "设计": ["UI 设计师证书"],
    "运营": ["新媒体运营师证书"],
    "测试": ["软件测试工程师证书"],
    "运维": ["云计算工程师证书"],
}

LEVEL_RULES = [
    ("实习", 1),
    ("助理", 1),
    ("初级", 2),
    ("专员", 2),
    ("工程师", 2),
    ("分析师", 2),
    ("设计师", 2),
    ("运营", 2),
    ("高级", 3),
    ("资深", 4),
    ("主管", 4),
    ("组长", 4),
    ("经理", 5),
    ("负责人", 5),
    ("总监", 6),
]


class JobKnowledgeSyncService:
    CONFIG_KEY = "job_kb_sync_meta"
    SYNC_SOURCE = "milvus"

    def __init__(self, db: Session):
        self.db = db
        self.vector_service = VectorSearchService()
        self.graph_service = JobGraphNeo4jService()
        self.neo4j = get_neo4j_service()

    def get_sync_status(self) -> dict[str, Any]:
        documents = self.vector_service.list_documents(limit=8000)
        meta = self._load_meta()
        fingerprint = self._fingerprint(documents) if documents else ""
        companies = sorted(
            {
                (doc.get("metadata") or {}).get("company_name")
                for doc in documents
                if (doc.get("metadata") or {}).get("company_name")
            }
        )
        categories = sorted({doc.get("job_category") for doc in documents if doc.get("job_category")})
        synced_jobs = (
            self.db.query(Job)
            .filter(Job.deleted.is_(False))
            .all()
        )
        synced_count = len([job for job in synced_jobs if self._is_synced_job(job)])

        graph_job_count = 0
        try:
            all_jobs = self.graph_service.get_all_jobs(limit=10000)
            graph_job_count = len(all_jobs)
        except Exception:
            pass

        return {
            "vector_backend": self.vector_service.backend_name,
            "document_count": len(documents),
            "company_count": len(companies),
            "category_count": len(categories),
            "sample_jobs": [doc.get("job_name") for doc in documents[:6]],
            "sample_companies": companies[:6],
            "current_fingerprint": fingerprint,
            "last_sync": meta.get("last_sync"),
            "last_result": meta.get("last_result"),
            "last_doc_count": meta.get("document_count", 0),
            "synced_job_count": synced_count,
            "graph_job_count": graph_job_count,
            "up_to_date": bool(fingerprint and meta.get("fingerprint") == fingerprint),
        }

    def sync_from_knowledge_base(self, operator_id: int | None = None, force: bool = True) -> dict[str, Any]:
        documents = self.vector_service.list_documents(limit=8000)
        if not documents:
            result = {
                "status": "empty",
                "message": "Milvus 岗位知识库中暂无可同步的岗位文档。",
                "document_count": 0,
                "jobs_synced": 0,
                "relations_created": 0,
            }
            self._save_meta(
                {
                    "fingerprint": "",
                    "last_sync": datetime.now().isoformat(timespec="seconds"),
                    "document_count": 0,
                    "last_result": result,
                }
            )
            self.db.commit()
            return result

        fingerprint = self._fingerprint(documents)
        meta = self._load_meta()
        if not force and meta.get("fingerprint") == fingerprint:
            return {
                "status": "unchanged",
                "message": "岗位知识库未发生变化，无需重新同步。",
                "document_count": len(documents),
                "jobs_synced": meta.get("last_result", {}).get("jobs_synced", 0),
                "relations_created": meta.get("last_result", {}).get("relations_created", 0),
                "last_sync": meta.get("last_sync"),
            }

        aggregated_jobs = self._aggregate_documents(documents)
        if not aggregated_jobs:
            return {
                "status": "empty",
                "message": "知识库中存在文档，但未识别出可用岗位数据。",
                "document_count": len(documents),
                "jobs_synced": 0,
                "relations_created": 0,
            }

        previous_synced_jobs = {
            job.name: job
            for job in self.db.query(Job).filter(Job.deleted.is_(False)).all()
            if self._is_synced_job(job)
        }
        active_names: set[str] = set()
        synced_jobs: list[Job] = []

        for payload in aggregated_jobs:
            active_names.add(payload["name"])
            existing_job = (
                self.db.query(Job)
                .filter(Job.name == payload["name"])
                .first()
            )
            job = self._upsert_job(existing_job, payload, operator_id)
            synced_jobs.append(job)

        stale_names = set(previous_synced_jobs) - active_names
        for stale_name in stale_names:
            previous_synced_jobs[stale_name].deleted = True

        self.db.flush()

        self.graph_service.delete_all_relations()
        relation_count = self._rebuild_relations(synced_jobs, operator_id)

        for job in synced_jobs:
            self.graph_service.create_job_node(
                job_id=job.id,
                name=job.name,
                properties={
                    "category": job.category or "",
                    "salary_range": job.salary_range or "",
                    "location": "",
                    "description": job.description or "",
                }
            )

        self._sync_relations_to_graph(synced_jobs, operator_id)

        result = {
            "status": "success",
            "message": "Milvus 岗位知识已同步到岗位业务库和 Neo4j 图数据库。",
            "document_count": len(documents),
            "jobs_synced": len(synced_jobs),
            "relations_created": relation_count,
            "deactivated_jobs": len(stale_names),
            "sample_jobs": [job.name for job in synced_jobs[:6]],
        }
        self._save_meta(
            {
                "fingerprint": fingerprint,
                "last_sync": datetime.now().isoformat(timespec="seconds"),
                "document_count": len(documents),
                "last_result": result,
            }
        )
        self.db.commit()
        return result

    def _sync_relations_to_graph(self, jobs: list[Job], operator_id: int | None) -> int:
        relation_count = 0
        active_jobs = self.db.query(Job).filter(Job.deleted.is_(False)).all()
        tracked_ids = [job.id for job in active_jobs]
        job_levels = {job.id: self._infer_job_level(job.name) for job in active_jobs}

        added_pairs: set[tuple[int, int]] = set()

        for source in active_jobs:
            candidates: list[tuple[float, dict[str, Any]]] = []
            for target in active_jobs:
                if source.id == target.id:
                    continue

                candidate = self._score_relation_candidate(source, target, job_levels)
                if candidate is None:
                    continue

                score, relation_type, similarity = candidate
                payload = self._build_relation_payload(source, target, relation_type, similarity, operator_id)
                candidates.append((score, payload))

            seen_targets: set[int] = set()
            for _, payload in sorted(candidates, key=lambda item: item[0], reverse=True):
                pair = (payload["source_job_id"], payload["target_job_id"])
                target_id = payload["target_job_id"]
                if pair in added_pairs or target_id in seen_targets:
                    continue
                relation_count += 1
                self.graph_service.create_job_relation(
                    from_job_id=payload["source_job_id"],
                    to_job_id=payload["target_job_id"],
                    relation_type=payload["relation_type"],
                    weight=similarity,
                )
                added_pairs.add(pair)
                seen_targets.add(target_id)
                if len(seen_targets) >= 4:
                    break

        for category_jobs in self._group_jobs_by_category(active_jobs).values():
            ordered_jobs = sorted(category_jobs, key=lambda job: (job_levels[job.id], job.name))
            for source, target in zip(ordered_jobs, ordered_jobs[1:]):
                pair = (source.id, target.id)
                if pair in added_pairs:
                    continue
                relation_type = "晋升岗位" if job_levels[source.id] < job_levels[target.id] else "可迁移岗位"
                similarity = self._pair_similarity(source, target)
                self.graph_service.create_job_relation(
                    from_job_id=source.id,
                    to_job_id=target.id,
                    relation_type=relation_type,
                    weight=similarity,
                )
                added_pairs.add(pair)
                relation_count += 1

        return relation_count

    def _aggregate_documents(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for document in documents:
            job_name = self._clean_text(document.get("job_name"))
            if not job_name:
                continue
            grouped[job_name].append(document)

        aggregated: list[dict[str, Any]] = []
        for job_name, items in grouped.items():
            categories = [self._clean_text(item.get("job_category")) for item in items]
            industries = [self._clean_text(item.get("industry")) for item in items]
            metadata_list = [(item.get("metadata") or {}) for item in items]
            core_skills = self._merge_ranked_tags(metadata_list, "core_skills", limit=10)
            common_skills = self._merge_ranked_tags(metadata_list, "common_skills", limit=8)
            certificate_tags = self._merge_ranked_tags(metadata_list, "certificates", limit=8)
            description = self._pick_longest_text(
                [metadata.get("description") for metadata in metadata_list] + [item.get("content") for item in items]
            )
            work_content = self._pick_longest_text([metadata.get("work_content") for metadata in metadata_list])
            development_direction = self._pick_longest_text(
                [metadata.get("development_direction") for metadata in metadata_list]
            )
            companies = sorted({self._clean_text(metadata.get("company_name")) for metadata in metadata_list if metadata.get("company_name")})
            aggregated.append(
                {
                    "name": job_name,
                    "category": self._pick_most_common(categories) or "综合",
                    "industry": self._pick_most_common(industries) or "",
                    "description": description[:3000],
                    "degree_requirement": self._pick_most_common(
                        [self._clean_text(metadata.get("degree_requirement")) for metadata in metadata_list]
                    ),
                    "major_requirement": self._pick_most_common(
                        [self._clean_text(metadata.get("major_requirement")) for metadata in metadata_list]
                    ),
                    "internship_requirement": self._pick_most_common(
                        [self._clean_text(metadata.get("internship_requirement")) for metadata in metadata_list]
                    ),
                    "work_content": work_content[:2000],
                    "development_direction": development_direction[:2000],
                    "salary_range": self._pick_most_common(
                        [self._clean_text(metadata.get("salary_range")) for metadata in metadata_list]
                    ),
                    "core_skill_tags": core_skills,
                    "common_skill_tags": common_skills,
                    "certificate_tags": certificate_tags,
                    "skills": self._build_skill_payloads(core_skills, common_skills),
                    "certificates": self._build_certificate_payloads(certificate_tags),
                    "job_profile": {
                        "sync_source": self.SYNC_SOURCE,
                        "knowledge_doc_ids": [item.get("id") for item in items if item.get("id")],
                        "source_doc_count": len(items),
                        "source_companies": companies,
                        "sample_source_file": items[0].get("source_file") if items else "",
                    },
                }
            )

        aggregated.sort(key=lambda item: (item["category"], item["name"]))
        return aggregated

    def _upsert_job(self, job: Job | None, payload: dict[str, Any], operator_id: int | None) -> Job:
        if job is None:
            job = Job(name=payload["name"])
            job.created_by = operator_id
            self.db.add(job)

        existing_profile = job.job_profile if isinstance(job.job_profile, dict) else {}
        incoming_profile = payload.get("job_profile") if isinstance(payload.get("job_profile"), dict) else {}

        if self._is_official_profile(existing_profile):
            merged_companies = sorted(
                {
                    self._clean_text(item)
                    for item in [*(existing_profile.get("source_companies") or []), *(incoming_profile.get("source_companies") or [])]
                    if self._clean_text(item)
                }
            )
            job.job_profile = {
                **existing_profile,
                "source_companies": merged_companies,
                "knowledge_sync": {
                    "sync_source": incoming_profile.get("sync_source", self.SYNC_SOURCE),
                    "knowledge_doc_ids": incoming_profile.get("knowledge_doc_ids") or [],
                    "source_doc_count": int(incoming_profile.get("source_doc_count") or 0),
                    "sample_source_file": incoming_profile.get("sample_source_file") or "",
                },
            }
            job.deleted = False
            job.generated_by_ai = True
            job.updated_by = operator_id
            self.db.flush()
            return job

        for key in [
            "name",
            "category",
            "industry",
            "description",
            "degree_requirement",
            "major_requirement",
            "internship_requirement",
            "work_content",
            "development_direction",
            "salary_range",
            "core_skill_tags",
            "common_skill_tags",
            "certificate_tags",
            "job_profile",
        ]:
            setattr(job, key, payload.get(key))

        job.skill_weight = 0.4
        job.certificate_weight = 0.1
        job.project_weight = 0.2
        job.soft_skill_weight = 0.1
        job.generated_by_ai = True
        job.deleted = False
        job.updated_by = operator_id

        job.skills.clear()
        for item in payload.get("skills", []):
            job.skills.append(JobSkill(**item))

        job.certificates.clear()
        for item in payload.get("certificates", []):
            job.certificates.append(JobCertificate(**item))

        self.db.flush()
        return job

    @staticmethod
    def _is_official_profile(profile: dict[str, Any]) -> bool:
        return bool(profile.get("portrait_dimensions")) and bool(profile.get("vertical_path")) and bool(profile.get("transfer_paths"))

    def _rebuild_relations(self, jobs: list[Job], operator_id: int | None) -> int:
        return self._sync_relations_to_graph(jobs, operator_id)

    def _build_relation_payload(
        self,
        source: Job,
        target: Job,
        relation_type: str,
        similarity: float,
        operator_id: int | None,
        reason_override: str | None = None,
    ) -> dict[str, Any]:
        source_skills = self._skill_set(source)
        target_skills = self._skill_set(target)
        overlap = [skill for skill in target.core_skill_tags if skill in source_skills][:3]
        missing = [skill for skill in target.core_skill_tags if skill not in source_skills][:3]
        related_skills = self._dedupe_list(
            overlap + missing or list(target_skills)[:5] or list(source_skills)[:5] or [target.category or source.category or "岗位通用能力"]
        )[:6]
        recommended_courses = self._recommend_courses(related_skills)
        recommended_certificates = self._dedupe_list(
            list(target.certificate_tags or [])[:3] + self._recommend_certificates(related_skills)
        )[:4]
        relation_reason = reason_override or (
            f"{source.name} 与 {target.name} 的技能重合度约为 {round(similarity * 100)}%，"
            f"建议重点围绕 {', '.join(related_skills[:3]) or '关键技能'} 进行衔接。"
        )
        return {
            "source_job_id": source.id,
            "target_job_id": target.id,
            "relation_type": relation_type,
            "reason": relation_reason,
            "related_skills": related_skills,
            "recommended_courses": recommended_courses,
            "recommended_certificates": recommended_certificates,
            "created_by": operator_id,
            "updated_by": operator_id,
        }

    def _score_relation_candidate(
        self,
        source: Job,
        target: Job,
        job_levels: dict[int, int],
    ) -> tuple[float, str, float] | None:
        metrics = self._pair_metrics(source, target, job_levels)
        score = metrics["similarity"]
        if metrics["same_category"]:
            score += 0.28
        if metrics["same_industry"]:
            score += 0.12
        if metrics["mentioned_in_path"]:
            score += 0.18
        if metrics["level_gap"] <= 1:
            score += 0.08
        if (not metrics["source_skills"] or not metrics["target_skills"]) and (
            metrics["same_category"] or metrics["same_industry"]
        ):
            score += 0.04

        if metrics["same_category"] and metrics["source_level"] < metrics["target_level"] and (
            metrics["similarity"] >= 0.08 or metrics["mentioned_in_path"] or metrics["same_industry"]
        ):
            return score + 0.2, "晋升岗位", metrics["similarity"]

        if metrics["same_category"] and metrics["source_level"] > metrics["target_level"] and (
            metrics["similarity"] >= 0.08 or metrics["same_industry"]
        ):
            return score + 0.16, "前置岗位", metrics["similarity"]

        if score >= 0.24:
            relation_type = "可迁移岗位" if (
                metrics["same_category"] or metrics["same_industry"] or metrics["similarity"] >= 0.12 or metrics["level_gap"] <= 1
            ) else "关联岗位"
            return score, relation_type, metrics["similarity"]

        return None

    def _group_jobs_by_category(self, jobs: list[Job]) -> dict[str, list[Job]]:
        grouped: dict[str, list[Job]] = defaultdict(list)
        for job in jobs:
            grouped[job.category or "综合"].append(job)
        return grouped

    def _pair_metrics(
        self,
        source: Job,
        target: Job,
        job_levels: dict[int, int],
    ) -> dict[str, Any]:
        source_skills = self._skill_set(source)
        target_skills = self._skill_set(target)
        similarity = self._jaccard(source_skills, target_skills)
        return {
            "source_skills": source_skills,
            "target_skills": target_skills,
            "similarity": similarity,
            "source_level": job_levels[source.id],
            "target_level": job_levels[target.id],
            "level_gap": abs(job_levels[source.id] - job_levels[target.id]),
            "same_category": bool(source.category and target.category and source.category == target.category),
            "same_industry": bool(source.industry and target.industry and source.industry == target.industry),
            "mentioned_in_path": bool(
                (source.development_direction and target.name in source.development_direction)
                or (target.development_direction and source.name in target.development_direction)
            ),
        }

    def _pair_similarity(self, source: Job, target: Job) -> float:
        return self._jaccard(self._skill_set(source), self._skill_set(target))

    def _name_similarity(self, left_name: str, right_name: str) -> float:
        return self._jaccard(self._job_name_tokens(left_name), self._job_name_tokens(right_name))

    @staticmethod
    def _job_name_tokens(job_name: str) -> set[str]:
        normalized = str(job_name or "").lower()
        return {token for token in re.findall(r"[a-z0-9+#./-]+|[\u4e00-\u9fff]{1,3}", normalized) if token}

    def _load_meta(self) -> dict[str, Any]:
        config = (
            self.db.query(SystemConfig)
            .filter(SystemConfig.key == self.CONFIG_KEY, SystemConfig.deleted.is_(False))
            .first()
        )
        if not config:
            return {}
        try:
            return json.loads(config.value or "{}")
        except json.JSONDecodeError:
            return {}

    def _save_meta(self, value: dict[str, Any]) -> None:
        config = (
            self.db.query(SystemConfig)
            .filter(SystemConfig.key == self.CONFIG_KEY, SystemConfig.deleted.is_(False))
            .first()
        )
        serialized = json.dumps(value, ensure_ascii=False)
        if config:
            config.value = serialized
            config.description = "Milvus 岗位知识库同步元数据"
            config.config_type = "json"
        else:
            self.db.add(
                SystemConfig(
                    key=self.CONFIG_KEY,
                    value=serialized,
                    config_type="json",
                    description="Milvus 岗位知识库同步元数据",
                )
            )

    @classmethod
    def _is_synced_job(cls, job: Job) -> bool:
        profile = job.job_profile or {}
        return profile.get("sync_source") == cls.SYNC_SOURCE

    @staticmethod
    def _fingerprint(documents: list[dict[str, Any]]) -> str:
        stable = [
            {
                "id": item.get("id"),
                "job_name": item.get("job_name"),
                "job_category": item.get("job_category"),
                "content": item.get("content"),
            }
            for item in documents
        ]
        serialized = json.dumps(stable, ensure_ascii=False, sort_keys=True)
        return hashlib.sha1(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _clean_text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _pick_most_common(values: list[str]) -> str:
        cleaned = [item for item in values if item]
        if not cleaned:
            return ""
        return Counter(cleaned).most_common(1)[0][0]

    @staticmethod
    def _pick_longest_text(values: list[str | None]) -> str:
        texts = [str(item).strip() for item in values if str(item or "").strip()]
        if not texts:
            return ""
        return max(texts, key=len)

    def _merge_ranked_tags(self, metadata_list: list[dict[str, Any]], field: str, limit: int = 8) -> list[str]:
        counter: Counter[str] = Counter()
        for metadata in metadata_list:
            for tag in self._split_tags(metadata.get(field)):
                counter[tag] += 1
        return [item for item, _ in counter.most_common(limit)]

    @staticmethod
    def _split_tags(value: Any) -> list[str]:
        if isinstance(value, list):
            parts = value
        else:
            text = str(value or "").strip()
            parts = re.split(r"[、,，;；/|\\\n]+", text)
        cleaned: list[str] = []
        for item in parts:
            tag = str(item or "").strip()
            if not tag or len(tag) > 50:
                continue
            cleaned.append(tag)
        return cleaned

    @staticmethod
    def _build_skill_payloads(core_skills: list[str], common_skills: list[str]) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for index, skill in enumerate(core_skills):
            payloads.append(
                {
                    "name": skill,
                    "importance": max(5 - index // 2, 3),
                    "category": "核心技能",
                    "description": f"来源于岗位知识库同步，归类为 {skill} 的关键能力要求。",
                }
            )
        for index, skill in enumerate(common_skills):
            payloads.append(
                {
                    "name": skill,
                    "importance": max(4 - index // 3, 2),
                    "category": "通用能力",
                    "description": f"来源于岗位知识库同步，归类为 {skill} 的通用能力要求。",
                }
            )
        return payloads

    @staticmethod
    def _build_certificate_payloads(certificates: list[str]) -> list[dict[str, Any]]:
        return [
            {
                "name": certificate,
                "importance": max(5 - index // 2, 3),
                "description": "来源于岗位知识库同步的证书要求。",
            }
            for index, certificate in enumerate(certificates)
        ]

    @staticmethod
    def _infer_job_level(job_name: str) -> int:
        for keyword, level in LEVEL_RULES:
            if keyword in job_name or keyword.lower() in str(job_name or "").lower():
                return level
        return 2

    @staticmethod
    def _skill_set(job: Job) -> set[str]:
        return {item for item in (job.core_skill_tags or []) + (job.common_skill_tags or []) if item}

    @staticmethod
    def _jaccard(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        union = left | right
        if not union:
            return 0.0
        return len(left & right) / len(union)

    @staticmethod
    def _dedupe_list(items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    def _recommend_courses(self, skills: list[str]) -> list[str]:
        courses: list[str] = []
        for skill in skills:
            courses.extend(COURSE_LIBRARY.get(skill.lower(), []))
            courses.extend(COURSE_LIBRARY.get(skill, []))
        return self._dedupe_list(courses)[:5]

    def _recommend_certificates(self, skills: list[str]) -> list[str]:
        certificates: list[str] = []
        for skill in skills:
            certificates.extend(CERTIFICATE_LIBRARY.get(skill.lower(), []))
            certificates.extend(CERTIFICATE_LIBRARY.get(skill, []))
        return self._dedupe_list(certificates)[:4]
