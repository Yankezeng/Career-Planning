from __future__ import annotations

import json
import socket
import ssl
from abc import ABC, abstractmethod
from time import perf_counter, sleep
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import get_settings
from app.services.llm_contracts import LLMCallError, LLMCallResult, LLMErrorKind, LLMErrorPayload


DEFAULT_MATCH_WEIGHTS = {
    "basic_requirement": 0.25,
    "professional_skill": 0.40,
    "professional_literacy": 0.20,
    "development_potential": 0.15,
}

MAX_CONTEXT_TOKENS = 60000
CONTEXT_RESERVE_TOKENS = 2000

SMALL_TALK_KEYWORDS = {"你好", "hi", "hello", "在吗", "早", "早上好", "晚上好", "嗨", "好的", "ok", "收到", "谢谢", "继续", "好", "行"}
GENERAL_QUESTIONS = {
    "你会干什么",
    "你会做什么",
    "你能干什么",
    "你能做什么",
    "你有什么用",
    "你可以做什么",
    "你会什么",
    "你有什么功能",
    "你能帮什么",
    "帮助",
    "干嘛的",
    "干什么用的",
}


def estimate_tokens(text: str) -> int:
    return len(text) // 4


def truncate_history_by_tokens(
    history: list[dict[str, Any]],
    max_tokens: int = MAX_CONTEXT_TOKENS - CONTEXT_RESERVE_TOKENS,
) -> list[dict[str, Any]]:
    result = []
    total_tokens = 0
    for item in reversed(history):
        content = str(item.get("content") or "")
        tokens = estimate_tokens(content) + 20
        if total_tokens + tokens > max_tokens:
            break
        result.insert(0, item)
        total_tokens += tokens
    return result


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_llm_call_meta(
    *,
    provider: str,
    model_name: str,
    scene: str,
    status: str,
    latency_ms: float | None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    input_chars: int = 0,
    output_chars: int = 0,
    error_message: str | None = None,
    raw_usage_json: dict[str, Any] | None = None,
    raw_meta_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "provider": provider or "mock",
        "model_name": model_name or "mock",
        "scene": scene or "assistant_chat",
        "status": status or "success",
        "latency_ms": float(latency_ms or 0),
        "prompt_tokens": _to_int(prompt_tokens),
        "completion_tokens": _to_int(completion_tokens),
        "total_tokens": _to_int(total_tokens),
        "input_chars": _to_int(input_chars),
        "output_chars": _to_int(output_chars),
        "error_message": str(error_message or "").strip() or None,
        "raw_usage_json": raw_usage_json or {},
        "raw_meta_json": raw_meta_json or {},
    }


