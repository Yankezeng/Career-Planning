from __future__ import annotations

from copy import deepcopy
from statistics import mean

from sqlalchemy.orm import Session, joinedload

from app.models.job import Job, JobMatchGap, JobMatchResult
from app.models.student import Student, StudentProfile
from app.schemas.portrait import MATCH_DIMENSION_KEY_ORDER, JobPortraitSchema, MatchSchema
from app.services.job_knowledge_sync_service import JobKnowledgeSyncService
from app.services.student_profile_service_clean import StudentProfileService
from app.utils.serializers import to_dict


DIMENSION_LABELS = {
    "basic_requirement": "基础要求",
    "professional_skill": "职业技能",
    "professional_literacy": "职业素养",
    "development_potential": "发展潜力",
}

DEFAULT_MATCH_WEIGHTS = {
    "basic_requirement": 0.25,
    "professional_skill": 0.40,
    "professional_literacy": 0.20,
    "development_potential": 0.15,
}


class JobMatchService:
    def __init__(self, db: Session):
        self.db = db
        self._job_catalog_checked = False

    def generate_matches(self, student_id: int, ensure_job_catalog: bool = True) -> list[dict]:
        if ensure_job_catalog:
            self._ensure_job_catalog()

        student = (
            self.db.query(Student)
            .options(
                joinedload(Student.skills),
                joinedload(Student.certificates),
                joinedload(Student.projects),
                joinedload(Student.internships),
                joinedload(Student.campus_experiences),
            )
            .filter(Student.id == student_id, Student.deleted.is_(False))
            .first()
        )
        if not student:
            raise ValueError("学生不存在")

        profile = self._load_profile(student_id)
        jobs = self._matchable_jobs()

        for item in self.db.query(JobMatchResult).filter(JobMatchResult.student_id == student_id).all():
            self.db.delete(item)
        self.db.flush()

        results: list[JobMatchResult] = []
        for job in jobs:
            result = self._calculate_match(student, profile, job)
            results.append(result)
            self.db.add(result)
        self.db.commit()
        results.sort(key=lambda item: item.total_score, reverse=True)
        return [self.serialize_match(item) for item in results]

    def get_matches(self, student_id: int) -> list[dict]:
        self._ensure_job_catalog()
        self._ensure_student_matches(student_id)
        results = (
            self.db.query(JobMatchResult)
            .options(joinedload(JobMatchResult.job), joinedload(JobMatchResult.gaps))
            .filter(JobMatchResult.student_id == student_id, JobMatchResult.deleted.is_(False))
            .order_by(JobMatchResult.total_score.desc())
            .all()
        )
        return [self.serialize_match(item) for item in results]

    def get_match(self, student_id: int, job_id: int) -> dict | None:
        self._ensure_job_catalog()
        self._ensure_student_matches(student_id)
        result = (
            self.db.query(JobMatchResult)
            .options(joinedload(JobMatchResult.job), joinedload(JobMatchResult.gaps))
            .filter(JobMatchResult.student_id == student_id, JobMatchResult.job_id == job_id, JobMatchResult.deleted.is_(False))
            .first()
        )
        return self.serialize_match(result) if result else None

    def _ensure_job_catalog(self) -> None:
        if self._job_catalog_checked:
            return
        self._job_catalog_checked = True
        try:
            sync_service = JobKnowledgeSyncService(self.db)
            documents = sync_service.vector_service.list_documents(limit=20000)
        except Exception:
            return
        names = {str(item.get("job_name") or "").strip() for item in documents if str(item.get("job_name") or "").strip()}
        if not names:
            return
        active_jobs = self.db.query(Job).filter(Job.deleted.is_(False)).all()
        synced_names = {job.name for job in active_jobs if JobKnowledgeSyncService._is_synced_job(job)}
        if names.issubset(synced_names):
            return
        try:
            sync_service.sync_from_knowledge_base(force=True)
        except Exception:
            self.db.rollback()

    def _ensure_student_matches(self, student_id: int) -> None:
        active_job_count = len(self._matchable_jobs())
        if not active_job_count:
            return
        current_match_count = (
            self.db.query(JobMatchResult)
            .filter(JobMatchResult.student_id == student_id, JobMatchResult.deleted.is_(False))
            .count()
        )
        if current_match_count == active_job_count:
            return
        self.generate_matches(student_id, ensure_job_catalog=False)

    def _matchable_jobs(self) -> list[Job]:
        jobs = self.db.query(Job).options(joinedload(Job.skills), joinedload(Job.certificates)).filter(Job.deleted.is_(False)).all()
        return [job for job in jobs if self._is_matchable_job(job)]

    @staticmethod
    def _is_matchable_job(job: Job) -> bool:
        profile = job.job_profile if isinstance(job.job_profile, dict) else None
        if profile:
            try:
                JobPortraitSchema.model_validate(profile)
                return True
            except Exception:
                pass
        return bool(job.core_skill_tags or [item for item in job.skills if not item.deleted])

    def _load_profile(self, student_id: int) -> StudentProfile | None:
        profile = (
            self.db.query(StudentProfile)
            .filter(StudentProfile.student_id == student_id, StudentProfile.deleted.is_(False))
            .order_by(StudentProfile.id.desc())
            .first()
        )
        if profile:
            return profile
        StudentProfileService(self.db).generate_profile(student_id)
        return (
            self.db.query(StudentProfile)
            .filter(StudentProfile.student_id == student_id, StudentProfile.deleted.is_(False))
            .order_by(StudentProfile.id.desc())
            .first()
        )

    def _calculate_match(self, student: Student, profile: StudentProfile | None, job: Job) -> JobMatchResult:
        profile_map = self._profile_dimension_map(profile)
        job_profile = job.job_profile if isinstance(job.job_profile, dict) else {}
        weights = self._resolve_match_weights(job_profile)

        student_skills = {item.name.lower() for item in student.skills if not item.deleted}
        student_certificates = {item.name.lower() for item in student.certificates if not item.deleted}
        project_skills = {skill.lower() for item in student.projects if not item.deleted for skill in (item.technologies or [])}
        internship_skills = {skill.lower() for item in student.internships if not item.deleted for skill in (item.skills or [])}

        required_skills = [item.lower() for item in (job.core_skill_tags or [skill.name for skill in job.skills]) if item]
        required_certs = [item.lower() for item in (job.certificate_tags or [cert.name for cert in job.certificates]) if item]
        common_skill_tags = {item.lower() for item in (job.common_skill_tags or []) if item}

        skill_hits = set(required_skills) & (student_skills | project_skills | internship_skills)
        cert_hits = set(required_certs) & student_certificates
        common_hits = common_skill_tags & {item.lower() for item in (student.interests or []) if item}

        basic_requirement_score = self._basic_requirement_score(student, job, profile_map, required_certs, cert_hits)
        certificate_score = self._certificate_score(profile_map, required_certs, cert_hits)
        project_score = self._project_score(student, required_skills, project_skills)
        internship_score = self._internship_score(student, required_skills, internship_skills, profile_map)
        professional_skill_score = self._professional_skill_score(profile_map, required_skills, skill_hits, project_score, internship_score)
        professional_literacy_score = self._professional_literacy_score(profile_map, common_hits)
        development_potential_score = self._development_potential_score(student, job, profile_map)

        total_score = round(
            basic_requirement_score * weights["basic_requirement"]
            + professional_skill_score * weights["professional_skill"]
            + professional_literacy_score * weights["professional_literacy"]
            + development_potential_score * weights["development_potential"],
            1,
        )
        key_skill_hit_rate = round((len(skill_hits) / len(required_skills) * 100) if required_skills else 100.0, 1)

        dimensions = [
            {"key": "basic_requirement", "label": DIMENSION_LABELS["basic_requirement"], "score": basic_requirement_score, "description": "围绕专业背景、证书准备和岗位进入门槛综合评估。"},
            {"key": "professional_skill", "label": DIMENSION_LABELS["professional_skill"], "score": professional_skill_score, "description": "围绕核心技能命中率、项目证据和实习证据综合评估。"},
            {"key": "professional_literacy", "label": DIMENSION_LABELS["professional_literacy"], "score": professional_literacy_score, "description": "围绕沟通协作、抗压能力与职业节奏综合评估。"},
            {"key": "development_potential", "label": DIMENSION_LABELS["development_potential"], "score": development_potential_score, "description": "围绕学习成长、创新能力与岗位意愿综合评估。"},
        ]
        MatchSchema.model_validate(
            {
                "total_score": total_score,
                "weights": weights,
                "dimensions": dimensions,
                "key_skill_hit_rate": key_skill_hit_rate,
            }
        )

        reasons = [
            f"基础要求得分 {basic_requirement_score} 分，重点参考专业背景、证书准备和岗位进入门槛。",
            f"职业技能得分 {professional_skill_score} 分，核心技能命中 {len(skill_hits)}/{len(required_skills) or 1}。",
            f"职业素养得分 {professional_literacy_score} 分，结合沟通、抗压和协作节奏判断。",
            f"发展潜力得分 {development_potential_score} 分，结合学习、创新和岗位意愿判断。",
        ]
        strongest = max(dimensions, key=lambda item: item["score"])["label"]
        weakest = min(dimensions, key=lambda item: item["score"])["label"]
        summary = f"当前对 {job.name} 的综合匹配度为 {total_score} 分，优势维度为 {strongest}，优先补齐 {weakest}。"

        result = JobMatchResult(
            student_id=student.id,
            job_id=job.id,
            total_score=total_score,
            major_match=basic_requirement_score,
            skill_match=professional_skill_score,
            certificate_match=certificate_score,
            project_match=project_score,
            internship_match=internship_score,
            soft_skill_match=professional_literacy_score,
            interest_match=development_potential_score,
            reasons=reasons,
            summary=summary,
        )
        for gap in self._build_gaps(required_skills, required_certs, student_skills, project_skills, internship_skills, student_certificates, profile_map, dimensions):
            result.gaps.append(JobMatchGap(**gap))
        return result

    @staticmethod
    def _resolve_match_weights(job_profile: dict) -> dict[str, float]:
        weights = job_profile.get("match_weights") if isinstance(job_profile, dict) else {}
        if not isinstance(weights, dict):
            return deepcopy(DEFAULT_MATCH_WEIGHTS)
        normalized = {key: float(weights.get(key, 0)) for key in MATCH_DIMENSION_KEY_ORDER}
        total = sum(normalized.values())
        if total <= 0:
            return deepcopy(DEFAULT_MATCH_WEIGHTS)
        normalized = {key: round(value / total, 6) for key, value in normalized.items()}
        return normalized

    def _basic_requirement_score(self, student: Student, job: Job, profile: dict[str, float], required_certs: list[str], cert_hits: set[str]) -> float:
        major_text = f"{student.major or ''} {student.college or ''}".lower()
        job_major = (job.major_requirement or "").lower()
        major_score = 62.0
        if student.major and job.major_requirement and student.major.lower() in job.major_requirement.lower():
            major_score = 96.0
        elif job_major and any(token in major_text for token in ["计算机", "软件", "数据", "统计", "设计", "营销", "管理"] if token in job_major):
            major_score = 82.0
        certificate_score = self._certificate_score(profile, required_certs, cert_hits)
        entry_score = min(100.0, round(40 + len([i for i in student.internships if not i.deleted]) * 12 + len([i for i in student.projects if not i.deleted]) * 6 + profile.get("completeness_score", 0) * 0.18, 1))
        return round(mean([major_score, certificate_score, entry_score]), 1)

    @staticmethod
    def _certificate_score(profile: dict[str, float], required_certs: list[str], cert_hits: set[str]) -> float:
        profile_score = profile.get("certificate", 60.0)
        if not required_certs:
            return round(mean([profile_score, 78.0]), 1)
        hit_rate = len(cert_hits) / len(required_certs)
        return round(min(100.0, hit_rate * 100 * 0.6 + profile_score * 0.4), 1)

    @staticmethod
    def _project_score(student: Student, required_skills: list[str], project_skills: set[str]) -> float:
        shared = len(set(required_skills) & project_skills)
        return round(min(100.0, 36 + len([i for i in student.projects if not i.deleted]) * 11 + shared * 8), 1)

    @staticmethod
    def _internship_score(student: Student, required_skills: list[str], internship_skills: set[str], profile: dict[str, float]) -> float:
        shared = len(set(required_skills) & internship_skills)
        evidence_score = min(100.0, 30 + len([i for i in student.internships if not i.deleted]) * 18 + shared * 8)
        return round(mean([evidence_score, profile.get("internship", 60.0)]), 1)

    @staticmethod
    def _professional_skill_score(profile: dict[str, float], required_skills: list[str], skill_hits: set[str], project_score: float, internship_score: float) -> float:
        profile_skill = profile.get("professional_skill", 60.0)
        hit_rate = 0.72 if not required_skills else len(skill_hits) / len(required_skills)
        return round(hit_rate * 100 * 0.5 + project_score * 0.25 + internship_score * 0.1 + profile_skill * 0.15, 1)

    @staticmethod
    def _professional_literacy_score(profile: dict[str, float], common_hits: set[str]) -> float:
        communication = profile.get("communication", 60.0)
        stress_resistance = profile.get("stress_resistance", 60.0)
        learning = profile.get("learning", 60.0)
        bonus = min(10.0, len(common_hits) * 4.0)
        return round(min(100.0, mean([communication, stress_resistance, learning]) + bonus), 1)

    @staticmethod
    def _development_potential_score(student: Student, job: Job, profile: dict[str, float]) -> float:
        learning = profile.get("learning", 60.0)
        innovation = profile.get("innovation", 60.0)
        target_text = " ".join((student.interests or []) + [student.target_industry or "", student.target_city or ""]).lower()
        interest_alignment = 90.0 if any(token and token.lower() in target_text for token in [job.name, job.category or "", job.industry or ""]) else 64.0
        return round(mean([learning, innovation, interest_alignment]), 1)

    @staticmethod
    def _profile_dimension_map(profile: StudentProfile | None) -> dict[str, float]:
        if not profile:
            return {"professional_skill": 60.0, "certificate": 60.0, "innovation": 60.0, "learning": 60.0, "stress_resistance": 60.0, "communication": 60.0, "internship": 60.0, "completeness_score": 60.0}
        raw = profile.raw_metrics if isinstance(profile.raw_metrics, dict) else {}
        dimension_items = raw.get("dimension_scores") or []
        dimensions = {item.get("key"): float(item.get("score") or 0) for item in dimension_items if item.get("key")}
        return {
            "professional_skill": dimensions.get("professional_skill", float(profile.professional_score or 0)),
            "certificate": dimensions.get("certificate", float(raw.get("certificate_score") or 0)),
            "innovation": dimensions.get("innovation", float(profile.innovation_score or 0)),
            "learning": dimensions.get("learning", float(profile.learning_score or 0)),
            "stress_resistance": dimensions.get("stress_resistance", float(raw.get("stress_score") or profile.professionalism_score or 0)),
            "communication": dimensions.get("communication", float(profile.communication_score or 0)),
            "internship": dimensions.get("internship", float(profile.practice_score or 0)),
            "completeness_score": float(raw.get("completeness_score") or 0),
        }

    @staticmethod
    def _build_gaps(required_skills: list[str], required_certs: list[str], student_skills: set[str], project_skills: set[str], internship_skills: set[str], student_certs: set[str], profile: dict[str, float], dimensions: list[dict]) -> list[dict]:
        gaps: list[dict] = []
        for skill in required_skills:
            if skill in student_skills or skill in project_skills or skill in internship_skills:
                continue
            gaps.append({"gap_type": "职业技能", "gap_item": skill, "description": f"当前缺少与 {skill} 直接相关的技能证据或项目证明。", "priority": 5})
        for cert in required_certs:
            if cert in student_certs:
                continue
            gaps.append({"gap_type": "基础要求", "gap_item": cert, "description": f"当前缺少 {cert} 相关证书或等价证明材料。", "priority": 4})
        if profile.get("internship", 0) < 65:
            gaps.append({"gap_type": "基础要求", "gap_item": "岗位相关实习", "description": "建议补充真实岗位实习或企业项目经历。", "priority": 5})
        literacy_score = next((item["score"] for item in dimensions if item["key"] == "professional_literacy"), 0)
        potential_score = next((item["score"] for item in dimensions if item["key"] == "development_potential"), 0)
        if literacy_score < 70:
            gaps.append({"gap_type": "职业素养", "gap_item": "沟通协作与抗压节奏", "description": "建议通过周报、复盘和协作演练提升职业协同能力。", "priority": 4})
        if potential_score < 70:
            gaps.append({"gap_type": "发展潜力", "gap_item": "学习与创新成果", "description": "建议通过课程、竞赛、作品或项目持续沉淀成长证据。", "priority": 4})
        return gaps[:8]

    def serialize_match(self, result: JobMatchResult) -> dict:
        data = to_dict(result, include=["gaps"])
        weights = self._resolve_match_weights(result.job.job_profile if isinstance(result.job.job_profile, dict) else {})
        dimensions = [
            {"key": "basic_requirement", "label": DIMENSION_LABELS["basic_requirement"], "score": result.major_match},
            {"key": "professional_skill", "label": DIMENSION_LABELS["professional_skill"], "score": result.skill_match},
            {"key": "professional_literacy", "label": DIMENSION_LABELS["professional_literacy"], "score": result.soft_skill_match},
            {"key": "development_potential", "label": DIMENSION_LABELS["development_potential"], "score": result.interest_match},
        ]
        data["job"] = {"id": result.job.id, "name": result.job.name, "category": result.job.category, "industry": result.job.industry}
        data["dimension_scores"] = dimensions
        data["sub_scores"] = [
            {"key": "certificate", "label": "证书准备", "score": result.certificate_match},
            {"key": "project", "label": "项目证明", "score": result.project_match},
            {"key": "internship", "label": "实习证明", "score": result.internship_match},
        ]
        data["match_weights"] = weights
        data["dimension_analysis"] = [
            {"key": "basic_requirement", "label": DIMENSION_LABELS["basic_requirement"], "score": result.major_match, "description": f"专业背景、证书准备和进入门槛得分为 {result.major_match} 分。"},
            {"key": "professional_skill", "label": DIMENSION_LABELS["professional_skill"], "score": result.skill_match, "description": f"核心技能命中与项目证据综合得分为 {result.skill_match} 分。"},
            {"key": "professional_literacy", "label": DIMENSION_LABELS["professional_literacy"], "score": result.soft_skill_match, "description": f"沟通协作、抗压节奏综合得分为 {result.soft_skill_match} 分。"},
            {"key": "development_potential", "label": DIMENSION_LABELS["development_potential"], "score": result.interest_match, "description": f"学习成长、创新表现与岗位意愿综合得分为 {result.interest_match} 分。"},
        ]
        data["key_skill_hit_rate"] = round(min(100.0, result.skill_match), 1)
        return data
