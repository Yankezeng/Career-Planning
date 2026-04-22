import json
from queue import Empty, Queue
from threading import Thread

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.deps import get_current_user, get_db
from app.models.auth import User
from app.schemas.assistant import ChatRequest, SessionCreateRequest, SessionUpdateRequest
from app.services.assistant_fallback_service import build_career_guidance_fallback
from app.services.assistant_profile_intent import is_profile_image_intent
from app.services.assistant_runtime_service import AssistantService
from app.utils.response import success_response


router = APIRouter()


def _sse_event(event: str, data: dict) -> str:
    payload = json.dumps(jsonable_encoder(data), ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _build_chat_error_result(*, requested_skill: str, session_id: int | None, error: Exception) -> dict:
    fallback = build_career_guidance_fallback(
        message="",
        selected_skill=requested_skill,
        reason=str(error),
    )
    error_reply = str(fallback.get("reply") or "这次回答没有完整完成，我先给你一个稳妥建议。")
    return {
        "reply": error_reply,
        "reply_mode": "brief",
        "reply_blocks": fallback.get("reply_blocks") or [{"type": "summary", "text": error_reply}],
        "tool_steps": [],
        "cards": [],
        "actions": fallback.get("actions") or [],
        "knowledge_hits": [],
        "context_binding": fallback.get("context_binding") or {},
        "session_state": fallback.get("session_state") or {},
        "used_skill": requested_skill,
        "normalized_skill": requested_skill,
        "session_id": session_id,
        "agent_route": "error",
        "requires_user_input": False,
        "artifacts": [],
        "file_task": {},
        "code_task": {},
        "agent_flow": [],
        "supervisor_plan": {},
        "dispatch_trace": {},
        "decision_trace": [],
        "error": fallback.get("error_message") or "复杂问题已自动切换为稳妥建议模式。",
    }


def _is_profile_image_request(payload: ChatRequest, requested_skill: str) -> bool:
    skill = str(requested_skill or payload.skill or "").strip().lower().replace("_", "-")
    if skill in {"profile-image", "profile_image", "persona-image", "persona_image", "cbti", "mbti"}:
        return True
    return is_profile_image_intent(payload.message)


def _run_chat_for_stream(
    *,
    output: Queue,
    user_id: int,
    payload: ChatRequest,
    history: list[dict],
) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id, User.deleted.is_(False)).first()
        if not user:
            raise RuntimeError("current user not found")
        result = AssistantService(db).chat(
            user,
            payload.message,
            history,
            payload.skill,
            payload.session_id,
            payload.context_binding,
            payload.client_state,
            payload.options,
        )
        output.put(("result", result))
    except Exception as exc:
        output.put(("error", exc))
    finally:
        db.close()


