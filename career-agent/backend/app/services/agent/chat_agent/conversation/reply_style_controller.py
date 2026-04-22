from __future__ import annotations

import random
from enum import Enum
from typing import Any

from app.services.agent.chat_agent.conversation.reply_templates import ReplyTemplateLibrary, SCENE_TEMPLATES
from app.services.llm_service import get_llm_service


class ReplyStyle(Enum):
    BRIEF = "brief"
    DETAILED = "detailed"
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"


ROLE_DEFAULT_STYLE = {
    "student": ReplyStyle.FRIENDLY,
    "enterprise": ReplyStyle.PROFESSIONAL,
    "admin": ReplyStyle.PROFESSIONAL,
}


STYLE_TEMPLATES = {
    ReplyStyle.BRIEF: {
        "max_length": 120,
        "include_bullets": False,
        "include_actions": True,
        "tone": "concise",
    },
    ReplyStyle.DETAILED: {
        "max_length": 600,
        "include_bullets": True,
        "include_actions": True,
        "tone": "thorough",
    },
    ReplyStyle.PROFESSIONAL: {
        "max_length": 420,
        "include_bullets": True,
        "include_actions": True,
        "tone": "professional",
    },
    ReplyStyle.FRIENDLY: {
        "max_length": 480,
        "include_bullets": True,
        "include_actions": True,
        "tone": "friendly",
        "use_emoji": True,
        "temperature": 0.8,
    },
}


