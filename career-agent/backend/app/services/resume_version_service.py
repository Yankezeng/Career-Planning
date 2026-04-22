from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.student import StudentAttachment, StudentResume, StudentResumeVersion


class ResumeVersionService:
    def __init__(self, db: Session):
        self.db = db

    def get_cached_parsed_resume(
        self,
        *,
        student_id: int,
        attachment_id: int,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        options = options or {}
        version_id = options.get("resume_version_id")
        if version_id:
            version = (
                self.db.query(StudentResumeVersion)
                .join(StudentResume, StudentResume.id == StudentResumeVersion.resume_id)
                .filter(
                    StudentResumeVersion.id == int(version_id),
                    StudentResumeVersion.deleted.is_(False),
                    StudentResume.student_id == student_id,
                    StudentResume.deleted.is_(False),
                )
                .first()
            )
            if version and isinstance(version.parsed_json, dict) and version.parsed_json:
                return version.parsed_json

        resume_id = options.get("resume_id")
        if resume_id:
            resume = (
                self.db.query(StudentResume)
                .options(joinedload(StudentResume.current_version))
                .filter(
                    StudentResume.id == int(resume_id),
                    StudentResume.student_id == student_id,
                    StudentResume.deleted.is_(False),
                )
                .first()
            )
            if resume and resume.current_version and isinstance(resume.current_version.parsed_json, dict) and resume.current_version.parsed_json:
                return resume.current_version.parsed_json

        version = (
            self.db.query(StudentResumeVersion)
            .join(StudentResume, StudentResume.id == StudentResumeVersion.resume_id)
            .filter(
                StudentResumeVersion.attachment_id == int(attachment_id),
                StudentResumeVersion.deleted.is_(False),
                StudentResume.student_id == student_id,
                StudentResume.deleted.is_(False),
            )
            .order_by(StudentResumeVersion.is_active.desc(), StudentResumeVersion.id.desc())
            .first()
        )
        if version and isinstance(version.parsed_json, dict) and version.parsed_json:
            return version.parsed_json
        return None

    def store_parsed_resume(
        self,
        *,
        student_id: int,
        attachment: StudentAttachment,
        parsed_resume: dict[str, Any],
    ) -> tuple[StudentResume, StudentResumeVersion]:
        resume = (
            self.db.query(StudentResume)
            .options(joinedload(StudentResume.current_version))
            .filter(
                StudentResume.student_id == student_id,
                StudentResume.source_attachment_id == attachment.id,
                StudentResume.deleted.is_(False),
            )
            .order_by(StudentResume.is_default.desc(), StudentResume.id.desc())
            .first()
        )
        if not resume:
            default_exists = (
                self.db.query(StudentResume)
                .filter(
                    StudentResume.student_id == student_id,
                    StudentResume.deleted.is_(False),
                    StudentResume.is_default.is_(True),
                )
                .first()
                is not None
            )
            resume = StudentResume(
                student_id=student_id,
                title=Path(attachment.file_name or "简历").stem or "简历",
                target_job=str(parsed_resume.get("target_role") or "").strip() or None,
                target_industry=str(parsed_resume.get("target_industry") or "").strip() or None,
                target_city=str(parsed_resume.get("target_city") or "").strip() or None,
                scene_type="uploaded_resume",
                is_default=not default_exists,
                status="active",
                source_attachment_id=attachment.id,
                summary=str(parsed_resume.get("summary") or "").strip() or None,
            )
            self.db.add(resume)
            self.db.flush()

        version = (
            self.db.query(StudentResumeVersion)
            .filter(
                StudentResumeVersion.resume_id == resume.id,
                StudentResumeVersion.attachment_id == attachment.id,
                StudentResumeVersion.deleted.is_(False),
            )
            .order_by(StudentResumeVersion.is_active.desc(), StudentResumeVersion.id.desc())
            .first()
        )
        if not version:
            max_version_no = (
                self.db.query(func.max(StudentResumeVersion.version_no))
                .filter(StudentResumeVersion.resume_id == resume.id, StudentResumeVersion.deleted.is_(False))
                .scalar()
                or 0
            )
            version = StudentResumeVersion(
                resume_id=resume.id,
                version_no=int(max_version_no) + 1,
                attachment_id=attachment.id,
                parsed_json=parsed_resume,
                optimized_json={},
                score_snapshot={},
                change_summary="简历解析版本",
                is_active=resume.current_version_id is None,
            )
            self.db.add(version)
            self.db.flush()

        version.parsed_json = parsed_resume
        if not version.change_summary:
            version.change_summary = "简历解析版本"
        if resume.current_version_id is None:
            resume.current_version_id = version.id
            version.is_active = True
        if parsed_resume.get("target_role"):
            resume.target_job = str(parsed_resume.get("target_role") or "").strip()
        if parsed_resume.get("target_industry"):
            resume.target_industry = str(parsed_resume.get("target_industry") or "").strip()
        if parsed_resume.get("target_city"):
            resume.target_city = str(parsed_resume.get("target_city") or "").strip()
        if parsed_resume.get("summary"):
            resume.summary = str(parsed_resume.get("summary") or "").strip()

        self.db.commit()
        self.db.refresh(resume)
        self.db.refresh(version)
        return resume, version
