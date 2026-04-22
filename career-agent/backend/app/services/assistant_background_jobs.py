from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.auth import User
from app.models.career import AssistantMessage, AssistantSession
from app.services.agent.file_agent.file_agent import FileAgent
from app.services.assistant_session_state_service import AssistantSessionStateService


_EXECUTOR = ThreadPoolExecutor(
    max_workers=int(getattr(get_settings(), "ASSISTANT_BACKGROUND_MAX_WORKERS", 2) or 2),
    thread_name_prefix="assistant-bg",
)


def submit_resume_optimization_job(job: dict[str, Any]) -> None:
    _EXECUTOR.submit(_run_resume_optimization_job, dict(job or {}))


def _run_resume_optimization_job(job: dict[str, Any]) -> None:
    db = SessionLocal()
    try:
        user_id = _to_int(job.get("user_id"))
        message_id = _to_int(job.get("message_id"))
        session_id = _to_int(job.get("session_id"))
        if not user_id or not message_id:
            return

        user = db.query(User).filter(User.id == user_id, User.deleted.is_(False)).first()
        message = db.query(AssistantMessage).filter(AssistantMessage.id == message_id, AssistantMessage.deleted.is_(False)).first()
        session = (
            db.query(AssistantSession)
            .filter(AssistantSession.id == session_id, AssistantSession.user_id == user_id, AssistantSession.deleted.is_(False))
            .first()
            if session_id
            else None
        )
        if not user or not message:
            return

        _mark_job_status(message, job, status="extracting", status_message="正在解析简历附件...", error="")
        db.commit()

        def update_phase(phase: str, phase_message: str) -> None:
            _mark_job_status(message, job, status=phase, status_message=phase_message, error="")
            db.commit()

        result = FileAgent(db).complete_resume_optimization_background(
            user=user,
            job_payload=job.get("payload") if isinstance(job.get("payload"), dict) else {},
            phase_callback=update_phase,
        )
        if str(result.get("status") or "") != "success":
            raise RuntimeError(str(result.get("reply") or result.get("question") or "后台简历优化失败。"))

        public_job = _public_job(job, status="done", error="")
        _update_assistant_message_from_result(message, result, background_job=public_job)
        if session:
            session.last_message = str(result.get("reply") or "")[:500]
            current_state = session.state_json or {}
            context_patch = result.get("context_patch") if isinstance(result.get("context_patch"), dict) else None
            if isinstance(result.get("session_state"), dict):
                session.state_json = result.get("session_state")
            elif context_patch:
                session.state_json = AssistantSessionStateService.merge(
                    current_state,
                    context_patch=context_patch,
                )
            if context_patch and isinstance(session.state_json, dict):
                if context_patch.get("last_resume_optimization"):
                    session.state_json["last_resume_optimization"] = context_patch["last_resume_optimization"]
        db.commit()
    except Exception as exc:
        db.rollback()
        _mark_background_job_failed(db, job, exc)
    finally:
        db.close()


def _update_assistant_message_from_result(
    message: AssistantMessage,
    result: dict[str, Any],
    *,
    background_job: dict[str, Any],
) -> None:
    reply = str(result.get("reply") or "")
    tool_outputs = _json_safe(result.get("tool_outputs") or [])
    message.content = reply
    message.knowledge_hits_json = _json_safe(result.get("knowledge_hits") or [])
    message.tool_steps_json = _json_safe(result.get("tool_steps") or [])
    message.result_cards_json = _json_safe(_result_cards(result))
    meta = dict(message.meta_json or {})
    meta.update(
        {
            "actions": _json_safe(result.get("actions") or []),
            "context": _json_safe(result.get("context") or {}),
            "context_binding": _json_safe(result.get("context_binding") or {}),
            "session_state": _json_safe(result.get("session_state") or {}),
            "task_patch": _json_safe(result.get("task_patch") or {}),
            "tool_outputs": tool_outputs,
            "reply_mode": str(result.get("reply_mode") or "structured"),
            "reply_blocks": _json_safe(result.get("reply_blocks") or [{"type": "summary", "text": reply}]),
            "agent_route": str(result.get("agent_route") or "file"),
            "requires_user_input": bool(result.get("requires_user_input")),
            "artifacts": _json_safe(result.get("artifacts") or []),
            "file_task": _json_safe(result.get("file_task") or {}),
            "code_task": _json_safe(result.get("code_task") or {}),
            "agent_flow": _json_safe(result.get("agent_flow") or []),
            "supervisor_summary": _json_safe(result.get("supervisor_summary") or {}),
            "supervisor_plan": _json_safe(result.get("supervisor_plan") or {}),
            "dispatch_trace": _json_safe(result.get("dispatch_trace") or {}),
            "decision_trace": _json_safe(result.get("decision_trace") or []),
            "background_job": background_job,
        }
    )
    message.meta_json = meta


