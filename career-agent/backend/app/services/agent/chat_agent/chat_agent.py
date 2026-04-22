from __future__ import annotations

import re
from typing import Any

from app.services.agent.chat_agent.conversation.conversation_strategy import get_conversation_strategy
from app.services.agent.chat_agent.conversation.reply_style_controller import get_reply_style_controller
from app.services.agent.common.agent_llm_profiles import build_agent_llm_service
from app.services.llm_service import LLMService


class ChatAgent:
    TASK_KEYWORDS = (
        "parse",
        "extract",
        "optimize",
        "generate",
        "report",
        "file",
        "resume",
        "analyze",
        "analysis",
        "upload",
        "download",
        "parse_file",
        "optimize_resume",
        "generate_report",
        "generate_document",
        "generate_chart",
        "generate_image",
        "write code",
        "generate code",
        "code agent",
        "coding",
        "python",
        "c++",
        "cpp",
        "javascript",
        "html",
        "css",
        "vue",
        "vbs",
        "vbscript",
        "mermaid",
        "mermain",
        "写代码",
        "编程",
        "代码",
        "脚本",
    )

    SHORT_QA_TOKENS = (
        "?",
        "can",
        "what",
        "how",
        "why",
        "who",
        "when",
        "where",
        "吗",
        "怎么",
        "如何",
    )

    def __init__(self, llm_service: LLMService | None = None):
        self.llm_service = llm_service or build_agent_llm_service("chat_agent")
        self.conversation_strategy = get_conversation_strategy()
        self.reply_style_controller = get_reply_style_controller()

    def try_handle_simple(self, *, message: str, role: str = "student") -> dict[str, Any] | None:
        intent_info = self.classify_simple_intent(message=message)
        if not intent_info["is_simple"]:
            return None

        result = self.reply_for_simple_intent(message=message, intent=str(intent_info["intent"]), role=role)
        result["intent"] = str(intent_info["intent"])
        result["agent_flow"] = [
            {"step": 1, "agent": "chat", "action": "receive_user_intent"},
            {"step": 2, "agent": "chat", "action": "direct_simple_reply"},
        ]
        return result

    def classify_simple_intent(self, *, message: str) -> dict[str, Any]:
        text = str(message or "").strip()
        compact = self._compact(text.lower())
        if not text:
            return {"is_simple": False, "intent": "", "reason": "empty_message"}

        if self._contains_task_tokens(compact) or self._contains_code_intent(text=text, compact_text=compact) or self._is_task_command_prefix(text):
            return {"is_simple": False, "intent": "", "reason": "task_like_message"}

        is_small_talk = self.llm_service.is_small_talk_message(text)
        if is_small_talk:
            return {"is_simple": True, "intent": "small_talk", "reason": "small_talk_rule"}

        is_general_question = self.llm_service.is_general_question(text) or self._is_short_question(text, compact)
        if is_general_question:
            return {"is_simple": True, "intent": "short_qa", "reason": "short_qa_rule"}

        return {"is_simple": False, "intent": "", "reason": "complex_or_task_message"}

    def reply_for_simple_intent(self, *, message: str, intent: str, role: str = "student") -> dict[str, Any]:
        text = str(message or "").strip()
        strategy_result = self.conversation_strategy.decide(
            intent=str(intent or "small_talk"),
            slots={"user_message": text},
            confidence=0.9,
            session_state={},
        )

        if intent == "small_talk":
            reply = str(strategy_result.get("reply") or self.llm_service.small_talk_reply(text))
        elif intent == "short_qa":
            reply = self.llm_service.general_question_reply(text)
        else:
            reply = "I have received your message."
        reply = self.reply_style_controller.adjust_style(
            reply=reply,
            role=str(role or "student"),
            context={"scene": "simple_chat", "intent": intent},
        )

        return {
            "reply": reply,
            "reply_mode": "brief",
            "reply_blocks": [{"type": "summary", "text": reply}],
            "actions": [],
        }

    def reply_for_file_result(self, result: dict[str, Any], role: str = "student") -> dict[str, Any]:
        status = str(result.get("status") or "")
        file_task = result.get("file_task") or {}
        task_type = str(file_task.get("type") or "file_task")
        missing_fields = [str(item) for item in (file_task.get("missing_fields") or []) if str(item)]
        invalid_fields = [str(item) for item in (file_task.get("invalid_fields") or []) if str(item)]

        if status == "needs_input":
            question = str(result.get("question") or "") if invalid_fields else ""
            if not question:
                question = self._needs_input_message(
                    task_type=task_type,
                    missing_fields=missing_fields,
                    default_message=str(result.get("question") or ""),
                )
            question = self.reply_style_controller.adjust_style(
                reply=question,
                role=str(role or "student"),
                context={"scene": "file_task", "intent": "clarify_required"},
            )
            return {
                "reply": question,
                "reply_mode": "brief",
                "reply_blocks": [{"type": "summary", "text": question}],
                "actions": [],
            }

        if status == "success":
            artifacts = list(result.get("artifacts") or [])
            tool_steps = list(result.get("tool_steps") or [])
            summary = str(result.get("reply") or "File task completed.")

            bullets = []
            file_names = []
            for item in artifacts:
                name = str(item.get("name") or "unnamed_file")
                file_type = str(item.get("type") or "file")
                if name:
                    file_names.append(name)
                bullets.append(f"{name} [{file_type}]")

            if file_names:
                summary = f"{summary} 文件：{', '.join(file_names[:3])}"
            summary = self.reply_style_controller.adjust_style(
                reply=summary,
                role=str(role or "student"),
                context={"scene": "file_task", "intent": "execute"},
            )

            step_items = [str(step.get("text") or "").strip() for step in tool_steps if isinstance(step, dict)]
            step_items = [item for item in step_items if item]

            blocks = [{"type": "summary", "text": summary}]
            if bullets:
                blocks.append({"type": "bullets", "title": "Artifacts", "items": bullets[:5]})
            if step_items:
                blocks.append({"type": "bullets", "title": "Execution Steps", "items": step_items[:5]})

            default_actions = {
                "parse_file": ["Continue parsing another file", "Generate downloadable document"],
                "optimize_resume": ["Generate career report", "Run job match analysis"],
                "generate_report": ["View report details", "Optimize action plan"],
                "generate_document": ["Generate chart", "Generate image"],
                "generate_chart": ["Generate image", "Generate downloadable document"],
                "generate_image": ["Generate chart", "Generate downloadable document"],
            }
            return {
                "reply": summary,
                "reply_mode": "structured",
                "reply_blocks": blocks,
                "actions": default_actions.get(task_type, []),
            }

        message = str(result.get("question") or result.get("failure_reason") or file_task.get("failure_reason") or "File task failed. Please retry.")
        message = self.reply_style_controller.adjust_style(
            reply=message,
            role=str(role or "student"),
            context={"scene": "file_task", "intent": "execution_failed"},
        )
        return {
            "reply": message,
            "reply_mode": "brief",
            "reply_blocks": [{"type": "summary", "text": message}],
            "actions": [],
        }

    def reply_for_file_unavailable(self, *, task_type: str = "", role: str = "student") -> dict[str, Any]:
        task_hints = {
            "parse_file": "文件解析",
            "optimize_resume": "简历优化",
            "generate_report": "报告生成",
            "generate_document": "文档生成",
            "generate_chart": "图表生成",
            "generate_image": "图片生成",
        }
        task_label = task_hints.get(str(task_type or "").strip(), "文件处理")
        summary = f"{task_label}能力当前暂不可用（File Agent 已暂停），我已记录你的诉求。"
        detail = "你可以先继续让我处理文本咨询或代码任务，文件能力恢复后我再接着帮你。"
        final_reply = self.reply_style_controller.adjust_style(
            reply=f"{summary} {detail}",
            role=str(role or "student"),
            context={"scene": "file_unavailable", "intent": "execute"},
        )
        return {
            "reply": final_reply,
            "reply_mode": "brief",
            "reply_blocks": [{"type": "summary", "text": final_reply}],
            "actions": ["继续文本咨询", "继续代码任务"],
        }

    def reply_for_code_result(self, result: dict[str, Any], role: str = "student") -> dict[str, Any]:
        status = str(result.get("status") or "").strip().lower()
        code_task = result.get("code_task") or {}
        language = str(code_task.get("language") or "code").strip()
        attempt = int(code_task.get("attempt") or 0)

        if status == "success":
            summary = str(result.get("reply") or "Code generation completed successfully.")
            file_offer_prompt = "如果你需要，我可以继续把这份代码导出为文件（Word/PDF）或打包下载。需要我现在生成吗？"
            summary = self.reply_style_controller.adjust_style(
                reply=summary,
                role=str(role or "student"),
                context={"scene": "code_task", "intent": "execute"},
            )
            artifacts = list(result.get("artifacts") or [])
            verification = result.get("verification") or {}
            verify_summary = str((verification.get("compile") or {}).get("summary") or "")
            test_summary = str((verification.get("tests") or {}).get("summary") or "")

            file_items = []
            for item in artifacts:
                name = str(item.get("name") or "code_file")
                file_type = str(item.get("type") or "code")
                file_items.append(f"{name} [{file_type}]")

            blocks = [{"type": "summary", "text": summary}]
            blocks.append(
                {
                    "type": "bullets",
                    "title": "Verification",
                    "items": [
                        f"Language: {language}",
                        f"Attempt: {attempt}",
                        verify_summary or "compile/syntax checks passed",
                        test_summary or "self-tests passed",
                    ],
                }
            )
            if file_items:
                blocks.append({"type": "bullets", "title": "Artifacts", "items": file_items[:8]})
            blocks.append({"type": "note", "text": file_offer_prompt})

            return {
                "reply": f"{summary} {file_offer_prompt}",
                "reply_mode": "structured",
                "reply_blocks": blocks,
                "actions": ["需要导出文件", "暂不需要文件", "Continue refining this code", "Add more test cases"],
            }

        failure_reason = str(code_task.get("failure_reason") or result.get("question") or "Code verification failed.")
        tool_outputs = list(result.get("tool_outputs") or [])
        suggestions = []
        if tool_outputs:
            data = tool_outputs[0].get("data") if isinstance(tool_outputs[0], dict) else {}
            suggestions = [str(item) for item in ((data or {}).get("fix_suggestions") or []) if str(item).strip()]

        blocks = [{"type": "summary", "text": "Code generation failed strict verification, so no final code was output."}]
        blocks.append({"type": "bullets", "title": "Failure Reason", "items": [failure_reason]})
        if suggestions:
            blocks.append({"type": "bullets", "title": "Fix Suggestions", "items": suggestions[:4]})
        failure_reply = self.reply_style_controller.adjust_style(
            reply="Code generation failed strict verification, so no final code was output.",
            role=str(role or "student"),
            context={"scene": "code_task", "intent": "execution_failed"},
        )

        return {
            "reply": failure_reply,
            "reply_mode": "structured",
            "reply_blocks": blocks,
            "actions": suggestions[:3],
        }

    @classmethod
    def _contains_task_tokens(cls, compact_text: str) -> bool:
        return any(token in compact_text for token in cls.TASK_KEYWORDS)

    @staticmethod
    def _contains_code_intent(*, text: str, compact_text: str) -> bool:
        lowered = f" {str(text or '').lower()} "
        code_tokens = (
            " python ",
            " c++ ",
            " cpp ",
            " javascript ",
            " html ",
            " css ",
            " vue ",
            " vbs ",
            " vbscript ",
            " mermaid ",
            " mermain ",
            "写代码",
            "编程",
            "代码",
            "脚本",
        )
        return any(token in lowered for token in code_tokens) or any(token in compact_text for token in ("写代码", "编程", "代码", "脚本"))

    @classmethod
    def _is_short_question(cls, text: str, compact_text: str) -> bool:
        if len(compact_text) > 18:
            return False
        if cls._contains_task_tokens(compact_text):
            return False
        return any(token in text.lower() for token in cls.SHORT_QA_TOKENS)

    @staticmethod
    def _compact(value: str) -> str:
        return re.sub(r"\s+", "", str(value or ""))

    @staticmethod
    def _is_task_command_prefix(text: str) -> bool:
        normalized = str(text or "").strip().lower()
        command_prefixes = ("help me", "please", "could you", "帮我", "请", "给我", "替我")
        return any(normalized.startswith(prefix) for prefix in command_prefixes)

    @staticmethod
    def _needs_input_message(*, task_type: str, missing_fields: list[str], default_message: str) -> str:
        if "attachment_id" in missing_fields:
            if task_type == "optimize_resume":
                return "Please upload an image, Word, or PDF resume first, then send 'start' or 'optimize my resume'."
            return "Please upload an image, Word, or PDF file first, then send 'start' or 'parse my file'."
        if "parse_quality_low" in missing_fields:
            return "Current parse quality is too low. Please upload a clearer PDF/image and retry."
        if "student_profile" in missing_fields:
            return "Please sign in with a student account before running file tasks."
        if "execution" in missing_fields:
            return "File task execution failed. Please retry once."
        return default_message or "Please provide the required information for this file task."
