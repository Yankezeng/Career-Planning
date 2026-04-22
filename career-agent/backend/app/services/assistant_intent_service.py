from __future__ import annotations

import re
from typing import Any


class AssistantIntentService:
    SMALL_TALK_TOKENS = {
        "你好",
        "hi",
        "hello",
        "在吗",
        "谢谢",
        "好的",
        "ok",
        "收到",
        "继续",
        "嗯",
        "在",
    }

    FOLLOW_UP_TOKENS = {"继续", "展开", "细说", "那", "再看", "再分析", "换成", "换一个方向"}

    def detect(self, message: str, *, session_state: dict[str, Any] | None = None) -> dict[str, Any]:
        text = self._normalize(message)
        session_state = session_state or {}

        if not text:
            return {"intent": "clarify_required", "reason": "empty_message"}

        if self.is_small_talk(text):
            if text in {"继续", "展开"} and session_state.get("last_analysis_focus"):
                return {"intent": "follow_up", "reason": "continue_previous_focus"}
            return {"intent": "small_talk", "reason": "light_message"}

        if any(token in text for token in ["切换技能", "换技能", "用技能", "切到"]):
            return {"intent": "switch_skill", "reason": "skill_switch"}
        if any(token in text for token in ["对比", "比较", "vs", "差异"]):
            return {"intent": "compare", "reason": "compare"}
        if any(token in text for token in ["执行", "生成", "创建", "优化", "投递", "设为默认"]):
            return {"intent": "execute", "reason": "action_request"}
        if any(token in text for token in ["计划", "规划", "路线", "路径", "成长", "成长路径", "学习路线", "职业路径", "步骤", "优先"]):
            return {"intent": "ask_plan", "reason": "planning"}
        if any(token in text for token in ["建议", "怎么办", "如何", "怎么做", "缺什么"]):
            return {"intent": "ask_advice", "reason": "advice"}
        if any(token in text for token in ["是什么", "当前", "多少", "有没有", "吗"]):
            return {"intent": "ask_fact", "reason": "fact_question"}
        if any(token in text for token in ["再优化", "润色", "改写", "精简", "细化"]):
            return {"intent": "refine", "reason": "refine"}
        if any(token in text for token in self.FOLLOW_UP_TOKENS):
            return {"intent": "follow_up", "reason": "follow_up"}
        return {"intent": "ask_advice", "reason": "default"}

    def is_small_talk(self, message: str) -> bool:
        text = self._normalize(message)
        if not text:
            return False
        if text in self.SMALL_TALK_TOKENS:
            return True
        if len(text) <= 4 and any(token in text for token in self.SMALL_TALK_TOKENS):
            return True
        return False

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", "", str(value or "").lower())