def _stream_chat_events(
    *,
    service: AssistantService,
    current_user,
    payload: ChatRequest,
    history: list[dict],
    requested_skill: str,
):
    yield _sse_event(
        "meta",
        {
            "session_id": payload.session_id,
            "used_skill": requested_skill,
            "normalized_skill": requested_skill,
            "agent_route": "chat",
            "agent_flow": [],
            "supervisor_plan": {},
            "dispatch_trace": {},
            "decision_trace": [],
        },
    )
    yield _sse_event(
        "progress",
        {
            "phase": "accepted",
            "status": "running",
            "message": "已收到问题，正在准备回答。",
        },
    )
    try:
        yield _sse_event(
            "progress",
            {
                "phase": "agent_workflow",
                "status": "running",
                "message": "正在分析问题并组织回复。",
            },
        )
        output: Queue = Queue(maxsize=1)
        worker = Thread(
            target=_run_chat_for_stream,
            kwargs={
                "output": output,
                "user_id": int(current_user.id),
                "payload": payload,
                "history": history,
            },
            daemon=True,
        )
        worker.start()
        while True:
            try:
                event_type, value = output.get(timeout=8)
            except Empty:
                yield _sse_event(
                    "progress",
                    {
                        "phase": "agent_workflow",
                        "status": "running",
                        "message": "任务仍在处理中，正在保持连接...",
                    },
                )
                continue
            if event_type == "error":
                raise value
            result = value
            break
    except Exception as exc:
        if _is_profile_image_request(payload, requested_skill):
            raise
        result = _build_chat_error_result(requested_skill=requested_skill, session_id=payload.session_id, error=exc)
        yield _sse_event(
            "error",
            {
                "phase": "agent_workflow",
                "status": "failed",
                "message": "深度分析没有完整完成，已切换为稳妥建议模式。",
                "error": "复杂问题已自动切换为稳妥建议模式。",
                "session_id": payload.session_id,
            },
        )

    yield _sse_event(
        "meta",
        {
            "session_id": result.get("session_id"),
            "used_skill": result.get("used_skill"),
            "normalized_skill": result.get("normalized_skill"),
            "agent_route": result.get("agent_route"),
            "agent_flow": result.get("agent_flow"),
            "supervisor_plan": result.get("supervisor_plan"),
            "dispatch_trace": result.get("dispatch_trace"),
            "decision_trace": result.get("decision_trace"),
        },
    )
    yield _sse_event(
        "progress",
        {
            "phase": "responding",
            "status": "running" if not result.get("error") else "failed",
            "message": "正在返回降级建议。" if result.get("error") else "正在生成回复。",
        },
    )
    reply = str(result.get("reply") or "")
    chunk_size = 18
    for index in range(0, len(reply), chunk_size):
        yield _sse_event("delta", {"text": reply[index:index + chunk_size]})
    yield _sse_event(
        "progress",
        {
            "phase": "done",
            "status": "failed" if result.get("error") else "done",
            "message": "已返回稳妥建议。" if result.get("error") else "回复已完成。",
        },
    )
    yield _sse_event("done", result)


@router.get("/welcome")
def welcome(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return success_response(AssistantService(db).build_welcome(current_user))


@router.get("/summary")
def summary(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return success_response(AssistantService(db).build_summary(current_user))


@router.get("/search")
def search(q: str = Query("", alias="q"), db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return success_response(AssistantService(db).build_search(current_user, q))


@router.get("/assets")
def assets(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return success_response(AssistantService(db).build_assets(current_user))


@router.get("/gallery")
def gallery(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return success_response(AssistantService(db).build_gallery(current_user))


@router.get("/skills")
def skills(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return success_response(AssistantService(db).build_skills(current_user))


@router.get("/sessions")
def sessions(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return success_response({"items": AssistantService(db).list_sessions(current_user.id)})


@router.post("/sessions")
def create_session(payload: SessionCreateRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return success_response(AssistantService(db).create_session(current_user.id, payload.title))


@router.patch("/sessions/{session_id}")
def update_session(
    session_id: int,
    payload: SessionUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return success_response(AssistantService(db).update_session(current_user.id, session_id, payload.model_dump(exclude_none=True)))


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    AssistantService(db).delete_session(current_user.id, session_id)
    return success_response(message="删除成功")


@router.get("/sessions/{session_id}/messages")
def session_messages(session_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return success_response({"items": AssistantService(db).list_session_messages(current_user.id, session_id)})


@router.get("/artifacts/{attachment_id}/download")
def download_artifact(attachment_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    payload = AssistantService(db).resolve_artifact_download(user_id=current_user.id, attachment_id=attachment_id)
    return FileResponse(
        path=payload["path"],
        filename=payload["file_name"],
        media_type=payload["media_type"],
        content_disposition_type="attachment",
    )


@router.post("/chat")
def chat(payload: ChatRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    service = AssistantService(db)
    history = [item.model_dump() for item in payload.history]
    requested_skill = str(payload.skill or "")
    return StreamingResponse(
        _stream_chat_events(
            service=service,
            current_user=current_user,
            payload=payload,
            history=history,
            requested_skill=requested_skill,
        ),
        media_type="text/event-stream",
    )
