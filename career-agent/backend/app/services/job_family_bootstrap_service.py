from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.job import Job, JobCertificate, JobSkill
from app.services.graph.career_path_neo4j import CareerPathNeo4jService
from app.services.graph.job_graph_neo4j import JobGraphNeo4jService
from app.services.structured_llm_service import MockStructuredLLMService, get_official_job_family


class JobFamilyBootstrapService:
    def __init__(self, db: Session):
        self.db = db
        self.mock_llm = MockStructuredLLMService()
        self.graph_service = JobGraphNeo4jService()
        self.career_service = CareerPathNeo4jService()

    def ensure_official_job_family(self) -> dict[str, int]:
        baselines = get_official_job_family()
        jobs_by_name: dict[str, Job] = {}
        relation_count = 0

        for job_name in baselines:
            job = self.db.query(Job).filter(Job.name == job_name).first()
            if not job:
                job = Job(name=job_name)
                self.db.add(job)
                self.db.flush()

            profile = self.mock_llm.generate_job_profile(job_name, "")
            job.category = job.category or "综合"
            job.industry = job.industry or "互联网"
            job.description = profile.get("summary")
            job.degree_requirement = profile.get("degree_requirement")
            job.major_requirement = profile.get("major_requirement")
            job.internship_requirement = profile.get("internship_requirement")
            job.work_content = profile.get("work_content")
            job.development_direction = profile.get("development_direction")
            job.core_skill_tags = profile.get("core_skills", [])
            job.common_skill_tags = profile.get("common_skills", [])
            job.certificate_tags = profile.get("certificates", [])
            job.job_profile = profile
            job.generated_by_ai = True
            job.deleted = False

            job.skills.clear()
            job.certificates.clear()
            for skill in profile.get("core_skills", []):
                job.skills.append(JobSkill(name=skill, importance=5, category="核心技能", description=f"{job_name}核心能力：{skill}"))
            for certificate in profile.get("certificates", []):
                job.certificates.append(JobCertificate(name=certificate, importance=4, description=f"{job_name}推荐证书"))
            jobs_by_name[job_name] = job

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

        self.db.flush()

        for source_name, source_job in jobs_by_name.items():
            source_profile = source_job.job_profile if isinstance(source_job.job_profile, dict) else {}
            for item in source_profile.get("transfer_paths", []):
                target_name = item.get("target_job_name")
                target_job = jobs_by_name.get(target_name)
                if not target_job:
                    continue

                relation_type = item.get("relation_type", "换岗路径")
                years_required = self._infer_years_from_relation(relation_type)

                if "晋升" in relation_type:
                    self.career_service.create_career_path(
                        from_job_id=source_job.id,
                        to_job_id=target_job.id,
                        years_required=years_required,
                        salary_boost=0.2,
                        difficulty="intermediate",
                    )
                else:
                    self.graph_service.create_job_relation(
                        from_job_id=source_job.id,
                        to_job_id=target_job.id,
                        relation_type=relation_type,
                        weight=0.8,
                    )

                relation_count += 1

        self.db.commit()
        return {"job_count": len(jobs_by_name), "relation_count": relation_count}

    @staticmethod
    def _infer_years_from_relation(relation_type: str) -> float:
        if "晋升" in relation_type:
            return 2.0
        if "换岗" in relation_type:
            return 1.5
        return 1.0
