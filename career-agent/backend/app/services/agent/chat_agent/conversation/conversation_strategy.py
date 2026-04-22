from __future__ import annotations

from enum import Enum
from typing import Any

from app.services.agent.chat_agent.conversation.nlg_service import get_nlg_service
from app.services.llm_service import get_llm_service


class ConversationStrategyType(Enum):
    NEED_MORE_INFO = "need_more_info"
    NEED_CONFIRMATION = "need_confirmation"
    READY_TO_EXECUTE = "ready_to_execute"
    NEED_EXPLANATION = "need_explanation"
    FOLLOW_UP = "follow_up"
    GENERAL_CHAT = "general_chat"
    GREETING = "greeting"
    EXECUTE = "execute"


class ConversationStrategy:
    def __init__(self):
        self.llm_service = get_llm_service()
        self.nlg_service = get_nlg_service()

    def decide(
        self,
        intent: str,
        slots: dict[str, Any],
        confidence: float | None = None,
        session_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session_state = session_state or {}

        if intent in {"clarify_required", "clarify"}:
            return self._need_more_info_strategy(slots)
        if intent == "small_talk":
            return self._general_chat_strategy(session_state)
        if intent == "follow_up":
            return self._follow_up_strategy(session_state)
        if confidence is not None and confidence < 0.7:
            return self._need_confirmation_strategy(intent, slots)

        missing_slots = self._check_missing_slots(slots)
        if missing_slots:
            return self._need_more_info_strategy(slots, missing_slots)

        if intent in {"execute", "generate", "create", "optimize", "deliver"}:
            return self._ready_to_execute_strategy(intent, slots)
        if intent in {"ask_fact", "compare"}:
            return self._need_explanation_strategy(intent, slots)
        return self._general_chat_strategy(session_state)

    def _need_more_info_strategy(
        self,
        slots: dict[str, Any],
        missing: list[str] | None = None,
    ) -> dict[str, Any]:
        missing = missing or self._check_missing_slots(slots)

        if not missing:
            if slots.get("target_job"):
                return {
                    "strategy": ConversationStrategyType.NEED_CONFIRMATION.value,
                    "clarify_question": self.nlg_service.generate_career_acknowledgment(
                        str(slots.get("target_job") or ""),
                        {"slots": slots},
                    ),
                    "missing_slots": [],
                    "reply_mode": "brief",
                }
            user_message = str(slots.get("user_message") or "")
            negative_keywords = ["没目标", "不知道", "不确定", "迷茫", "not sure", "no idea"]
            if user_message and any(keyword in user_message.lower() for keyword in [k.lower() for k in negative_keywords]):
                return {
                    "strategy": ConversationStrategyType.GREETING.value,
                    "reply": self.nlg_service.acknowledge_negative(user_message, {"slots": slots}),
                    "reply_mode": "brief",
                }
            return {
                "strategy": ConversationStrategyType.NEED_MORE_INFO.value,
                "reply": self.nlg_service.guide_user([], {"slots": slots}),
                "missing_slots": [],
                "reply_mode": "brief",
            }

        slot_labels = {
            "target_job": "target job",
            "target_city": "target city",
            "target_industry": "target industry",
            "target_skill": "target skill",
        }
        missing_labels = [slot_labels.get(item, item) for item in missing[:2]]

        if len(missing_labels) == 1:
            clarify = f"Please share your {missing_labels[0]} so I can give more precise guidance."
        else:
            clarify = f"Please share your {missing_labels[0]} and {missing_labels[1]} so I can give more precise guidance."

        return {
            "strategy": ConversationStrategyType.NEED_MORE_INFO.value,
            "clarify_question": clarify,
            "missing_slots": missing,
            "reply_mode": "brief",
        }

    def _need_confirmation_strategy(
        self,
        intent: str,
        slots: dict[str, Any],
    ) -> dict[str, Any]:
        _ = intent
        target_job = str(slots.get("target_job") or "your target role")
        target_city = str(slots.get("target_city") or "").strip()

        confirm_question = f"Do you want guidance for {target_job}"
        if target_city:
            confirm_question += f" in {target_city}"
        confirm_question += "?"

        return {
            "strategy": ConversationStrategyType.NEED_CONFIRMATION.value,
            "clarify_question": confirm_question,
            "reply_mode": "brief",
        }

    def _ready_to_execute_strategy(
        self,
        intent: str,
        slots: dict[str, Any],
    ) -> dict[str, Any]:
        intent_labels = {
            "execute": "handle",
            "generate": "generate",
            "create": "create",
            "optimize": "optimize",
            "deliver": "prepare",
        }
        action = intent_labels.get(intent, "handle")
        target = str(slots.get("target_job") or "your request")
        return {
            "strategy": ConversationStrategyType.READY_TO_EXECUTE.value,
            "message": f"Understood. I will {action} content related to {target}.",
            "reply_mode": "structured",
            "skip_clarify": True,
        }

    def _need_explanation_strategy(
        self,
        intent: str,
        slots: dict[str, Any],
    ) -> dict[str, Any]:
        _ = (intent, slots)
        return {
            "strategy": ConversationStrategyType.NEED_EXPLANATION.value,
            "reply_mode": "detailed",
            "format": "structured",
        }

    def _follow_up_strategy(
        self,
        session_state: dict[str, Any],
    ) -> dict[str, Any]:
        last_focus = session_state.get("last_analysis_focus")
        career_pref = session_state.get("career_preferences") or {}
        last_target_job = career_pref.get("last_target_job") if isinstance(career_pref, dict) else None

        continue_topic = last_focus or (f"{last_target_job} gap analysis" if last_target_job else "")
        if continue_topic and "gap" in str(continue_topic).lower():
            role_text = str(last_target_job or "the target role")
            return {
                "strategy": ConversationStrategyType.EXECUTE.value,
                "continue_topic": continue_topic,
                "last_target_job": last_target_job,
                "reply_mode": "structured",
                "reply": f"Great, let's continue the gap analysis for {role_text}. What relevant skills or experience do you have now?",
            }

        return {
            "strategy": ConversationStrategyType.FOLLOW_UP.value,
            "continue_topic": continue_topic,
            "last_target_job": last_target_job,
            "reply_mode": "detailed",
        }

    def _general_chat_strategy(
        self,
        session_state: dict[str, Any],
    ) -> dict[str, Any]:
        _ = session_state
        return {
            "strategy": ConversationStrategyType.GENERAL_CHAT.value,
            "reply_mode": "brief",
        }

    def _greeting_strategy(
        self,
        session_state: dict[str, Any],
    ) -> dict[str, Any]:
        last_topic = session_state.get("last_topic")
        return {
            "strategy": ConversationStrategyType.GREETING.value,
            "reply": self.nlg_service.generate_greeting({"last_topic": last_topic}),
            "reply_mode": "brief",
        }

    def _check_missing_slots(self, slots: dict[str, Any]) -> list[str]:
        required_slots = ["target_job"]
        missing: list[str] = []
        for slot in required_slots:
            value = slots.get(slot)
            if not value or (isinstance(value, str) and not value.strip()):
                missing.append(slot)
        return missing

    def generate_clarify_question(
        self,
        intent: str,
        slots: dict[str, Any],
    ) -> str:
        result = self.decide(intent, slots)
        return str(result.get("clarify_question") or "Please share more details.")

    def get_reply_mode(self, strategy: str) -> str:
        strategy_reply_mode_map = {
            ConversationStrategyType.NEED_MORE_INFO.value: "brief",
            ConversationStrategyType.NEED_CONFIRMATION.value: "brief",
            ConversationStrategyType.READY_TO_EXECUTE.value: "structured",
            ConversationStrategyType.NEED_EXPLANATION.value: "detailed",
            ConversationStrategyType.FOLLOW_UP.value: "detailed",
            ConversationStrategyType.GENERAL_CHAT.value: "brief",
            ConversationStrategyType.GREETING.value: "brief",
            ConversationStrategyType.EXECUTE.value: "structured",
        }
        return strategy_reply_mode_map.get(strategy, "structured")


def get_conversation_strategy() -> ConversationStrategy:
    return ConversationStrategy()

