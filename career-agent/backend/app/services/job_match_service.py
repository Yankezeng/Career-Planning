from statistics import mean

from sqlalchemy.orm import Session, joinedload

from app.models.job import Job, JobMatchGap, JobMatchResult
from app.models.student import Student, StudentProfile
from app.services.job_knowledge_sync_service import JobKnowledgeSyncService
from app.utils.serializers import to_dict


class JobMatchService:
    def __init__(self, db: Session):
        self.db = db
        self._job_catalog_checked = False

    def generate_matches(self, student_id: int, ensure_job_catalog: bool = True):
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
        profile = (
            self.db.query(StudentProfile)
            .filter(StudentProfile.student_id == student_id, StudentProfile.deleted.is_(False))
            .order_by(StudentProfile.id.desc())
            .first()
        )
        jobs = self.db.query(Job).options(joinedload(Job.skills), joinedload(Job.certificates)).filter(Job.deleted.is_(False)).all()
        for item in self.db.query(JobMatchResult).filter(JobMatchResult.student_id == student_id).all():
            self.db.delete(item)
        self.db.flush()

        results = []
        for job in jobs:
            result = self._calculate_match(student, profile, job)
            results.append(result)
            self.db.add(result)
        self.db.commit()
        results.sort(key=lambda item: item.total_score, reverse=True)
        return [self.serialize_match(item) for item in results]

    def get_matches(self, student_id: int):
        self._ensure_job_catalog()
        self._ensure_student_matches(student_id)
        results = (
            self.db.query(JobMatchResult)
            .options(joinedload(JobMatchResult.job), joinedload(JobMatchResult.gaps))
            .filter(JobMatchResult.student_id == student_id, JobMatchResult.deleted.is_(False))
            .order_by(JobMatchResult.total_score.desc())
            .all()
        )
        return [self.serialize_match(result) for result in results]

    def get_match(self, student_id: int, job_id: int):
        self._ensure_job_catalog()
        self._ensure_student_matches(student_id)
        result = (
            self.db.query(JobMatchResult)
            .options(joinedload(JobMatchResult.job), joinedload(JobMatchResult.gaps))
            .filter(
                JobMatchResult.student_id == student_id,
                JobMatchResult.job_id == job_id,
                JobMatchResult.deleted.is_(False),
            )
            .first()
        )
        return self.serialize_match(result) if result else None

    def _ensure_job_catalog(self):
        if self._job_catalog_checked:
            return

        self._job_catalog_checked = True
        try:
            sync_service = JobKnowledgeSyncService(self.db)
            documents = sync_service.vector_service.list_documents(limit=20000)
        except Exception:
            return

        knowledge_job_names = {
            str(document.get("job_name") or "").strip()
            for document in documents
            if str(document.get("job_name") or "").strip()
        }
        if not knowledge_job_names:
            return

        active_jobs = self.db.query(Job).filter(Job.deleted.is_(False)).all()
        synced_job_names = {
            job.name
            for job in active_jobs
            if JobKnowledgeSyncService._is_synced_job(job)
        }
        if knowledge_job_names.issubset(synced_job_names):
            return

        try:
            sync_service.sync_from_knowledge_base(force=True)
        except Exception:
            self.db.rollback()

    def _ensure_student_matches(self, student_id: int):
        active_job_count = self.db.query(Job).filter(Job.deleted.is_(False)).count()
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

    def _calculate_match(self, student: Student, profile: StudentProfile | None, job: Job):
        student_skills = {item.name.lower() for item in student.skills if not item.deleted}
        student_certificates = {item.name.lower() for item in student.certificates if not item.deleted}
        project_skills = {skill.lower() for item in student.projects if not item.deleted for skill in (item.technologies or [])}
        internship_skills = {skill.lower() for item in student.internships if not item.deleted for skill in (item.skills or [])}
        campus_tags = {item.title.lower() for item in student.campus_experiences if not item.deleted}

        required_skills = [item.lower() for item in (job.core_skill_tags or [skill.name for skill in job.skills])]
        required_certs = [item.lower() for item in (job.certificate_tags or [cert.name for cert in job.certificates])]
        major_text = f"{student.major or ''}{student.college or ''}".lower()
        job_major = (job.major_requirement or "").lower()

        major_match = 92 if job_major and any(token in major_text for token in ["计算机", "软件", "数据", "管理", "设计", "市场"]) and any(token in job_major for token in ["相关", "计算机", "数据", "管理", "设计", "市场"]) else 70
        if student.major and job.major_requirement and student.major.lower() in job.major_requirement.lower():
            major_match = 96

        skill_hit_count = len(set(required_skills) & (student_skills | project_skills | internship_skills))
        skill_match = 70 if not required_skills else min(100, round(skill_hit_count / max(len(required_skills), 1) * 100, 1))
        cert_hit_count = len(set(required_certs) & student_certificates)
        certificate_match = 75 if not required_certs else min(100, round(cert_hit_count / max(len(required_certs), 1) * 100, 1))
        project_match = min(100, 40 + len(student.projects) * 12 + len(set(required_skills) & project_skills) * 8)
        internship_match = min(100, 35 + len(student.internships) * 18 + len(set(required_skills) & internship_skills) * 6)

        soft_source = mean(
            [
                profile.communication_score if profile else 60,
                profile.learning_score if profile else 60,
                profile.professionalism_score if profile else 60,
            ]
        )
        common_tags = {item.lower() for item in (job.common_skill_tags or [])}
        soft_bonus = 8 if common_tags & campus_tags else 0
        soft_skill_match = min(100, round(soft_source * 0.9 + soft_bonus, 1))

        interest_text = " ".join((student.interests or []) + [student.target_industry or "", student.target_city or ""]).lower()
        interest_match = 88 if any(token and token in interest_text for token in [job.industry or "", job.category or "", job.name]) else 65

        total_score = round(
            major_match * 0.15
            + skill_match * 0.30
            + certificate_match * 0.10
            + project_match * 0.15
            + internship_match * 0.10
            + soft_skill_match * 0.10
            + interest_match * 0.10,
            1,
        )
        reasons = [
            f"岗位核心技能命中 {skill_hit_count} 项",
            f"项目经历 {len(student.projects)} 段，实习经历 {len(student.internships)} 段",
            f"学生职业成熟度参考值 {round(soft_source, 1)} 分",
        ]
        gaps = self._build_gaps(required_skills, required_certs, student_skills, project_skills, internship_skills, student_certificates)
        result = JobMatchResult(
            student_id=student.id,
            job_id=job.id,
            total_score=total_score,
            major_match=major_match,
            skill_match=skill_match,
            certificate_match=certificate_match,
            project_match=project_match,
            internship_match=internship_match,
            soft_skill_match=soft_skill_match,
            interest_match=interest_match,
            reasons=reasons,
            summary=f"当前对 {job.name} 的匹配度为 {total_score} 分，建议围绕差距项开展针对性补强。",
        )
        for gap in gaps:
            result.gaps.append(JobMatchGap(**gap))
        return result

    def _build_gaps(
        self,
        required_skills: list[str],
        required_certs: list[str],
        student_skills: set[str],
        project_skills: set[str],
        internship_skills: set[str],
        student_certificates: set[str],
    ):
        gaps = []
        for skill in required_skills:
            if skill not in student_skills and skill not in project_skills and skill not in internship_skills:
                gaps.append(
                    {
                        "gap_type": "skill",
                        "gap_item": skill,
                        "description": f"缺少 {skill} 相关技能或实战经历",
                        "priority": 5,
                    }
                )
        for cert in required_certs:
            if cert not in student_certificates:
                gaps.append(
                    {
                        "gap_type": "certificate",
                        "gap_item": cert,
                        "description": f"缺少 {cert} 证书或同类证明",
                        "priority": 4,
                    }
                )
        if not internship_skills:
            gaps.append(
                {
                    "gap_type": "internship",
                    "gap_item": "相关实习经历",
                    "description": "缺少与目标岗位相关的实习经历",
                    "priority": 5,
                }
            )
        if not project_skills:
            gaps.append(
                {
                    "gap_type": "project",
                    "gap_item": "实战项目",
                    "description": "缺少可用于展示的项目成果",
                    "priority": 4,
                }
            )
        return gaps[:8]

    def serialize_match(self, result: JobMatchResult):
        data = to_dict(result, include=["gaps"])
        data["job"] = {"id": result.job.id, "name": result.job.name, "category": result.job.category, "industry": result.job.industry}
        return data


