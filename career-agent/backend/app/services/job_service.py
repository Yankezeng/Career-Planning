from __future__ import annotations

import math
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models.auth import EnterpriseProfile, User
from app.models.job import Job, JobCertificate, JobSkill
from app.services.vector_search_service import VectorSearchService
from app.utils.serializers import to_dict


class JobService:
    def __init__(self, db: Session):
        self.db = db
        self.vector_service = VectorSearchService()

    def list_jobs(self, current_user: User | None = None):
        jobs = (
            self.db.query(Job)
            .options(joinedload(Job.skills), joinedload(Job.certificates))
            .filter(Job.deleted.is_(False))
            .order_by(Job.id.asc())
            .all()
        )
        visible_jobs = self._filter_jobs_for_user(jobs, current_user)
        return [to_dict(job, include=["skills", "certificates"]) for job in visible_jobs]

    def get_job(self, job_id: int, current_user: User | None = None):
        job = (
            self.db.query(Job)
            .options(joinedload(Job.skills), joinedload(Job.certificates))
            .filter(Job.id == job_id, Job.deleted.is_(False))
            .first()
        )
        if not job or not self._job_visible_to_user(job, current_user):
            raise HTTPException(status_code=404, detail="Job not found or access denied.")
        return job

    def list_knowledge_postings(
        self,
        current_user: User | None = None,
        page: int = 1,
        page_size: int = 40,
        keyword: str = "",
        category: str = "",
        company: str = "",
    ) -> dict[str, Any]:
        page = max(1, int(page or 1))
        page_size = min(120, max(1, int(page_size or 40)))
        keyword = self._clean_text(keyword).lower()
        category = self._clean_text(category)
        company = self._clean_text(company).lower()

        source_count = self.vector_service.count_documents()
        fetch_limit = max(20000, source_count or 0, page * page_size)
        documents = [item for item in (self.vector_service.list_documents(limit=fetch_limit) or []) if isinstance(item, dict)]
        knowledge_doc_count = source_count or len(documents)

        standard_jobs = (
            self.db.query(Job)
            .options(joinedload(Job.skills), joinedload(Job.certificates))
            .filter(Job.deleted.is_(False))
            .order_by(Job.id.asc())
            .all()
        )
        job_by_name = {self._normalize_job_name(job.name): job for job in standard_jobs if self._clean_text(job.name)}
        jobs_by_category: dict[str, Job] = {}
        for job in standard_jobs:
            category_key = self._clean_text(job.category).lower()
            if category_key and category_key not in jobs_by_category:
                jobs_by_category[category_key] = job

        fallback_job = standard_jobs[0] if standard_jobs else None
        rows: list[dict[str, Any]] = []
        for index, document in enumerate(documents):
            posting = self._serialize_knowledge_posting(
                document=document,
                index=index,
                job_by_name=job_by_name,
                jobs_by_category=jobs_by_category,
                fallback_job=fallback_job,
            )
            if posting and self._posting_visible_to_user(posting, current_user):
                rows.append(posting)

        categories = sorted({self._clean_text(item.get("category")) for item in rows if self._clean_text(item.get("category"))})
        companies = sorted({self._clean_text(item.get("company_name")) for item in rows if self._clean_text(item.get("company_name"))})

        if category:
            rows = [item for item in rows if self._clean_text(item.get("category")) == category]
        if company:
            rows = [item for item in rows if company in self._clean_text(item.get("company_name")).lower()]
        if keyword:
            rows = [item for item in rows if self._posting_matches_keyword(item, keyword)]
        rows = self._with_display_names(rows)

        total = len(rows)
        start = (page - 1) * page_size
        page_items = rows[start : start + page_size]
        total_pages = max(1, math.ceil(total / page_size)) if total else 0

        return {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "stats": {
                "knowledge_doc_count": knowledge_doc_count,
                "displayable_posting_count": len(rows),
                "matched_profile_count": len([item for item in rows if item.get("target_job_id")]),
                "canonical_job_count": len(standard_jobs),
                "company_count": len(companies),
                "categories": categories,
                "companies": companies[:200],
                "backend": getattr(self.vector_service, "backend_name", ""),
            },
        }

    def create_job(self, payload: dict, operator_id: int | None = None):
        job = Job(**{k: v for k, v in payload.items() if k not in {"skills", "certificates"}})
        job.created_by = operator_id
        self.db.add(job)
        self.db.flush()
        self._sync_nested(job, payload)
        self.db.commit()
        self.db.refresh(job)
        return job

    def update_job(self, job_id: int, payload: dict, operator_id: int | None = None):
        job = self.get_job(job_id)
        for key, value in payload.items():
            if key not in {"skills", "certificates"}:
                setattr(job, key, value)
        job.updated_by = operator_id
        self._sync_nested(job, payload)
        self.db.commit()
        self.db.refresh(job)
        return job

    def delete_job(self, job_id: int):
        job = self.get_job(job_id)
        job.deleted = True
        self.db.commit()

    def _sync_nested(self, job: Job, payload: dict):
        job.skills.clear()
        job.certificates.clear()
        for item in payload.get("skills", []):
            job.skills.append(JobSkill(**item))
        for item in payload.get("certificates", []):
            job.certificates.append(JobCertificate(**item))

    def _filter_jobs_for_user(self, jobs: list[Job], current_user: User | None = None) -> list[Job]:
        if not current_user or not current_user.role or current_user.role.code != "enterprise":
            return jobs

        company_name = self._get_enterprise_company_name(current_user)
        return [job for job in jobs if self._job_matches_company(job, company_name)]

    def _job_visible_to_user(self, job: Job, current_user: User | None = None) -> bool:
        if not current_user or not current_user.role or current_user.role.code != "enterprise":
            return True
        company_name = self._get_enterprise_company_name(current_user)
        return self._job_matches_company(job, company_name)

    def _job_matches_company(self, job: Job, company_name: str) -> bool:
        if not company_name:
            return True

        profile = job.job_profile if isinstance(job.job_profile, dict) else {}
        source_companies = list(profile.get("source_companies") or [])
        if profile.get("company_name"):
            source_companies.append(profile.get("company_name"))

        normalized_companies = {self._normalize_company_name(item) for item in source_companies if item}
        return company_name in normalized_companies

    def _get_enterprise_company_name(self, current_user: User) -> str:
        enterprise_profile = (
            self.db.query(EnterpriseProfile)
            .filter(EnterpriseProfile.user_id == current_user.id, EnterpriseProfile.deleted.is_(False))
            .first()
        )
        if not enterprise_profile:
            raise HTTPException(status_code=404, detail="Enterprise profile is not bound to this account.")
        return self._normalize_company_name(enterprise_profile.company_name)

    def _serialize_knowledge_posting(
        self,
        document: dict[str, Any],
        index: int,
        job_by_name: dict[str, Job],
        jobs_by_category: dict[str, Job],
        fallback_job: Job | None,
    ) -> dict[str, Any] | None:
        metadata = document.get("metadata") if isinstance(document.get("metadata"), dict) else {}
        content = self._clean_text(document.get("content") or "")
        parsed_content = self._parse_labeled_text(content)
        job_name = self._extract_posting_job_name(document, metadata, parsed_content)
        if not job_name:
            return None

        category = self._clean_text(
            document.get("job_category")
            or document.get("category")
            or metadata.get("job_category")
            or metadata.get("category")
            or parsed_content.get("岗位类别")
        )
        standard_job = (
            job_by_name.get(self._normalize_job_name(job_name))
            or jobs_by_category.get(category.lower())
            or fallback_job
        )
        profile = standard_job.job_profile if standard_job and isinstance(standard_job.job_profile, dict) else {}
        standard_payload = to_dict(standard_job, include=["skills", "certificates"]) if standard_job else {}

        company_name = self._clean_text(
            document.get("company_name")
            or document.get("enterprise_name")
            or metadata.get("company_name")
            or metadata.get("enterprise_name")
            or parsed_content.get("公司名称")
        ) or "未知企业"
        industry = self._clean_text(document.get("industry") or metadata.get("industry") or parsed_content.get("所属行业") or standard_payload.get("industry"))
        description = self._clean_text(
            metadata.get("description")
            or document.get("description")
            or content
            or standard_payload.get("description")
            or profile.get("summary")
        )

        core_skills = self._dedupe_list(
            self._as_list(metadata.get("core_skills"))
            + self._as_list(document.get("core_skill_tags"))
            + self._as_list(standard_payload.get("core_skill_tags"))
            + self._as_list(profile.get("core_skills"))
        )
        common_skills = self._dedupe_list(
            self._as_list(metadata.get("common_skills"))
            + self._as_list(document.get("common_skill_tags"))
            + self._as_list(standard_payload.get("common_skill_tags"))
            + self._as_list(profile.get("common_skills"))
        )
        certificate_tags = self._dedupe_list(
            self._as_list(metadata.get("certificates"))
            + self._as_list(document.get("certificate_tags"))
            + self._as_list(standard_payload.get("certificate_tags"))
            + self._as_list(profile.get("certificates"))
        )
        doc_id = self._clean_text(document.get("id") or document.get("doc_id") or metadata.get("id") or metadata.get("doc_id")) or f"knowledge:{index}"
        posting_info = self._extract_posting_info(document, metadata, description)

        return {
            "id": f"knowledge:{doc_id}",
            "source": "knowledge",
            "knowledge_doc_id": doc_id,
            "target_job_id": standard_job.id if standard_job else None,
            "name": job_name,
            "display_name": job_name,
            "category": category or standard_payload.get("category") or profile.get("category") or "综合",
            "industry": industry or profile.get("industry") or "",
            "company_name": company_name,
            "salary_range": self._clean_text(metadata.get("salary_range") or document.get("salary_range") or posting_info.get("salary_range") or standard_payload.get("salary_range")),
            "work_location": posting_info.get("location") or "",
            "company_size": posting_info.get("company_size") or "",
            "company_type": posting_info.get("company_type") or "",
            "job_code": posting_info.get("job_code") or "",
            "degree_requirement": self._clean_text(metadata.get("degree_requirement") or document.get("degree_requirement") or standard_payload.get("degree_requirement") or profile.get("degree_requirement")),
            "major_requirement": self._clean_text(metadata.get("major_requirement") or document.get("major_requirement") or standard_payload.get("major_requirement") or profile.get("major_requirement")),
            "internship_requirement": self._clean_text(metadata.get("internship_requirement") or document.get("internship_requirement") or standard_payload.get("internship_requirement") or profile.get("internship_requirement")),
            "description": (posting_info.get("job_description") or description)[:600],
            "core_skill_tags": core_skills[:12],
            "common_skill_tags": common_skills[:12],
            "certificate_tags": certificate_tags[:8],
            "job_profile": profile,
            "profile_job": self._serialize_profile_job(standard_job) if standard_job else None,
            "posting_info": posting_info,
            "metadata": {
                "source_file": self._clean_text(document.get("source_file") or metadata.get("source_file")),
                "raw_category": self._clean_text(document.get("job_category") or metadata.get("job_category")),
            },
        }

    def _extract_posting_info(self, document: dict[str, Any], metadata: dict[str, Any], description: str) -> dict[str, Any]:
        content = self._clean_text(document.get("content") or "")
        parsed = self._parse_labeled_text(content)
        job_description = self._clean_text(metadata.get("description") or parsed.get("岗位描述") or description)
        responsibilities, requirements = self._split_responsibilities_and_requirements(job_description)
        parsed_requirements = self._clean_text(parsed.get("任职要求") or parsed.get("岗位要求") or parsed.get("职位要求"))
        if parsed_requirements:
            requirements = parsed_requirements

        info = {
            "location": self._clean_text(metadata.get("address") or parsed.get("工作地点")),
            "salary_range": self._clean_text(metadata.get("salary_range") or parsed.get("薪资范围") or parsed.get("薪资待遇")),
            "company_size": self._clean_text(metadata.get("company_size") or parsed.get("公司规模")),
            "company_type": self._clean_text(metadata.get("company_type") or parsed.get("公司类型")),
            "job_code": self._clean_text(metadata.get("job_code") or parsed.get("岗位编码")),
            "update_date": self._clean_text(metadata.get("update_date") or parsed.get("更新日期")),
            "source_url": self._clean_text(metadata.get("source_url") or parsed.get("来源地址")),
            "job_description": job_description,
            "responsibilities": responsibilities,
            "requirements": requirements,
            "work_content": self._clean_text(parsed.get("工作内容")),
            "salary_benefits": self._clean_text(parsed.get("薪资待遇")),
            "work_time": self._clean_text(parsed.get("工作时间")),
            "welfare": self._clean_text(parsed.get("福利待遇")),
            "highlights": self._clean_text(parsed.get("岗位亮点")),
            "company_detail": self._clean_text(metadata.get("company_detail") or parsed.get("公司详情")),
        }
        info["facts"] = self._posting_fact_items(info)
        info["sections"] = self._posting_section_items(info)
        return info

    @staticmethod
    def _parse_labeled_text(text: str) -> dict[str, str]:
        labels = [
            "岗位名称",
            "岗位类别",
            "工作地点",
            "薪资范围",
            "公司名称",
            "所属行业",
            "公司规模",
            "公司类型",
            "岗位编码",
            "岗位描述",
            "任职要求",
            "工作内容",
            "薪资待遇",
            "工作时间",
            "福利待遇",
            "岗位亮点",
            "更新日期",
            "公司详情",
            "来源地址",
        ]
        if not text:
            return {}
        pattern = re.compile(rf"({'|'.join(re.escape(label) for label in labels)})[：:]")
        matches = list(pattern.finditer(text))
        result: dict[str, str] = {}
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            value = text[start:end].strip()
            if value:
                result[match.group(1)] = value
        return result

    @staticmethod
    def _split_responsibilities_and_requirements(text: str) -> tuple[str, str]:
        if not text:
            return "", ""
        duty_match = re.search(r"(岗位职责|工作职责|职责描述)[：:]", text)
        requirement_match = re.search(r"(任职要求|岗位要求|职位要求)[：:]", text)
        if duty_match and requirement_match and duty_match.end() < requirement_match.start():
            return text[duty_match.end() : requirement_match.start()].strip(), text[requirement_match.end() :].strip()
        if duty_match:
            return text[duty_match.end() :].strip(), ""
        if requirement_match:
            return text[: requirement_match.start()].strip(), text[requirement_match.end() :].strip()
        return text.strip(), ""

    @staticmethod
    def _posting_fact_items(info: dict[str, Any]) -> list[dict[str, str]]:
        fact_map = [
            ("location", "工作地点"),
            ("salary_range", "薪资范围"),
            ("company_size", "公司规模"),
            ("company_type", "公司类型"),
            ("job_code", "岗位编码"),
            ("update_date", "更新日期"),
        ]
        return [{"key": key, "label": label, "value": str(info.get(key) or "").strip()} for key, label in fact_map if str(info.get(key) or "").strip()]

    @staticmethod
    def _posting_section_items(info: dict[str, Any]) -> list[dict[str, str]]:
        section_map = [
            ("responsibilities", "岗位职责"),
            ("requirements", "任职要求"),
            ("work_content", "工作内容"),
            ("salary_benefits", "薪资待遇"),
            ("work_time", "工作时间"),
            ("welfare", "福利待遇"),
            ("highlights", "岗位亮点"),
            ("company_detail", "公司详情"),
        ]
        return [{"key": key, "label": label, "value": str(info.get(key) or "").strip()} for key, label in section_map if str(info.get(key) or "").strip()]

    def _serialize_profile_job(self, job: Job) -> dict[str, Any]:
        profile = job.job_profile if isinstance(job.job_profile, dict) else {}
        return {
            "id": job.id,
            "name": job.name,
            "category": job.category or profile.get("category"),
            "industry": job.industry or profile.get("industry"),
            "profile_summary": profile.get("summary") or job.description or "",
        }

    def _posting_visible_to_user(self, posting: dict[str, Any], current_user: User | None = None) -> bool:
        if not current_user or not current_user.role or current_user.role.code != "enterprise":
            return True
        company_name = self._get_enterprise_company_name(current_user)
        return self._normalize_company_name(posting.get("company_name")) == company_name

    def _posting_matches_keyword(self, posting: dict[str, Any], keyword: str) -> bool:
        haystack = " ".join(
            [
                self._clean_text(posting.get("name")),
                self._clean_text(posting.get("display_name")),
                self._clean_text(posting.get("category")),
                self._clean_text(posting.get("industry")),
                self._clean_text(posting.get("company_name")),
                self._clean_text(posting.get("description")),
                self._clean_text(posting.get("work_location")),
                self._clean_text(posting.get("company_size")),
                self._clean_text(posting.get("job_code")),
                *self._as_list(posting.get("core_skill_tags")),
                *self._as_list(posting.get("common_skill_tags")),
                *self._as_list(posting.get("certificate_tags")),
                *[self._clean_text(item.get("value")) for item in ((posting.get("posting_info") or {}).get("facts") or []) if isinstance(item, dict)],
                *[self._clean_text(item.get("value")) for item in ((posting.get("posting_info") or {}).get("sections") or []) if isinstance(item, dict)],
            ]
        ).lower()
        return keyword in haystack

    @classmethod
    def _extract_posting_job_name(cls, document: dict[str, Any], metadata: dict[str, Any], parsed_content: dict[str, str]) -> str:
        candidates = [
            parsed_content.get("岗位名称"),
            metadata.get("job_name"),
            metadata.get("position_name"),
            metadata.get("name"),
            metadata.get("title"),
            document.get("job_name"),
            document.get("position_name"),
            document.get("name"),
            document.get("title"),
        ]
        for candidate in candidates:
            title = cls._clean_job_name_candidate(candidate)
            if title:
                return title
        return ""

    @classmethod
    def _clean_job_name_candidate(cls, value: Any) -> str:
        text = cls._clean_text(value).replace("\n", " ")
        text = re.sub(r"\s+", " ", text).strip(" ：:，,。")
        if not text:
            return ""
        text = re.sub(r"^(岗位名称|职位名称|岗位|职位|名称)[：:]\s*", "", text).strip()
        label_pattern = r"(岗位类别|职位类别|工作地点|薪资范围|公司名称|所属行业|公司规模|岗位编码|岗位描述|任职要求|工作内容|福利待遇)[：:]"
        split_text = re.split(label_pattern, text, maxsplit=1)[0].strip()
        if split_text:
            text = split_text
        label_hits = len(re.findall(label_pattern, text))
        if label_hits or len(text) > 80:
            return ""
        return text[:60].strip()

    @classmethod
    def _with_display_names(cls, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        name_counts: dict[str, int] = {}
        for item in rows:
            key = cls._normalize_job_name(item.get("name"))
            if key:
                name_counts[key] = name_counts.get(key, 0) + 1

        result: list[dict[str, Any]] = []
        for item in rows:
            row = dict(item)
            name = cls._clean_text(row.get("name"))
            key = cls._normalize_job_name(name)
            if name and name_counts.get(key, 0) > 1:
                company = cls._clean_text(row.get("company_name"))
                location = cls._clean_text(row.get("work_location"))
                suffix = company or location
                if company and location and location not in company:
                    suffix = f"{company} · {location}"
                row["display_name"] = f"{name} · {suffix}" if suffix else name
            else:
                row["display_name"] = name
            result.append(row)
        return result

    @staticmethod
    def _normalize_job_name(value: str | None) -> str:
        return re.sub(r"\s+", "", str(value or "").strip().lower())

    @staticmethod
    def _clean_text(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def _as_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [cls._clean_text(item) for item in value if cls._clean_text(item)]
        if isinstance(value, tuple | set):
            return [cls._clean_text(item) for item in value if cls._clean_text(item)]
        text = cls._clean_text(value)
        if not text:
            return []
        return [item.strip() for item in re.split(r"[，,、/;；\s]+", text) if item.strip()]

    @staticmethod
    def _dedupe_list(items: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for item in items or []:
            text = str(item or "").strip()
            key = text.lower()
            if text and key not in seen:
                seen.add(key)
                result.append(text)
        return result

    @staticmethod
    def _normalize_company_name(value: str | None) -> str:
        return (value or "").strip().lower()
