from __future__ import annotations

from app.services.assistant_plan_service import AssistantPlanService
from app.services.assistant_slot_service import AssistantSlotService


STALE_PROFILE_STATE = {"current_skill": "profile-image", "last_skill": "profile-image"}


def _plan_for(message: str, *, intent: str, selected_skill: str = "profile-image") -> dict:
    slots = AssistantSlotService().extract(
        message=message,
        selected_skill=selected_skill,
        session_state=STALE_PROFILE_STATE,
        client_state={"selected_skill": selected_skill},
    )
    return AssistantPlanService().build(
        role="student",
        message=message,
        intent=intent,
        slots=slots,
        selected_skill=selected_skill,
        fallback_skill=selected_skill,
        session_state=STALE_PROFILE_STATE,
        context_binding={},
    )


def test_growth_path_overrides_stale_profile_image_skill() -> None:
    message = "\u6211\u7684\u63a8\u8350\u804c\u4e1a\u662fJava\u5f00\u53d1\u5de5\u7a0b\u5e08\uff0c\u8bf7\u4f60\u4e3a\u6211\u89c4\u5212\u4e00\u4e2a\u6210\u957f\u8def\u5f84"

    plan = _plan_for(message, intent="ask_plan")

    assert plan["normalized_skill"] == "growth-planner"
    assert plan["tool_plan"] == ["generate_growth_path"]


def test_explicit_profile_image_request_keeps_profile_image_skill() -> None:
    message = "\u8bf7\u5e2e\u6211\u751f\u6210\u4e00\u5f20\u804c\u4e1a\u753b\u50cf\u56fe"

    plan = _plan_for(message, intent="execute", selected_skill="")

    assert plan["normalized_skill"] == "profile-image"
    assert plan["tool_plan"] == ["generate_profile_image"]


def test_job_match_request_overrides_stale_profile_image_skill() -> None:
    message = "\u6211\u7684\u76ee\u6807\u5c97\u4f4d\u662f\u4ea7\u54c1\u7ecf\u7406\uff0c\u770b\u770b\u9002\u5408\u54ea\u4e9b\u5c97\u4f4d"

    plan = _plan_for(message, intent="ask_advice")

    assert plan["normalized_skill"] == "match-center"
    assert plan["tool_plan"] == ["generate_matches"]