def _mark_job_status(message: AssistantMessage, job: dict[str, Any], *, status: str, status_message: str = "", error: str = "") -> None:
    job["status"] = status
    job["phase"] = status
    if status_message:
        job["message"] = status_message
    meta = dict(message.meta_json or {})
    meta["background_job"] = _public_job(job, status=status, error=error)
    meta["file_task"] = {
        "type": "optimize_resume",
        "status": status,
        "phase": status,
        "message": str(job.get("message") or ""),
        "background": True,
        "background_job_id": str(job.get("id") or ""),
    }
    message.meta_json = meta


def _mark_background_job_failed(db, job: dict[str, Any], exc: Exception) -> None:
    message_id = _to_int(job.get("message_id"))
    if not message_id:
        return
    message = db.query(AssistantMessage).filter(AssistantMessage.id == message_id, AssistantMessage.deleted.is_(False)).first()
    if not message:
        return
    reason = _friendly_failure_reason(exc)
    message.content = reason
    message.tool_steps_json = [
        {"tool": "resume_optimization_background", "status": "failed", "text": f"failed: {reason}"}
    ]
    message.result_cards_json = []
    meta = dict(message.meta_json or {})
    meta.update(
        {
            "reply_mode": "brief",
            "reply_blocks": [{"type": "summary", "text": reason}],
            "file_task": {
                "type": "optimize_resume",
                "status": "failed",
                "failure_reason": reason,
                "background": True,
                "background_job_id": str(job.get("id") or ""),
            },
            "artifacts": [],
            "background_job": _public_job(job, status="failed", error=reason),
        }
    )
    message.meta_json = meta
    session_id = _to_int(job.get("session_id"))
    user_id = _to_int(job.get("user_id"))
    if session_id and user_id:
        session = (
            db.query(AssistantSession)
            .filter(AssistantSession.id == session_id, AssistantSession.user_id == user_id, AssistantSession.deleted.is_(False))
            .first()
        )
        if session:
            session.last_message = reason[:500]
    db.commit()


def _public_job(job: dict[str, Any], *, status: str | None = None, error: str = "") -> dict[str, Any]:
    public = {
        "id": str(job.get("id") or ""),
        "type": str(job.get("type") or "resume_optimization"),
        "status": str(status or job.get("status") or "running"),
        "phase": str(status or job.get("phase") or job.get("status") or "running"),
        "message": str(job.get("message") or "正在后台优化简历，我会在这条消息中自动更新最终优化稿。"),
        "message_id": _to_int(job.get("message_id")),
        "session_id": _to_int(job.get("session_id")),
        "started_at": str(job.get("started_at") or ""),
        "finished_at": datetime.now().isoformat(timespec="seconds") if status in {"done", "failed"} else "",
    }
    if error:
        public["error"] = error
    return public


def _friendly_failure_reason(exc: Exception) -> str:
    raw = str(exc or "").strip()
    if raw.startswith("Word 文档生成失败") and not _looks_internal_failure(raw):
        return raw
    if "renderer test failed:" in raw:
        raw = raw.replace("renderer test failed:", "").strip() or "文档渲染自检失败。"
    if "DOCX render command failed:" in raw:
        raw = raw.replace("DOCX render command failed:", "").strip() or "文档渲染命令失败。"
    if _looks_internal_failure(raw):
        return "Word 文档生成失败：渲染脚本执行异常，已停止导出。请重新发起“优化并导出 Word”。"
    return f"简历优化或 Word 导出失败：{raw or '后台任务处理异常。'}"


def _looks_internal_failure(raw: str) -> bool:
    lowered = str(raw or "").lower()
    return any(
        token in lowered
        for token in (
            "traceback",
            "nameerror",
            "runtimeerror",
            "valueerror",
            "keyerror",
            "typeerror",
            "file \"",
            "line ",
            "stack",
        )
    )


def _result_cards(result: dict[str, Any]) -> list[dict[str, Any]]:
    cards = result.get("cards") if isinstance(result.get("cards"), list) else []
    if cards:
        return [dict(item) for item in cards if isinstance(item, dict)]

    fallback_cards: list[dict[str, Any]] = []
    for item in list(result.get("tool_outputs") or []):
        if not isinstance(item, dict):
            continue
        card = item.get("card") if isinstance(item.get("card"), dict) else {}
        if card.get("type"):
            fallback_cards.append(dict(card))
    return fallback_cards


def _to_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed or None


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return value
