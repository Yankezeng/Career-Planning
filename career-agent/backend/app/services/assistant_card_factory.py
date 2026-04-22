from __future__ import annotations

from typing import Any


class AssistantCardFactory:
    TOOL_CARD_TYPE_MAP = {
        "profile_insight": "profile_card",
        "generate_profile": "profile_card",
        "match_center": "match_card",
        "generate_matches": "match_card",
        "generate_gap_analysis": "gap_card",
        "generate_growth_path": "growth_card",
        "generate_report": "report_card",
        "resume_workbench": "resume_card",
        "optimize_resume": "resume_card",
        "rank_candidates": "candidate_rank_card",
        "generate_interview_questions": "interview_question_card",
        "summarize_admin_metrics": "metrics_card",
        "prepare_delivery": "action_checklist_card",
    }

    def build_from_tool_output(self, tool_output: dict[str, Any]) -> dict[str, Any] | None:
        tool = str(tool_output.get("tool") or "")
        if tool == "generate_profile_image":
            return None
        data = tool_output.get("data") or {}
        card = tool_output.get("card")
        if isinstance(card, dict) and card.get("type") == "profile_image_card":
            return None
        if isinstance(card, dict) and card.get("type"):
            return card
        return {
            "type": self.TOOL_CARD_TYPE_MAP.get(tool, "action_checklist_card"),
            "tool": tool,
            "title": tool_output.get("title") or "分析结果",
            "summary": tool_output.get("summary") or "",
            "data": data,
        }

    def build_many(self, tool_outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        for item in tool_outputs:
            if not isinstance(item, dict):
                continue
            card = self.build_from_tool_output(item)
            if card:
                cards.append(card)
        return cards
