from __future__ import annotations

from copy import deepcopy
from typing import Any


class AssistantSessionStateService:
    @staticmethod
    def normalize_state(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return deepcopy(value)
        return {}

    @staticmethod
    def merge(
        current_state: dict[str, Any] | None,
        *,
        context_binding: dict[str, Any] | None = None,
        context_patch: dict[str, Any] | None = None,
        selected_skill: str | None = None,
    ) -> dict[str, Any]:
        merged = AssistantSessionStateService.normalize_state(current_state)
        patch = deepcopy(context_patch or {})

        if context_binding is not None:
            merged["context_binding"] = deepcopy(context_binding)

        if selected_skill:
            merged["last_skill"] = selected_skill
            merged["current_skill"] = selected_skill

        if patch:
            merged.update(patch)
            if isinstance(patch.get("context_binding"), dict):
                merged["context_binding"] = deepcopy(patch["context_binding"])

        binding = merged.get("context_binding") or {}
        slots = patch.get("slots") if isinstance(patch.get("slots"), dict) else {}

        current_target_job = (
            slots.get("target_job")
            or AssistantSessionStateService._pick(binding, ["target_job", "target_job_name"])
            or AssistantSessionStateService._pick(binding.get("target_job") if isinstance(binding.get("target_job"), dict) else {}, ["name", "title"])
        )
        current_target_city = slots.get("target_city") or AssistantSessionStateService._pick(binding, ["target_city"])
        current_target_industry = slots.get("target_industry") or AssistantSessionStateService._pick(binding, ["target_industry"])

        resume_payload = binding.get("resume") if isinstance(binding.get("resume"), dict) else {}
        current_resume_id = (
            slots.get("resume_id")
            or AssistantSessionStateService._to_int(binding.get("resume_id"))
            or AssistantSessionStateService._to_int(resume_payload.get("resume_id"))
            or AssistantSessionStateService._to_int(resume_payload.get("id"))
        )
        current_resume_version_id = (
            slots.get("resume_version_id")
            or AssistantSessionStateService._to_int(binding.get("resume_version_id"))
            or AssistantSessionStateService._to_int(resume_payload.get("resume_version_id"))
            or AssistantSessionStateService._to_int(resume_payload.get("current_version_id"))
        )

        current_focus = slots.get("current_focus") or patch.get("last_analysis_focus")

        if current_target_job:
            merged["current_target_job"] = current_target_job
        if current_target_city:
            merged["current_target_city"] = current_target_city
        if current_target_industry:
            merged["current_target_industry"] = current_target_industry
        if current_resume_id:
            merged["current_resume_id"] = current_resume_id
        if current_resume_version_id:
            merged["current_resume_version_id"] = current_resume_version_id
        if current_focus:
            merged["last_analysis_focus"] = current_focus

        career_preferences = patch.get("career_preferences") if isinstance(patch.get("career_preferences"), dict) else None
        if career_preferences:
            merged["career_preferences"] = career_preferences

        if current_target_job:
            career_pref = merged.get("career_preferences") or {}
            if not isinstance(career_pref, dict):
                career_pref = {}
            history_jobs = career_pref.get("target_job_history") or []
            if current_target_job not in history_jobs:
                history_jobs.append(current_target_job)
            career_pref["target_job_history"] = history_jobs[-5:]
            career_pref["last_target_job"] = current_target_job
            merged["career_preferences"] = career_pref

        if patch.get("last_intent"):
            merged["last_intent"] = patch.get("last_intent")

        current_stage = patch.get("conversation_stage")
        if current_stage:
            merged["conversation_stage"] = current_stage
        elif not merged.get("conversation_stage"):
            merged["conversation_stage"] = "greeting"

        if patch.get("intent") in ["career_exploration", "gap_analysis", "growth_planning"]:
            if merged.get("conversation_stage") == "greeting":
                merged["conversation_stage"] = "exploring"

        if patch.get("target_job"):
            merged["last_topic"] = patch.get("target_job")
            merged["last_target_job"] = patch.get("target_job")

        return merged

    @staticmethod
    def _pick(payload: dict[str, Any], keys: list[str]) -> str:
        if not isinstance(payload, dict):
            return ""
        for key in keys:
            if payload.get(key):
                return str(payload.get(key)).strip()
        return ""

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def get_inherited_context(merged: dict[str, Any]) -> dict[str, Any]:
        """获取应继承的上下文信息用于新对话"""
        career_pref = merged.get("career_preferences") or {}
        return {
            "last_target_job": career_pref.get("last_target_job"),
            "target_job_history": career_pref.get("target_job_history") or [],
            "last_intent": merged.get("last_intent"),
            "last_skill": merged.get("last_skill"),
        }

    @staticmethod
    def advance_conversation_stage(current_stage: str, event: str) -> str:
        """根据事件推进对话阶段

        Stages: greeting -> exploring -> confirming -> executing -> closing
        """
        stage_flow = {
            "greeting": {
                "user_expressed_intent": "exploring",
                "user_gave_info": "exploring",
            },
            "exploring": {
                "user_confirmed": "confirming",
                "user_clarified": "exploring",
                "user_declared_topic": "exploring",
            },
            "confirming": {
                "user_confirmed": "executing",
                "user_changed_topic": "greeting",
            },
            "executing": {
                "task_complete": "closing",
                "user_continued": "executing",
            },
            "closing": {
                "new_message": "greeting",
            },
        }

        return stage_flow.get(current_stage, {}).get(event, current_stage)
