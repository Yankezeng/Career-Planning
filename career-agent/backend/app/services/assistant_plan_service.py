from __future__ import annotations

from typing import Any

from app.services.assistant_profile_intent import is_profile_image_intent, is_profile_insight_intent
from app.services.assistant_skill_catalog_service import get_skill_definition, normalize_skill_code
from app.services.assistant_turn_intent_guard import (
    has_explicit_continue_request,
    infer_explicit_student_skill,
    is_profile_image_skill,
)


class AssistantPlanService:
    RETRIEVAL_SKILLS = {"match-center", "gap-analysis", "growth-planner", "report-builder", "profile-image"}
    DEEP_TOKENS = ["详细", "展开", "完整", "深入", "分步骤", "深度"]

    def build(
        self,
        *,
        role: str,
        message: str,
        intent: str,
        slots: dict[str, Any],
        selected_skill: str | None,
        fallback_skill: str,
        session_state: dict[str, Any] | None = None,
        context_binding: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        text = str(message or "").strip()
        session_state = session_state or {}
        context_binding = context_binding or {}

        if intent == "small_talk":
            return {
                "intent": "small_talk",
                "selected_skill": "general-chat",
                "normalized_skill": "general-chat",
                "steps": [{"step": 1, "tool": "general-chat", "purpose": "轻量回复"}],
                "tool_plan": [],
                "need_retrieval": False,
                "reply_mode": "brief",
                "small_talk": True,
                "required_bindings": [],
                "slots": slots,
            }

        explicit_skill = infer_explicit_student_skill(
            text,
            slots=slots,
            intent_info={"intent": intent, "extracted_job": slots.get("target_job")},
        )
        selected_candidate = selected_skill or slots.get("selected_skill") or fallback_skill or ""
        allow_carryover = bool(slots.get("continue_previous_task")) or has_explicit_continue_request(text)
        safe_fallback_skill = fallback_skill
        if not allow_carryover and is_profile_image_skill(fallback_skill) and not self._is_profile_image_task(text):
            safe_fallback_skill = ""

        if role == "student" and explicit_skill:
            normalized_selected = explicit_skill
        elif not allow_carryover and is_profile_image_skill(selected_candidate) and not self._is_profile_image_task(text):
            normalized_selected = normalize_skill_code(safe_fallback_skill, role)
        else:
            normalized_selected = normalize_skill_code(selected_candidate, role)
        if normalized_selected == "general-chat":
            carry_skill = session_state.get("current_skill") if allow_carryover else ""
            normalized_selected = normalize_skill_code(carry_skill or safe_fallback_skill or "general-chat", role)
        if normalized_selected == "general-chat":
            normalized_selected = self._guess_skill_from_slots(role, slots)

        need_retrieval = normalized_selected in self.RETRIEVAL_SKILLS
        composite = self._is_composite_task(text)
        tool_plan = list(get_skill_definition(normalized_selected).get("tools") or [])

        if self._is_profile_image_task(text):
            normalized_selected = "profile-image"
            tool_plan = ["generate_profile_image"]
            need_retrieval = True
        elif self._is_profile_insight_task(text):
            normalized_selected = "profile-insight"
            tool_plan = ["ingest_resume_attachment", "generate_profile"]
            need_retrieval = False

        if intent == "follow_up" and slots.get("continue_previous_task") and session_state.get("last_plan"):
            previous_tool_plan = list((session_state.get("last_plan") or {}).get("tool_plan") or [])
            if previous_tool_plan:
                tool_plan = previous_tool_plan
                normalized_selected = normalize_skill_code((session_state.get("last_plan") or {}).get("normalized_skill"), role)

        if composite and normalized_selected != "profile-image":
            tool_plan = ["generate_profile", "generate_matches", "generate_gap_analysis", "generate_growth_path"]
            need_retrieval = True

        if intent == "switch_skill" and slots.get("selected_skill"):
            normalized_selected = normalize_skill_code(slots.get("selected_skill"), role)
            tool_plan = list(get_skill_definition(normalized_selected).get("tools") or [])

        if self._is_profile_image_task(text):
            normalized_selected = "profile-image"
            tool_plan = ["generate_profile_image"]
            need_retrieval = True
        elif self._is_profile_insight_task(text) and not composite:
            normalized_selected = "profile-insight"
            tool_plan = ["ingest_resume_attachment", "generate_profile"]
            need_retrieval = False

        if intent in {"ask_fact", "ask_advice"} and normalized_selected == "general-chat" and slots.get("continue_previous_task"):
            normalized_selected = normalize_skill_code(session_state.get("current_skill") or "general-chat", role)
            tool_plan = list(get_skill_definition(normalized_selected).get("tools") or [])

        missing_slots = self._missing_slots(intent=intent, skill=normalized_selected, slots=slots)
        if missing_slots:
            return {
                "intent": "clarify_required",
                "selected_skill": normalized_selected,
                "normalized_skill": normalized_selected,
                "steps": [{"step": 1, "tool": "clarify", "purpose": "追问关键槽位"}],
                "tool_plan": [],
                "need_retrieval": False,
                "reply_mode": "brief",
                "small_talk": False,
                "required_bindings": list(context_binding.keys()),
                "slots": slots,
                "missing_slots": missing_slots,
                "clarify_question": self._clarify_question(missing_slots),
            }

        steps: list[dict[str, Any]] = []
        step_no = 1
        if need_retrieval:
            steps.append({"step": step_no, "tool": "job_kb_search", "purpose": "检索岗位知识库"})
            step_no += 1
        for tool in tool_plan:
            steps.append({"step": step_no, "tool": tool, "purpose": "执行业务步骤"})
            step_no += 1
        if not steps:
            steps = [{"step": 1, "tool": "general-chat", "purpose": "通用问答"}]

        return {
            "intent": intent,
            "selected_skill": normalized_selected,
            "normalized_skill": normalized_selected,
            "steps": steps,
            "tool_plan": tool_plan,
            "need_retrieval": need_retrieval,
            "reply_mode": self._reply_mode(text),
            "small_talk": False,
            "required_bindings": list(context_binding.keys()),
            "slots": slots,
        }

    @staticmethod
    def _guess_skill_from_slots(role: str, slots: dict[str, Any]) -> str:
        if role != "student":
            return "general-chat"
        if slots.get("resume_id"):
            return "resume-workbench"
        if slots.get("target_job"):
            return "match-center"
        if slots.get("target_city"):
            return "gap-analysis"
        return "general-chat"

    @staticmethod
    def _missing_slots(*, intent: str, skill: str, slots: dict[str, Any]) -> list[str]:
        if intent not in {"ask_plan", "ask_advice", "execute", "compare", "refine"}:
            return []
        if slots.get("continue_previous_task"):
            return []
        if skill in {"match-center", "gap-analysis", "growth-planner", "delivery-ready"} and not slots.get("target_job"):
            return ["target_job"]
        return []

    @staticmethod
    def _clarify_question(missing_slots: list[str]) -> str:
        if "target_job" in missing_slots:
            return "你想按哪个目标岗位继续分析？"
        return "我还缺少关键信息，先补充一下再继续。"

    def _reply_mode(self, text: str) -> str:
        if any(token in text for token in self.DEEP_TOKENS):
            return "deep"
        return "structured"

    @staticmethod
    def _is_composite_task(text: str) -> bool:
        return all(token in text for token in ["画像", "成长", "岗位"]) or all(token in text for token in ["缺什么", "先补", "步骤"])

    @staticmethod
    def _is_profile_image_task(text: str) -> bool:
        return is_profile_image_intent(text)

    @staticmethod
    def _is_profile_insight_task(text: str) -> bool:
        return is_profile_insight_intent(text)
