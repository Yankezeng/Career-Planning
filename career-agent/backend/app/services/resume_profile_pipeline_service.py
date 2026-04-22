from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException
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
    StudentSkill,
)
from app.services.resume_content_formatter import ResumeContentFormatter
from app.services.resume_parser_service import ResumeParserService
from app.services.resume_version_service import ResumeVersionService
from app.utils.upload_paths import resolve_upload_reference


class ResumeProfilePipelineService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.parser = ResumeParserService()

    def ingest_resume(self, student_id: int, attachment_id: int) -> dict[str, Any]:
        student = (
            self.db.query(Student)
            .options(
                joinedload(Student.skills),
                joinedload(Student.certificates),
                joinedload(Student.projects),
                joinedload(Student.internships),
                joinedload(Student.competitions),
                joinedload(Student.campus_experiences),
            )
            .filter(Student.id == student_id, Student.deleted.is_(False))
            .first()
        )
        if not student:
            raise HTTPException(status_code=404, detail="student not found")

        attachment = self._get_attachment(student_id, attachment_id)
        version_service = ResumeVersionService(self.db)
        parsed_resume = version_service.get_cached_parsed_resume(
            student_id=student_id,
            attachment_id=attachment.id,
        )
        if not parsed_resume:
            file_path = self._attachment_file_path(attachment)
            parsed_resume = self.parser.parse(attachment.file_name, str(file_path))
            if self.parser.is_low_quality(parsed_resume, attachment_chain=True):
                raise HTTPException(
                    status_code=422,
                    detail="resume parse quality is too low; please upload a clearer PDF/image or provide resume text and retry",
                )
            version_service.store_parsed_resume(
                student_id=student_id,
                attachment=attachment,
                parsed_resume=parsed_resume,
            )

        parsed_resume = dict(parsed_resume)
        parsed_resume["education_experience"] = ResumeContentFormatter.format_education(
            parsed_resume.get("education_experience")
        )
        sync_result = self._sync_resume(student, parsed_resume)
        self.db.commit()
        self.db.refresh(student)
        sync_summary = {
            "updated_fields": sync_result.get("updated_fields") or [],
            "skills_added": int((sync_result.get("merged_counts") or {}).get("skills") or 0),
            "certificates_added": int((sync_result.get("merged_counts") or {}).get("certificates") or 0),
            "projects_added": int((sync_result.get("merged_counts") or {}).get("projects") or 0),
            "internships_added": int((sync_result.get("merged_counts") or {}).get("internships") or 0),
        }
        return {
            "student_id": student.id,
            "attachment_id": attachment.id,
            "attachment_name": attachment.file_name,
            "parsed_resume": parsed_resume,
            "updated_fields": sync_result.get("updated_fields") or [],
            "merged_counts": sync_result.get("merged_counts") or {},
            "sync_summary": sync_summary,
            "profile": {"summary": student.bio or ""},
        }

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

    def _attachment_file_path(self, attachment) -> Path:
        file_path = resolve_upload_reference(
            upload_root=self.settings.upload_path,
            reference=getattr(attachment, "file_path", ""),
            must_exist=True,
        )
        if not file_path:
            raise HTTPException(status_code=404, detail="resume file not found, please re-upload and retry")
        return file_path

    def _sync_resume(self, student, parsed_resume):
        updated_fields: list[str] = []
        merged_counts: dict[str, int] = {}

        scalar_field_map = {
            "name": "name",
            "phone": "phone",
            "email": "email",
            "grade": "grade",
            "major": "major",
            "college": "college",
            "target_industry": "target_industry",
            "target_city": "target_city",
            "education_experience": "education_experience",
            "bio": "bio",
        }
        for model_field, parsed_field in scalar_field_map.items():
            current = getattr(student, model_field, "")
            new_value = self._clean_text(parsed_resume.get(parsed_field))
            if self._should_update_scalar(model_field, current, new_value):
                setattr(student, model_field, new_value)
                updated_fields.append(model_field)

        self._fill_if_empty(student, "bio", self._clean_text(parsed_resume.get("summary")))

        merged_counts["skills"] = self._merge_skills(student, parsed_resume.get("skills") or [])
        merged_counts["certificates"] = self._merge_certificates(student, parsed_resume.get("certificates") or [])
        merged_counts["projects"] = self._merge_projects(student, parsed_resume.get("projects") or [])
        merged_counts["internships"] = self._merge_internships(student, parsed_resume.get("internships") or [])
        merged_counts["competitions"] = self._merge_competitions(student, parsed_resume.get("competitions") or [])
        merged_counts["campus_experiences"] = self._merge_campus_experiences(
            student,
            parsed_resume.get("campus_experiences") or [],
        )

        return {"updated_fields": updated_fields, "merged_counts": merged_counts}

    def _merge_skills(self, student, skills):
        normalized = []
        for item in skills:
            if isinstance(item, dict):
                name = self._clean_text(item.get("name"))
                level = self._clean_text(item.get("level"))
                category = self._clean_text(item.get("category"))
                description = self._clean_text(item.get("description"))
            else:
                name = self._clean_text(item)
                level = ""
                category = ""
                description = ""
            if name:
                normalized.append((name, level, category, description))

        existing = {
            self._clean_text(row.name).lower(): row
            for row in student.skills
            if not getattr(row, "deleted", False)
        }
        created = 0
        for name, level, category, description in normalized:
            key = name.lower()
            row = existing.get(key)
            if row:
                self._fill_if_empty(row, "level", level)
                self._fill_if_empty(row, "category", category)
                self._fill_if_empty(row, "description", description)
                continue
            self.db.add(
                StudentSkill(
                    student_id=student.id,
                    name=name,
                    level=level or None,
                    category=category or None,
                    description=description or None,
                )
            )
            created += 1
            existing[key] = True
        return created

    def _merge_certificates(self, student, certificates):
        normalized = []
        for item in certificates:
            if isinstance(item, dict):
                name = self._clean_text(item.get("name"))
                issuer = self._clean_text(item.get("issuer"))
                issued_date = self._clean_text(item.get("issued_date"))
                score = self._clean_text(item.get("score"))
                description = self._clean_text(item.get("description"))
            else:
                name = self._clean_text(item)
                issuer = ""
                issued_date = ""
                score = ""
                description = ""
            if name:
                normalized.append((name, issuer, issued_date, score, description))

        existing = {
            self._clean_text(row.name).lower(): row
            for row in student.certificates
            if not getattr(row, "deleted", False)
        }
        created = 0
        for name, issuer, issued_date, score, description in normalized:
            key = name.lower()
            row = existing.get(key)
            if row:
                self._fill_if_empty(row, "issuer", issuer)
                self._fill_if_empty(row, "issued_date", issued_date)
                self._fill_if_empty(row, "score", score)
                self._fill_if_empty(row, "description", description)
                continue
            self.db.add(
                StudentCertificate(
                    student_id=student.id,
                    name=name,
                    issuer=issuer or None,
                    issued_date=issued_date or None,
                    score=score or None,
                    description=description or None,
                )
            )
            created += 1
            existing[key] = True
        return created

    def _merge_projects(self, student, projects):
        existing = {
            self._clean_text(row.name).lower(): row
            for row in student.projects
            if not getattr(row, "deleted", False)
        }
        created = 0
        for item in projects:
            if not isinstance(item, dict):
                continue
            name = self._clean_text(item.get("name"))
            if not name:
                continue
            key = name.lower()
            row = existing.get(key)
            technologies = item.get("technologies") if isinstance(item.get("technologies"), list) else []
            if row:
                self._fill_if_empty(row, "role", self._clean_text(item.get("role")))
                self._fill_if_empty(row, "description", self._clean_text(item.get("description")))
                if not row.technologies and technologies:
                    row.technologies = technologies
                self._fill_if_empty(row, "outcome", self._clean_text(item.get("outcome")))
                self._fill_if_empty(row, "start_date", self._clean_text(item.get("start_date")))
                self._fill_if_empty(row, "end_date", self._clean_text(item.get("end_date")))
                continue
            self.db.add(
                StudentProject(
                    student_id=student.id,
                    name=name,
                    role=self._clean_text(item.get("role")) or None,
                    description=self._clean_text(item.get("description")) or None,
                    technologies=technologies or [],
                    outcome=self._clean_text(item.get("outcome")) or None,
                    start_date=self._clean_text(item.get("start_date")) or None,
                    end_date=self._clean_text(item.get("end_date")) or None,
                    relevance_score=float(item.get("relevance_score") or 75),
                )
            )
            created += 1
            existing[key] = True
        return created

    def _merge_internships(self, student, internships):
        existing = {
            f"{self._clean_text(row.company).lower()}::{self._clean_text(row.position).lower()}": row
            for row in student.internships
            if not getattr(row, "deleted", False)
        }
        created = 0
        for item in internships:
            if not isinstance(item, dict):
                continue
            company = self._clean_text(item.get("company"))
            position = self._clean_text(item.get("position"))
            if not company or not position:
                continue
            key = f"{company.lower()}::{position.lower()}"
            row = existing.get(key)
            skills = item.get("skills") if isinstance(item.get("skills"), list) else []
            if row:
                self._fill_if_empty(row, "description", self._clean_text(item.get("description")))
                if not row.skills and skills:
                    row.skills = skills
                self._fill_if_empty(row, "start_date", self._clean_text(item.get("start_date")))
                self._fill_if_empty(row, "end_date", self._clean_text(item.get("end_date")))
                continue
            self.db.add(
                StudentInternship(
                    student_id=student.id,
                    company=company,
                    position=position,
                    description=self._clean_text(item.get("description")) or None,
                    skills=skills or [],
                    start_date=self._clean_text(item.get("start_date")) or None,
                    end_date=self._clean_text(item.get("end_date")) or None,
                    relevance_score=float(item.get("relevance_score") or 75),
                )
            )
            created += 1
            existing[key] = True
        return created

    def _merge_competitions(self, student, competitions):
        existing = {
            self._clean_text(row.name).lower(): row
            for row in student.competitions
            if not getattr(row, "deleted", False)
        }
        created = 0
        for item in competitions:
            if isinstance(item, dict):
                name = self._clean_text(item.get("name"))
                award = self._clean_text(item.get("award"))
                level = self._clean_text(item.get("level"))
                description = self._clean_text(item.get("description"))
            else:
                name = self._clean_text(item)
                award = ""
                level = ""
                description = ""
            if not name:
                continue
            key = name.lower()
            row = existing.get(key)
            if row:
                self._fill_if_empty(row, "award", award)
                self._fill_if_empty(row, "level", level)
                self._fill_if_empty(row, "description", description)
                continue
            self.db.add(
                StudentCompetition(
                    student_id=student.id,
                    name=name,
                    award=award or None,
                    level=level or None,
                    description=description or None,
                )
            )
            created += 1
            existing[key] = True
        return created

    def _merge_campus_experiences(self, student, experiences):
        existing = {
            self._clean_text(row.title).lower(): row
            for row in student.campus_experiences
            if not getattr(row, "deleted", False)
        }
        created = 0
        for item in experiences:
            if not isinstance(item, dict):
                continue
            title = self._clean_text(item.get("title"))
            if not title:
                continue
            key = title.lower()
            row = existing.get(key)
            if row:
                self._fill_if_empty(row, "role", self._clean_text(item.get("role")))
                self._fill_if_empty(row, "description", self._clean_text(item.get("description")))
                self._fill_if_empty(row, "duration", self._clean_text(item.get("duration")))
                continue
            self.db.add(
                StudentCampusExperience(
                    student_id=student.id,
                    title=title,
                    role=self._clean_text(item.get("role")) or None,
                    description=self._clean_text(item.get("description")) or None,
                    duration=self._clean_text(item.get("duration")) or None,
                )
            )
            created += 1
            existing[key] = True
        return created

    @staticmethod
    def _clean_text(value):
        text = str(value or "").strip()
        return text if text else ""

    @staticmethod
    def _should_update_scalar(field_name, current, new_value):
        new_text = str(new_value or "").strip()
        if not new_text:
            return False
        current_text = str(current or "").strip()
        if not current_text:
            return True
        if field_name in {"education_experience", "bio"} and len(new_text) > len(current_text):
            return True
        if field_name in {"phone", "email", "target_industry", "target_city"} and current_text != new_text:
            return True
        return False

    @staticmethod
    def _fill_if_empty(model, field_name, value):
        value_text = str(value or "").strip()
        if not value_text:
            return
        if not str(getattr(model, field_name, "") or "").strip():
            setattr(model, field_name, value_text)
