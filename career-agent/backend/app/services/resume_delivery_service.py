from __future__ import annotations

import math
import re
import time
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models.auth import EnterpriseProfile, Role, User
from app.models.career import ResumeDelivery
from app.models.job import Job, JobMatchResult
from app.models.student import Student, StudentAttachment, StudentResume, StudentResumeVersion
from app.services.resume_parser_service import ResumeParserService
from app.services.vector_search_service import VectorSearchService
from app.utils.upload_paths import resolve_upload_reference


class ResumeDeliveryService:
    def __init__(self, db):
        self.db: Session = db
        self.settings = get_settings()
        self.resume_parser = ResumeParserService()
        self.vector_search = VectorSearchService()

    def list_targets(self, student_id: int, limit: int = 20):
        student = self._get_student(student_id)
        documents = self.vector_search.list_documents(limit=max(200, limit * 20))
        groups = self._build_company_groups(student, documents)
        return groups[: max(1, int(limit or 20))]

    def create_delivery(self, student_id: int, payload: dict):
        student = self._get_student(student_id)
        attachment_id = int(payload.get("attachment_id") or 0)
        if not attachment_id:
            raise HTTPException(status_code=400, detail="attachment_id is required")
        attachment = self._get_attachment(student_id, attachment_id)

        resume, resume_version = self._resolve_resume_binding(student_id, payload, attachment)
        target_job = self._resolve_target_job(payload.get("target_job_id"))
        should_resolve_document = bool(payload.get("knowledge_doc_id")) or not target_job
        document = (
            self._resolve_target_document(
                payload.get("knowledge_doc_id"),
                payload.get("company_name"),
                payload.get("target_job_name"),
            )
            if should_resolve_document
            else None
        )
        if target_job:
            document = self._merge_target_job_document(target_job, document or {}, payload)
        company_name = (
            self._clean_text(payload.get("company_name"))
            or self._clean_text(document.get("company_name") if isinstance(document, dict) else "")
            or ("平台岗位库" if target_job else "未知企业")
        )
        enterprise_profile = (
            self._ensure_platform_enterprise_profile()
            if target_job and company_name == "平台岗位库"
            else self._ensure_enterprise_profile(document or {}, company_name)
        )
        target_job_name = (
            self._clean_text(payload.get("target_job_name"))
            or self._clean_text(target_job.name if target_job else "")
            or self._clean_text(document.get("job_name") if isinstance(document, dict) else "")
            or ""
        )
        target_job_category = (
            self._clean_text(payload.get("target_job_category"))
            or self._clean_text(target_job.category if target_job else "")
            or self._clean_text(document.get("job_category") if isinstance(document, dict) else "")
            or ""
        )
        knowledge_doc_id = (
            self._clean_text(payload.get("knowledge_doc_id"))
            or self._clean_text(document.get("id") if isinstance(document, dict) else "")
            or self._clean_text(document.get("doc_id") if isinstance(document, dict) else "")
            or (f"job:{target_job.id}" if target_job else None)
            or None
        )

        raw_score = self._calculate_job_score(student, target_job) if target_job else float((document or {}).get("score") or 0)
        if raw_score <= 0 and not target_job:
            raw_score = self._calculate_document_score(student, document or {})
        match_score = round(max(0.0, min(100.0, raw_score)), 1)

        snapshot = self._build_delivery_snapshot(
            student,
            attachment,
            document or {},
            match_score,
            resume,
            resume_version,
            target_job=target_job,
        )
        delivery = ResumeDelivery(
            student_id=student.id,
            attachment_id=attachment.id,
            resume_id=resume.id if resume else None,
            resume_version_id=resume_version.id if resume_version else None,
            target_job_id=target_job.id if target_job else None,
            enterprise_profile_id=enterprise_profile.id,
            knowledge_doc_id=knowledge_doc_id,
            target_job_name=target_job_name or None,
            target_job_category=target_job_category or None,
            match_score=match_score,
            delivery_status="delivered",
            delivery_note=self._clean_text(payload.get("delivery_note")) or None,
            snapshot=snapshot,
        )
        self.db.add(delivery)
        self.db.commit()
        self.db.refresh(delivery)
        return self._serialize_delivery(delivery, include_student=False)

    def list_student_deliveries(self, student_id: int):
        self._get_student(student_id)
        rows = (
            self.db.query(ResumeDelivery)
            .options(
                joinedload(ResumeDelivery.enterprise_profile),
                joinedload(ResumeDelivery.attachment),
                joinedload(ResumeDelivery.resume),
                joinedload(ResumeDelivery.resume_version),
                joinedload(ResumeDelivery.job),
            )
            .filter(ResumeDelivery.student_id == student_id, ResumeDelivery.deleted.is_(False))
            .order_by(ResumeDelivery.id.desc())
            .all()
        )
        return [self._serialize_delivery(item, include_student=False) for item in rows]

    def list_enterprise_deliveries(self, user_id: int):
        user = self.db.query(User).filter(User.id == user_id, User.deleted.is_(False)).first()
        if not user:
            raise HTTPException(status_code=404, detail="user not found")

        query = self.db.query(ResumeDelivery).options(
            joinedload(ResumeDelivery.student).joinedload(Student.profiles),
            joinedload(ResumeDelivery.enterprise_profile),
            joinedload(ResumeDelivery.attachment),
            joinedload(ResumeDelivery.resume),
            joinedload(ResumeDelivery.resume_version),
            joinedload(ResumeDelivery.job),
        )
        if not (user.role and user.role.code == "admin"):
            profile = (
                self.db.query(EnterpriseProfile)
                .filter(EnterpriseProfile.user_id == user.id, EnterpriseProfile.deleted.is_(False))
                .first()
            )
            if not profile:
                raise HTTPException(status_code=404, detail="enterprise profile not found")
            query = query.filter(ResumeDelivery.enterprise_profile_id == profile.id)

        rows = query.filter(ResumeDelivery.deleted.is_(False)).order_by(ResumeDelivery.id.desc()).all()
        return [self._serialize_delivery(item, include_student=True) for item in rows]

    def get_enterprise_board(self, user_id: int):
        deliveries = self.list_enterprise_deliveries(user_id)
        total = len(deliveries)
        if not total:
            return {
                "total_deliveries": 0,
                "avg_match_score": 0.0,
                "stage_counts": {},
                "top_candidates": [],
            }

        avg_match = round(sum(float(item.get("match_score") or 0) for item in deliveries) / total, 1)
        stage_counts: dict[str, int] = {}
        for item in deliveries:
            stage = self._derive_pipeline_stage(
                item.get("match_score") or 0,
                bool(item.get("reviewed")),
                item.get("student") or {},
            )
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

        top_candidates = sorted(deliveries, key=lambda row: float(row.get("match_score") or 0), reverse=True)[:8]
        return {
            "total_deliveries": total,
            "avg_match_score": avg_match,
            "stage_counts": stage_counts,
            "top_candidates": top_candidates,
        }

    def get_enterprise_delivery(self, user_id: int, delivery_id: int):
        delivery = self._load_enterprise_delivery(user_id, delivery_id)
        return self._serialize_delivery(delivery, include_student=True)

    def get_enterprise_resume_analysis(self, user_id: int, delivery_id: int) -> dict[str, Any]:
        # Backward-compatible path for lightweight unit tests that instantiate via object.__new__
        # and inject a mocked legacy object.
        if getattr(self, "_legacy", None) is not None and not hasattr(self, "db"):
            delivery = self._legacy._load_enterprise_delivery(user_id, delivery_id)
            attachment = delivery.attachment
            if not attachment:
                raise HTTPException(status_code=404, detail="resume attachment is missing for this delivery")
            file_type = str(getattr(attachment, "file_type", "") or "").lower()
            if file_type not in self._legacy.resume_parser.supported_types:
                raise HTTPException(status_code=400, detail="unsupported attachment type for resume analysis")
            file_path = resolve_upload_reference(
                upload_root=self._legacy.settings.upload_path,
                reference=getattr(attachment, "file_path", "") or "",
                must_exist=True,
            )
            if not file_path:
                raise HTTPException(status_code=404, detail="resume file not found, please refresh and retry")
            parsed = self._legacy.resume_parser.parse(
                getattr(attachment, "file_name", "") or "resume_attachment",
                str(file_path),
            )
            if self._legacy.resume_parser.is_low_quality(parsed, attachment_chain=True):
                raise HTTPException(
                    status_code=422,
                    detail="resume parse quality is too low; please upload a clearer PDF/image or provide resume text and retry",
                )
            latest_profile = self._legacy._latest_profile(delivery.student)
            return {
                "basic": {
                    "name": parsed.get("name") or delivery.student.name,
                    "phone": parsed.get("phone") or delivery.student.phone,
                    "email": parsed.get("email") or delivery.student.email,
                    "grade": parsed.get("grade") or delivery.student.grade,
                    "major": parsed.get("major") or delivery.student.major,
                    "college": parsed.get("college") or delivery.student.college,
                    "target_role": parsed.get("target_role") or delivery.target_job_name,
                    "target_industry": parsed.get("target_industry") or "",
                    "target_city": parsed.get("target_city") or "",
                },
                "skills": parsed.get("skills") or [],
                "projects": parsed.get("projects") or [],
                "internships": parsed.get("internships") or [],
                "education": parsed.get("education_experience") or "",
                "summary": parsed.get("summary") or parsed.get("bio") or "",
                "match_score": float(delivery.match_score or 0),
                "profile_summary": (latest_profile.summary if latest_profile else "") or (delivery.snapshot or {}).get("profile_summary", ""),
            }

        delivery = self._load_enterprise_delivery(user_id, delivery_id)
        attachment = delivery.attachment
        if not attachment:
            raise HTTPException(status_code=404, detail="resume attachment is missing for this delivery")

        file_type = str(getattr(attachment, "file_type", "") or "").lower()
        if file_type not in self.resume_parser.supported_types:
            raise HTTPException(status_code=400, detail="unsupported attachment type for resume analysis")

        file_path = resolve_upload_reference(
            upload_root=self.settings.upload_path,
            reference=getattr(attachment, "file_path", "") or "",
            must_exist=True,
        )
        if not file_path:
            raise HTTPException(status_code=404, detail="resume file not found, please refresh and retry")

        parsed = self.resume_parser.parse(getattr(attachment, "file_name", "") or "resume_attachment", str(file_path))
        if self.resume_parser.is_low_quality(parsed, attachment_chain=True):
            raise HTTPException(
                status_code=422,
                detail="resume parse quality is too low; please upload a clearer PDF/image or provide resume text and retry",
            )
        latest_profile = self._latest_profile(delivery.student)

        return {
            "basic": {
                "name": parsed.get("name") or delivery.student.name,
                "phone": parsed.get("phone") or delivery.student.phone,
                "email": parsed.get("email") or delivery.student.email,
                "grade": parsed.get("grade") or delivery.student.grade,
                "major": parsed.get("major") or delivery.student.major,
                "college": parsed.get("college") or delivery.student.college,
                "target_role": parsed.get("target_role") or delivery.target_job_name,
                "target_industry": parsed.get("target_industry") or "",
                "target_city": parsed.get("target_city") or "",
            },
            "skills": parsed.get("skills") or [],
            "projects": parsed.get("projects") or [],
            "internships": parsed.get("internships") or [],
            "education": parsed.get("education_experience") or "",
            "summary": parsed.get("summary") or parsed.get("bio") or "",
            "match_score": float(delivery.match_score or 0),
            "profile_summary": (latest_profile.summary if latest_profile else "") or (delivery.snapshot or {}).get("profile_summary", ""),
        }

    def _load_enterprise_delivery(self, user_id: int, delivery_id: int):
        delivery = (
            self.db.query(ResumeDelivery)
            .options(
                joinedload(ResumeDelivery.student).joinedload(Student.profiles),
                joinedload(ResumeDelivery.enterprise_profile),
                joinedload(ResumeDelivery.attachment),
                joinedload(ResumeDelivery.resume),
                joinedload(ResumeDelivery.resume_version),
                joinedload(ResumeDelivery.job),
            )
            .filter(ResumeDelivery.id == delivery_id, ResumeDelivery.deleted.is_(False))
            .first()
        )
        if not delivery:
            raise HTTPException(status_code=404, detail="delivery not found")

        user = self.db.query(User).filter(User.id == user_id, User.deleted.is_(False)).first()
        if not user:
            raise HTTPException(status_code=404, detail="user not found")

        if user.role and user.role.code == "admin":
            return delivery

        profile = (
            self.db.query(EnterpriseProfile)
            .filter(EnterpriseProfile.user_id == user.id, EnterpriseProfile.deleted.is_(False))
            .first()
        )
        if not profile or delivery.enterprise_profile_id != profile.id:
            raise HTTPException(status_code=404, detail="delivery not found")
        return delivery

    def _resolve_target_job(self, target_job_id) -> Job | None:
        if not target_job_id:
            return None
        try:
            job_id = int(target_job_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="target_job_id must be an integer")
        job = (
            self.db.query(Job)
            .options(joinedload(Job.skills), joinedload(Job.certificates))
            .filter(Job.id == job_id, Job.deleted.is_(False))
            .first()
        )
        if not job:
            raise HTTPException(status_code=404, detail="target job not found")
        return job

    def _build_job_document(self, job: Job) -> dict[str, Any]:
        profile = job.job_profile if isinstance(job.job_profile, dict) else {}
        source_companies = [self._clean_text(item) for item in (profile.get("source_companies") or []) if self._clean_text(item)]
        company_name = self._clean_text(profile.get("company_name")) or (source_companies[0] if source_companies else "平台岗位库")
        return {
            "id": f"job:{job.id}",
            "job_id": job.id,
            "job_name": job.name,
            "job_category": job.category or profile.get("category") or "",
            "company_name": company_name,
            "industry": job.industry or profile.get("industry") or "",
            "description": job.description or profile.get("summary") or "",
            "skills": self._job_skill_names(job),
            "metadata": {
                "company_name": company_name,
                "industry": job.industry or profile.get("industry") or "",
                "core_skills": list(job.core_skill_tags or profile.get("core_skills") or []),
                "common_skills": list(job.common_skill_tags or profile.get("common_skills") or []),
            },
        }

    def _resolve_target_document(self, knowledge_doc_id, company_name, job_name):
        doc_id = self._clean_text(knowledge_doc_id)
        if doc_id:
            direct = self.vector_search.get_document_by_id(doc_id)
            if isinstance(direct, dict):
                return direct
        document_count = self.vector_search.count_documents()
        documents = self.vector_search.list_documents(limit=max(4000, min(50000, document_count or 0)))
        return self._find_document(documents, knowledge_doc_id, company_name, job_name)

    def _merge_target_job_document(self, target_job: Job, document: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        base_document = self._build_job_document(target_job)
        incoming = document if isinstance(document, dict) else {}
        base_metadata = base_document.get("metadata") if isinstance(base_document.get("metadata"), dict) else {}
        incoming_metadata = incoming.get("metadata") if isinstance(incoming.get("metadata"), dict) else {}
        merged = {
            **base_document,
            **incoming,
            "job_id": target_job.id,
            "job_name": self._clean_text(payload.get("target_job_name"))
            or self._clean_text(incoming.get("job_name"))
            or target_job.name,
            "job_category": self._clean_text(payload.get("target_job_category"))
            or self._clean_text(incoming.get("job_category"))
            or target_job.category
            or "",
            "company_name": self._clean_text(payload.get("company_name"))
            or self._clean_text(incoming.get("company_name"))
            or self._clean_text(incoming_metadata.get("company_name"))
            or self._clean_text(base_document.get("company_name"))
            or "平台岗位库",
            "metadata": {**base_metadata, **incoming_metadata},
        }
        return merged

    def _build_company_groups(self, student, documents):
        groups: dict[str, dict[str, Any]] = {}
        for document in documents or []:
            if not isinstance(document, dict):
                continue
            company = self._clean_text(document.get("company_name") or (document.get("metadata") or {}).get("company_name")) or "未知企业"
            score = self._calculate_document_score(student, document)
            group = groups.get(company)
            if not group:
                group = {
                    "company_name": company,
                    "match_score": score,
                    "knowledge_doc_id": self._clean_text(document.get("id") or document.get("doc_id")),
                    "target_job_name": self._clean_text(document.get("job_name")),
                    "target_job_category": self._clean_text(document.get("job_category")),
                    "sample_jobs": [],
                }
                groups[company] = group
            if score > float(group.get("match_score") or 0):
                group["match_score"] = score
                group["knowledge_doc_id"] = self._clean_text(document.get("id") or document.get("doc_id"))
                group["target_job_name"] = self._clean_text(document.get("job_name"))
                group["target_job_category"] = self._clean_text(document.get("job_category"))
            job_name = self._clean_text(document.get("job_name"))
            if job_name and job_name not in group["sample_jobs"]:
                group["sample_jobs"].append(job_name)
        rows = list(groups.values())
        rows.sort(key=lambda item: float(item.get("match_score") or 0), reverse=True)
        return rows

    def _calculate_document_score(self, student, document):
        if not isinstance(document, dict):
            return 0.0

        explicit_score = document.get("score")
        try:
            if explicit_score is not None:
                score = float(explicit_score)
                if score > 0:
                    return max(0.0, min(100.0, score))
        except (TypeError, ValueError):
            pass

        local_scores = self._get_local_job_scores(student.id)
        job_name = self._clean_text(document.get("job_name")).lower()
        if job_name and job_name in local_scores:
            return max(0.0, min(100.0, float(local_scores[job_name])))

        student_skills = {self._clean_text(item.name).lower() for item in (student.skills or []) if not item.deleted}
        target_industry = self._clean_text(student.target_industry).lower()
        target_city = self._clean_text(student.target_city).lower()

        skill_tags: list[str] = []
        metadata = document.get("metadata")
        if isinstance(metadata, dict):
            for key in ("core_skills", "common_skills", "skills", "skill_tags"):
                value = metadata.get(key)
                if isinstance(value, str):
                    skill_tags.extend([token.strip() for token in re.split(r"[，,、/\s]+", value) if token.strip()])
                elif isinstance(value, list):
                    skill_tags.extend([self._clean_text(item) for item in value if self._clean_text(item)])
        if not skill_tags and isinstance(document.get("content"), str):
            skill_tags = [token.strip() for token in re.split(r"[，,、/\s]+", str(document.get("content"))) if len(token.strip()) <= 20]

        skill_hits = len([item for item in skill_tags if item.lower() in student_skills])
        base = 45.0 + min(30.0, skill_hits * 5.0)

        industry = self._clean_text(document.get("industry") or (metadata or {}).get("industry")).lower()
        if target_industry and industry and target_industry in industry:
            base += 12.0
        address = self._clean_text((metadata or {}).get("address") if isinstance(metadata, dict) else "").lower()
        if target_city and address and target_city in address:
            base += 8.0
        return round(max(0.0, min(100.0, base)), 1)

    def _build_student_query(self, student):
        tokens = [
            self._clean_text(student.major),
            self._clean_text(student.college),
            self._clean_text(student.target_industry),
            self._clean_text(student.target_city),
        ]
        tokens.extend([self._clean_text(item.name) for item in (student.skills or []) if not item.deleted][:10])
        return " ".join([token for token in tokens if token])

    def _get_local_job_scores(self, student_id):
        rows = (
            self.db.query(JobMatchResult, Job)
            .join(Job, Job.id == JobMatchResult.job_id)
            .filter(JobMatchResult.student_id == student_id, JobMatchResult.deleted.is_(False), Job.deleted.is_(False))
            .all()
        )
        result: dict[str, float] = {}
        for match_row, job_row in rows:
            key = self._clean_text(job_row.name).lower()
            if key:
                result[key] = float(match_row.total_score or 0)
        return result

    def _calculate_job_score(self, student: Student, job: Job | None) -> float:
        if not job:
            return 0.0

        match_row = (
            self.db.query(JobMatchResult)
            .filter(
                JobMatchResult.student_id == student.id,
                JobMatchResult.job_id == job.id,
                JobMatchResult.deleted.is_(False),
            )
            .order_by(JobMatchResult.id.desc())
            .first()
        )
        if match_row:
            return max(0.0, min(100.0, float(match_row.total_score or 0)))

        student_skills = {self._clean_text(item.name).lower() for item in (student.skills or []) if not getattr(item, "deleted", False)}
        student_certs = {self._clean_text(item.name).lower() for item in (student.certificates or []) if not getattr(item, "deleted", False)}
        job_skills = {item.lower() for item in self._job_skill_names(job)}
        job_certs = {self._clean_text(item).lower() for item in (job.certificate_tags or []) if self._clean_text(item)}
        job_certs.update(
            self._clean_text(item.name).lower()
            for item in (job.certificates or [])
            if not getattr(item, "deleted", False) and self._clean_text(item.name)
        )

        score = 48.0
        if job_skills:
            skill_hits = len(student_skills.intersection(job_skills))
            score += min(32.0, (skill_hits / max(1, len(job_skills))) * 40.0)
        if job_certs:
            cert_hits = len(student_certs.intersection(job_certs))
            score += min(8.0, (cert_hits / max(1, len(job_certs))) * 10.0)
        if self._clean_text(student.target_industry).lower() and self._clean_text(job.industry).lower():
            if self._clean_text(student.target_industry).lower() in self._clean_text(job.industry).lower():
                score += 5.0
        if any(not getattr(item, "deleted", False) for item in (student.internships or [])):
            score += 5.0
        if any(not getattr(item, "deleted", False) for item in (student.projects or [])):
            score += 4.0
        return round(max(0.0, min(100.0, score)), 1)

    def _ensure_enterprise_profile(self, document, company_name):
        existing = (
            self.db.query(EnterpriseProfile)
            .filter(EnterpriseProfile.company_name == company_name, EnterpriseProfile.deleted.is_(False))
            .first()
        )
        if existing:
            if isinstance(document, dict):
                doc_id = self._clean_text(document.get("id") or document.get("doc_id"))
                if doc_id:
                    source_doc_ids = list(existing.source_doc_ids or [])
                    if doc_id not in source_doc_ids:
                        source_doc_ids.append(doc_id)
                        existing.source_doc_ids = source_doc_ids
                        self.db.commit()
                        self.db.refresh(existing)
            return existing

        role = self._ensure_enterprise_role()
        username = self._generate_enterprise_username(company_name)
        user = User(
            username=username,
            password_hash="!",
            real_name=company_name,
            role_id=role.id,
            is_active=True,
        )
        self.db.add(user)
        self.db.flush()

        metadata = document.get("metadata") if isinstance(document, dict) and isinstance(document.get("metadata"), dict) else {}
        source_doc_id = self._clean_text(document.get("id") or document.get("doc_id")) if isinstance(document, dict) else ""
        profile = EnterpriseProfile(
            user_id=user.id,
            company_name=company_name,
            industry=self._clean_text(document.get("industry") if isinstance(document, dict) else "") or self._clean_text(metadata.get("industry")) or None,
            address=self._clean_text(metadata.get("address")) or None,
            company_type=self._clean_text(metadata.get("company_type")) or None,
            company_size=self._clean_text(metadata.get("company_size")) or None,
            description=self._clean_text(metadata.get("company_detail")) or None,
            source_doc_ids=[source_doc_id] if source_doc_id else [],
        )
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def _ensure_platform_enterprise_profile(self):
        company_name = "平台岗位库"
        existing = (
            self.db.query(EnterpriseProfile)
            .filter(EnterpriseProfile.company_name == company_name, EnterpriseProfile.deleted.is_(False))
            .first()
        )
        if existing:
            return existing

        profile = EnterpriseProfile(
            company_name=company_name,
            company_code="PLATFORM-JOB-BANK",
            industry="综合岗位库",
            company_type="平台内置",
            company_size="系统",
            description="系统内置数据库岗位画像与简历投递归属档案。",
            source_doc_ids=[],
        )
        self.db.add(profile)
        self.db.flush()
        return profile

    def _ensure_enterprise_role(self):
        row = self.db.query(Role).filter(Role.code == "enterprise", Role.deleted.is_(False)).first()
        if row:
            return row
        row = Role(name="企业", code="enterprise", description="Auto-created enterprise role")
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def _generate_enterprise_username(self, company_name):
        base = re.sub(r"[^a-z0-9]+", "", self._clean_text(company_name).lower())
        if not base:
            base = "enterprise"
        base = base[:18]
        candidate = f"{base}{int(time.time() * 1000) % 100000:05d}"
        while self.db.query(User).filter(User.username == candidate).first():
            candidate = f"{base}{int(time.time() * 1000) % 100000:05d}"
        return candidate

    def _build_delivery_snapshot(self, student, attachment, document, match_score, resume, resume_version, target_job: Job | None = None):
        latest_profile = self._latest_profile(student)
        profile_summary = self._clean_text(getattr(latest_profile, "summary", "")) if latest_profile else ""
        job_profile = target_job.job_profile if target_job and isinstance(target_job.job_profile, dict) else {}
        snapshot = {
            "student_name": student.name,
            "student_major": student.major,
            "student_college": student.college,
            "target_industry": student.target_industry,
            "target_city": student.target_city,
            "attachment": {
                "id": attachment.id,
                "file_name": attachment.file_name,
                "file_type": attachment.file_type,
            },
            "target_job_name": self._clean_text((document or {}).get("job_name")),
            "target_job_category": self._clean_text((document or {}).get("job_category")),
            "company_name": self._clean_text((document or {}).get("company_name")),
            "match_score": float(match_score or 0),
            "profile_summary": profile_summary,
            "resume_id": resume.id if resume else None,
            "resume_version_id": resume_version.id if resume_version else None,
        }
        if target_job:
            snapshot["job"] = self._serialize_job_snapshot(target_job)
            snapshot["job_profile"] = {
                "summary": job_profile.get("summary") or target_job.description or "",
                "portrait_dimensions": job_profile.get("portrait_dimensions") or [],
                "vertical_path": job_profile.get("vertical_path") or [],
                "transfer_paths": job_profile.get("transfer_paths") or [],
            }
        return snapshot

    def _serialize_delivery(self, delivery, include_student):
        student_payload = {}
        if include_student and delivery.student:
            latest_profile = self._latest_profile(delivery.student)
            student_payload = {
                "id": delivery.student.id,
                "name": delivery.student.name,
                "grade": delivery.student.grade,
                "major": delivery.student.major,
                "college": delivery.student.college,
                "profile_summary": self._clean_text(getattr(latest_profile, "summary", "")) if latest_profile else "",
            }

        return {
            "id": delivery.id,
            "student_id": delivery.student_id,
            "attachment_id": delivery.attachment_id,
            "resume_id": delivery.resume_id,
            "resume_version_id": delivery.resume_version_id,
            "target_job_id": delivery.target_job_id,
            "enterprise_profile_id": delivery.enterprise_profile_id,
            "knowledge_doc_id": delivery.knowledge_doc_id,
            "target_job_name": delivery.target_job_name,
            "target_job_category": delivery.target_job_category,
            "match_score": float(delivery.match_score or 0),
            "delivery_status": delivery.delivery_status,
            "delivery_note": delivery.delivery_note,
            "enterprise_feedback": delivery.enterprise_feedback,
            "snapshot": delivery.snapshot or {},
            "stage": self._derive_pipeline_stage(
                delivery.match_score or 0,
                bool(delivery.enterprise_feedback),
                student_payload,
            ),
            "reviewed": bool(delivery.enterprise_feedback),
            "created_at": delivery.created_at.isoformat() if delivery.created_at else "",
            "updated_at": delivery.updated_at.isoformat() if delivery.updated_at else "",
            "enterprise": {
                "id": delivery.enterprise_profile.id,
                "company_name": delivery.enterprise_profile.company_name,
                "industry": delivery.enterprise_profile.industry,
            }
            if delivery.enterprise_profile
            else None,
            "attachment": {
                "id": delivery.attachment.id,
                "file_name": delivery.attachment.file_name,
                "file_type": delivery.attachment.file_type,
                "file_path": delivery.attachment.file_path,
            }
            if delivery.attachment
            else None,
            "resume": {
                "id": delivery.resume.id,
                "title": delivery.resume.title,
            }
            if delivery.resume
            else None,
            "resume_version": {
                "id": delivery.resume_version.id,
                "version_no": delivery.resume_version.version_no,
            }
            if delivery.resume_version
            else None,
            "job": self._serialize_delivery_job(delivery),
            "student": student_payload if include_student else None,
        }

    def _serialize_delivery_job(self, delivery) -> dict[str, Any] | None:
        if delivery.job:
            return self._serialize_job_snapshot(delivery.job)
        snapshot_job = (delivery.snapshot or {}).get("job")
        return snapshot_job if isinstance(snapshot_job, dict) else None

    def _serialize_job_snapshot(self, job: Job) -> dict[str, Any]:
        profile = job.job_profile if isinstance(job.job_profile, dict) else {}
        return {
            "id": job.id,
            "name": job.name,
            "category": job.category or profile.get("category"),
            "industry": job.industry or profile.get("industry"),
            "profile_summary": profile.get("summary") or job.description or "",
        }

    @staticmethod
    def _derive_pipeline_stage(match_score, reviewed, student_payload):
        score = float(match_score or 0)
        if reviewed:
            return "reviewed"
        if score >= 85:
            return "high_match"
        if score >= 70:
            return "pending_review"
        return "low_match"

    def _get_student(self, student_id):
        student = (
            self.db.query(Student)
            .options(
                joinedload(Student.skills),
                joinedload(Student.certificates),
                joinedload(Student.projects),
                joinedload(Student.internships),
                joinedload(Student.profiles),
            )
            .filter(Student.id == student_id, Student.deleted.is_(False))
            .first()
        )
        if not student:
            raise HTTPException(status_code=404, detail="student not found")
        return student

    def _get_attachment(self, student_id, attachment_id):
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

    def _resolve_resume_binding(self, student_id, payload, attachment):
        resume_id = int(payload.get("resume_id") or 0)
        resume_version_id = int(payload.get("resume_version_id") or 0)

        resume = None
        resume_version = None
        if resume_id:
            resume = (
                self.db.query(StudentResume)
                .filter(
                    StudentResume.id == resume_id,
                    StudentResume.student_id == student_id,
                    StudentResume.deleted.is_(False),
                )
                .first()
            )
        if resume_version_id:
            resume_version = (
                self.db.query(StudentResumeVersion)
                .filter(
                    StudentResumeVersion.id == resume_version_id,
                    StudentResumeVersion.deleted.is_(False),
                )
                .first()
            )
            if resume_version and not resume:
                resume = (
                    self.db.query(StudentResume)
                    .filter(
                        StudentResume.id == resume_version.resume_id,
                        StudentResume.student_id == student_id,
                        StudentResume.deleted.is_(False),
                    )
                    .first()
                )

        if not resume:
            resume = (
                self.db.query(StudentResume)
                .filter(StudentResume.student_id == student_id, StudentResume.deleted.is_(False))
                .order_by(StudentResume.is_default.desc(), StudentResume.id.desc())
                .first()
            )
        if resume and not resume_version and resume.current_version_id:
            resume_version = (
                self.db.query(StudentResumeVersion)
                .filter(
                    StudentResumeVersion.id == resume.current_version_id,
                    StudentResumeVersion.deleted.is_(False),
                )
                .first()
            )
        if resume_version and resume and resume_version.resume_id != resume.id:
            resume_version = None
        return resume, resume_version

    @staticmethod
    def _find_document(documents, knowledge_doc_id, company_name, job_name):
        docs = [item for item in (documents or []) if isinstance(item, dict)]
        target_doc_id = str(knowledge_doc_id or "").strip()
        if target_doc_id:
            for item in docs:
                if str(item.get("id") or item.get("doc_id") or "").strip() == target_doc_id:
                    return item

        company = str(company_name or "").strip().lower()
        job = str(job_name or "").strip().lower()
        if company or job:
            scored: list[tuple[float, dict[str, Any]]] = []
            for item in docs:
                item_company = str(item.get("company_name") or (item.get("metadata") or {}).get("company_name") or "").strip().lower()
                item_job = str(item.get("job_name") or "").strip().lower()
                score = 0.0
                if company and item_company:
                    if company == item_company:
                        score += 1.0
                    elif company in item_company or item_company in company:
                        score += 0.6
                if job and item_job:
                    if job == item_job:
                        score += 1.0
                    elif job in item_job or item_job in job:
                        score += 0.6
                if score > 0:
                    scored.append((score, item))
            if scored:
                scored.sort(key=lambda row: row[0], reverse=True)
                return scored[0][1]

        return docs[0] if docs else None

    @staticmethod
    def _latest_profile(student):
        profiles = [item for item in (getattr(student, "profiles", []) or []) if not getattr(item, "deleted", False)]
        if not profiles:
            return None
        profiles.sort(key=lambda row: int(getattr(row, "id", 0) or 0), reverse=True)
        return profiles[0]

    @staticmethod
    def _clean_text(value):
        text = str(value or "").strip()
        return text

    def _job_skill_names(self, job: Job) -> list[str]:
        values: list[str] = []
        profile = job.job_profile if isinstance(job.job_profile, dict) else {}
        for source in (
            job.core_skill_tags or [],
            job.common_skill_tags or [],
            profile.get("core_skills") or [],
            profile.get("common_skills") or [],
        ):
            values.extend([self._clean_text(item) for item in source if self._clean_text(item)])
        values.extend(
            self._clean_text(item.name)
            for item in (job.skills or [])
            if not getattr(item, "deleted", False) and self._clean_text(item.name)
        )
        result: list[str] = []
        seen: set[str] = set()
        for item in values:
            key = item.lower()
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    @staticmethod
    def _cosine(left, right):
        if not isinstance(left, (list, tuple)) or not isinstance(right, (list, tuple)):
            return 0.0
        if len(left) != len(right) or not left:
            return 0.0
        sum_dot = 0.0
        sum_left = 0.0
        sum_right = 0.0
        for l_value, r_value in zip(left, right):
            try:
                l = float(l_value)
                r = float(r_value)
            except (TypeError, ValueError):
                return 0.0
            sum_dot += l * r
            sum_left += l * l
            sum_right += r * r
        if sum_left <= 0 or sum_right <= 0:
            return 0.0
        return float(sum_dot / (math.sqrt(sum_left) * math.sqrt(sum_right)))
