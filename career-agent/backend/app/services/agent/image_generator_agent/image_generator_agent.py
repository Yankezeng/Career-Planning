from __future__ import annotations

import math
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import joinedload

from app.models.career import CareerGoal
from app.models.job import Job
from app.models.student import Student, StudentAttachment, StudentProfile
from app.services.ability_scoring_service import AbilityScoringService, DIMENSION_LABELS
from app.services.agent.common.business_agent_runtime import BusinessAgentResult
from app.services.growth_tracking_service import GrowthTrackingService
from app.services.persona_image_asset_service import PersonaImageAssetService
from app.services.resume_profile_pipeline_service import ResumeProfilePipelineService
from app.utils.serializers import to_dict

if TYPE_CHECKING:
    from app.models.auth import User
    from app.services.agent_tool_registry import AgentToolRegistry


PERSONA_NAMES = {
    "TLIS": "技术探索稳健型",
    "TLIG": "技术探索跃迁型",
    "TLCS": "技术协作稳健型",
    "TLCG": "技术协作成长型",
    "TEIS": "技术执行稳健型",
    "TEIG": "技术执行冲刺型",
    "TECS": "技术交付稳健型",
    "TECG": "技术交付高潜型",
    "PLIS": "实践探索稳健型",
    "PLIG": "实践探索跃迁型",
    "PLCS": "实践协作稳健型",
    "PLCG": "实践协作成长型",
    "PEIS": "实践执行稳健型",
    "PEIG": "实践执行冲刺型",
    "PECS": "实践交付稳健型",
    "PECG": "实践交付高潜型",
}

MBTI_NAMES = {
    "ISTJ": "责任执行型",
    "ISFJ": "支持守护型",
    "INFJ": "洞察规划型",
    "INTJ": "战略分析型",
    "ISTP": "实践解决型",
    "ISFP": "灵活体验型",
    "INFP": "理想探索型",
    "INTP": "逻辑探索型",
    "ESTP": "行动突破型",
    "ESFP": "现场表达型",
    "ENFP": "创意启发型",
    "ENTP": "创新辩论型",
    "ESTJ": "组织推进型",
    "ESFJ": "协作服务型",
    "ENFJ": "影响引导型",
    "ENTJ": "目标统筹型",
}

PERSONA_VECTOR_DIMENSIONS = (
    "technical_depth",
    "practice_depth",
    "learning_exploration",
    "execution_delivery",
    "innovation_breakthrough",
    "collaboration_communication",
    "stable_growth",
    "high_potential_growth",
)

VECTOR_LABELS = {
    "technical_depth": "技术深度",
    "practice_depth": "实践深度",
    "learning_exploration": "学习探索",
    "execution_delivery": "执行交付",
    "innovation_breakthrough": "创新突破",
    "collaboration_communication": "协作沟通",
    "stable_growth": "稳定成长",
    "high_potential_growth": "高潜成长",
}

AXIS_WORDS = {
    "T": ("技术驱动", "技术理解深、工程表达清晰", "补充真实业务指标和项目复盘"),
    "P": ("实践驱动", "实践意识强、能从任务中提炼经验", "补强系统化技术栈和专业标签"),
    "L": ("学习探索", "学习吸收快、愿意尝试新方法", "收敛学习方向并形成阶段性交付"),
    "E": ("执行落地", "推进稳定、交付意识强", "增加方案设计和复盘沉淀"),
    "I": ("创新突破", "创新意识强、适合攻克变化任务", "用作品或竞赛结果证明突破价值"),
    "C": ("协作沟通", "团队适配好、表达和推进较稳", "突出个人主导模块和量化贡献"),
    "S": ("稳定成长", "节奏稳定、持续积累能力强", "增加高亮成果避免画像过于保守"),
    "G": ("高潜成长", "成长势能强、适合快速进阶", "控制节奏并补齐长期规划"),
}


def _build_persona_catalog() -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for code, name in PERSONA_NAMES.items():
        axis_traits = [AXIS_WORDS[axis][0] for axis in code]
        advantages = [AXIS_WORDS[axis][1] for axis in code[:3]]
        risks = [AXIS_WORDS[axis][2] for axis in code]
        fit_directions = ["Java 后端开发", "项目型研发", "业务交付研发"] if code[0] == "T" else ["应用开发", "项目交付", "技术产品支持"]
        catalog[code] = {
            "name": name,
            "trait": "、".join(axis_traits) + "，适合把简历证据沉淀为清晰的职业画像。",
            "advantages": advantages,
            "risk": "；".join(risks[:2]),
            "fit_directions": fit_directions,
            "growth_advice": risks[-1],
        }
    return catalog


PERSONA_CATALOG = _build_persona_catalog()


