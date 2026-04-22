from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models.student import (
    Student,
    StudentAttachment,
    StudentCampusExperience,
    StudentCertificate,
    StudentCompetition,
    StudentInternship,
    StudentProject,
    StudentResume,
    StudentResumeVersion,
    StudentSkill,
)
from app.services.resume_delivery_service import ResumeDeliveryService
from app.services.resume_optimizer_service import ResumeOptimizerService
from app.services.resume_parser_service import ResumeParserService
from app.services.resume_version_service import ResumeVersionService
from app.utils.serializers import to_dict
from app.utils.upload_paths import resolve_upload_reference


class StudentService:
    resource_map = {
        "skills": StudentSkill,
        "certificates": StudentCertificate,
        "projects": StudentProject,
        "internships": StudentInternship,
        "competitions": StudentCompetition,
        "campus-experiences": StudentCampusExperience,
        "attachments": StudentAttachment,
    }

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.resume_parser = ResumeParserService()

    def get_student_by_user_id(self, user_id: int) -> Student:
        student = self.db.query(Student).filter(Student.user_id == user_id, Student.deleted.is_(False)).first()
        if not student:
            raise HTTPException(status_code=404, detail="student not found")
        return student

    def get_student(self, student_id: int) -> Student:
        student = self.db.query(Student).filter(Student.id == student_id, Student.deleted.is_(False)).first()
        if not student:
            raise HTTPException(status_code=404, detail="student not found")
        return student

    def get_me(self, user_id: int):
        return to_dict(self.get_student_by_user_id(user_id))

    def update_me(self, user_id: int, payload: dict):
        student = self.get_student_by_user_id(user_id)
        for key, value in payload.items():
            setattr(student, key, value)
        self.db.commit()
        self.db.refresh(student)
        return to_dict(student)

    def list_resource(self, student_id: int, resource: str):
        model = self.resource_map[resource]
        items = self.db.query(model).filter(model.student_id == student_id, model.deleted.is_(False)).all()
        return [to_dict(item) for item in items]

    def create_resource(self, student_id: int, resource: str, payload: dict):
        model = self.resource_map[resource]
        item = model(student_id=student_id, **payload)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return to_dict(item)

    def update_resource(self, student_id: int, resource: str, item_id: int, payload: dict):
        model = self.resource_map[resource]
        item = (
            self.db.query(model)
            .filter(model.id == item_id, model.student_id == student_id, model.deleted.is_(False))
            .first()
        )
        if not item:
            raise HTTPException(status_code=404, detail="record not found")
        for key, value in payload.items():
            setattr(item, key, value)
        self.db.commit()
        self.db.refresh(item)
        return to_dict(item)

    def delete_resource(self, student_id: int, resource: str, item_id: int):
        model = self.resource_map[resource]
        item = (
            self.db.query(model)
            .filter(model.id == item_id, model.student_id == student_id, model.deleted.is_(False))
            .first()
        )
        if not item:
            raise HTTPException(status_code=404, detail="record not found")
        item.deleted = True
        self.db.commit()

    def upload_attachment(self, student_id: int, file: UploadFile, description: str | None = None):
        ext = Path(file.filename or "").suffix
        file_name = f"{uuid4().hex}{ext}"
        save_path = self.settings.upload_path / file_name
        with save_path.open("wb") as output:
            output.write(file.file.read())
        attachment = StudentAttachment(
            student_id=student_id,
            file_name=file.filename or file_name,
            file_path=f"/uploads/{file_name}",
            file_type=ext.replace(".", ""),
            description=description,
        )
        self.db.add(attachment)
        self.db.commit()
        self.db.refresh(attachment)
        return to_dict(attachment)

    def parse_resume(self, attachment_id: int, student_id: int):
        attachment = (
            self.db.query(StudentAttachment)
            .filter(
                StudentAttachment.id == attachment_id,
                StudentAttachment.student_id == student_id,
                StudentAttachment.deleted.is_(False),
            )
            .first()
        )
        if not attachment:
            raise HTTPException(status_code=404, detail="attachment not found")
        file_path = resolve_upload_reference(
            upload_root=self.settings.upload_path,
            reference=attachment.file_path,
            must_exist=True,
        )
        if not file_path:
            raise HTTPException(status_code=404, detail="resume file not found, please re-upload and retry")

        parsed = self.resume_parser.parse(attachment.file_name, str(file_path))
        if self.resume_parser.is_low_quality(parsed, attachment_chain=True):
            raise HTTPException(
                status_code=422,
                detail="resume parse quality is too low; please upload a clearer PDF/image or provide resume text and retry",
            )
        ResumeVersionService(self.db).store_parsed_resume(
            student_id=student_id,
            attachment=attachment,
            parsed_resume=parsed,
        )
        return parsed

    def list_resumes(self, student_id: int) -> list[dict]:
        self._ensure_resume_seed_from_attachments(student_id)
        resumes = (
            self.db.query(StudentResume)
            .options(joinedload(StudentResume.current_version), joinedload(StudentResume.source_attachment))
            .filter(StudentResume.student_id == student_id, StudentResume.deleted.is_(False))
            .order_by(StudentResume.is_default.desc(), StudentResume.updated_at.desc(), StudentResume.id.desc())
            .all()
        )
        return [self._serialize_resume(item) for item in resumes]

    def create_resume(self, student_id: int, payload: dict) -> dict:
        attachment_id = payload.get("source_attachment_id") or payload.get("attachment_id")
        attachment = self._get_attachment(student_id, int(attachment_id)) if attachment_id else None

        is_default = bool(payload.get("is_default"))
        if is_default:
            self._clear_default_resume(student_id)

        title = str(payload.get("title") or (attachment.file_name if attachment else "新简历")).strip() or "新简历"
        resume = StudentResume(
            student_id=student_id,
            title=title,
            target_job=payload.get("target_job"),
            target_industry=payload.get("target_industry"),
            target_city=payload.get("target_city"),
            scene_type=payload.get("scene_type"),
            is_default=is_default,
            status=payload.get("status") or "active",
            source_attachment_id=attachment.id if attachment else None,
            summary=payload.get("summary"),
        )
        self.db.add(resume)
        self.db.flush()

        if attachment or payload.get("parsed_json") or payload.get("optimized_json"):
            version = StudentResumeVersion(
                resume_id=resume.id,
                version_no=1,
                attachment_id=attachment.id if attachment else None,
                parsed_json=payload.get("parsed_json") or {},
                optimized_json=payload.get("optimized_json") or {},
                score_snapshot=payload.get("score_snapshot") or {},
                change_summary=payload.get("change_summary") or "初始版本",
                is_active=True,
            )
            self.db.add(version)
            self.db.flush()
            resume.current_version_id = version.id

        self.db.commit()
        self.db.refresh(resume)
        return self._serialize_resume(resume)

    def update_resume(self, student_id: int, resume_id: int, payload: dict) -> dict:
        resume = self._get_resume(student_id, resume_id)
        if payload.get("is_default") is True:
            self._clear_default_resume(student_id)

        for field in ["title", "target_job", "target_industry", "target_city", "scene_type", "status", "summary", "is_default"]:
            if field in payload:
                setattr(resume, field, payload.get(field))

        if "current_version_id" in payload and payload.get("current_version_id"):
            version = self._get_resume_version(resume.id, int(payload["current_version_id"]))
            resume.current_version_id = version.id

        self.db.commit()
        self.db.refresh(resume)
        return self._serialize_resume(resume)

    def delete_resume(self, student_id: int, resume_id: int) -> None:
        resume = self._get_resume(student_id, resume_id)
        resume.deleted = True
        versions = (
            self.db.query(StudentResumeVersion)
            .filter(StudentResumeVersion.resume_id == resume.id, StudentResumeVersion.deleted.is_(False))
            .all()
        )
        for item in versions:
            item.deleted = True

        if resume.is_default:
            fallback = (
                self.db.query(StudentResume)
                .filter(
                    StudentResume.student_id == student_id,
                    StudentResume.deleted.is_(False),
                    StudentResume.id != resume.id,
                )
                .order_by(StudentResume.updated_at.desc(), StudentResume.id.desc())
                .first()
            )
            if fallback:
                fallback.is_default = True

        self.db.commit()

    def list_resume_versions(self, student_id: int, resume_id: int) -> list[dict]:
        self._get_resume(student_id, resume_id)
        versions = (
            self.db.query(StudentResumeVersion)
            .options(joinedload(StudentResumeVersion.attachment))
            .filter(StudentResumeVersion.resume_id == resume_id, StudentResumeVersion.deleted.is_(False))
            .order_by(StudentResumeVersion.version_no.desc(), StudentResumeVersion.id.desc())
            .all()
        )
        return [self._serialize_resume_version(item) for item in versions]

    def create_resume_version(self, student_id: int, resume_id: int, payload: dict) -> dict:
        resume = self._get_resume(student_id, resume_id)
        attachment_id = payload.get("attachment_id")
        attachment = self._get_attachment(student_id, int(attachment_id)) if attachment_id else None

        max_version_no = (
            self.db.query(func.max(StudentResumeVersion.version_no))
            .filter(StudentResumeVersion.resume_id == resume.id, StudentResumeVersion.deleted.is_(False))
            .scalar()
            or 0
        )
        self.db.query(StudentResumeVersion).filter(
            StudentResumeVersion.resume_id == resume.id,
            StudentResumeVersion.deleted.is_(False),
        ).update({"is_active": False})

        version = StudentResumeVersion(
            resume_id=resume.id,
            version_no=int(max_version_no) + 1,
            attachment_id=attachment.id if attachment else None,
            parsed_json=payload.get("parsed_json") or {},
            optimized_json=payload.get("optimized_json") or {},
            score_snapshot=payload.get("score_snapshot") or {},
            change_summary=payload.get("change_summary") or "手动新建版本",
            is_active=True,
        )
        self.db.add(version)
        self.db.flush()

        resume.current_version_id = version.id
        resume.status = payload.get("resume_status") or resume.status
        self.db.commit()
        self.db.refresh(version)
        self.db.refresh(resume)
        return {
            "resume": self._serialize_resume(resume),
            "version": self._serialize_resume_version(version),
        }

    def clone_resume(self, student_id: int, resume_id: int, payload: dict | None = None) -> dict:
        source = self._get_resume(student_id, resume_id)
        payload = payload or {}

        cloned = StudentResume(
            student_id=student_id,
            title=str(payload.get("title") or f"{source.title}-副本").strip() or f"{source.title}-副本",
            target_job=source.target_job,
            target_industry=source.target_industry,
            target_city=source.target_city,
            scene_type=source.scene_type,
            is_default=False,
            status="active",
            source_attachment_id=source.source_attachment_id,
            summary=source.summary,
        )
        self.db.add(cloned)
        self.db.flush()

        source_versions = (
            self.db.query(StudentResumeVersion)
            .filter(StudentResumeVersion.resume_id == source.id, StudentResumeVersion.deleted.is_(False))
            .order_by(StudentResumeVersion.version_no.asc(), StudentResumeVersion.id.asc())
            .all()
        )

        current_source_version_id = source.current_version_id
        current_new_version_id = None
        for item in source_versions:
            version = StudentResumeVersion(
                resume_id=cloned.id,
                version_no=item.version_no,
                attachment_id=item.attachment_id,
                parsed_json=item.parsed_json or {},
                optimized_json=item.optimized_json or {},
                score_snapshot=item.score_snapshot or {},
                change_summary=item.change_summary or "克隆版本",
                is_active=False,
            )
            self.db.add(version)
            self.db.flush()
            if item.id == current_source_version_id:
                current_new_version_id = version.id

        if current_new_version_id:
            cloned.current_version_id = current_new_version_id
            self.db.query(StudentResumeVersion).filter(StudentResumeVersion.id == current_new_version_id).update(
                {"is_active": True}
            )

        self.db.commit()
        self.db.refresh(cloned)
        return self._serialize_resume(cloned)

    def set_default_resume(self, student_id: int, resume_id: int) -> dict:
        resume = self._get_resume(student_id, resume_id)
        self._clear_default_resume(student_id)
        resume.is_default = True
        self.db.commit()
        self.db.refresh(resume)
        return self._serialize_resume(resume)

    def create_resume_from_attachment(self, student_id: int, attachment_id: int, payload: dict | None = None) -> dict:
        payload = payload or {}
        attachment = self._get_attachment(student_id, attachment_id)
        default_exists = (
            self.db.query(StudentResume)
            .filter(StudentResume.student_id == student_id, StudentResume.deleted.is_(False), StudentResume.is_default.is_(True))
            .first()
            is not None
        )

        title = str(payload.get("title") or self._title_from_file(attachment.file_name)).strip() or "简历"
        resume = StudentResume(
            student_id=student_id,
            title=title,
            target_job=payload.get("target_job"),
            target_industry=payload.get("target_industry"),
            target_city=payload.get("target_city"),
            scene_type=payload.get("scene_type"),
            is_default=not default_exists,
            status="active",
            source_attachment_id=attachment.id,
            summary=payload.get("summary"),
        )
        self.db.add(resume)
        self.db.flush()

        version = StudentResumeVersion(
            resume_id=resume.id,
            version_no=1,
            attachment_id=attachment.id,
            parsed_json=payload.get("parsed_json") or {},
            optimized_json=payload.get("optimized_json") or {},
            score_snapshot=payload.get("score_snapshot") or {},
            change_summary=payload.get("change_summary") or "从附件创建",
            is_active=True,
        )
        self.db.add(version)
        self.db.flush()

        resume.current_version_id = version.id
        self.db.commit()
        self.db.refresh(resume)
        return self._serialize_resume(resume)

    def optimize_resume_by_resume(self, student_id: int, resume_id: int, payload: dict | None = None) -> dict:
        payload = payload or {}
        resume = self._get_resume(student_id, resume_id)
        version = self._resolve_version_from_payload(resume, payload)
        attachment_id = version.attachment_id if version else resume.source_attachment_id
        if not attachment_id:
            raise HTTPException(status_code=400, detail="resume attachment not found")

        optimization_options = {
            "resume_id": resume.id,
            "resume_version_id": version.id if version else None,
            "target_role": payload.get("target_role") or resume.target_job,
            "target_job_id": payload.get("target_job_id"),
            "job_description": payload.get("job_description"),
        }
        optimization = ResumeOptimizerService(self.db).optimize_resume(
            student_id,
            int(attachment_id),
            options=optimization_options,
        )
        max_version_no = (
            self.db.query(func.max(StudentResumeVersion.version_no))
            .filter(StudentResumeVersion.resume_id == resume.id, StudentResumeVersion.deleted.is_(False))
            .scalar()
            or 0
        )

        self.db.query(StudentResumeVersion).filter(
            StudentResumeVersion.resume_id == resume.id,
            StudentResumeVersion.deleted.is_(False),
        ).update({"is_active": False})

        new_version = StudentResumeVersion(
            resume_id=resume.id,
            version_no=int(max_version_no) + 1,
            attachment_id=int(attachment_id),
            parsed_json=optimization.get("parsed_resume") or {},
            optimized_json=optimization,
            score_snapshot={
                "resume_score": optimization.get("resume_score") or 0,
                "keyword_match_score": optimization.get("keyword_match_score") or 0,
                "content_richness_score": optimization.get("content_richness_score") or 0,
                "project_evidence_score": optimization.get("project_evidence_score") or 0,
            },
            change_summary=payload.get("change_summary") or "优化生成新版本",
            is_active=True,
        )
        self.db.add(new_version)
        self.db.flush()

        resume.current_version_id = new_version.id
        resume.summary = optimization.get("optimized_summary") or resume.summary
        if optimization.get("target_role"):
            resume.target_job = optimization.get("target_role")

        self.db.commit()
        self.db.refresh(resume)
        self.db.refresh(new_version)
        return {
            "resume": self._serialize_resume(resume),
            "version": self._serialize_resume_version(new_version),
            "optimization": optimization,
        }

    def deliver_resume_by_resume(self, student_id: int, resume_id: int, payload: dict) -> dict:
        resume = self._get_resume(student_id, resume_id)
        version = self._resolve_version_from_payload(resume, payload)
        attachment_id = version.attachment_id if version else resume.source_attachment_id
        if not attachment_id:
            raise HTTPException(status_code=400, detail="resume attachment not found")

        delivery_payload = {
            **payload,
            "attachment_id": int(attachment_id),
            "resume_id": resume.id,
            "resume_version_id": version.id if version else resume.current_version_id,
        }
        return ResumeDeliveryService(self.db).create_delivery(student_id, delivery_payload)

    def _resolve_version_from_payload(self, resume: StudentResume, payload: dict) -> StudentResumeVersion | None:
        resume_version_id = payload.get("resume_version_id") or resume.current_version_id
        if not resume_version_id:
            return None
        return self._get_resume_version(resume.id, int(resume_version_id))

    def _get_resume(self, student_id: int, resume_id: int) -> StudentResume:
        resume = (
            self.db.query(StudentResume)
            .options(joinedload(StudentResume.current_version), joinedload(StudentResume.source_attachment))
            .filter(
                StudentResume.id == resume_id,
                StudentResume.student_id == student_id,
                StudentResume.deleted.is_(False),
            )
            .first()
        )
        if not resume:
            raise HTTPException(status_code=404, detail="resume not found")
        return resume

    def _get_resume_version(self, resume_id: int, version_id: int) -> StudentResumeVersion:
        version = (
            self.db.query(StudentResumeVersion)
            .options(joinedload(StudentResumeVersion.attachment))
            .filter(
                StudentResumeVersion.id == version_id,
                StudentResumeVersion.resume_id == resume_id,
                StudentResumeVersion.deleted.is_(False),
            )
            .first()
        )
        if not version:
            raise HTTPException(status_code=404, detail="resume version not found")
        return version

    def _get_attachment(self, student_id: int, attachment_id: int) -> StudentAttachment:
        attachment = (
            self.db.query(StudentAttachment)
            .filter(
                StudentAttachment.id == attachment_id,
                StudentAttachment.student_id == student_id,
                StudentAttachment.deleted.is_(False),
            )
            .first()
        )
        if not attachment:
            raise HTTPException(status_code=404, detail="attachment not found")
        return attachment

    def _clear_default_resume(self, student_id: int) -> None:
        self.db.query(StudentResume).filter(
            StudentResume.student_id == student_id,
            StudentResume.deleted.is_(False),
            StudentResume.is_default.is_(True),
        ).update({"is_default": False})

    def _ensure_resume_seed_from_attachments(self, student_id: int) -> None:
        has_resume = (
            self.db.query(StudentResume)
            .filter(StudentResume.student_id == student_id, StudentResume.deleted.is_(False))
            .first()
            is not None
        )
        if has_resume:
            return

        attachments = (
            self.db.query(StudentAttachment)
            .filter(StudentAttachment.student_id == student_id, StudentAttachment.deleted.is_(False))
            .order_by(StudentAttachment.created_at.asc(), StudentAttachment.id.asc())
            .all()
        )
        if not attachments:
            return

        for index, attachment in enumerate(attachments, start=1):
            resume = StudentResume(
                student_id=student_id,
                title=self._title_from_file(attachment.file_name) or f"简历{index}",
                is_default=index == 1,
                status="active",
                source_attachment_id=attachment.id,
            )
            self.db.add(resume)
            self.db.flush()

            version = StudentResumeVersion(
                resume_id=resume.id,
                version_no=1,
                attachment_id=attachment.id,
                parsed_json={},
                optimized_json={},
                score_snapshot={},
                change_summary="历史附件自动迁移",
                is_active=True,
            )
            self.db.add(version)
            self.db.flush()
            resume.current_version_id = version.id

        self.db.commit()

    def _serialize_resume(self, resume: StudentResume) -> dict:
        current_version = resume.current_version
        source_attachment = resume.source_attachment
        return {
            "id": resume.id,
            "student_id": resume.student_id,
            "title": resume.title,
            "target_job": resume.target_job,
            "target_industry": resume.target_industry,
            "target_city": resume.target_city,
            "scene_type": resume.scene_type,
            "is_default": bool(resume.is_default),
            "status": resume.status,
            "source_attachment_id": resume.source_attachment_id,
            "current_version_id": resume.current_version_id,
            "summary": resume.summary,
            "created_at": resume.created_at.isoformat() if resume.created_at else "",
            "updated_at": resume.updated_at.isoformat() if resume.updated_at else "",
            "current_version": self._serialize_resume_version(current_version) if current_version else None,
            "source_attachment": {
                "id": source_attachment.id,
                "file_name": source_attachment.file_name,
                "file_type": source_attachment.file_type,
                "file_path": source_attachment.file_path,
            }
            if source_attachment
            else None,
        }

    def _serialize_resume_version(self, version: StudentResumeVersion | None) -> dict | None:
        if not version:
            return None
        attachment = version.attachment
        return {
            "id": version.id,
            "resume_id": version.resume_id,
            "version_no": version.version_no,
            "attachment_id": version.attachment_id,
            "parsed_json": version.parsed_json or {},
            "optimized_json": version.optimized_json or {},
            "score_snapshot": version.score_snapshot or {},
            "change_summary": version.change_summary,
            "is_active": bool(version.is_active),
            "created_at": version.created_at.isoformat() if version.created_at else "",
            "attachment": {
                "id": attachment.id,
                "file_name": attachment.file_name,
                "file_type": attachment.file_type,
                "file_path": attachment.file_path,
            }
            if attachment
            else None,
        }

    @staticmethod
    def _title_from_file(file_name: str) -> str:
        text = str(file_name or "").strip()
        if not text:
            return ""
        path = Path(text)
        return path.stem or text