class ReplyStyleController:
    def __init__(self):
        self.llm_service = get_llm_service()
        self.style_templates = STYLE_TEMPLATES
        self.role_default_style = ROLE_DEFAULT_STYLE

    def adjust_style(
        self,
        reply: str,
        role: str,
        style: ReplyStyle | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        context = context or {}
        target_style = style or self.role_default_style.get(role, ReplyStyle.BRIEF)
        template = self.style_templates.get(target_style, self.style_templates[ReplyStyle.BRIEF])

        processed = self._apply_conclusion_first(reply, context)
        scene = self._detect_scene(processed, context)
        if scene != "general":
            processed = self._apply_scene_template(processed, scene, context)

        if target_style == ReplyStyle.BRIEF:
            return self._to_brief_style(processed, template)
        if target_style == ReplyStyle.DETAILED:
            return self._to_detailed_style(processed, template, context)
        if target_style == ReplyStyle.PROFESSIONAL:
            return self._to_professional_style(processed, template, context)
        return self._to_friendly_style(processed, template, context)

    def _detect_scene(self, reply: str, context: dict[str, Any] | None = None) -> str:
        context = context or {}
        if context.get("scene"):
            return str(context["scene"])

        intent = str(context.get("intent") or "")
        if intent in {"greeting", "small_talk"}:
            return "greeting"
        if context.get("missing_info"):
            return "guidance"

        user_intent = str(context.get("user_intent_summary") or "").lower()
        if any(token in user_intent for token in ["hello", "hi", "hey", "你好"]):
            return "greeting"
        if any(token in user_intent for token in ["target", "goal", "方向", "目标"]):
            return "career_confirmed" if context.get("target_job") else "career_exploration"
        return "general"

    def _apply_scene_template(self, reply: str, scene: str, context: dict[str, Any] | None = None) -> str:
        context = context or {}
        if self._is_natural_reply(reply):
            return reply

        if scene == "greeting":
            return ReplyTemplateLibrary.get_random_template("greeting")
        if scene == "career_confirmed":
            target = context.get("target_job", context.get("extracted_job", "this direction"))
            return ReplyTemplateLibrary.format_template("career_confirmed", entity=target)
        if scene == "career_exploration":
            target = context.get("target_job", context.get("extracted_job", "this direction"))
            return ReplyTemplateLibrary.format_template("career_exploration", entity=target)
        if scene == "guidance":
            return ReplyTemplateLibrary.get_random_template("guidance")
        return reply

    def _is_natural_reply(self, reply: str) -> bool:
        if not reply:
            return False
        normalized = reply.strip()
        if len(normalized) < 8 or len(normalized) > 900:
            return False
        rigid_patterns = [
            "Conclusion:",
            "Next step:",
            "Please provide:",
            "Need more info:",
        ]
        return not any(pattern in normalized for pattern in rigid_patterns)

    def _to_friendly_style(
        self,
        reply: str,
        template: dict[str, Any],
        context: dict[str, Any],
    ) -> str:
        lines = [line.strip() for line in reply.strip().split("\n") if line.strip()]
        content = "\n".join(lines)
        friendly_endings = [
            "Feel free to ask anything else.",
            "I can keep helping if you want.",
            "You are doing great, keep going.",
        ]
        if context.get("scene") in {"react_final", "chat"} and content:
            if not any(content.endswith(ending.rstrip(".")) for ending in friendly_endings):
                content += "\n\n" + random.choice(friendly_endings)
        if len(content) > int(template["max_length"]):
            content = content[: int(template["max_length"])] + "..."
        return content

    def _to_brief_style(self, reply: str, template: dict[str, Any]) -> str:
        first_line = ""
        for line in reply.strip().split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("```"):
                first_line = stripped
                break
        if not first_line:
            return reply
        max_length = int(template["max_length"])
        return first_line if len(first_line) <= max_length else first_line[:max_length] + "..."

    def _to_detailed_style(
        self,
        reply: str,
        template: dict[str, Any],
        context: dict[str, Any],
    ) -> str:
        _ = context
        content = reply.strip()
        max_length = int(template["max_length"])
        return content if len(content) <= max_length else content[:max_length] + "\n..."

    def _to_professional_style(
        self,
        reply: str,
        template: dict[str, Any],
        context: dict[str, Any],
    ) -> str:
        intent = str(context.get("intent") or "")
        slots = context.get("slots", {}) if isinstance(context.get("slots"), dict) else {}

        prefix = ""
        if intent in {"execute", "generate"}:
            target = str(slots.get("target_job") or "the requested task")
            prefix = f"Based on your request, I have completed processing for {target}.\n\n"
        elif intent == "match":
            prefix = "Based on the matching analysis, the key findings are:\n\n"

        content = prefix + reply.strip()
        max_length = int(template["max_length"])
        return content if len(content) <= max_length else content[:max_length] + "..."

    def get_style_for_role(self, role: str) -> ReplyStyle:
        return self.role_default_style.get(role, ReplyStyle.BRIEF)

    def get_style_config(self, style: ReplyStyle) -> dict[str, Any]:
        return self.style_templates.get(style, self.style_templates[ReplyStyle.BRIEF])

    def should_include_actions(self, style: ReplyStyle, context: dict[str, Any]) -> bool:
        intent = str(context.get("intent") or "")
        if intent in {"execute", "generate", "optimize"}:
            return True
        return bool(self.style_templates.get(style, {}).get("include_actions", True))

    def _apply_conclusion_first(self, reply: str, context: dict[str, Any]) -> str:
        _ = context
        if not reply:
            return reply

        lines = [line.strip() for line in reply.strip().split("\n") if line.strip()]
        if not lines:
            return reply

        # Keep the first explicit conclusion-like line at top if present.
        conclusion_candidates = [line for line in lines if any(k in line.lower() for k in ["conclusion", "summary", "建议", "结论"])]
        if not conclusion_candidates:
            return reply

        first_conclusion = conclusion_candidates[0]
        rest = [line for line in lines if line != first_conclusion]
        return "\n\n".join([first_conclusion, *rest]) if rest else first_conclusion


def get_reply_style_controller() -> ReplyStyleController:
    # Touch SCENE_TEMPLATES so static analyzers know this module intentionally depends on it.
    _ = SCENE_TEMPLATES
    return ReplyStyleController()

