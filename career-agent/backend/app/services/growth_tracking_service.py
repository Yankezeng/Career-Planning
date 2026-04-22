from sqlalchemy.orm import Session

from app.models.student import (
    GrowthRecord,
    StudentCertificate,
    StudentInternship,
    StudentProject,
    StudentSkill,
)
from app.utils.serializers import to_dict


class GrowthTrackingService:
    def __init__(self, db: Session):
        self.db = db

    def list_records(self, student_id: int):
        records = (
            self.db.query(GrowthRecord)
            .filter(GrowthRecord.student_id == student_id, GrowthRecord.deleted.is_(False))
            .order_by(GrowthRecord.id.desc())
            .all()
        )
        return [to_dict(record) for record in records]

    def create_record(self, student_id: int, payload: dict):
        record = GrowthRecord(student_id=student_id, **payload)
        self.db.add(record)
        self.db.flush()
        self._sync_growth_artifacts(student_id, payload)
        self.db.commit()
        self.db.refresh(record)
        return to_dict(record)

    def get_trend(self, student_id: int):
        records = self.list_records(student_id)
        return {
            "labels": [item["stage_label"] for item in reversed(records)],
            "completion_rates": [item["completion_rate"] for item in reversed(records)],
            "skill_counts": [len(item.get("new_skills", [])) for item in reversed(records)],
            "certificate_counts": [len(item.get("new_certificates", [])) for item in reversed(records)],
            "project_counts": [len(item.get("new_projects", [])) for item in reversed(records)],
            "internship_counts": [len(item.get("new_internships", [])) for item in reversed(records)],
            "effort_index": [
                min(
                    100,
                    round(
                        item.get("completion_rate", 0) * 0.55
                        + len(item.get("new_skills", [])) * 8
                        + len(item.get("new_certificates", [])) * 7
                        + len(item.get("new_projects", [])) * 10
                        + len(item.get("new_internships", [])) * 12,
                        1,
                    ),
                )
                for item in reversed(records)
            ],
        }

    def _sync_growth_artifacts(self, student_id: int, payload: dict):
        self._upsert_skills(student_id, payload.get("new_skills", []))
        self._upsert_certificates(student_id, payload.get("new_certificates", []))
        self._upsert_projects(student_id, payload.get("new_projects", []))
        self._upsert_internships(student_id, payload.get("new_internships", []))

    def _upsert_skills(self, student_id: int, skills: list[str]):
        existing = {
            item.name.lower()
            for item in self.db.query(StudentSkill)
            .filter(StudentSkill.student_id == student_id, StudentSkill.deleted.is_(False))
            .all()
        }
        for skill in skills:
            if skill.lower() in existing:
                continue
            self.db.add(StudentSkill(student_id=student_id, name=skill, level="成长新增", category="阶段成果"))
            existing.add(skill.lower())

    def _upsert_certificates(self, student_id: int, certificates: list[str]):
        existing = {
            item.name.lower()
            for item in self.db.query(StudentCertificate)
            .filter(StudentCertificate.student_id == student_id, StudentCertificate.deleted.is_(False))
            .all()
        }
        for certificate in certificates:
            if certificate.lower() in existing:
                continue
            self.db.add(
                StudentCertificate(
                    student_id=student_id,
                    name=certificate,
                    issuer="阶段成果提交",
                    description="由成长跟踪模块自动同步的新增证书/训练营成果",
                )
            )
            existing.add(certificate.lower())

    def _upsert_projects(self, student_id: int, projects: list[str]):
        existing = {
            item.name.lower()
            for item in self.db.query(StudentProject)
            .filter(StudentProject.student_id == student_id, StudentProject.deleted.is_(False))
            .all()
        }
        for project in projects:
            if project.lower() in existing:
                continue
            self.db.add(
                StudentProject(
                    student_id=student_id,
                    name=project,
                    role="阶段成长项目",
                    description="由成长跟踪模块自动沉淀的新增项目成果",
                    technologies=[],
                    outcome="已纳入职业成长复盘，可继续补充量化结果。",
                    relevance_score=82,
                )
            )
            existing.add(project.lower())

    def _upsert_internships(self, student_id: int, internships: list[str]):
        existing = {
            f"{item.company}-{item.position}".lower()
            for item in self.db.query(StudentInternship)
            .filter(StudentInternship.student_id == student_id, StudentInternship.deleted.is_(False))
            .all()
        }
        for internship in internships:
            identity = f"{internship}-阶段实践".lower()
            if identity in existing:
                continue
            self.db.add(
                StudentInternship(
                    student_id=student_id,
                    company=internship,
                    position="阶段实践 / 新增实习",
                    description="由成长跟踪模块自动同步的新增实习或岗位实践经历",
                    skills=[],
                    relevance_score=80,
                )
            )
            existing.add(identity)