class LLMService(ABC):
    def __init__(self, provider: str = "mock", model_name: str = "mock"):
        self.provider = provider
        self.model_name = model_name
        self._last_call_meta: dict[str, Any] = {}

    @abstractmethod
    def generate_job_profile(self, job_name: str, description: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    def generate_career_advice(self, student_name: str, job_name: str, gaps: list[dict]) -> dict:
        raise NotImplementedError

    @abstractmethod
    def generate_report_summary(self, student_name: str, top_job_name: str, total_score: float) -> str:
        raise NotImplementedError

    @abstractmethod
    def polish_report_section(self, section_title: str, content: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def chat(
        self,
        user_role: str,
        user_name: str,
        message: str,
        history: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        raise NotImplementedError

    def get_last_call_meta(self) -> dict[str, Any]:
        return dict(self._last_call_meta or {})

    def clear_last_call_meta(self) -> None:
        self._last_call_meta = {}

    def _set_last_call_meta(self, meta: dict[str, Any] | None) -> None:
        self._last_call_meta = dict(meta or {})

    @staticmethod
    def _scene_from_context(context: dict[str, Any] | None) -> str:
        return str((context or {}).get("scene") or "assistant_chat")

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def is_small_talk_message(cls, message: str) -> bool:
        text = cls._normalize_text(message).lower().replace(" ", "")
        if not text:
            return False
        if text in SMALL_TALK_KEYWORDS:
            return True
        return len(text) <= 4 and any(token in text for token in SMALL_TALK_KEYWORDS)

    @classmethod
    def is_general_question(cls, message: str) -> bool:
        text = cls._normalize_text(message).lower().replace(" ", "")
        if not text:
            return False
        return any(q in text for q in GENERAL_QUESTIONS)

    @classmethod
    def general_question_reply(cls, message: str) -> str:
        return "我能帮你做简历优化、岗位匹配、能力差距分析、成长计划和职业规划报告。你可以直接告诉我目标岗位或当前问题。"

    @classmethod
    def small_talk_reply(cls, message: str) -> str:
        text = cls._normalize_text(message).lower()
        if any(token in text for token in ["你好", "hi", "hello", "在吗", "早", "早上好", "晚上好"]):
            return "在的，今天想先聊哪件事？"
        if "谢谢" in text:
            return "不客气，有问题随时继续发我。"
        if "继续" in text:
            return "好的，我们继续。"
        if any(token in text for token in ["好的", "嗨", "ok", "收到", "好", "行", "可以"]):
            return "好的，继续说。"
        if "拜拜" in text or "再见" in text:
            return "再见，有需要随时回来找我。"
        return "在的，说说你的问题。"

    def _build_local_reply(
        self,
        *,
        user_name: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        text = self._normalize_text(message)
        context = context or {}
        if self.is_small_talk_message(text):
            return self.small_talk_reply(text)

        tool_outputs = context.get("tool_outputs") or []
        retrieval_chunks = context.get("retrieval_chunks") or []
        reply_mode = str(context.get("reply_mode") or "structured")

        if tool_outputs:
            first = tool_outputs[0]
            summary = str(first.get("summary") or "已完成本轮分析").strip()
            if reply_mode == "brief":
                return f"结论：{summary}"
            steps = first.get("next_actions") or ["确认目标岗位", "补齐关键差距", "继续细化计划"]
            lines = [f"结论：{summary}", "下一步："]
            for index, step in enumerate(steps[:3], start=1):
                lines.append(f"{index}. {step}")
            return "\n".join(lines)

        if retrieval_chunks:
            top = retrieval_chunks[0]
            job_name = top.get("job_name") or "目标岗位"
            snippet = top.get("snippet") or "已检索到岗位知识片段。"
            if reply_mode == "brief":
                return f"结论：已找到和{job_name}相关的信息。"
            return f"结论：已找到和{job_name}相关的信息。\n依据：{snippet}\n下一步：告诉我你的背景，我给你可执行建议。"

        safe_name = user_name or "同学"
        if len(text) <= 12:
            return f"{safe_name}，收到。补充一句目标岗位，我马上给结论。"
        return f"结论：已理解你的需求（{text}）。\n下一步：告诉我目标岗位或当前困境，我给你执行清单。"

    def plan(
        self,
        *,
        role: str,
        message: str,
        normalized_skill: str,
        tool_plan: list[str],
        need_retrieval: bool,
    ) -> dict[str, Any]:
        return {
            "role": role,
            "intent": normalized_skill if normalized_skill != "general-chat" else "general_chat",
            "need_retrieval": bool(need_retrieval),
            "tool_plan": tool_plan,
            "message": message,
        }

    def summarize_tool_outputs(
        self,
        *,
        tool_outputs: list[dict[str, Any]],
        retrieval_chunks: list[dict[str, Any]],
        user_message: str,
    ) -> str:
        if tool_outputs:
            summary = str(tool_outputs[0].get("summary") or "已完成本轮分析").strip()
            return f"结论：{summary}\n下一步：先执行最关键一步，再把结果发我继续细化。"
        if retrieval_chunks:
            return "结论：已完成岗位知识检索。下一步：给我你的目标岗位和背景，我给你可执行方案。"
        return f"结论：已理解你的需求（{self._normalize_text(user_message)}）。下一步：告诉我目标和限制，我给你执行清单。"

    def generate_followup_actions(
        self,
        *,
        role: str,
        normalized_skill: str,
        tool_outputs: list[dict[str, Any]],
        user_message: str,
    ) -> list[str]:
        if normalized_skill == "report-builder":
            return ["查看报告摘要", "补充行动计划", "导出报告"]
        if normalized_skill == "match-center":
            return ["查看前三岗位", "分析技能差距", "生成成长路径"]
        if normalized_skill == "candidate-screening":
            return ["查看前三候选人", "生成沟通话术", "生成复评建议"]
        return ["继续追问细节", "让我给出执行清单", "切换到另一个技能"]


class MockLLMService(LLMService):
    def __init__(self):
        super().__init__(provider="mock", model_name="mock")

    def generate_job_profile(self, job_name: str, description: str) -> dict:
        return {
            "job_name": job_name,
            "summary": f"{job_name} 需要扎实基础、项目证据和稳定交付能力。",
            "core_skills": ["专业基础", "项目实践", "沟通协作"],
            "common_skills": ["学习能力", "执行力", "复盘能力"],
            "certificates": ["岗位相关证书"],
            "degree_requirement": "本科及以上",
            "major_requirement": "相关专业优先",
            "internship_requirement": "至少 1 段相关实习或项目经历",
            "work_content": description or f"参与 {job_name} 相关任务，完成阶段交付与复盘。",
            "development_direction": f"{job_name} -> 高级岗位 -> 负责人/专家",
            "recommended_courses": ["岗位核心课程", "项目实战课程"],
            "match_weights": DEFAULT_MATCH_WEIGHTS,
        }

    def generate_career_advice(self, student_name: str, job_name: str, gaps: list[dict]) -> dict:
        gap_items = [item.get("gap_item") for item in gaps[:4] if item.get("gap_item")]
        primary = "、".join(gap_items[:2]) or "岗位核心能力"
        return {
            "overview": f"{student_name} 当前可先以 {job_name} 为目标，优先补齐 {primary}。",
            "short_term": f"短期补齐 {primary}，并完成 1 个与 {job_name} 相关的小项目。",
            "medium_term": "中期通过课程、项目、实习沉淀可展示成果。",
            "long_term": f"长期持续积累岗位证据，稳定提升 {job_name} 竞争力。",
        }

    def generate_report_summary(self, student_name: str, top_job_name: str, total_score: float) -> str:
        return f"{student_name} 当前推荐岗位为 {top_job_name}，综合匹配度约 {round(total_score, 1)} 分。"

    def polish_report_section(self, section_title: str, content: str) -> str:
        text = self._normalize_text(content).replace("\n", "；")
        return f"{section_title}：{text}" if text else self._normalize_text(content)

    def chat(
        self,
        user_role: str,
        user_name: str,
        message: str,
        history: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        clean_message = self._normalize_text(message)
        if self.is_small_talk_message(clean_message):
            return self.small_talk_reply(clean_message)
        if self.is_general_question(clean_message):
            return self.general_question_reply(clean_message)
        scene = self._scene_from_context(context)
        start = perf_counter()
        reply = self._build_local_reply(user_name=user_name, message=message, context=context)
        self._set_last_call_meta(
            build_llm_call_meta(
                provider=self.provider,
                model_name=self.model_name,
                scene=scene,
                status="success",
                latency_ms=round((perf_counter() - start) * 1000, 2),
                input_chars=len(clean_message),
                output_chars=len(reply),
                raw_meta_json={"source": "mock"},
            )
        )
        return reply


class OpenAICompatibleLLMService(MockLLMService):
    def __init__(self, *, provider: str, model_name: str, api_key: str, base_url: str, temperature: float):
        super().__init__()
        self.provider = provider
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = str(base_url or "").rstrip("/")
        self.temperature = temperature

    def _build_messages(
        self,
        *,
        user_role: str,
        user_name: str,
        message: str,
        history: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> list[dict[str, str]]:
        context_payload = {
            "selected_skill": context.get("selected_skill") or "",
            "intent": context.get("intent") or "",
            "tool_outputs": context.get("tool_outputs") or [],
            "retrieval_chunks": context.get("retrieval_chunks") or [],
            "business_snapshot": context.get("business_snapshot") or {},
            "reply_mode": context.get("reply_mode") or "structured",
            "slots": context.get("slots") or {},
            "supervisor_plan": context.get("supervisor_plan") or {},
            "dispatch_trace": context.get("dispatch_trace") or {},
        }
        conversation = [
            {
                "role": item.get("role", "user") if item.get("role", "user") in {"system", "user", "assistant"} else "user",
                "content": str(item.get("content") or ""),
            }
            for item in truncate_history_by_tokens(history)
            if str(item.get("content") or "").strip()
        ]
        return [
            {
                "role": "system",
                "content": (
                    "你是职业规划平台的 AI 助手，可以帮助学生和企业用户解决职业相关问题。"
                    "始终使用中文，先给结论，再给依据。不要输出 HTML 标签，不要编造事实。"
                    "如果提供了 tool_outputs、retrieval_chunks、supervisor_plan 或 dispatch_trace，优先依据这些信息回答。"
                    "只展示用户可理解的决策摘要，不展示隐藏链式思考原文。"
                ),
            },
            {
                "role": "system",
                "content": (
                    f"用户角色：{user_role}\n"
                    f"用户姓名：{user_name}\n"
                    f"结构化上下文：{json.dumps(context_payload, ensure_ascii=False, default=str)}"
                ),
            },
            *conversation,
            {"role": "user", "content": self._normalize_text(message)},
        ]

    def _request_chat_completion_once(self, payload: dict[str, Any], timeout: int | None = None) -> dict[str, Any]:
        resolved_timeout = int(timeout or get_settings().LLM_REQUEST_TIMEOUT_SECONDS or 25)
        req = Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=resolved_timeout) as response:
                body = response.read().decode("utf-8")
            return json.loads(body)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore") if exc.fp else str(exc)
            raise self._llm_error_from_http(exc.code, detail) from exc
        except URLError as exc:
            raise self._llm_error_from_url_error(exc, timeout=resolved_timeout) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise LLMCallError(
                LLMErrorPayload(kind=LLMErrorKind.TIMEOUT, message=f"LLM request timed out after {resolved_timeout}s.", retryable=True)
            ) from exc
        except json.JSONDecodeError as exc:
            raise LLMCallError(
                LLMErrorPayload(kind=LLMErrorKind.VALIDATION, message=f"LLM response JSON parse failed: {exc}", retryable=False)
            ) from exc

    def _request_chat_completion_result(self, payload: dict[str, Any], timeout: int | None = None) -> LLMCallResult:
        settings = get_settings()
        max_attempts = max(1, int(getattr(settings, "LLM_RETRY_MAX_ATTEMPTS", 3) or 3))
        delay = max(0.0, float(getattr(settings, "LLM_RETRY_INITIAL_DELAY_SECONDS", 1.0) or 1.0))
        multiplier = max(1.0, float(getattr(settings, "LLM_RETRY_BACKOFF_MULTIPLIER", 2.0) or 2.0))
        max_delay = max(delay, float(getattr(settings, "LLM_RETRY_MAX_DELAY_SECONDS", 30.0) or 30.0))
        started = perf_counter()
        last_error: LLMCallError | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                data = self._request_chat_completion_once(payload, timeout=timeout)
                return LLMCallResult(ok=True, data=data, attempts=attempt, latency_ms=round((perf_counter() - started) * 1000, 2))
            except LLMCallError as exc:
                exc.payload.attempt = attempt
                last_error = exc
                if not exc.retryable or attempt >= max_attempts:
                    return LLMCallResult(ok=False, error=exc.payload, attempts=attempt, latency_ms=round((perf_counter() - started) * 1000, 2))
                sleep(min(delay, max_delay))
                delay = min(delay * multiplier, max_delay)
        if last_error is not None:
            return LLMCallResult(ok=False, error=last_error.payload, attempts=max_attempts, latency_ms=round((perf_counter() - started) * 1000, 2))
        return LLMCallResult(
            ok=False,
            error=LLMErrorPayload(kind=LLMErrorKind.PROVIDER, message="LLM call failed before issuing a request.", retryable=False, attempt=max_attempts),
            attempts=max_attempts,
            latency_ms=round((perf_counter() - started) * 1000, 2),
        )

    def _request_chat_completion(self, payload: dict[str, Any], timeout: int | None = None) -> dict[str, Any]:
        return self._request_chat_completion_result(payload, timeout=timeout).unwrap()

    @staticmethod
    def _llm_error_from_http(status_code: int, detail: str) -> LLMCallError:
        if status_code in {401, 403}:
            kind = LLMErrorKind.AUTH
            retryable = False
        elif status_code == 429:
            kind = LLMErrorKind.RATE_LIMIT
            retryable = True
        elif status_code >= 500:
            kind = LLMErrorKind.TRANSIENT
            retryable = True
        else:
            kind = LLMErrorKind.PROVIDER
            retryable = False
        return LLMCallError(
            LLMErrorPayload(
                kind=kind,
                message=f"LLM provider HTTP {status_code}: {detail}"[:800],
                retryable=retryable,
                status_code=status_code,
            )
        )

    @staticmethod
    def _llm_error_from_url_error(exc: URLError, *, timeout: int) -> LLMCallError:
        reason = getattr(exc, "reason", None)
        text = str(reason or exc)
        lowered = text.lower()
        is_timeout = isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in lowered or "timeout" in lowered
        if is_timeout:
            return LLMCallError(
                LLMErrorPayload(kind=LLMErrorKind.TIMEOUT, message=f"LLM request timed out after {timeout}s: {text}", retryable=True)
            )
        is_transient_network = isinstance(reason, (ssl.SSLError, ConnectionResetError, ConnectionAbortedError, OSError)) or any(
            token in lowered
            for token in (
                "unexpected_eof",
                "unexpected eof",
                "eof occurred",
                "connection reset",
                "connection aborted",
                "remote end closed",
                "remote disconnected",
                "temporarily unavailable",
                "tls",
                "ssl",
            )
        )
        if is_transient_network:
            return LLMCallError(
                LLMErrorPayload(kind=LLMErrorKind.TRANSIENT, message=f"LLM transient network error: {text}"[:800], retryable=True)
            )
        return LLMCallError(LLMErrorPayload(kind=LLMErrorKind.PROVIDER, message=f"LLM network error: {text}"[:800], retryable=False))

    def chat(
        self,
        user_role: str,
        user_name: str,
        message: str,
        history: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        history = history or []
        context = context or {}
        scene = self._scene_from_context(context)
        clean_message = self._normalize_text(message)

        if self.is_small_talk_message(clean_message):
            start = perf_counter()
            reply = self.small_talk_reply(clean_message)
            self._set_last_call_meta(
                build_llm_call_meta(
                    provider=self.provider,
                    model_name=self.model_name,
                    scene=scene,
                    status="success",
                    latency_ms=round((perf_counter() - start) * 1000, 2),
                    input_chars=len(clean_message),
                    output_chars=len(reply),
                    raw_meta_json={"source": "local_rule"},
                )
            )
            return reply

        if self.is_general_question(clean_message):
            start = perf_counter()
            reply = self.general_question_reply(clean_message)
            self._set_last_call_meta(
                build_llm_call_meta(
                    provider=self.provider,
                    model_name=self.model_name,
                    scene=scene,
                    status="success",
                    latency_ms=round((perf_counter() - start) * 1000, 2),
                    input_chars=len(clean_message),
                    output_chars=len(reply),
                    raw_meta_json={"source": "general_question"},
                )
            )
            return reply

        if not self.api_key:
            raise LLMCallError(
                LLMErrorPayload(
                    kind=LLMErrorKind.AUTH,
                    message=f"{self.provider} API key is not configured for model {self.model_name}.",
                    retryable=False,
                )
            )

        payload = {
            "model": self.model_name,
            "temperature": self.temperature,
            "messages": self._build_messages(
                user_role=user_role,
                user_name=user_name,
                message=clean_message,
                history=history,
                context=context,
            ),
        }

        input_chars = len(json.dumps(payload.get("messages") or [], ensure_ascii=False))
        start = perf_counter()
        try:
            body = self._request_chat_completion(payload)
            choice = ((body.get("choices") or [{}])[0].get("message") or {}).get("content")
            if isinstance(choice, list):
                choice = "".join(str(item.get("text") or "") for item in choice if isinstance(item, dict))
            reply = self._normalize_text(choice)
            if not reply or len(reply) < 5:
                raise LLMCallError(
                    LLMErrorPayload(kind=LLMErrorKind.VALIDATION, message="LLM response content is empty or too short.", retryable=False)
                )
            usage = body.get("usage") or {}
            prompt_tokens = _to_int(usage.get("prompt_tokens"))
            completion_tokens = _to_int(usage.get("completion_tokens"))
            total_tokens = _to_int(usage.get("total_tokens"), prompt_tokens + completion_tokens)
            self._set_last_call_meta(
                build_llm_call_meta(
                    provider=self.provider,
                    model_name=self.model_name,
                    scene=scene,
                    status="success",
                    latency_ms=round((perf_counter() - start) * 1000, 2),
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    input_chars=input_chars,
                    output_chars=len(reply),
                    raw_usage_json=usage,
                    raw_meta_json={"source": "provider_api"},
                )
            )
            return reply
        except (LLMCallError, KeyError, IndexError, TypeError, ValueError) as exc:
            error = exc if isinstance(exc, LLMCallError) else LLMCallError(
                LLMErrorPayload(kind=LLMErrorKind.VALIDATION, message=f"LLM response schema is invalid: {exc}", retryable=False)
            )
            self._set_last_call_meta(
                build_llm_call_meta(
                    provider=self.provider,
                    model_name=self.model_name,
                    scene=scene,
                    status="failed",
                    latency_ms=round((perf_counter() - start) * 1000, 2),
                    input_chars=input_chars,
                    output_chars=0,
                    error_message=str(error),
                    raw_meta_json={"source": "provider_api", "error": error.to_dict()},
                )
            )
            raise error


class OpenAILLMService(OpenAICompatibleLLMService):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
    ):
        settings = get_settings()
        super().__init__(
            provider="openai",
            model_name=model_name if model_name is not None else settings.OPENAI_MODEL,
            api_key=api_key if api_key is not None else settings.OPENAI_API_KEY,
            base_url=base_url if base_url is not None else settings.OPENAI_BASE_URL,
            temperature=settings.LLM_TEMPERATURE,
        )


class QwenLLMService(OpenAICompatibleLLMService):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
    ):
        settings = get_settings()
        super().__init__(
            provider="qwen",
            model_name=model_name if model_name is not None else settings.LANGCHAIN_MODEL,
            api_key=api_key if api_key is not None else settings.DASHSCOPE_API_KEY or settings.OPENAI_API_KEY,
            base_url=base_url if base_url is not None else settings.LANGCHAIN_BASE_URL,
            temperature=settings.LLM_TEMPERATURE,
        )


class ZhipuLLMService(MockLLMService):
    def __init__(self):
        super().__init__()
        self.provider = "zhipu"
        self.model_name = "zhipu-mock"


class DeepSeekLLMService(MockLLMService):
    def __init__(self):
        super().__init__()
        self.provider = "deepseek"
        self.model_name = "deepseek-mock"


def get_llm_service(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    module_name: str | None = None,
) -> LLMService:
    provider = get_settings().LLM_PROVIDER.lower()
    if provider == "openai":
        return OpenAILLMService(api_key=api_key, base_url=base_url, model_name=module_name)
    if provider == "qwen":
        return QwenLLMService(api_key=api_key, base_url=base_url, model_name=module_name)
    if provider == "mock":
        return MockLLMService()
    if provider == "zhipu":
        return ZhipuLLMService()
    if provider == "deepseek":
        return DeepSeekLLMService()
    raise RuntimeError(f"Unsupported LLM_PROVIDER: {provider}")
