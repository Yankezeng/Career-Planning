from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.auth import EnterpriseProfile
from app.models.job import Job, JobCertificate, JobSkill
from app.services.structured_llm_service_clean import get_structured_llm_service


class JobProfileService:
    def __init__(self, db: Session):
        self.db = db
        self.llm_service = get_structured_llm_service()

    def generate_profile(self, job_id: int) -> Job:
        job = self.db.query(Job).filter(Job.id == job_id, Job.deleted.is_(False)).first()
        if not job:
            raise ValueError("岗位不存在")

        profile = self.llm_service.generate_job_profile(job.name, job.description or "")
        profile["source_companies"] = self._resolve_source_companies(job)

        job.job_profile = profile
        job.generated_by_ai = True
        job.category = job.category or profile.get("category")
        job.industry = job.industry or profile.get("industry")
        job.core_skill_tags = profile.get("core_skills", [])
        job.common_skill_tags = profile.get("common_skills", [])
        job.certificate_tags = profile.get("certificates", [])
        job.degree_requirement = profile.get("degree_requirement")
        job.major_requirement = profile.get("major_requirement")
        job.internship_requirement = profile.get("internship_requirement")
        job.work_content = profile.get("work_content")
        job.development_direction = profile.get("development_direction")

        job.skills.clear()
        job.certificates.clear()
        for name in profile.get("core_skills", []):
            job.skills.append(
                JobSkill(
                    name=name,
                    category="核心技能",
                    importance=5,
                    description=f"岗位画像要求：{name}",
                )
            )
        for name in profile.get("certificates", []):
            job.certificates.append(
                JobCertificate(
                    name=name,
                    importance=4,
                    description=f"岗位画像建议证书：{name}",
                )
            )

        self.db.commit()
        self.db.refresh(job)
        return job

    def _resolve_source_companies(self, job: Job) -> list[str]:
        current = job.job_profile if isinstance(job.job_profile, dict) else {}
        companies = {str(item).strip() for item in (current.get("source_companies") or []) if str(item).strip()}
        company_name = current.get("company_name")
        if company_name:
            companies.add(str(company_name).strip())
        if not companies:
            rows = self.db.query(EnterpriseProfile.company_name).filter(EnterpriseProfile.deleted.is_(False)).all()
            companies = {str(item[0]).strip() for item in rows if item and str(item[0]).strip()}
        return sorted(companies)