from copy import deepcopy

from app.schemas.portrait import MATCH_DIMENSION_KEYS, MatchSchema
from app.services.student_profile_service import StudentProfileService


DIMENSION_LABELS = {
    "basic_requirement": "基础要求",
    "professional_skill": "职业技能",
    "professional_literacy": "职业素养",
    "development_potential": "发展潜力",
}

DEFAULT_MATCH_WEIGHTS = {
    "basic_requirement": 0.25,
    "professional_skill": 0.4,
    "professional_literacy": 0.2,
    "development_potential": 0.15,
}


class JobMatchService:
    def __init__(self, db: Session):
        self.db = db
        self._job_catalog_checked = False

    def generate_matches(self, student_id: int, ensure_job_catalog: bool = True):
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
        jobs = self.db.query(Job).options(joinedload(Job.skills), joinedload(Job.certificates)).filter(Job.deleted.is_(False)).all()

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

    def get_matches(self, student_id: int):
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

    def get_match(self, student_id: int, job_id: int):
        self._ensure_job_catalog()
        self._ensure_student_matches(student_id)
        result = (
            self.db.query(JobMatchResult)
            .options(joinedload(JobMatchResult.job), joinedload(JobMatchResult.gaps))
            .filter(
                JobMatchResult.student_id == student_id,
                JobMatchResult.job_id == job_id,
                JobMatchResult.deleted.is_(False),
            )
            .first()
        )
        return self.serialize_match(result) if result else None

    def _ensure_job_catalog(self):
        if self._job_catalog_checked:
            return
        self._job_catalog_checked = True
        try:
            sync_service = JobKnowledgeSyncService(self.db)
            documents = sync_service.vector_service.list_documents(limit=20000)
        except Exception:
            return

        knowledge_job_names = {
            str(document.get("job_name") or "").strip()
            for document in documents
            if str(document.get("job_name") or "").strip()
        }
        if not knowledge_job_names:
            return

        active_jobs = self.db.query(Job).filter(Job.deleted.is_(False)).all()
        synced_job_names = {job.name for job in active_jobs if JobKnowledgeSyncService._is_synced_job(job)}
        if knowledge_job_names.issubset(synced_job_names):
            return
        sync_service.sync_from_knowledge_base(force=True)

    def _ensure_student_matches(self, student_id: int):
        active_job_count = self.db.query(Job).filter(Job.deleted.is_(False)).count()
        if not active_job_count:
            return
        existing_count = (
            self.db.query(JobMatchResult)
            .filter(JobMatchResult.student_id == student_id, JobMatchResult.deleted.is_(False))
            .count()
        )
        if existing_count == active_job_count:
            return
        self.generate_matches(student_id, ensure_job_catalog=False)

    def _load_profile(self, student_id: int) -> StudentProfile:
        profile = (
            self.db.query(StudentProfile)
            .filter(StudentProfile.student_id == student_id, StudentProfile.deleted.is_(False))
            .order_by(StudentProfile.id.desc())
            .first()
        )
        if profile:
            return profile
        StudentProfileService(self.db).generate_profile(student_id)
        profile = (
            self.db.query(StudentProfile)
            .filter(StudentProfile.student_id == student_id, StudentProfile.deleted.is_(False))
            .order_by(StudentProfile.id.desc())
            .first()
        )
        if not profile:
            raise ValueError("学生画像不存在")
        return profile

    def _calculate_match(self, student: Student, profile: StudentProfile, job: Job) -> JobMatchResult:
        student_skill_set = {item.name.lower() for item in student.skills if not item.deleted}
        student_cert_set = {item.name.lower() for item in student.certificates if not item.deleted}
        project_skill_set = {skill.lower() for item in student.projects if not item.deleted for skill in (item.technologies or [])}
        internship_skill_set = {skill.lower() for item in student.internships if not item.deleted for skill in (item.skills or [])}
        profile_dimensions = self._profile_dimension_scores(profile)

        required_skills = [item.lower() for item in (job.core_skill_tags or [skill.name for skill in job.skills]) if item]
        required_certs = [item.lower() for item in (job.certificate_tags or [cert.name for cert in job.certificates]) if item]
        common_skill_tags = {item.lower() for item in (job.common_skill_tags or []) if item}

        skill_hit_count = len(set(required_skills) & (student_skill_set | project_skill_set | internship_skill_set))
        cert_hit_count = len(set(required_certs) & student_cert_set)
        common_hit_count = len(common_skill_tags & {item.lower() for item in (student.interests or []) if item})

        basic_requirement = self._basic_requirement_score(student, job, profile_dimensions, cert_hit_count)
        professional_skill = self._professional_skill_score(
            profile_dimensions,
            required_skills,
            skill_hit_count,
            student.projects,
            student.internships,
            project_skill_set,
            internship_skill_set,
        )
        professional_literacy = self._professional_literacy_score(profile_dimensions, common_hit_count)
        development_potential = self._development_potential_score(student, job, profile_dimensions)
        match_weights = self._resolve_match_weights(job)

        total_score = round(
            basic_requirement * match_weights["basic_requirement"]
            + professional_skill * match_weights["professional_skill"]
            + professional_literacy * match_weights["professional_literacy"]
            + development_potential * match_weights["development_potential"],
            1,
        )
        key_skill_hit_rate = round(skill_hit_count / max(len(required_skills), 1) * 100, 1) if required_skills else 100.0
        dimensions = [
            {"key": "basic_requirement", "label": DIMENSION_LABELS["basic_requirement"], "score": basic_requirement, "description": "基础要求维度评估了专业背景、证书准备和入岗证明。"},
            {"key": "professional_skill", "label": DIMENSION_LABELS["professional_skill"], "score": professional_skill, "description": "职业技能维度评估了核心技能命中和项目/实习证据。"},
            {"key": "professional_literacy", "label": DIMENSION_LABELS["professional_literacy"], "score": professional_literacy, "description": "职业素养维度评估了沟通协作、抗压节奏和通用能力。"},
            {"key": "development_potential", "label": DIMENSION_LABELS["development_potential"], "score": development_potential, "description": "发展潜力维度评估了学习能力、创新能力和岗位意愿。"},
        ]
        MatchSchema.model_validate(
            {
                "total_score": total_score,
                "weights": match_weights,
                "dimensions": dimensions,
                "key_skill_hit_rate": key_skill_hit_rate,
            }
        )

        project_match = round(min(100.0, 35 + len([item for item in student.projects if not item.deleted]) * 12 + len(set(required_skills) & project_skill_set) * 7), 1)
        internship_match = round(min(100.0, 30 + len([item for item in student.internships if not item.deleted]) * 15 + len(set(required_skills) & internship_skill_set) * 8), 1)
        certificate_match = round(min(100.0, profile_dimensions["certificate"] * 0.45 + cert_hit_count * 25), 1)

        result = JobMatchResult(
            student_id=student.id,
            job_id=job.id,
            total_score=total_score,
            major_match=basic_requirement,
            skill_match=professional_skill,
            certificate_match=certificate_match,
            project_match=project_match,
            internship_match=internship_match,
            soft_skill_match=professional_literacy,
            interest_match=development_potential,
            reasons=[
                f"基础要求 {basic_requirement} 分：基于专业背景、证书和入岗证明。",
                f"职业技能 {professional_skill} 分：核心技能命中 {skill_hit_count}/{len(required_skills) or 1} 项。",
                f"职业素养 {professional_literacy} 分：基于沟通、抗压和协作能力。",
                f"发展潜力 {development_potential} 分：基于学习、创新和岗位目标一致性。",
            ],
            summary=f"当前岗位匹配度 {total_score} 分，建议优先提升分值最低维度并补齐关键技能证据。",
        )
        for gap in self._build_gaps(
            required_skills=required_skills,
            required_certs=required_certs,
            student_skill_set=student_skill_set,
            project_skill_set=project_skill_set,
            internship_skill_set=internship_skill_set,
            student_cert_set=student_cert_set,
            dimension_scores={
                "basic_requirement": basic_requirement,
                "professional_skill": professional_skill,
                "professional_literacy": professional_literacy,
                "development_potential": development_potential,
            },
        ):
            result.gaps.append(JobMatchGap(**gap))
        return result

    def _profile_dimension_scores(self, profile: StudentProfile) -> dict[str, float]:
        raw_metrics = profile.raw_metrics if isinstance(profile.raw_metrics, dict) else {}
        dimension_items = raw_metrics.get("dimension_scores") or []
        dimension_map = {item.get("key"): float(item.get("score") or 0) for item in dimension_items if item.get("key")}
        return {
            "professional_skill": dimension_map.get("professional_skill", float(profile.professional_score or 0)),
            "certificate": dimension_map.get("certificate", float(raw_metrics.get("certificate_score") or 0)),
            "innovation": dimension_map.get("innovation", float(profile.innovation_score or 0)),
            "learning": dimension_map.get("learning", float(profile.learning_score or 0)),
            "stress_resistance": dimension_map.get("stress_resistance", float(raw_metrics.get("stress_score") or profile.professionalism_score or 0)),
            "communication": dimension_map.get("communication", float(profile.communication_score or 0)),
            "internship": dimension_map.get("internship", float(profile.practice_score or 0)),
        }

    def _resolve_match_weights(self, job: Job) -> dict[str, float]:
        job_profile = job.job_profile if isinstance(job.job_profile, dict) else {}
        weights = job_profile.get("match_weights") or DEFAULT_MATCH_WEIGHTS
        if set(weights) != MATCH_DIMENSION_KEYS:
            return deepcopy(DEFAULT_MATCH_WEIGHTS)
        total = round(sum(float(value) for value in weights.values()), 6)
        if abs(total - 1.0) > 1e-4:
            return deepcopy(DEFAULT_MATCH_WEIGHTS)
        return {key: float(weights[key]) for key in DEFAULT_MATCH_WEIGHTS}

    @staticmethod
    def _basic_requirement_score(student: Student, job: Job, profile_dimensions: dict[str, float], cert_hit_count: int) -> float:
        major_text = f"{student.major or ''} {student.college or ''}".lower()
        major_requirement = str(job.major_requirement or "").lower()
        major_match = 62.0
        if student.major and major_requirement and student.major.lower() in major_requirement:
            major_match = 96.0
        elif major_requirement and any(token in major_text for token in ["计算机", "软件", "数据", "管理", "设计", "市场"]):
            major_match = 82.0
        certificate_score = round(min(100.0, profile_dimensions["certificate"] * 0.45 + cert_hit_count * 25), 1)
        entry_score = min(
            100.0,
            round(
                40 + len([item for item in student.internships if not item.deleted]) * 12 + len([item for item in student.projects if not item.deleted]) * 7,
                1,
            ),
        )
        return round((major_match + certificate_score + entry_score) / 3, 1)

    @staticmethod
    def _professional_skill_score(
        profile_dimensions: dict[str, float],
        required_skills: list[str],
        skill_hit_count: int,
        projects: list,
        internships: list,
        project_skill_set: set[str],
        internship_skill_set: set[str],
    ) -> float:
        skill_hit_rate = (skill_hit_count / max(len(required_skills), 1) * 100) if required_skills else 100
        project_score = min(100.0, 35 + len([item for item in projects if not item.deleted]) * 12 + len(set(required_skills) & project_skill_set) * 7)
        internship_score = min(100.0, 30 + len([item for item in internships if not item.deleted]) * 15 + len(set(required_skills) & internship_skill_set) * 8)
        return round(skill_hit_rate * 0.52 + project_score * 0.28 + internship_score * 0.08 + profile_dimensions["professional_skill"] * 0.12, 1)

    @staticmethod
    def _professional_literacy_score(profile_dimensions: dict[str, float], common_hit_count: int) -> float:
        base = (profile_dimensions["communication"] + profile_dimensions["stress_resistance"] + profile_dimensions["learning"]) / 3
        return round(min(100.0, base + common_hit_count * 4), 1)

    @staticmethod
    def _development_potential_score(student: Student, job: Job, profile_dimensions: dict[str, float]) -> float:
        target_text = " ".join((student.interests or []) + [student.target_industry or "", student.target_city or ""]).lower()
        alignment = 90.0 if any(token and token.lower() in target_text for token in [job.name, job.category or "", job.industry or ""]) else 64.0
        return round((profile_dimensions["learning"] + profile_dimensions["innovation"] + alignment) / 3, 1)

    @staticmethod
    def _build_gaps(
        *,
        required_skills: list[str],
        required_certs: list[str],
        student_skill_set: set[str],
        project_skill_set: set[str],
        internship_skill_set: set[str],
        student_cert_set: set[str],
        dimension_scores: dict[str, float],
    ) -> list[dict]:
        gaps: list[dict] = []
        for skill in required_skills:
            if skill in student_skill_set or skill in project_skill_set or skill in internship_skill_set:
                continue
            gaps.append({"gap_type": "职业技能", "gap_item": skill, "description": f"缺少{skill}相关可验证证据。", "priority": 5})
        for cert in required_certs:
            if cert in student_cert_set:
                continue
            gaps.append({"gap_type": "基础要求", "gap_item": cert, "description": f"缺少{cert}证书或同等级证明。", "priority": 4})
        if dimension_scores["professional_literacy"] < 70:
            gaps.append({"gap_type": "职业素养", "gap_item": "沟通协作与抗压节奏", "description": "需要提升协作推进与稳定交付节奏。", "priority": 4})
        if dimension_scores["development_potential"] < 70:
            gaps.append({"gap_type": "发展潜力", "gap_item": "学习与创新成果", "description": "需要通过课程与项目沉淀持续成长证据。", "priority": 4})
        return gaps[:8]

    def serialize_match(self, result: JobMatchResult):
        data = to_dict(result, include=["gaps"])
        data["job"] = {"id": result.job.id, "name": result.job.name, "category": result.job.category, "industry": result.job.industry}
        data["match_weights"] = self._resolve_match_weights(result.job)
        data["key_skill_hit_rate"] = round(result.skill_match, 1)
        data["dimension_scores"] = [
            {"key": "basic_requirement", "label": DIMENSION_LABELS["basic_requirement"], "score": result.major_match},
            {"key": "professional_skill", "label": DIMENSION_LABELS["professional_skill"], "score": result.skill_match},
            {"key": "professional_literacy", "label": DIMENSION_LABELS["professional_literacy"], "score": result.soft_skill_match},
            {"key": "development_potential", "label": DIMENSION_LABELS["development_potential"], "score": result.interest_match},
        ]
        data["dimension_analysis"] = [
            {"key": "basic_requirement", "label": DIMENSION_LABELS["basic_requirement"], "score": result.major_match, "description": "基础要求评估了专业背景、证书准备和入岗证明。"},
            {"key": "professional_skill", "label": DIMENSION_LABELS["professional_skill"], "score": result.skill_match, "description": "职业技能评估了核心技能命中与项目/实习证据。"},
            {"key": "professional_literacy", "label": DIMENSION_LABELS["professional_literacy"], "score": result.soft_skill_match, "description": "职业素养评估了沟通、抗压和协作能力。"},
            {"key": "development_potential", "label": DIMENSION_LABELS["development_potential"], "score": result.interest_match, "description": "发展潜力评估了学习、创新和岗位目标一致性。"},
        ]
        return data