def _build_persona_prototype_vectors() -> dict[str, dict[str, float]]:
    axis_map = {
        "T": ("technical_depth", "practice_depth"),
        "P": ("practice_depth", "technical_depth"),
        "L": ("learning_exploration", "execution_delivery"),
        "E": ("execution_delivery", "learning_exploration"),
        "I": ("innovation_breakthrough", "collaboration_communication"),
        "C": ("collaboration_communication", "innovation_breakthrough"),
        "S": ("stable_growth", "high_potential_growth"),
        "G": ("high_potential_growth", "stable_growth"),
    }
    vectors: dict[str, dict[str, float]] = {}
    for code in PERSONA_CATALOG:
        vector = {dimension: 0.36 for dimension in PERSONA_VECTOR_DIMENSIONS}
        for axis in code:
            primary, secondary = axis_map[axis]
            vector[primary] = 1.0
            vector[secondary] = min(vector[secondary], 0.44)
        vectors[code] = vector
    return vectors


PERSONA_PROTOTYPE_VECTORS = _build_persona_prototype_vectors()


class ImageGeneratorAgent:
    name = "ImageGeneratorAgent"

    def __init__(self, registry: AgentToolRegistry):
        self.registry = registry
        self.db = registry.db
        self.settings = registry.settings
        self.vector_search_service = registry.vector_search_service
        self.profile_service = registry.profile_service
        self.match_service = registry.match_service
        self.ability_scoring = AbilityScoringService()
        self.growth_service = GrowthTrackingService(self.db)
        self.resume_pipeline = ResumeProfilePipelineService(self.db)
        self.persona_image_service = PersonaImageAssetService(self.db)

    def execute(self, *, user: User, message: str, target_job: str) -> BusinessAgentResult:
        data = self.generate_for_user(user=user, message=message, target_job=target_job)
        tool_output = {
            "tool": "generate_profile_image",
            "title": "CBTI 人格画像",
            "summary": data["analysis_summary"],
            "data": data,
            "next_actions": [],
            "context_patch": {"context_binding": {"profile_image": data}},
        }
        return BusinessAgentResult(
            agent_name=self.name,
            reply=data["assistant_reply"],
            tool_outputs=[tool_output],
            tool_steps=[{"step": 1, "tool": "generate_profile_image", "status": "done", "text": "done: CBTI persona profile"}],
            actions=[],
            context_patch={"context_binding": {"profile_image": data}},
            call_flow=["call:image(generate_profile_image)"],
            data_flow=["data:resume->profile->persona_vector->cbti_image_asset"],
        )

    def generate_for_user(self, *, user: User, message: str = "", target_job: str = "") -> dict[str, Any]:
        student = self._student_by_user(user.id)
        return self.generate_for_student(student_id=student.id, message=message, target_job=target_job)

    def generate_for_student(
        self,
        *,
        student_id: int,
        message: str = "",
        target_job: str = "",
        profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resume_sync = self._sync_latest_resume_into_profile(student_id)
        refreshed_profile = self.profile_service.generate_profile(student_id) if resume_sync else profile
        context = self._build_student_profile_context(student_id=student_id, profile=refreshed_profile)
        career_semantics = self._analyze_career_semantics(context=context, message=message, target_job=target_job)
        dynamic_profile = self._generate_dynamic_profile(context=context)
        match_gap = self._analyze_match_and_gap(context=context)
        growth = self._generate_growth_conclusion(context=context, match_gap=match_gap)
        student_vector = self._build_student_persona_vector(
            context=context,
            dynamic_profile=dynamic_profile,
            match_gap=match_gap,
            growth=growth,
        )
        persona = self._match_persona_by_cosine_similarity(
            student_vector=student_vector,
            dynamic_profile=dynamic_profile,
            growth=growth,
        )
        mbti_profile = self._derive_mbti_profile(persona=persona, student_vector=student_vector)
        persona = {**persona, "mbti": mbti_profile, "mbti_code": mbti_profile["code"], "mbti_name": mbti_profile["name"]}
        image_asset = self.persona_image_service.get_asset(persona["code"])
        image_url = self.persona_image_service.get_image_url(image_asset.code)
        profile_report = self._build_profile_report_tables(
            context=context,
            career_semantics=career_semantics,
            dynamic_profile=dynamic_profile,
            match_gap=match_gap,
            growth=growth,
            student_vector=student_vector,
        )
        generated_at = datetime.now().isoformat(timespec="seconds")
        data = {
            "student_id": context["student"]["id"],
            "profile_id": context["profile"]["id"],
            "resume_sync": resume_sync,
            "persona": persona,
            "persona_code": persona["code"],
            "persona_name": persona["name"],
            "mbti": mbti_profile,
            "mbti_code": mbti_profile["code"],
            "mbti_name": mbti_profile["name"],
            "career_semantics": career_semantics,
            "dynamic_profile": dynamic_profile,
            "match_gap": match_gap,
            "growth_conclusion": growth,
            "student_vector": student_vector,
            "profile_report": profile_report,
            "ability_table": profile_report["ability_table"],
            "experience_evidence_table": profile_report["experience_evidence_table"],
            "semantic_gap_table": profile_report["semantic_gap_table"],
            "growth_suggestions": profile_report["growth_suggestions"],
            "career_conclusion": growth["career_conclusion"],
            "image_url": image_url,
            "image_mime": image_asset.mime_type,
            "image_alt": f"{persona['code']} {persona['name']} CBTI 人格画像图",
            "image_source": "persona_image_assets",
            "generated_at": generated_at,
        }
        data["analysis_summary"] = self._build_analysis_summary(context=context, persona=persona, mbti=mbti_profile)
        data["assistant_reply"] = self._build_assistant_reply(data)
        self._persist_profile_image_metadata(context=context, data=data)
        return data

    def get_latest_profile_image(self, student_id: int) -> dict[str, Any] | None:
        profile = (
            self.db.query(StudentProfile)
            .filter(StudentProfile.student_id == student_id, StudentProfile.deleted.is_(False))
            .order_by(StudentProfile.id.desc())
            .first()
        )
        if not profile:
            return None
        raw_metrics = profile.raw_metrics if isinstance(profile.raw_metrics, dict) else {}
        image_meta = raw_metrics.get("profile_image")
        return image_meta if isinstance(image_meta, dict) else None

    def _sync_latest_resume_into_profile(self, student_id: int) -> dict[str, Any] | None:
        attachment = (
            self.db.query(StudentAttachment)
            .filter(StudentAttachment.student_id == student_id, StudentAttachment.deleted.is_(False))
            .order_by(StudentAttachment.updated_at.desc(), StudentAttachment.id.desc())
            .first()
        )
        if not attachment:
            return None
        result = self.resume_pipeline.ingest_resume(student_id, attachment.id)
        return {
            "attachment_id": attachment.id,
            "attachment_name": attachment.file_name,
            "sync_summary": result.get("sync_summary") or {},
            "updated_fields": result.get("updated_fields") or [],
            "merged_counts": result.get("merged_counts") or {},
        }

    def _build_student_profile_context(self, *, student_id: int, profile: dict[str, Any] | None = None) -> dict[str, Any]:
        student = (
            self.db.query(Student)
            .options(
                joinedload(Student.skills),
                joinedload(Student.certificates),
                joinedload(Student.projects),
                joinedload(Student.internships),
                joinedload(Student.competitions),
                joinedload(Student.campus_experiences),
                joinedload(Student.growth_records),
            )
            .filter(Student.id == student_id, Student.deleted.is_(False))
            .first()
        )
        if not student:
            raise ValueError("student not found")
        profile_payload = profile or self.profile_service.get_latest_profile(student.id) or self.profile_service.generate_profile(student.id)
        profile_row = self.db.query(StudentProfile).filter(StudentProfile.id == int(profile_payload["id"])).one()
        ability_payload = self.ability_scoring.calculate(student)
        goal = (
            self.db.query(CareerGoal)
            .filter(CareerGoal.student_id == student.id, CareerGoal.deleted.is_(False))
            .order_by(CareerGoal.id.desc())
            .first()
        )
        return {
            "student_model": student,
            "profile_model": profile_row,
            "student": {
                "id": student.id,
                "name": student.name,
                "major": student.major,
                "college": student.college,
                "grade": student.grade,
                "target_industry": student.target_industry,
                "target_city": student.target_city,
                "interests": student.interests or [],
                "bio": student.bio,
            },
            "profile": profile_payload,
            "ability": ability_payload,
            "goal": to_dict(goal) if goal else {},
            "evidence": {
                "skills": [item.name for item in student.skills if not item.deleted],
                "certificates": [item.name for item in student.certificates if not item.deleted],
                "projects": [
                    {
                        "name": item.name,
                        "role": item.role,
                        "technologies": item.technologies or [],
                        "outcome": item.outcome,
                        "description": item.description,
                    }
                    for item in student.projects
                    if not item.deleted
                ],
                "internships": [
                    {
                        "company": item.company,
                        "position": item.position,
                        "skills": item.skills or [],
                        "description": item.description,
                    }
                    for item in student.internships
                    if not item.deleted
                ],
                "competitions": [
                    {
                        "name": item.name,
                        "award": item.award,
                        "level": item.level,
                        "description": item.description,
                    }
                    for item in student.competitions
                    if not item.deleted
                ],
                "campus_experiences": [
                    {
                        "title": item.title,
                        "role": item.role,
                        "duration": item.duration,
                        "description": item.description,
                    }
                    for item in student.campus_experiences
                    if not item.deleted
                ],
                "growth_records": [to_dict(item) for item in student.growth_records if not item.deleted],
            },
            "dimension_scores": self._dimension_score_map(profile_payload, ability_payload),
        }

    def _analyze_career_semantics(self, *, context: dict[str, Any], message: str, target_job: str) -> dict[str, Any]:
        goal = context["goal"]
        target_job_id = goal.get("target_job_id")
        goal_job = self.db.query(Job).filter(Job.id == int(target_job_id), Job.deleted.is_(False)).first() if target_job_id else None
        query = " ".join(
            [
                str(target_job or ""),
                str(goal_job.name if goal_job else ""),
                str(context["student"].get("target_industry") or ""),
                str(context["student"].get("major") or ""),
                str(message or ""),
            ]
        ).strip()
        hits = self.vector_search_service.search(query=query, top_k=3) if query else []
        keywords: list[str] = []
        for value in [
            target_job,
            goal_job.name if goal_job else "",
            context["student"].get("target_industry"),
            context["student"].get("target_city"),
            context["student"].get("major"),
        ]:
            text = str(value or "").strip()
            if text and text not in keywords:
                keywords.append(text)
        for hit in hits:
            for value in [hit.get("job_name"), hit.get("job_category"), hit.get("company_name")]:
                text = str(value or "").strip()
                if text and text not in keywords:
                    keywords.append(text)
        return {
            "target_job": target_job or (goal_job.name if goal_job else ""),
            "target_industry": context["student"].get("target_industry") or (goal_job.industry if goal_job else ""),
            "target_city": context["student"].get("target_city") or "",
            "keywords": keywords[:8],
            "knowledge_hits": [self._to_retrieval_chunk(hit) for hit in hits],
        }

    def _generate_dynamic_profile(self, *, context: dict[str, Any]) -> dict[str, Any]:
        dimensions = [
            {"key": key, "label": DIMENSION_LABELS.get(key, key), "score": score}
            for key, score in context["dimension_scores"].items()
            if key != "completeness_score"
        ]
        sorted_dimensions = sorted(dimensions, key=lambda item: item["score"], reverse=True)
        return {
            "summary": context["profile"].get("summary") or context["ability"].get("summary") or "",
            "ability_tags": context["profile"].get("ability_tags") or context["ability"].get("ability_tags") or [],
            "strengths": context["profile"].get("strengths") or context["ability"].get("strengths") or [],
            "weaknesses": context["profile"].get("weaknesses") or context["ability"].get("weaknesses") or [],
            "maturity_level": context["profile"].get("maturity_level") or context["ability"].get("maturity_level") or "",
            "dimensions": dimensions,
            "top_dimensions": sorted_dimensions[:3],
            "low_dimensions": sorted_dimensions[-3:],
        }

    def _analyze_match_and_gap(self, *, context: dict[str, Any]) -> dict[str, Any]:
        matches = self.match_service.get_matches(context["student"]["id"]) or self.match_service.generate_matches(context["student"]["id"])
        top_match = matches[0] if matches else {}
        gaps = list(top_match.get("gaps") or [])
        return {
            "top_match": top_match,
            "top_matches": matches[:3],
            "gaps": gaps[:8],
            "avg_top_score": round(
                sum(float(item.get("total_score") or item.get("match_score") or 0) for item in matches[:3])
                / max(len(matches[:3]), 1),
                1,
            ),
        }

    def _generate_growth_conclusion(self, *, context: dict[str, Any], match_gap: dict[str, Any]) -> dict[str, Any]:
        records = self.growth_service.list_records(context["student"]["id"])
        trend = self.growth_service.get_trend(context["student"]["id"])
        weaknesses = list(context["profile"].get("weaknesses") or context["ability"].get("weaknesses") or [])
        gap_items = [
            str(item.get("gap_item") or item.get("name") or "").strip()
            for item in match_gap["gaps"]
            if str(item.get("gap_item") or item.get("name") or "").strip()
        ]
        tasks: list[str] = []
        for item in weaknesses[:3]:
            tasks.append(f"补强{DIMENSION_LABELS.get(str(item), str(item))}，形成可验证项目或材料")
        for item in gap_items[:3]:
            tasks.append(f"围绕{item}完成学习、练习和成果沉淀")
        if not tasks:
            tasks = ["选择一个目标岗位，补充项目指标、技术复盘和面试表达材料"]
        return {
            "records": records[:5],
            "trend": trend,
            "priority_tasks": tasks[:6],
            "career_conclusion": "当前应把简历证据、能力画像、岗位差距和成长记录统一到一个可展示的职业画像闭环中。",
        }

    def _build_student_persona_vector(
        self,
        *,
        context: dict[str, Any],
        dynamic_profile: dict[str, Any],
        match_gap: dict[str, Any],
        growth: dict[str, Any],
    ) -> dict[str, float]:
        scores = context["dimension_scores"]
        evidence = context["evidence"]
        skills_count = len(evidence["skills"])
        certificates_count = len(evidence["certificates"])
        projects_count = len(evidence["projects"])
        internships_count = len(evidence["internships"])
        competitions_count = len(evidence["competitions"])
        campus_count = len(evidence["campus_experiences"])
        growth_count = len(growth["records"])
        avg_match = float(match_gap["avg_top_score"] or 0) / 100
        return {
            "technical_depth": self._avg(
                self._score(scores.get("professional_skill")),
                self._score(scores.get("certificate")),
                self._ratio(skills_count + certificates_count, 8),
            ),
            "practice_depth": self._avg(
                self._score(scores.get("internship")),
                self._ratio(projects_count, 3),
                self._ratio(internships_count, 2),
            ),
            "learning_exploration": self._avg(
                self._score(scores.get("learning")),
                self._score(scores.get("certificate")),
                self._ratio(growth_count + certificates_count, 5),
            ),
            "execution_delivery": self._avg(
                self._score(scores.get("internship")),
                self._score(scores.get("stress_resistance")),
                avg_match,
            ),
            "innovation_breakthrough": self._avg(
                self._score(scores.get("innovation")),
                self._ratio(competitions_count, 2),
                self._ratio(projects_count, 3),
            ),
            "collaboration_communication": self._avg(
                self._score(scores.get("communication")),
                self._ratio(campus_count, 2),
                self._score(scores.get("stress_resistance")),
            ),
            "stable_growth": self._avg(
                self._score(scores.get("stress_resistance")),
                self._score(scores.get("communication")),
                self._ratio(growth_count + projects_count, 6),
            ),
            "high_potential_growth": self._avg(
                self._score(scores.get("learning")),
                self._score(scores.get("innovation")),
                avg_match,
            ),
        }

    def _match_persona_by_cosine_similarity(
        self,
        *,
        student_vector: dict[str, float],
        dynamic_profile: dict[str, Any],
        growth: dict[str, Any],
    ) -> dict[str, Any]:
        candidates = []
        for code, prototype in PERSONA_PROTOTYPE_VECTORS.items():
            similarity = self._cosine_similarity(student_vector, prototype)
            catalog = PERSONA_CATALOG[code]
            candidates.append(
                {
                    "code": code,
                    "name": catalog["name"],
                    "similarity": round(similarity, 6),
                    "similarity_percent": round(similarity * 100, 2),
                }
            )
        candidates.sort(key=lambda item: item["similarity"], reverse=True)
        winner = candidates[0]
        catalog = PERSONA_CATALOG[winner["code"]]
        return {
            "code": winner["code"],
            "name": catalog["name"],
            "trait": catalog["trait"],
            "advantages": catalog["advantages"],
            "risk": catalog["risk"],
            "fit_directions": catalog["fit_directions"],
            "growth_advice": catalog["growth_advice"],
            "similarity": winner["similarity"],
            "similarity_percent": winner["similarity_percent"],
            "matched_by": "cosine_similarity",
            "top_candidates": candidates[:3],
            "axis_scores": self._persona_axis_scores(student_vector),
            "persona_vector": student_vector,
            "prototype_vector": PERSONA_PROTOTYPE_VECTORS[winner["code"]],
            "risks": [catalog["risk"], *growth["priority_tasks"][:2]],
            "career_suggestion": growth["career_conclusion"],
            "advantages_from_profile": dynamic_profile["top_dimensions"],
        }

    @staticmethod
    def _derive_mbti_profile(*, persona: dict[str, Any], student_vector: dict[str, float]) -> dict[str, Any]:
        vector = student_vector or {}
        code = str(persona.get("code") or "")
        e_i = "E" if float(vector.get("collaboration_communication") or 0) >= float(vector.get("innovation_breakthrough") or 0) else "I"
        s_n = "N" if float(vector.get("technical_depth") or 0) >= float(vector.get("practice_depth") or 0) else "S"
        t_f = "T" if (
            float(vector.get("technical_depth") or 0) + float(vector.get("execution_delivery") or 0)
        ) >= (
            float(vector.get("collaboration_communication") or 0) + float(vector.get("practice_depth") or 0)
        ) else "F"
        j_p = "J" if (
            float(vector.get("execution_delivery") or 0) + float(vector.get("stable_growth") or 0)
        ) >= (
            float(vector.get("learning_exploration") or 0) + float(vector.get("high_potential_growth") or 0)
        ) else "P"
        mbti_code = f"{e_i}{s_n}{t_f}{j_p}"
        return {
            "code": mbti_code,
            "name": MBTI_NAMES.get(mbti_code, "职业倾向型"),
            "source": "cbti_projection",
            "summary": f"基于 CBTI {code} 的职业画像维度投影生成，用于辅助理解沟通、决策与行动风格；不替代专业 MBTI 测评。",
        }

    def _build_profile_report_tables(
        self,
        *,
        context: dict[str, Any],
        career_semantics: dict[str, Any],
        dynamic_profile: dict[str, Any],
        match_gap: dict[str, Any],
        growth: dict[str, Any],
        student_vector: dict[str, float],
    ) -> dict[str, Any]:
        evidence = context["evidence"]
        ability_table = [
            {
                "dimension": VECTOR_LABELS[key],
                "score": round(value * 100, 1),
                "evidence": self._vector_evidence(key, evidence, dynamic_profile, match_gap, growth),
                "conclusion": self._score_conclusion(value),
            }
            for key, value in student_vector.items()
        ]
        experience_evidence_table = [
            {"category": "项目", "count": len(evidence["projects"]), "evidence": self._join_names(evidence["projects"], "name"), "conclusion": "证明技术深度、实践交付和问题解决"},
            {"category": "实习", "count": len(evidence["internships"]), "evidence": self._join_names(evidence["internships"], "position"), "conclusion": "证明真实业务环境中的执行与协作"},
            {"category": "竞赛", "count": len(evidence["competitions"]), "evidence": self._join_names(evidence["competitions"], "name"), "conclusion": "证明创新突破、抗压和结果意识"},
            {"category": "证书", "count": len(evidence["certificates"]), "evidence": "、".join(evidence["certificates"][:6]), "conclusion": "证明基础能力和学习投入"},
            {"category": "技能", "count": len(evidence["skills"]), "evidence": "、".join(evidence["skills"][:8]), "conclusion": "证明岗位关键词匹配"},
            {"category": "校园/团队", "count": len(evidence["campus_experiences"]), "evidence": self._join_names(evidence["campus_experiences"], "title"), "conclusion": "证明沟通协作和组织推进"},
        ]
        top_matches = match_gap.get("top_matches") or []
        gaps = match_gap.get("gaps") or []
        semantic_gap_table = [
            {
                "dimension": "目标方向",
                "content": career_semantics.get("target_job") or career_semantics.get("target_industry") or "未明确",
                "evidence": "、".join(career_semantics.get("keywords") or []),
                "conclusion": "画像按目标方向和简历证据共同判断",
            },
            {
                "dimension": "适配岗位",
                "content": "、".join(str(item.get("job_name") or item.get("name") or "") for item in top_matches[:3] if item),
                "evidence": "、".join(str(item.get("total_score") or item.get("match_score") or "") for item in top_matches[:3] if item),
                "conclusion": f"前三岗位平均匹配度 {match_gap.get('avg_top_score', 0)}",
            },
            {
                "dimension": "主要短板",
                "content": "、".join(str(item.get("gap_item") or item.get("name") or "") for item in gaps[:5] if item),
                "evidence": "、".join(str(item.get("suggestion") or item.get("reason") or "") for item in gaps[:3] if item),
                "conclusion": "短板将进入成长建议和近期任务",
            },
            {
                "dimension": "知识库命中",
                "content": "、".join(str(item.get("job_name") or item.get("job_category") or "") for item in career_semantics.get("knowledge_hits", [])[:3] if item),
                "evidence": "、".join(str(item.get("snippet") or "")[:30] for item in career_semantics.get("knowledge_hits", [])[:3] if item),
                "conclusion": "用于补充岗位语义和能力关键词",
            },
        ]
        growth_suggestions = [
            {
                "direction": f"近期任务 {index + 1}",
                "task": task,
                "output": "沉淀为简历项目描述、作品截图、代码仓库或面试 STAR 表达",
            }
            for index, task in enumerate(growth["priority_tasks"][:6])
        ]
        return {
            "ability_table": ability_table,
            "experience_evidence_table": experience_evidence_table,
            "semantic_gap_table": semantic_gap_table,
            "growth_suggestions": growth_suggestions,
        }

    def _persist_profile_image_metadata(self, *, context: dict[str, Any], data: dict[str, Any]) -> None:
        profile_row: StudentProfile = context["profile_model"]
        raw_metrics = dict(profile_row.raw_metrics or {})
        raw_metrics["profile_image"] = {
            "image_url": data["image_url"],
            "image_mime": data["image_mime"],
            "image_alt": data["image_alt"],
            "image_source": data["image_source"],
            "persona": data["persona"],
            "persona_code": data["persona_code"],
            "persona_name": data["persona_name"],
            "mbti": data["mbti"],
            "mbti_code": data["mbti_code"],
            "mbti_name": data["mbti_name"],
            "analysis_summary": data["analysis_summary"],
            "career_conclusion": data["career_conclusion"],
            "career_semantics": data["career_semantics"],
            "student_vector": data["student_vector"],
            "profile_report": data["profile_report"],
            "ability_table": data["ability_table"],
            "experience_evidence_table": data["experience_evidence_table"],
            "semantic_gap_table": data["semantic_gap_table"],
            "growth_suggestions": data["growth_suggestions"],
            "resume_sync": data["resume_sync"],
            "generated_at": data["generated_at"],
        }
        profile_row.raw_metrics = raw_metrics
        self.db.commit()

    def _build_profile_image_card(self, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "profile_image_card",
            "tool": "generate_profile_image",
            "title": f"{data['persona_code']} {data['persona_name']}",
            "summary": data["analysis_summary"],
            "data": {
                "image_url": data["image_url"],
                "image_mime": data["image_mime"],
                "image_alt": data["image_alt"],
                "persona": data["persona"],
                "mbti": data["mbti"],
                "mbti_code": data["mbti_code"],
                "mbti_name": data["mbti_name"],
                "analysis_summary": data["analysis_summary"],
                "career_conclusion": data["career_conclusion"],
                "profile_report": data["profile_report"],
                "ability_table": data["ability_table"],
                "experience_evidence_table": data["experience_evidence_table"],
                "semantic_gap_table": data["semantic_gap_table"],
                "growth_suggestions": data["growth_suggestions"],
                "career_semantics": data["career_semantics"],
                "resume_sync": data["resume_sync"],
            },
        }

    def _build_analysis_summary(self, *, context: dict[str, Any], persona: dict[str, Any], mbti: dict[str, Any]) -> str:
        return (
            f"{context['student']['name']} 的 CBTI 人格画像为 {persona['code']}「{persona['name']}」，"
            f"匹配度 {persona['similarity_percent']}%。MBTI 倾向为 {mbti['code']}（{mbti['name']}）。{persona['trait']}"
        )

    def _build_assistant_reply(self, data: dict[str, Any]) -> str:
        persona = data["persona"]
        mbti = data.get("mbti") or {}
        candidates = "、".join(f"{item['code']} {item['similarity_percent']}%" for item in persona["top_candidates"])
        top_abilities = "、".join(f"{row['dimension']} {row['score']}" for row in data["ability_table"][:4])
        advantages = "、".join(str(item) for item in persona.get("advantages", [])[:4] if item)
        fit_directions = "、".join(str(item) for item in persona.get("fit_directions", [])[:4] if item)
        image_url = str(data.get("image_url") or "").strip()
        image_alt = str(data.get("image_alt") or f"{persona['code']} CBTI 人格画像图").strip()
        image_markdown = f"![{image_alt}]({image_url})" if image_url else ""
        return "\n".join(
            [line for line in [
                "**CBTI 画像结果**",
                image_markdown,
                f"- CBTI：{persona['code']}（{persona['name']}），匹配度 {persona['similarity_percent']}%",
                f"- MBTI 倾向：{mbti.get('code', data.get('mbti_code', '-'))}（{mbti.get('name', data.get('mbti_name', '职业风格参考'))}）",
                f"- 核心特征：{persona['trait']}",
                f"- 优势能力：{advantages or '暂无明显优势标签'}",
                f"- 潜在风险：{persona['risk']}",
                f"- 适配方向：{fit_directions or '结合目标岗位继续分析'}",
                f"- 能力画像重点：{top_abilities}",
                f"- 候选人格 Top 3：{candidates}",
                f"- 成长建议：{persona.get('growth_advice') or data['career_conclusion']}",
                "",
                "说明：MBTI 倾向由 CBTI 职业画像维度投影生成，用于辅助理解沟通、决策与行动风格，不替代专业 MBTI 测评。",
            ] if line]
        )

    def _student_by_user(self, user_id: int) -> Student:
        student = (
            self.db.query(Student)
            .filter(Student.user_id == user_id, Student.deleted.is_(False))
            .first()
        )
        if not student:
            raise ValueError("student not found")
        return student

    @staticmethod
    def _dimension_score_map(profile: dict[str, Any], ability: dict[str, Any]) -> dict[str, float]:
        raw = profile.get("raw_metrics") if isinstance(profile.get("raw_metrics"), dict) else {}
        dimension_items = raw.get("dimension_scores") or []
        dimensions = {str(item.get("key")): float(item.get("score") or 0) for item in dimension_items if item.get("key")}
        ability_raw = ability.get("raw_metrics") if isinstance(ability.get("raw_metrics"), dict) else {}
        ability_items = ability_raw.get("dimension_scores") or []
        ability_dimensions = {str(item.get("key")): float(item.get("score") or 0) for item in ability_items if item.get("key")}
        return {
            "professional_skill": dimensions.get("professional_skill", float(profile.get("professional_score") or ability.get("professional_score") or 0)),
            "certificate": dimensions.get("certificate", float(raw.get("certificate_score") or ability_raw.get("certificate_score") or 0)),
            "innovation": dimensions.get("innovation", float(profile.get("innovation_score") or ability.get("innovation_score") or 0)),
            "learning": dimensions.get("learning", float(profile.get("learning_score") or ability.get("learning_score") or 0)),
            "stress_resistance": dimensions.get("stress_resistance", float(raw.get("stress_score") or profile.get("professionalism_score") or ability.get("professionalism_score") or 0)),
            "communication": dimensions.get("communication", float(profile.get("communication_score") or ability.get("communication_score") or 0)),
            "internship": dimensions.get("internship", float(profile.get("practice_score") or ability.get("practice_score") or 0)),
            "completeness_score": float(raw.get("completeness_score") or ability_raw.get("completeness_score") or 0),
            **{key: value for key, value in ability_dimensions.items() if key not in dimensions},
        }

    @staticmethod
    def _to_retrieval_chunk(hit: dict[str, Any]) -> dict[str, Any]:
        metadata = hit.get("metadata") if isinstance(hit.get("metadata"), dict) else {}
        return {
            "job_name": str(hit.get("job_name") or metadata.get("job_name") or "").strip(),
            "job_category": str(hit.get("job_category") or metadata.get("job_category") or "").strip(),
            "company_name": str(hit.get("company_name") or metadata.get("company_name") or "").strip(),
            "score": float(hit.get("score") or 0),
            "snippet": str(hit.get("content") or "")[:220],
        }

    @staticmethod
    def _score(value: Any) -> float:
        return min(max(float(value or 0), 0), 100) / 100

    @staticmethod
    def _ratio(value: int, scale: int) -> float:
        return min(max(float(value), 0), float(scale)) / float(scale)

    @staticmethod
    def _avg(*values: float) -> float:
        return round(sum(values) / len(values), 4)

    @staticmethod
    def _cosine_similarity(student_vector: dict[str, float], prototype: dict[str, float]) -> float:
        dot = sum(float(student_vector[dimension]) * float(prototype[dimension]) for dimension in PERSONA_VECTOR_DIMENSIONS)
        left = math.sqrt(sum(float(student_vector[dimension]) ** 2 for dimension in PERSONA_VECTOR_DIMENSIONS))
        right = math.sqrt(sum(float(prototype[dimension]) ** 2 for dimension in PERSONA_VECTOR_DIMENSIONS))
        return dot / (left * right)

    @staticmethod
    def _persona_axis_scores(vector: dict[str, float]) -> dict[str, dict[str, Any]]:
        return {
            "technical_practical": {"left": "T", "left_score": round(vector["technical_depth"] * 100, 1), "right": "P", "right_score": round(vector["practice_depth"] * 100, 1)},
            "learning_execution": {"left": "L", "left_score": round(vector["learning_exploration"] * 100, 1), "right": "E", "right_score": round(vector["execution_delivery"] * 100, 1)},
            "innovation_collaboration": {"left": "I", "left_score": round(vector["innovation_breakthrough"] * 100, 1), "right": "C", "right_score": round(vector["collaboration_communication"] * 100, 1)},
            "stable_growth": {"left": "S", "left_score": round(vector["stable_growth"] * 100, 1), "right": "G", "right_score": round(vector["high_potential_growth"] * 100, 1)},
        }

    @staticmethod
    def _vector_evidence(
        key: str,
        evidence: dict[str, Any],
        dynamic_profile: dict[str, Any],
        match_gap: dict[str, Any],
        growth: dict[str, Any],
    ) -> str:
        mapping = {
            "technical_depth": "、".join([*evidence["skills"][:4], *evidence["certificates"][:2]]),
            "practice_depth": "、".join([*(item.get("name") or "" for item in evidence["projects"][:3]), *(item.get("position") or "" for item in evidence["internships"][:2])]),
            "learning_exploration": "、".join([*evidence["certificates"][:3], *(str(item.get("stage_label") or "") for item in growth["records"][:2])]),
            "execution_delivery": "、".join(str(item.get("job_name") or item.get("name") or "") for item in match_gap.get("top_matches", [])[:3]),
            "innovation_breakthrough": "、".join([*(item.get("name") or "" for item in evidence["competitions"][:3]), *(item.get("name") or "" for item in evidence["projects"][:2])]),
            "collaboration_communication": "、".join([*(item.get("title") or "" for item in evidence["campus_experiences"][:3]), *(item.get("role") or "" for item in evidence["projects"][:2])]),
            "stable_growth": dynamic_profile.get("maturity_level") or "稳定性来自抗压、沟通和持续积累指标",
            "high_potential_growth": "、".join(str(item.get("label") or item.get("key") or "") for item in dynamic_profile.get("top_dimensions", [])[:3]),
        }
        return str(mapping[key] or "简历与画像暂无明确证据")

    @staticmethod
    def _score_conclusion(value: float) -> str:
        if value >= 0.78:
            return "优势明显，可作为核心卖点"
        if value >= 0.58:
            return "具备基础，需要继续沉淀证据"
        return "当前偏弱，建议近期重点补强"

    @staticmethod
    def _join_names(items: list[dict[str, Any]], key: str) -> str:
        return "、".join(str(item.get(key) or "").strip() for item in items[:6] if str(item.get(key) or "").strip())
