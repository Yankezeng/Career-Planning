from __future__ import annotations

import re
from typing import Any

from app.services.assistant_skill_catalog_service import normalize_skill_code
from app.services.assistant_turn_intent_guard import extract_target_job_from_text


class AssistantSlotService:
    CITY_TOKENS = ["上海", "北京", "深圳", "广州", "杭州", "成都", "南京", "苏州", "武汉", "西安", "重庆"]

    def extract(
        self,
        *,
        message: str,
        selected_skill: str | None,
        session_state: dict[str, Any] | None = None,
        context_binding: dict[str, Any] | None = None,
        client_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        text = str(message or "").strip()
        compact = re.sub(r"\s+", "", text)
        session_state = session_state or {}
        context_binding = context_binding or {}
        client_state = client_state or {}

        slots: dict[str, Any] = {
            "target_job": self._extract_target_job(text),
            "target_city": self._extract_target_city(compact),
            "target_industry": self._extract_target_industry(text),
            "resume_id": self._to_int(client_state.get("resume_id")) or self._to_int(context_binding.get("resume_id")),
            "resume_version_id": self._to_int(client_state.get("resume_version_id"))
            or self._to_int(context_binding.get("resume_version_id")),
            "selected_skill": normalize_skill_code(selected_skill or client_state.get("selected_skill") or ""),
            "comparison_target": self._extract_compare_target(text),
            "current_focus": self._extract_focus(text),
            "use_latest_resume": any(token in compact for token in ["最新简历", "最新版本", "用最近那份"]),
            "continue_previous_task": any(token in compact for token in ["继续", "展开", "再看", "再分析", "接着"]) or compact in {"好的", "收到"},
        }

        binding_resume = context_binding.get("resume") if isinstance(context_binding.get("resume"), dict) else {}
        if not slots.get("resume_id"):
            slots["resume_id"] = self._to_int(binding_resume.get("resume_id")) or self._to_int(binding_resume.get("id"))
        if not slots.get("resume_version_id"):
            slots["resume_version_id"] = self._to_int(binding_resume.get("resume_version_id")) or self._to_int(binding_resume.get("current_version_id"))

        self._fill_from_state(slots, session_state)
        self._fill_from_client(slots, client_state)

        return slots

    def _fill_from_state(self, slots: dict[str, Any], state: dict[str, Any]) -> None:
        fallback_map = {
            "target_job": state.get("current_target_job"),
            "target_city": state.get("current_target_city"),
            "target_industry": state.get("current_target_industry"),
            "resume_id": self._to_int(state.get("current_resume_id")),
            "resume_version_id": self._to_int(state.get("current_resume_version_id")),
            "selected_skill": normalize_skill_code(state.get("current_skill") or "")
            if slots.get("continue_previous_task")
            else "",
            "current_focus": state.get("last_analysis_focus"),
        }
        for key, value in fallback_map.items():
            if not slots.get(key) and value:
                slots[key] = value

    def _fill_from_client(self, slots: dict[str, Any], client_state: dict[str, Any]) -> None:
        for key in ["target_job", "target_city", "target_industry"]:
            if not slots.get(key) and client_state.get(key):
                slots[key] = str(client_state.get(key)).strip()

    @staticmethod
    def _extract_target_job(text: str) -> str:
        guarded = extract_target_job_from_text(text)
        if guarded:
            return guarded
        explicit = re.findall(r"(?:按|换成|看|做|走)?([\u4e00-\u9fa5A-Za-z0-9]{2,20})(?:岗位|方向|职位|简历)", text)
        if explicit:
            return explicit[-1]
        compact = re.sub(r"\s+", "", str(text or "")).lower()
        if "java开发" in compact or "java工程师" in compact:
            return "Java开发工程师"
        if "产品经理" in text:
            return "产品经理"
        if "开发" in text and "前端" in text:
            return "前端开发"
        if "后端" in text:
            return "后端开发"
        return ""

    def _extract_target_city(self, compact: str) -> str:
        for city in self.CITY_TOKENS:
            if city in compact:
                return city
        return ""

    @staticmethod
    def _extract_target_industry(text: str) -> str:
        for token in ["互联网", "金融", "制造", "电商", "教育", "医疗", "游戏", "新能源", "半导体"]:
            if token in text:
                return token
        return ""

    @staticmethod
    def _extract_compare_target(text: str) -> str:
        if "对比" not in text and "比较" not in text:
            return ""
        match = re.findall(r"(?:对比|比较)(.+?)(?:和|与|vs|$)", text)
        return match[-1].strip() if match else ""

    @staticmethod
    def _extract_focus(text: str) -> str:
        for token in ["技能", "投递", "简历", "画像", "成长", "岗位", "城市", "行业"]:
            if token in text:
                return token
        return ""

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