DIMENSION_LABELS = {
    "basic_requirement": "基础要求",
    "professional_skill": "职业技能",
    "professional_literacy": "职业素养",
    "development_potential": "发展潜力",
}

DEFAULT_MATCH_WEIGHTS = {
    "basic_requirement": 0.25,
    "professional_skill": 0.4,
    "professional_literacy": 0.2,
    "development_potential": 0.15,
}


class JobMatchService:
    def __init__(self, db: Session):
        self.db = db
        self._job_catalog_checked = False

    def generate_matches(self, student_id: int, ensure_job_catalog: bool = True):
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
        jobs = self.db.query(Job).options(joinedload(Job.skills), joinedload(Job.certificates)).filter(Job.deleted.is_(False)).all()

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

    def get_matches(self, student_id: int):
        self._ensure_job_catalog()
        self._ensure_student_matches(student_id)
        results = (
            self.db.query(JobMatchResult)
            .options(joinedload(JobMatchResult.job), joinedload(JobMatchResult.gaps))
            .filter(JobMatchResult.student_id == student_id, JobMatchResult.deleted.is_(False))
            .order_by(JobMatchResult.total_score.desc())
            .all()
        )
        return [self.serialize_match(result) for result in results]

    def get_match(self, student_id: int, job_id: int):
        self._ensure_job_catalog()
        self._ensure_student_matches(student_id)
        result = (
            self.db.query(JobMatchResult)
            .options(joinedload(JobMatchResult.job), joinedload(JobMatchResult.gaps))
            .filter(
                JobMatchResult.student_id == student_id,
                JobMatchResult.job_id == job_id,
                JobMatchResult.deleted.is_(False),
            )
            .first()
        )
        return self.serialize_match(result) if result else None

    def _ensure_job_catalog(self):
        if self._job_catalog_checked:
            return

        self._job_catalog_checked = True
        try:
            sync_service = JobKnowledgeSyncService(self.db)
            documents = sync_service.vector_service.list_documents(limit=20000)
        except Exception:
            return

        knowledge_job_names = {
            str(document.get("job_name") or "").strip()
            for document in documents
            if str(document.get("job_name") or "").strip()
        }
        if not knowledge_job_names:
            return

        active_jobs = self.db.query(Job).filter(Job.deleted.is_(False)).all()
        synced_job_names = {
            job.name
            for job in active_jobs
            if JobKnowledgeSyncService._is_synced_job(job)
        }
        if knowledge_job_names.issubset(synced_job_names):
            return

        try:
            sync_service.sync_from_knowledge_base(force=True)
        except Exception:
            self.db.rollback()

    def _ensure_student_matches(self, student_id: int):
        active_job_count = self.db.query(Job).filter(Job.deleted.is_(False)).count()
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

    def _load_profile(self, student_id: int) -> StudentProfile | None:
        profile = (
            self.db.query(StudentProfile)
            .filter(StudentProfile.student_id == student_id, StudentProfile.deleted.is_(False))
            .order_by(StudentProfile.id.desc())
            .first()
        )
        if profile:
            return profile

        from app.services.student_profile_service import StudentProfileService

        StudentProfileService(self.db).generate_profile(student_id)
        return (
            self.db.query(StudentProfile)
            .filter(StudentProfile.student_id == student_id, StudentProfile.deleted.is_(False))
            .order_by(StudentProfile.id.desc())
            .first()
        )

    def _calculate_match(self, student: Student, profile: StudentProfile | None, job: Job):
        profile_dimensions = self._profile_dimension_map(profile)
        job_profile = job.job_profile if isinstance(job.job_profile, dict) else {}
        match_weights = job_profile.get("match_weights") or DEFAULT_MATCH_WEIGHTS

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

        major_match = self._basic_requirement_score(student, job, profile_dimensions, required_certs, cert_hits)
        certificate_match = self._certificate_score(profile_dimensions, required_certs, cert_hits)
        project_match = self._project_score(student, required_skills, project_skills)
        internship_match = self._internship_score(student, required_skills, internship_skills, profile_dimensions)
        skill_match = self._professional_skill_score(profile_dimensions, required_skills, skill_hits, project_match, internship_match)
        soft_skill_match = self._professional_literacy_score(profile_dimensions, common_hits)
        interest_match = self._development_potential_score(student, job, profile_dimensions)

        total_score = round(
            major_match * match_weights["basic_requirement"]
            + skill_match * match_weights["professional_skill"]
            + soft_skill_match * match_weights["professional_literacy"]
            + interest_match * match_weights["development_potential"],
            1,
        )

        strongest_dimension = max(
            [
                ("基础要求", major_match),
                ("职业技能", skill_match),
                ("职业素养", soft_skill_match),
                ("发展潜力", interest_match),
            ],
            key=lambda item: item[1],
        )[0]
        weakest_dimension = min(
            [
                ("基础要求", major_match),
                ("职业技能", skill_match),
                ("职业素养", soft_skill_match),
                ("发展潜力", interest_match),
            ],
            key=lambda item: item[1],
        )[0]

        reasons = [
            f"基础要求维度 {major_match} 分，重点参考专业背景、证书准备和岗位进入门槛。",
            f"职业技能维度 {skill_match} 分，核心技能命中 {len(skill_hits)}/{len(required_skills) or 1} 项。",
            f"职业素养维度 {soft_skill_match} 分，结合沟通、抗压和协作准备进行判断。",
            f"发展潜力维度 {interest_match} 分，结合学习、创新和目标岗位意愿进行判断。",
        ]
        summary = (
            f"当前对 {job.name} 的综合匹配度为 {total_score} 分，优势维度为{strongest_dimension}，"
            f"当前最需要优先补强的是{weakest_dimension}。"
        )

        gaps = self._build_gaps(
            required_skills=required_skills,
            required_certs=required_certs,
            student_skills=student_skills,
            project_skills=project_skills,
            internship_skills=internship_skills,
            student_certificates=student_certificates,
            profile_dimensions=profile_dimensions,
            dimension_scores={
                "basic_requirement": major_match,
                "professional_skill": skill_match,
                "professional_literacy": soft_skill_match,
                "development_potential": interest_match,
            },
        )
        result = JobMatchResult(
            student_id=student.id,
            job_id=job.id,
            total_score=total_score,
            major_match=major_match,
            skill_match=skill_match,
            certificate_match=certificate_match,
            project_match=project_match,
            internship_match=internship_match,
            soft_skill_match=soft_skill_match,
            interest_match=interest_match,
            reasons=reasons,
            summary=summary,
        )
        for gap in gaps:
            result.gaps.append(JobMatchGap(**gap))
        return result

    def _basic_requirement_score(
        self,
        student: Student,
        job: Job,
        profile_dimensions: dict[str, float],
        required_certs: list[str],
        cert_hits: set[str],
    ) -> float:
        major_text = f"{student.major or ''} {student.college or ''}".lower()
        job_major = (job.major_requirement or "").lower()
        major_score = 62.0
        if student.major and job.major_requirement and student.major.lower() in job.major_requirement.lower():
            major_score = 96.0
        elif job_major and any(token in major_text for token in self._major_tokens(job_major)):
            major_score = 82.0

        certificate_score = self._certificate_score(profile_dimensions, required_certs, cert_hits)
        entry_score = min(
            100.0,
            round(
                40
                + len([item for item in student.internships if not item.deleted]) * 12
                + len([item for item in student.projects if not item.deleted]) * 6
                + (profile_dimensions.get("completeness_score", 0) * 0.18),
                1,
            ),
        )
        return round(mean([major_score, certificate_score, entry_score]), 1)

    def _certificate_score(self, profile_dimensions: dict[str, float], required_certs: list[str], cert_hits: set[str]) -> float:
        profile_score = profile_dimensions.get("certificate", 60.0)
        if not required_certs:
            return round(mean([profile_score, 78.0]), 1)
        hit_rate = len(cert_hits) / len(required_certs)
        return round(min(100.0, hit_rate * 100 * 0.6 + profile_score * 0.4), 1)

    def _project_score(self, student: Student, required_skills: list[str], project_skills: set[str]) -> float:
        shared_project_skills = len(set(required_skills) & project_skills)
        return round(min(100.0, 36 + len([item for item in student.projects if not item.deleted]) * 11 + shared_project_skills * 8), 1)

    def _internship_score(
        self,
        student: Student,
        required_skills: list[str],
        internship_skills: set[str],
        profile_dimensions: dict[str, float],
    ) -> float:
        shared_internship_skills = len(set(required_skills) & internship_skills)
        evidence_score = min(
            100.0,
            30 + len([item for item in student.internships if not item.deleted]) * 18 + shared_internship_skills * 8,
        )
        return round(mean([evidence_score, profile_dimensions.get("internship", 60.0)]), 1)

    def _professional_skill_score(
        self,
        profile_dimensions: dict[str, float],
        required_skills: list[str],
        skill_hits: set[str],
        project_match: float,
        internship_match: float,
    ) -> float:
        profile_skill = profile_dimensions.get("professional_skill", 60.0)
        hit_rate = 0.72 if not required_skills else len(skill_hits) / len(required_skills)
        skill_hit_score = round(hit_rate * 100, 1)
        return round(skill_hit_score * 0.5 + project_match * 0.25 + internship_match * 0.1 + profile_skill * 0.15, 1)

    def _professional_literacy_score(self, profile_dimensions: dict[str, float], common_hits: set[str]) -> float:
        communication = profile_dimensions.get("communication", 60.0)
        stress_resistance = profile_dimensions.get("stress_resistance", 60.0)
        learning = profile_dimensions.get("learning", 60.0)
        shared_tag_bonus = min(10.0, len(common_hits) * 4.0)
        return round(min(100.0, mean([communication, stress_resistance, learning]) + shared_tag_bonus), 1)

    def _development_potential_score(self, student: Student, job: Job, profile_dimensions: dict[str, float]) -> float:
        learning = profile_dimensions.get("learning", 60.0)
        innovation = profile_dimensions.get("innovation", 60.0)
        target_text = " ".join((student.interests or []) + [student.target_industry or "", student.target_city or ""]).lower()
        interest_alignment = (
            90.0 if any(token and token.lower() in target_text for token in [job.name, job.category or "", job.industry or ""]) else 64.0
        )
        return round(mean([learning, innovation, interest_alignment]), 1)

    def _build_gaps(
        self,
        *,
        required_skills: list[str],
        required_certs: list[str],
        student_skills: set[str],
        project_skills: set[str],
        internship_skills: set[str],
        student_certificates: set[str],
        profile_dimensions: dict[str, float],
        dimension_scores: dict[str, float],
    ) -> list[dict]:
        gaps: list[dict] = []
        for skill in required_skills:
            if skill in student_skills or skill in project_skills or skill in internship_skills:
                continue
            gaps.append(
                {
                    "gap_type": "职业技能",
                    "gap_item": skill,
                    "description": f"当前缺少与 {skill} 直接相关的技能证据或项目证明。",
                    "priority": 5,
                }
            )
        for cert in required_certs:
            if cert in student_certificates:
                continue
            gaps.append(
                {
                    "gap_type": "基础要求",
                    "gap_item": cert,
                    "description": f"当前还没有 {cert} 相关证书或同类型证明材料。",
                    "priority": 4,
                }
            )
        if profile_dimensions.get("internship", 0) < 65:
            gaps.append(
                {
                    "gap_type": "基础要求",
                    "gap_item": "岗位相关实习",
                    "description": "当前真实岗位、企业项目或校企合作经历不足，进入岗位的基础证据还不够完整。",
                    "priority": 5,
                }
            )
        if dimension_scores["professional_literacy"] < 70:
            gaps.append(
                {
                    "gap_type": "职业素养",
                    "gap_item": "沟通协作与抗压节奏",
                    "description": "需要进一步补强沟通推进、任务协同和持续交付节奏。",
                    "priority": 4,
                }
            )
        if dimension_scores["development_potential"] < 70:
            gaps.append(
                {
                    "gap_type": "发展潜力",
                    "gap_item": "学习与创新成果",
                    "description": "建议通过课程、证书、比赛或作品证明学习能力与持续成长潜力。",
                    "priority": 4,
                }
            )
        return gaps[:8]

    def _profile_dimension_map(self, profile: StudentProfile | None) -> dict[str, float]:
        if not profile:
            return {
                "professional_skill": 60.0,
                "certificate": 60.0,
                "innovation": 60.0,
                "learning": 60.0,
                "stress_resistance": 60.0,
                "communication": 60.0,
                "internship": 60.0,
                "completeness_score": 60.0,
                "competitiveness_score": 60.0,
            }

        raw_metrics = profile.raw_metrics if isinstance(profile.raw_metrics, dict) else {}
        dimension_items = raw_metrics.get("dimension_scores") or []
        dimensions = {item.get("key"): float(item.get("score") or 0) for item in dimension_items if item.get("key")}
        return {
            "professional_skill": dimensions.get("professional_skill", float(profile.professional_score or 0)),
            "certificate": dimensions.get("certificate", float(raw_metrics.get("certificate_score") or 0)),
            "innovation": dimensions.get("innovation", float(profile.innovation_score or 0)),
            "learning": dimensions.get("learning", float(profile.learning_score or 0)),
            "stress_resistance": dimensions.get("stress_resistance", float(raw_metrics.get("stress_score") or profile.professionalism_score or 0)),
            "communication": dimensions.get("communication", float(profile.communication_score or 0)),
            "internship": dimensions.get("internship", float(profile.practice_score or 0)),
            "completeness_score": float(raw_metrics.get("completeness_score") or 0),
            "competitiveness_score": float(raw_metrics.get("competitiveness_score") or 0),
        }

    def _major_tokens(self, job_major: str) -> list[str]:
        return [token for token in ["计算机", "软件", "数据", "统计", "设计", "营销", "管理", "传播", "心理"] if token in job_major]

    def serialize_match(self, result: JobMatchResult):
        data = to_dict(result, include=["gaps"])
        job_profile = result.job.job_profile if isinstance(result.job.job_profile, dict) else {}
        match_weights = job_profile.get("match_weights") or DEFAULT_MATCH_WEIGHTS
        data["job"] = {
            "id": result.job.id,
            "name": result.job.name,
            "category": result.job.category,
            "industry": result.job.industry,
        }
        data["dimension_scores"] = [
            {"key": "basic_requirement", "label": DIMENSION_LABELS["basic_requirement"], "score": result.major_match},
            {"key": "professional_skill", "label": DIMENSION_LABELS["professional_skill"], "score": result.skill_match},
            {"key": "professional_literacy", "label": DIMENSION_LABELS["professional_literacy"], "score": result.soft_skill_match},
            {"key": "development_potential", "label": DIMENSION_LABELS["development_potential"], "score": result.interest_match},
        ]
        data["sub_scores"] = [
            {"key": "certificate", "label": "证书准备", "score": result.certificate_match},
            {"key": "project", "label": "项目证明", "score": result.project_match},
            {"key": "internship", "label": "实习证明", "score": result.internship_match},
        ]
        data["match_weights"] = match_weights
        data["dimension_analysis"] = [
            {"key": "basic_requirement", "label": DIMENSION_LABELS["basic_requirement"], "score": result.major_match, "description": f"专业背景、证书准备和进入岗位的基础证据得分为 {result.major_match} 分。"},
            {"key": "professional_skill", "label": DIMENSION_LABELS["professional_skill"], "score": result.skill_match, "description": f"核心技能、项目与岗位技能贴合度得分为 {result.skill_match} 分。"},
            {"key": "professional_literacy", "label": DIMENSION_LABELS["professional_literacy"], "score": result.soft_skill_match, "description": f"沟通协作、抗压和职业协同准备得分为 {result.soft_skill_match} 分。"},
            {"key": "development_potential", "label": DIMENSION_LABELS["development_potential"], "score": result.interest_match, "description": f"学习成长、创新能力与岗位发展意愿得分为 {result.interest_match} 分。"},
        ]
        return data
