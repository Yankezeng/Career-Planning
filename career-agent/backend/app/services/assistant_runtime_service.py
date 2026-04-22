
from __future__ import annotations

import base64
import mimetypes
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.auth import EnterpriseProfile, User
from app.models.career import AssistantMessage, AssistantSession, CareerPath, LLMRequestLog, Report, ResumeDelivery
from app.models.job import Job, JobMatchResult
from app.models.student import GrowthRecord, Student, StudentAttachment, StudentResume, StudentResumeVersion
from app.services.agent_orchestrator_service import AgentOrchestratorService
from app.services.assistant_fallback_service import build_career_guidance_fallback
from app.services.assistant_session_state_service import AssistantSessionStateService
from app.services.assistant_skill_catalog_service import list_skills_for_role, normalize_skill_code
from app.services.llm_service import build_llm_call_meta, get_llm_service
from app.services.vector_search_service import VectorSearchService
from app.utils.upload_paths import resolve_upload_reference


BACKGROUND_JOB_ACTIVE_STATUSES = {"queued", "running", "extracting", "optimizing", "rendering_word", "registering_artifact"}


class AssistantService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.llm_service = get_llm_service()
        self.vector_search_service = VectorSearchService()
        self.orchestrator = AgentOrchestratorService(db, self.llm_service, self.vector_search_service)
        self.state_service = AssistantSessionStateService()

    def build_welcome(self, user: User) -> dict:
        role = user.role.code if user.role else "student"
        suggestions = {
            "student": [
                "根据我的简历生成能力画像并给出岗位方向。",
                "帮我做岗位匹配和技能差距分析。",
                "生成三个月成长路径和执行清单。",
            ],
            "enterprise": [
                "筛选最适合岗位的前三位候选人。",
                "生成候选人复评建议和沟通话术。",
                "输出岗位优先级与人才画像摘要。",
            ],
            "admin": [
                "汇总系统关键指标并给出演示主线。",
                "生成运营复盘和风险建议。",
                "给我明天答辩可直接讲的 demo 脚本。",
            ],
        }
        return {
            "welcome_message": f"{user.real_name}，欢迎来到 Career Agent。",
            "suggestions": suggestions.get(role, suggestions["student"]),
            "skills": list_skills_for_role(role),
            "knowledge_base": self.vector_search_service.describe(),
        }

    def build_skills(self, user: User) -> dict:
        role = user.role.code if user.role else "student"
        return {"items": list_skills_for_role(role)}

    def build_search(self, user: User, query: str) -> dict:
        keyword = str(query or "").strip()
        if not keyword:
            return {"items": []}

        role = user.role.code if user.role else "student"
        if role == "student":
            items = self._search_student(user.id, keyword)
        elif role == "enterprise":
            items = self._search_enterprise(user.id, keyword)
        else:
            items = self._search_admin(keyword)
        items.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
        return {"items": items[:30]}

    def build_assets(self, user: User) -> dict:
        role = user.role.code if user.role else "student"
        if role == "student":
            items = self._assets_student(user.id)
        elif role == "enterprise":
            items = self._assets_enterprise(user.id)
        else:
            items = self._assets_admin()
        items.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
        return {"items": items[:40]}

    def build_gallery(self, user: User) -> dict:
        role = user.role.code if user.role else "student"
        if role == "student":
            items = self._gallery_student(user.id)
        elif role == "enterprise":
            items = self._gallery_enterprise(user.id)
        else:
            items = self._gallery_admin()
        items.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return {"items": items[:24]}

    def list_sessions(self, user_id: int) -> list[dict]:
        sessions = (
            self.db.query(AssistantSession)
            .filter(AssistantSession.user_id == user_id, AssistantSession.deleted.is_(False))
            .order_by(AssistantSession.pinned.desc(), AssistantSession.updated_at.desc(), AssistantSession.id.desc())
            .all()
        )
        if not sessions:
            return []

        session_ids = [item.id for item in sessions]
        skill_rows = (
            self.db.query(AssistantMessage.session_id, AssistantMessage.skill)
            .filter(
                AssistantMessage.session_id.in_(session_ids),
                AssistantMessage.deleted.is_(False),
                AssistantMessage.skill.isnot(None),
                AssistantMessage.skill != "",
            )
            .order_by(AssistantMessage.session_id.asc(), AssistantMessage.created_at.desc(), AssistantMessage.id.desc())
            .all()
        )
        last_skill_map: dict[int, str] = {}
        for session_id, skill in skill_rows:
            if session_id in last_skill_map or not skill:
                continue
            code = normalize_skill_code(str(skill))
            if code != "general-chat":
                last_skill_map[session_id] = code

        return [self._serialize_session(item, last_skill_map.get(item.id, "")) for item in sessions]

    def create_session(self, user_id: int, title: str | None = None) -> dict:
        session_payload = {
            "user_id": user_id,
            "title": self._normalize_session_title(title),
            "last_message": "",
            "pinned": False,
            "state_json": {},
        }
        if self._is_sqlite():
            session_payload["id"] = self._next_model_id(AssistantSession)
        session = AssistantSession(**session_payload)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return self._serialize_session(session)

    def update_session(self, user_id: int, session_id: int, payload: dict) -> dict:
        session = self._require_session(user_id, session_id)
        if payload.get("title") is not None:
            session.title = self._normalize_session_title(payload.get("title"))
        if payload.get("pinned") is not None:
            session.pinned = bool(payload.get("pinned"))
        self.db.commit()
        self.db.refresh(session)
        return self._serialize_session(session, self._last_skill_for_session(session.id))

    def delete_session(self, user_id: int, session_id: int) -> None:
        session = self._require_session(user_id, session_id)
        artifact_names = self._extract_artifact_names_from_session(session.id)
        student = self._student_by_user(user_id)

        try:
            self.db.query(LLMRequestLog).filter(LLMRequestLog.session_id == session.id).delete(synchronize_session=False)
            self.db.query(AssistantMessage).filter(AssistantMessage.session_id == session.id).delete(synchronize_session=False)
            self.db.query(AssistantSession).filter(
                AssistantSession.id == session.id,
                AssistantSession.user_id == user_id,
            ).delete(synchronize_session=False)

            if student and artifact_names:
                self._purge_student_content_by_artifact_names(student.id, artifact_names)

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def list_session_messages(self, user_id: int, session_id: int) -> list[dict]:
        session = self._require_session(user_id, session_id)
        rows = (
            self.db.query(AssistantMessage)
            .filter(AssistantMessage.session_id == session.id, AssistantMessage.deleted.is_(False))
            .order_by(AssistantMessage.created_at.asc(), AssistantMessage.id.asc())
            .all()
        )
        return [self._serialize_message(item) for item in rows]

    def resolve_artifact_download(self, *, user_id: int, attachment_id: int) -> dict[str, Any]:
        student = self._student_by_user(user_id)
        if not student:
            raise HTTPException(status_code=404, detail="artifact not found")

        attachment = (
            self.db.query(StudentAttachment)
            .filter(
                StudentAttachment.id == int(attachment_id),
                StudentAttachment.student_id == int(student.id),
                StudentAttachment.deleted.is_(False),
            )
            .first()
        )
        if not attachment:
            raise HTTPException(status_code=404, detail="artifact not found")

        file_path = resolve_upload_reference(
            upload_root=self.settings.upload_path,
            reference=attachment.file_path,
            must_exist=True,
        )
        if not file_path:
            raise HTTPException(status_code=404, detail="artifact file not found")

        file_name = str(attachment.file_name or "").strip() or file_path.name
        media_type = self._infer_artifact_media_type(file_path=file_path, attachment=attachment)
        return {
            "path": file_path,
            "file_name": file_name,
            "media_type": media_type,
        }
    def chat(
        self,
        user: User,
        message: str,
        history: list[dict],
        skill: str | None = None,
        session_id: int | None = None,
        context_binding: dict[str, Any] | None = None,
        client_state: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict:
        clean_message = str(message or "").strip()
        role = user.role.code if user.role else "student"
        normalized_skill = normalize_skill_code(skill, role)
        log_meta_override: dict[str, Any] | None = None

        if session_id:
            session = self._require_session(user.id, session_id)
        else:
            session_payload = {
                "user_id": user.id,
                "title": self._normalize_session_title(clean_message[:16]),
                "last_message": "",
                "pinned": False,
                "state_json": {},
            }
            if self._is_sqlite():
                session_payload["id"] = self._next_model_id(AssistantSession)
            session = AssistantSession(**session_payload)
            self.db.add(session)
            self.db.flush()

        runtime_history = self._build_session_history(session.id)
        if not runtime_history and history:
            runtime_history = history

        self.llm_service.clear_last_call_meta()
        current_state = self.state_service.normalize_state(session.state_json)
        try:
            result = self.orchestrator.orchestrate(
                user=user,
                message=clean_message,
                history=runtime_history,
                selected_skill=normalized_skill,
                session_state=current_state,
                context_binding=context_binding or {},
                client_state=client_state or {},
                options=options or {},
                db=self.db,
            )
        except Exception as exc:
            fallback = build_career_guidance_fallback(
                message=clean_message,
                selected_skill=normalized_skill,
                session_state=current_state,
                context_binding=context_binding or {},
                client_state=client_state or {},
                reason=str(exc),
            )
            fallback_reply = str(fallback.get("reply") or "我先给你一个稳妥建议。")
            result = {
                "reply": fallback_reply,
                "reply_mode": "brief",
                "reply_blocks": fallback.get("reply_blocks") or [{"type": "summary", "text": fallback_reply}],
                "used_skill": normalized_skill,
                "normalized_skill": normalized_skill,
                "plan": {},
                "tool_steps": [],
                "cards": [],
                "actions": fallback.get("actions") or [],
                "knowledge_hits": [],
                "context_binding": fallback.get("context_binding") or {},
                "session_state": {**current_state, **(fallback.get("session_state") or {})},
                "task_patch": {},
                "tool_outputs": [],
                "context": {"scene": "assistant_chat"},
                "agent_route": "chat",
                "requires_user_input": False,
                "artifacts": [],
                "file_task": {},
                "code_task": {},
                "agent_flow": [],
                "supervisor_summary": {},
                "supervisor_plan": {},
                "dispatch_trace": {},
                "decision_trace": [],
                "error": fallback.get("error_message") or "复杂问题已自动切换为稳妥建议模式。",
            }
            log_meta_override = build_llm_call_meta(
                provider=getattr(self.llm_service, "provider", "mock"),
                model_name=getattr(self.llm_service, "model_name", "mock"),
                scene="assistant_chat",
                status="failed",
                latency_ms=0,
                input_chars=len(clean_message),
                output_chars=len(fallback_reply),
                error_message=str(exc),
                raw_meta_json={"source": "orchestrator_exception", "fallback": "runtime_summary"},
            )

        reply = str(result.get("reply") or "I have received your request.")
        reply_mode = str(result.get("reply_mode") or "structured")
        reply_blocks = self._json_safe(result.get("reply_blocks") or [])
        used_skill = normalize_skill_code(result.get("used_skill") or normalized_skill, role)
        normalized_response_skill = normalize_skill_code(result.get("normalized_skill") or used_skill, role)
        tool_steps = result.get("tool_steps") or []
        cards = result.get("cards") or []
        actions = result.get("actions") or []
        knowledge_hits = result.get("knowledge_hits") or []
        context_binding_out = result.get("context_binding") or {}
        session_state_out = self._json_safe(self.state_service.normalize_state(result.get("session_state") or {}))
        context_obj = result.get("context") or {}
        plan = result.get("plan") or {}
        tool_outputs = result.get("tool_outputs") or []
        task_patch = self._json_safe(result.get("task_patch") or {})
        agent_route = str(result.get("agent_route") or "chat")
        requires_user_input = bool(result.get("requires_user_input"))
        artifacts = self._json_safe(result.get("artifacts") or [])
        file_task = self._json_safe(result.get("file_task") or {})
        code_task = self._json_safe(result.get("code_task") or {})
        agent_flow = self._json_safe(result.get("agent_flow") or [])
        supervisor_summary = self._json_safe(result.get("supervisor_summary") or {})
        supervisor_plan = self._json_safe(result.get("supervisor_plan") or {})
        dispatch_trace = self._json_safe(result.get("dispatch_trace") or {})
        decision_trace = self._json_safe(result.get("decision_trace") or [])
        background_job = self._json_safe(result.get("background_job") or {})

        self._append_session_message(
            session.id,
            "user",
            clean_message,
            normalized_skill,
            [],
            [],
            [],
            {"context_binding": context_binding or {}, "client_state": client_state or {}},
        )
        assistant_message = self._append_session_message(
            session.id,
            "assistant",
            reply,
            normalized_response_skill,
            knowledge_hits,
            tool_steps,
            cards,
            {
                "actions": actions,
                "plan": plan,
                "context": context_obj,
                "context_binding": context_binding_out,
                "session_state": session_state_out,
                "task_patch": task_patch,
                "tool_outputs": tool_outputs,
                "reply_mode": reply_mode,
                "reply_blocks": reply_blocks,
                "agent_route": agent_route,
                "requires_user_input": requires_user_input,
                "artifacts": artifacts,
                "file_task": file_task,
                "code_task": code_task,
                "agent_flow": agent_flow,
                "supervisor_summary": supervisor_summary,
                "supervisor_plan": supervisor_plan,
                "dispatch_trace": dispatch_trace,
                "decision_trace": decision_trace,
                "background_job": self._public_background_job(background_job),
            },
        )
        if str(background_job.get("status") or "") in BACKGROUND_JOB_ACTIVE_STATUSES:
            background_job["user_id"] = int(user.id)
            background_job["session_id"] = int(session.id)
            background_job["message_id"] = int(assistant_message.id)
            assistant_meta = dict(assistant_message.meta_json or {})
            assistant_meta["background_job"] = self._public_background_job(background_job)
            assistant_message.meta_json = assistant_meta

        if not session.title:
            session.title = self._normalize_session_title(clean_message[:16])
        session.last_message = reply[:500]
        session.state_json = session_state_out

        self.db.commit()
        self.db.refresh(session)
        if str(background_job.get("status") or "") in BACKGROUND_JOB_ACTIVE_STATUSES:
            from app.services.assistant_background_jobs import submit_resume_optimization_job

            submit_resume_optimization_job(background_job)
        quality_meta = {
            "intent_confidence": context_obj.get("intent_confidence"),
            "retrieval_hit_count": len(knowledge_hits),
            "tool_fail_count": len([item for item in (tool_steps or []) if item.get("status") == "failed"]),
            "reply_mode": reply_mode,
        }
        merged_log_meta = self._merge_llm_meta(log_meta_override, quality_meta)
        self._write_llm_request_log(
            user_id=user.id,
            session_id=session.id,
            scene="assistant_chat",
            meta_override=merged_log_meta,
        )

        return {
            "reply": reply,
            "reply_mode": reply_mode,
            "reply_blocks": reply_blocks,
            "used_skill": used_skill,
            "normalized_skill": normalized_response_skill,
            "plan": plan,
            "tool_steps": tool_steps,
            "cards": cards,
            "actions": actions,
            "knowledge_hits": knowledge_hits,
            "context_binding": context_binding_out,
            "session_state": session_state_out,
            "task_patch": task_patch,
            "tool_outputs": tool_outputs,
            "context": context_obj,
            "agent_route": agent_route,
            "requires_user_input": requires_user_input,
            "artifacts": artifacts,
            "file_task": file_task,
            "code_task": code_task,
            "agent_flow": agent_flow,
            "supervisor_summary": supervisor_summary,
            "supervisor_plan": supervisor_plan,
            "dispatch_trace": dispatch_trace,
            "decision_trace": decision_trace,
            "background_job": self._public_background_job(background_job),
            "knowledge_base": self.vector_search_service.describe(),
            "session_id": session.id,
            "session": self._serialize_session(session, self._last_skill_for_session(session.id)),
        }

    def build_summary(self, user: User) -> dict:
        role = user.role.code if user.role else "student"
        if role == "student":
            cards = self._summary_student(user.id)
        elif role == "enterprise":
            cards = self._summary_enterprise(user.id)
        else:
            cards = self._summary_admin()
        return {"cards": cards, "updated_at": datetime.now(timezone.utc).isoformat()}

    def _search_student(self, user_id: int, keyword: str) -> list[dict]:
        student = self._student_by_user(user_id)
        if not student:
            return []
        pattern = f"%{keyword}%"

        items: list[dict] = []
        attachments = (
            self.db.query(StudentAttachment)
            .filter(
                StudentAttachment.student_id == student.id,
                StudentAttachment.deleted.is_(False),
                or_(StudentAttachment.file_name.ilike(pattern), StudentAttachment.description.ilike(pattern)),
            )
            .order_by(StudentAttachment.created_at.desc(), StudentAttachment.id.desc())
            .limit(10)
            .all()
        )
        for row in attachments:
            items.append({
                "id": row.id,
                "type": "attachment",
                "title": row.file_name,
                "subtitle": row.description or "",
                "route": "/student/resume",
                "score": 0.9,
                "updated_at": self._format_time(row.updated_at),
            })

        reports = (
            self.db.query(Report)
            .filter(
                Report.student_id == student.id,
                Report.deleted.is_(False),
                or_(Report.title.ilike(pattern), Report.summary.ilike(pattern)),
            )
            .order_by(Report.created_at.desc(), Report.id.desc())
            .limit(10)
            .all()
        )
        for row in reports:
            items.append({
                "id": row.id,
                "type": "report",
                "title": row.title,
                "subtitle": row.summary or "",
                "route": f"/reports/center?tab=preview&reportId={row.id}",
                "score": 0.8,
                "updated_at": self._format_time(row.updated_at),
            })
        return items
    def _search_enterprise(self, user_id: int, keyword: str) -> list[dict]:
        profile = (
            self.db.query(EnterpriseProfile)
            .filter(EnterpriseProfile.user_id == user_id, EnterpriseProfile.deleted.is_(False))
            .first()
        )
        if not profile:
            return []
        pattern = f"%{keyword}%"

        rows = (
            self.db.query(ResumeDelivery)
            .options(joinedload(ResumeDelivery.student))
            .filter(
                ResumeDelivery.enterprise_profile_id == profile.id,
                ResumeDelivery.deleted.is_(False),
                or_(
                    ResumeDelivery.target_job_name.ilike(pattern),
                    ResumeDelivery.enterprise_feedback.ilike(pattern),
                    ResumeDelivery.delivery_note.ilike(pattern),
                ),
            )
            .order_by(ResumeDelivery.created_at.desc(), ResumeDelivery.id.desc())
            .limit(20)
            .all()
        )
        return [
            {
                "id": row.id,
                "type": "candidate",
                "title": row.student.name if row.student else "Candidate",
                "subtitle": row.target_job_name or "Target Job",
                "route": "/enterprise/deliveries",
                "score": max(0.3, float(row.match_score or 0) / 100),
                "updated_at": self._format_time(row.updated_at),
            }
            for row in rows
        ]

    def _search_admin(self, keyword: str) -> list[dict]:
        pattern = f"%{keyword}%"
        jobs = (
            self.db.query(Job)
            .filter(Job.deleted.is_(False), or_(Job.name.ilike(pattern), Job.category.ilike(pattern), Job.description.ilike(pattern)))
            .order_by(Job.created_at.desc(), Job.id.desc())
            .limit(12)
            .all()
        )
        reports = (
            self.db.query(Report)
            .filter(Report.deleted.is_(False), or_(Report.title.ilike(pattern), Report.summary.ilike(pattern)))
            .order_by(Report.created_at.desc(), Report.id.desc())
            .limit(12)
            .all()
        )
        items = [
            {
                "id": row.id,
                "type": "job",
                "title": row.name,
                "subtitle": row.category or "",
                "route": "/dashboard",
                "score": 0.75,
                "updated_at": self._format_time(row.updated_at),
            }
            for row in jobs
        ]
        items.extend(
            {
                "id": row.id,
                "type": "report",
                "title": row.title,
                "subtitle": row.summary or "",
                "route": "/dashboard",
                "score": 0.7,
                "updated_at": self._format_time(row.updated_at),
            }
            for row in reports
        )
        return items

    def _assets_student(self, user_id: int) -> list[dict]:
        student = self._student_by_user(user_id)
        if not student:
            return []

        items: list[dict] = []
        attachments = (
            self.db.query(StudentAttachment)
            .filter(StudentAttachment.student_id == student.id, StudentAttachment.deleted.is_(False))
            .order_by(StudentAttachment.created_at.desc(), StudentAttachment.id.desc())
            .limit(8)
            .all()
        )
        for row in attachments:
            items.append(
                {
                    "id": row.id,
                    "name": row.file_name,
                    "title": row.file_name,
                    "type": (row.file_type or "file").lower(),
                    "status": "available",
                    "updated_at": self._format_time(row.updated_at),
                    "download_url": self._to_download_url(row.file_path),
                }
            )

        reports = (
            self.db.query(Report)
            .filter(Report.student_id == student.id, Report.deleted.is_(False))
            .order_by(Report.created_at.desc(), Report.id.desc())
            .limit(8)
            .all()
        )
        for row in reports:
            items.append(
                {
                    "id": row.id,
                    "name": row.title,
                    "title": row.title,
                    "type": "report",
                    "status": "available",
                    "updated_at": self._format_time(row.updated_at),
                    "download_url": self._to_download_url(row.pdf_path),
                }
            )

        return items

    def _assets_enterprise(self, user_id: int) -> list[dict]:
        profile = (
            self.db.query(EnterpriseProfile)
            .filter(EnterpriseProfile.user_id == user_id, EnterpriseProfile.deleted.is_(False))
            .first()
        )
        if not profile:
            return []
        rows = (
            self.db.query(ResumeDelivery)
            .options(joinedload(ResumeDelivery.student))
            .filter(ResumeDelivery.enterprise_profile_id == profile.id, ResumeDelivery.deleted.is_(False))
            .order_by(ResumeDelivery.created_at.desc(), ResumeDelivery.id.desc())
            .limit(16)
            .all()
        )
        return [
            {
                "id": row.id,
                "type": "candidate",
                "name": f"{row.student.name if row.student else 'Candidate'} - {row.target_job_name or 'Target Job'}",
                "title": f"{row.student.name if row.student else 'Candidate'} - {row.target_job_name or 'Target Job'}",
                "status": "available",
                "updated_at": self._format_time(row.updated_at),
                "download_url": "",
            }
            for row in rows
        ]

    def _assets_admin(self) -> list[dict]:
        now = self._format_time(datetime.now(timezone.utc))
        return [
            {
                "id": "users",
                "type": "metric",
                "name": "users",
                "title": "users",
                "status": "available",
                "value": self.db.query(func.count(User.id)).filter(User.deleted.is_(False)).scalar() or 0,
                "updated_at": now,
                "download_url": "",
            },
            {
                "id": "students",
                "type": "metric",
                "name": "students",
                "title": "students",
                "status": "available",
                "value": self.db.query(func.count(Student.id)).filter(Student.deleted.is_(False)).scalar() or 0,
                "updated_at": now,
                "download_url": "",
            },
            {
                "id": "jobs",
                "type": "metric",
                "name": "jobs",
                "title": "jobs",
                "status": "available",
                "value": self.db.query(func.count(Job.id)).filter(Job.deleted.is_(False)).scalar() or 0,
                "updated_at": now,
                "download_url": "",
            },
            {
                "id": "reports",
                "type": "metric",
                "name": "reports",
                "title": "reports",
                "status": "available",
                "value": self.db.query(func.count(Report.id)).filter(Report.deleted.is_(False)).scalar() or 0,
                "updated_at": now,
                "download_url": "",
            },
        ]

    def _gallery_student(self, user_id: int) -> list[dict]:
        return self._to_gallery(self._assets_student(user_id), "/assistant")

    def _gallery_enterprise(self, user_id: int) -> list[dict]:
        return self._to_gallery(self._assets_enterprise(user_id), "/enterprise/deliveries")

    def _gallery_admin(self) -> list[dict]:
        return self._to_gallery(self._assets_admin(), "/dashboard")

    def _summary_student(self, user_id: int) -> list[dict]:
        student = self._student_by_user(user_id)
        if not student:
            return []
        match_count = self.db.query(func.count(JobMatchResult.id)).filter(JobMatchResult.student_id == student.id, JobMatchResult.deleted.is_(False)).scalar() or 0
        growth_count = self.db.query(func.count(GrowthRecord.id)).filter(GrowthRecord.student_id == student.id, GrowthRecord.deleted.is_(False)).scalar() or 0
        report_count = self.db.query(func.count(Report.id)).filter(Report.student_id == student.id, Report.deleted.is_(False)).scalar() or 0
        latest_path = (
            self.db.query(CareerPath)
            .options(joinedload(CareerPath.tasks))
            .filter(CareerPath.student_id == student.id, CareerPath.deleted.is_(False))
            .order_by(CareerPath.created_at.desc(), CareerPath.id.desc())
            .first()
        )
        return [
            {"id": "matches", "title": "岗位匹配", "value": int(match_count), "description": "历史匹配次数"},
            {"id": "growth", "title": "成长记录", "value": int(growth_count), "description": "成长追踪条目"},
            {"id": "reports", "title": "报告数量", "value": int(report_count), "description": "已生成报告"},
            {"id": "path", "title": "路径任务", "value": len(latest_path.tasks) if latest_path else 0, "description": "当前成长路径任务"},
        ]

    def _summary_enterprise(self, user_id: int) -> list[dict]:
        profile = self.db.query(EnterpriseProfile).filter(EnterpriseProfile.user_id == user_id, EnterpriseProfile.deleted.is_(False)).first()
        if not profile:
            return []
        rows = self.db.query(ResumeDelivery).filter(ResumeDelivery.enterprise_profile_id == profile.id, ResumeDelivery.deleted.is_(False)).all()
        high_match = len([row for row in rows if float(row.match_score or 0) >= 70])
        reviewed = len([row for row in rows if row.enterprise_feedback])
        return [
            {"id": "candidates", "title": "候选人数量", "value": len(rows), "description": "候选人池总数"},
            {"id": "high_match", "title": "高匹配候选", "value": high_match, "description": "匹配度 >= 70"},
            {"id": "reviewed", "title": "已复评", "value": reviewed, "description": "已完成复评"},
        ]

    def _summary_admin(self) -> list[dict]:
        return [
            {"id": "users", "title": "用户总数", "value": self.db.query(func.count(User.id)).filter(User.deleted.is_(False)).scalar() or 0},
            {"id": "students", "title": "学生总数", "value": self.db.query(func.count(Student.id)).filter(Student.deleted.is_(False)).scalar() or 0},
            {"id": "jobs", "title": "岗位总数", "value": self.db.query(func.count(Job.id)).filter(Job.deleted.is_(False)).scalar() or 0},
            {"id": "reports", "title": "报告总数", "value": self.db.query(func.count(Report.id)).filter(Report.deleted.is_(False)).scalar() or 0},
            {"id": "deliveries", "title": "投递总数", "value": self.db.query(func.count(ResumeDelivery.id)).filter(ResumeDelivery.deleted.is_(False)).scalar() or 0},
        ]

    def _student_by_user(self, user_id: int) -> Student | None:
        return self.db.query(Student).filter(Student.user_id == user_id, Student.deleted.is_(False)).first()

    def _extract_artifact_names_from_session(self, session_id: int) -> set[str]:
        rows = self.db.query(AssistantMessage.meta_json).filter(AssistantMessage.session_id == session_id).all()
        names: set[str] = set()
        for row in rows:
            if hasattr(row, "_mapping"):
                meta = row._mapping.get("meta_json")  # type: ignore[attr-defined]
            elif isinstance(row, (tuple, list)):
                meta = row[0] if row else {}
            else:
                meta = row
            if not isinstance(meta, dict):
                continue
            artifacts = meta.get("artifacts")
            if not isinstance(artifacts, list):
                continue
            for item in artifacts:
                if not isinstance(item, dict):
                    continue
                candidate = str(item.get("name") or item.get("file_name") or "").strip()
                normalized = self._normalize_attachment_name(candidate)
                if normalized:
                    names.add(normalized)
        return names

    @staticmethod
    def _normalize_attachment_name(name: str) -> str:
        return " ".join(str(name or "").strip().lower().split())

    @staticmethod
    def _infer_artifact_media_type(*, file_path: Path, attachment: StudentAttachment) -> str:
        suffix = file_path.suffix.lower()
        extension_map = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".doc": "application/msword",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".mp4": "video/mp4",
            ".txt": "text/plain",
        }
        if suffix in extension_map:
            return extension_map[suffix]

        file_type = str(getattr(attachment, "file_type", "") or "").strip().lower()
        if file_type:
            guessed_from_type = mimetypes.types_map.get(f".{file_type}")
            if guessed_from_type:
                return guessed_from_type

        guessed_from_name, _ = mimetypes.guess_type(str(file_path))
        return guessed_from_name or "application/octet-stream"

    def _purge_student_content_by_artifact_names(self, student_id: int, artifact_names: set[str]) -> None:
        normalized_targets = {self._normalize_attachment_name(name) for name in (artifact_names or set()) if str(name or "").strip()}
        if not normalized_targets:
            return

        attachment_rows = (
            self.db.query(StudentAttachment.id, StudentAttachment.file_name)
            .filter(StudentAttachment.student_id == student_id)
            .all()
        )
        matched_attachment_ids = {
            int(row.id)
            for row in attachment_rows
            if self._normalize_attachment_name(str(row.file_name or "")) in normalized_targets
        }
        if not matched_attachment_ids:
            return

        resume_ids = {
            int(row.id)
            for row in (
                self.db.query(StudentResume.id)
                .filter(
                    StudentResume.student_id == student_id,
                    StudentResume.source_attachment_id.in_(list(matched_attachment_ids)),
                )
                .all()
            )
        }

        version_rows = (
            self.db.query(StudentResumeVersion.id, StudentResumeVersion.resume_id)
            .join(StudentResume, StudentResume.id == StudentResumeVersion.resume_id)
            .filter(
                StudentResume.student_id == student_id,
                StudentResumeVersion.attachment_id.in_(list(matched_attachment_ids)),
            )
            .all()
        )
        resume_version_ids = {int(row.id) for row in version_rows}
        resume_ids.update(int(row.resume_id) for row in version_rows if row.resume_id is not None)

        if resume_ids:
            resume_version_ids.update(
                int(row.id)
                for row in (
                    self.db.query(StudentResumeVersion.id)
                    .filter(StudentResumeVersion.resume_id.in_(list(resume_ids)))
                    .all()
                )
            )

        delivery_conditions: list[Any] = []
        if matched_attachment_ids:
            delivery_conditions.append(ResumeDelivery.attachment_id.in_(list(matched_attachment_ids)))
        if resume_ids:
            delivery_conditions.append(ResumeDelivery.resume_id.in_(list(resume_ids)))
        if resume_version_ids:
            delivery_conditions.append(ResumeDelivery.resume_version_id.in_(list(resume_version_ids)))
        if delivery_conditions:
            self.db.query(ResumeDelivery).filter(
                ResumeDelivery.student_id == student_id,
                or_(*delivery_conditions),
            ).delete(synchronize_session=False)

        if resume_version_ids:
            self.db.query(StudentResume).filter(
                StudentResume.id.in_(list(resume_ids)),
                StudentResume.current_version_id.in_(list(resume_version_ids)),
            ).update({StudentResume.current_version_id: None}, synchronize_session=False)
            self.db.query(StudentResumeVersion).filter(
                StudentResumeVersion.id.in_(list(resume_version_ids))
            ).delete(synchronize_session=False)

        if resume_ids:
            self.db.query(StudentResume).filter(
                StudentResume.id.in_(list(resume_ids))
            ).delete(synchronize_session=False)

        self.db.query(StudentAttachment).filter(
            StudentAttachment.id.in_(list(matched_attachment_ids))
        ).delete(synchronize_session=False)

    def _require_session(self, user_id: int, session_id: int | None) -> AssistantSession:
        session = (
            self.db.query(AssistantSession)
            .filter(
                AssistantSession.id == session_id,
                AssistantSession.user_id == user_id,
                AssistantSession.deleted.is_(False),
            )
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        return session

    def _append_session_message(
        self,
        session_id: int,
        role: str,
        content: str,
        skill: str | None,
        knowledge_hits: list[Any],
        tool_steps: list[Any] | None = None,
        result_cards: list[Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> AssistantMessage:
        payload = {
            "session_id": session_id,
            "role": role,
            "content": content,
            "skill": skill,
            "knowledge_hits_json": self._json_safe(knowledge_hits),
            "tool_steps_json": self._json_safe(tool_steps or []),
            "result_cards_json": self._json_safe(result_cards or []),
            "meta_json": self._json_safe(meta or {}),
        }
        if self._is_sqlite():
            payload["id"] = self._next_model_id(AssistantMessage)
        row = AssistantMessage(**payload)
        self.db.add(row)
        if self._is_sqlite():
            self.db.flush()
        else:
            self.db.flush()
        return row

    def _is_sqlite(self) -> bool:
        bind = self.db.get_bind()
        return bool(bind and bind.dialect.name == "sqlite")

    def _next_model_id(self, model: Any, db: Session | None = None) -> int:
        source_db = db or self.db
        current = source_db.query(func.max(model.id)).scalar() or 0
        return int(current) + 1
 
    def _build_session_history(self, session_id: int) -> list[dict]:
        rows = (
            self.db.query(AssistantMessage.role, AssistantMessage.content)
            .filter(AssistantMessage.session_id == session_id, AssistantMessage.deleted.is_(False))
            .order_by(AssistantMessage.created_at.desc(), AssistantMessage.id.desc())
            .limit(40)
            .all()
        )
        return [{"role": item.role, "content": item.content} for item in reversed(rows)]

    def _serialize_session(self, session: AssistantSession, last_skill: str = "") -> dict:
        normalized_last_skill = normalize_skill_code(last_skill)
        if normalized_last_skill == "general-chat":
            normalized_last_skill = ""
        return {
            "id": session.id,
            "title": session.title,
            "last_message": session.last_message,
            "updated_at": self._format_time(session.updated_at),
            "pinned": bool(session.pinned),
            "last_skill": normalized_last_skill,
            "state_json": self.state_service.normalize_state(session.state_json),
        }

    @staticmethod
    def _public_background_job(job: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(job, dict) or not job:
            return {}

        def _to_int(value: Any) -> int | None:
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                return None
            return parsed or None

        public = {
            "id": str(job.get("id") or ""),
            "type": str(job.get("type") or "resume_optimization"),
            "status": str(job.get("status") or "running"),
            "phase": str(job.get("phase") or job.get("status") or "running"),
            "message": str(job.get("message") or ""),
            "message_id": _to_int(job.get("message_id")),
            "session_id": _to_int(job.get("session_id")),
            "started_at": str(job.get("started_at") or ""),
            "finished_at": str(job.get("finished_at") or ""),
        }
        error = str(job.get("error") or "").strip()
        if error:
            public["error"] = error
        return public

    def _serialize_message(self, message: AssistantMessage) -> dict:
        skill_code = normalize_skill_code(message.skill)
        if skill_code == "general-chat":
            skill_code = ""
        meta = message.meta_json or {}
        reply_mode = str(meta.get("reply_mode") or "")
        reply_blocks = meta.get("reply_blocks") if isinstance(meta.get("reply_blocks"), list) else []
        task_patch = meta.get("task_patch") if isinstance(meta.get("task_patch"), dict) else {}
        agent_route = str(meta.get("agent_route") or "chat")
        requires_user_input = bool(meta.get("requires_user_input"))
        artifacts = meta.get("artifacts") if isinstance(meta.get("artifacts"), list) else []
        file_task = meta.get("file_task") if isinstance(meta.get("file_task"), dict) else {}
        code_task = meta.get("code_task") if isinstance(meta.get("code_task"), dict) else {}
        agent_flow = meta.get("agent_flow") if isinstance(meta.get("agent_flow"), list) else []
        supervisor_summary = meta.get("supervisor_summary") if isinstance(meta.get("supervisor_summary"), dict) else {}
        supervisor_plan = meta.get("supervisor_plan") if isinstance(meta.get("supervisor_plan"), dict) else {}
        dispatch_trace = meta.get("dispatch_trace") if isinstance(meta.get("dispatch_trace"), dict) else {}
        decision_trace = meta.get("decision_trace") if isinstance(meta.get("decision_trace"), list) else []
        background_job = self._public_background_job(meta.get("background_job") if isinstance(meta.get("background_job"), dict) else {})

        tool_steps = list(message.tool_steps_json or [])
        if not tool_steps and message.role == "assistant" and message.skill:
            tool_steps.append({"tool": skill_code or message.skill, "status": "done", "text": f"used skill: {skill_code or message.skill}"})
        if not tool_steps and message.role == "assistant" and (message.knowledge_hits_json or []):
            tool_steps.append({"tool": "job_kb_search", "status": "done", "text": "knowledge search completed"})

        return {
            "id": message.id,
            "session_id": message.session_id,
            "role": message.role,
            "content": message.content,
            "skill": skill_code,
            "knowledge_hits_json": message.knowledge_hits_json or [],
            "tool_steps": tool_steps,
            "result_cards": message.result_cards_json or [],
            "reply_mode": reply_mode or None,
            "reply_blocks": reply_blocks,
            "task_patch": task_patch,
            "agent_route": agent_route,
            "requires_user_input": requires_user_input,
            "artifacts": artifacts,
            "file_task": file_task,
            "code_task": code_task,
            "agent_flow": agent_flow,
            "supervisor_summary": supervisor_summary,
            "supervisor_plan": supervisor_plan,
            "dispatch_trace": dispatch_trace,
            "decision_trace": decision_trace,
            "background_job": background_job,
            "meta": meta,
            "created_at": self._format_time(message.created_at),
        }

    def _last_skill_for_session(self, session_id: int) -> str:
        row = (
            self.db.query(AssistantMessage.skill)
            .filter(
                AssistantMessage.session_id == session_id,
                AssistantMessage.deleted.is_(False),
                AssistantMessage.skill.isnot(None),
                AssistantMessage.skill != "",
            )
            .order_by(AssistantMessage.created_at.desc(), AssistantMessage.id.desc())
            .first()
        )
        if not row or not row.skill:
            return ""
        code = normalize_skill_code(str(row.skill))
        return "" if code == "general-chat" else code

    def _to_gallery(self, assets: list[dict], route: str) -> list[dict]:
        return [
            {
                "id": item.get("id"),
                "type": f"{item.get('type', 'item')}_preview",
                "title": item.get("title") or item.get("name") or "Item",
                "thumb_url": self._placeholder_thumb(item.get("title") or item.get("name") or "Item", item.get("type") or "report-composite"),
                "cover_mode": "icon",
                "icon_type": item.get("type") or "report-composite",
                "preview_route": route,
                "created_at": item.get("updated_at") or "",
            }
            for item in assets
        ]

    def _write_llm_request_log(
        self,
        *,
        user_id: int | None,
        session_id: int | None,
        scene: str = "assistant_chat",
        meta_override: dict[str, Any] | None = None,
    ) -> None:
        meta = meta_override or self.llm_service.get_last_call_meta() or {}
        if not meta:
            return
        payload = self._build_llm_log_record(meta=meta, user_id=user_id, session_id=session_id, scene=scene)
        log_db = SessionLocal()
        try:
            if self._is_sqlite():
                payload["id"] = self._next_model_id(LLMRequestLog, db=log_db)
            log_db.add(LLMRequestLog(**payload))
            log_db.commit()
        except Exception:
            log_db.rollback()
        finally:
            log_db.close()

    @staticmethod
    def _build_llm_log_record(*, meta: dict[str, Any], user_id: int | None, session_id: int | None, scene: str) -> dict[str, Any]:
        return {
            "provider": str(meta.get("provider") or "mock"),
            "model_name": str(meta.get("model_name") or "mock"),
            "scene": str(meta.get("scene") or scene or "assistant_chat"),
            "user_id": user_id,
            "session_id": session_id,
            "request_id": str(meta.get("request_id") or uuid4()),
            "status": str(meta.get("status") or "success"),
            "latency_ms": float(meta.get("latency_ms") or 0),
            "prompt_tokens": int(meta.get("prompt_tokens") or 0),
            "completion_tokens": int(meta.get("completion_tokens") or 0),
            "total_tokens": int(meta.get("total_tokens") or 0),
            "input_chars": int(meta.get("input_chars") or 0),
            "output_chars": int(meta.get("output_chars") or 0),
            "error_message": str(meta.get("error_message") or "")[:500] or None,
            "raw_usage_json": meta.get("raw_usage_json") or {},
            "raw_meta_json": meta.get("raw_meta_json") or {},
        }

    def _merge_llm_meta(self, meta_override: dict[str, Any] | None, quality_meta: dict[str, Any]) -> dict[str, Any] | None:
        base_meta = self._json_safe(meta_override or self.llm_service.get_last_call_meta() or {})
        if not base_meta:
            return None
        raw_meta = base_meta.get("raw_meta_json") if isinstance(base_meta.get("raw_meta_json"), dict) else {}
        base_meta["raw_meta_json"] = {**raw_meta, **quality_meta}
        return base_meta

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: AssistantService._json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [AssistantService._json_safe(item) for item in value]
        if isinstance(value, tuple):
            return [AssistantService._json_safe(item) for item in value]
        if isinstance(value, datetime):
            return value.isoformat(timespec="seconds")
        return value

    @staticmethod
    def _normalize_session_title(value: Any) -> str:
        text = str(value or "").strip()
        return (text or "新任务")[:40]

    def _to_download_url(self, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        if text.startswith("/uploads/"):
            return text
        try:
            resolved = Path(text).resolve()
            upload_root = self.settings.upload_path.resolve()
            if str(resolved).startswith(str(upload_root)):
                relative = resolved.relative_to(upload_root).as_posix()
                return f"/uploads/{relative}"
        except Exception:
            return ""
        return ""

    @staticmethod
    def _format_time(value: datetime | None) -> str:
        return value.isoformat(timespec="seconds") if value else ""

    @staticmethod
    def _placeholder_thumb(title: str, icon_type: str = "report-composite") -> str:
        label_map = {
            "report-composite": "Report Preview",
            "resume": "Resume Workspace",
            "delivery": "Delivery Progress",
        }
        label = label_map.get(icon_type, "Preview")
        safe_title = escape((title or "Career Agent")[:24])
        safe_label = escape(label)
        svg = f"""
        <svg xmlns='http://www.w3.org/2000/svg' width='480' height='270' viewBox='0 0 480 270'>
          <defs>
            <linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>
              <stop offset='0%' stop-color='#f7fafc'/>
              <stop offset='100%' stop-color='#e7eef8'/>
            </linearGradient>
          </defs>
          <rect width='480' height='270' rx='24' fill='url(#g)'/>
          <rect x='20' y='20' width='440' height='230' rx='18' fill='#ffffff' stroke='#dbe5f3' stroke-width='1.5'/>
          <text x='40' y='66' fill='#64748b' font-size='20' font-family='Segoe UI, Arial'>{safe_label}</text>
          <text x='40' y='214' fill='#0f172a' font-size='24' font-family='Segoe UI, Arial'>{safe_title}</text>
        </svg>
        """.strip()
        svg_base64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        return f"data:image/svg+xml;base64,{svg_base64}"

