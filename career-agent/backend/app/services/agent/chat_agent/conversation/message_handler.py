from __future__ import annotations
from typing import Any


class MessageHandler:
    def __init__(self):
        self.duplicate_count = 0
        self.last_message = ""

    def preprocess_message(self, message: str, session_state: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
        """预处理用户消息，返回处理后的消息和上下文补丁"""
        session_state = session_state or {}

        if not message or not message.strip():
            return self._handle_empty_message(session_state)

        message = message.strip()

        if message == self.last_message:
            self.duplicate_count += 1
            if self.duplicate_count >= 3:
                return self._handle_duplicate_message(message, session_state)
        else:
            self.duplicate_count = 0

        self.last_message = message

        if self._is_irrelevant_message(message, session_state):
            return self._handle_irrelevant_message(message, session_state)

        return message, {"status": "normal"}

    def _handle_empty_message(self, session_state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """处理空白消息"""
        last_topic = session_state.get("last_topic", "")
        if last_topic:
            return f"你之前聊到{last_topic}，想继续了解吗？", {"status": "empty_handled", "context": "continuation"}
        return "你好，有什么职业规划方面的问题吗？", {"status": "empty_handled", "context": "greeting"}

    def _handle_duplicate_message(self, message: str, session_state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """处理连续重复消息"""
        return (
            "我理解你的意思。你是不是想说些别的？或者我们可以换个话题聊聊？",
            {"status": "duplicate_handled", "context": "redirect"}
        )

    def _is_irrelevant_message(self, message: str, session_state: dict[str, Any]) -> bool:
        """检测消息是否与当前话题无关"""
        current_topic = session_state.get("last_topic", "")
        if not current_topic:
            return False

        irrelevant_patterns = [
            "天气", "今天", "明天", "新闻", "疫情", "电影", "音乐",
            "吃饭", "睡觉", "游戏", "运动", "旅游"
        ]

        message_lower = message.lower()
        for pattern in irrelevant_patterns:
            if pattern in message_lower and len(message) < 20:
                return True

        return False

    def _handle_irrelevant_message(self, message: str, session_state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """处理无关消息"""
        previous_topic = session_state.get("last_topic", "")

        if previous_topic:
            return (
                f"我们之前在聊{previous_topic}，想继续聊这个话题吗？还是你有新的问题？",
                {"status": "irrelevant_handled", "context": "topic_switch"}
            )

        return message, {"status": "normal"}

    def should_use_context(self, current_message: str, session_state: dict[str, Any] | None = None) -> bool:
        """判断是否应该使用上下文进行回复"""
        session_state = session_state or {}

        continue_keywords = ["继续", "展开", "再看", "再分析", "接着", "然后"]
        for kw in continue_keywords:
            if kw in current_message:
                return True

        change_keywords = ["其实", "不是", "不对", "我想", "换个"]
        for kw in change_keywords:
            if kw in current_message:
                return False

        if session_state.get("last_target_job") and session_state.get("conversation_stage") != "greeting":
            return True

        return False


_message_handler_instance = None

def get_message_handler() -> MessageHandler:
    global _message_handler_instance
    if _message_handler_instance is None:
        _message_handler_instance = MessageHandler()
    return _message_handler_instance
