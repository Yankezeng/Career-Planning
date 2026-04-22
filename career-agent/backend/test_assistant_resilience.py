from __future__ import annotations

import ssl
from urllib.error import URLError

from app.services.assistant_fallback_service import build_career_guidance_fallback
from app.services.llm_contracts import LLMErrorKind
from app.services.llm_service import OpenAICompatibleLLMService


def test_fallback_hides_llm_network_error_and_keeps_target_job() -> None:
    result = build_career_guidance_fallback(
        message="我的推荐职业是Java开发工程师，请你为我规划一个成长路径",
        selected_skill="growth-planner",
        reason="LLM network error: [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred",
    )

    reply = result["reply"]
    assert "Java" in reply
    assert "成长路径" in reply
    assert "LLM network error" not in reply
    assert "UNEXPECTED_EOF" not in reply
    assert "补充提示" not in reply
    assert result["context_binding"]["target_job"] == "Java开发工程师"


def test_gap_fallback_uses_gap_template() -> None:
    result = build_career_guidance_fallback(
        message="能力差距分析",
        selected_skill="gap-analysis",
        context_binding={"target_job": "Java 开发工程师"},
        reason="RuntimeError: provider failed",
    )

    reply = result["reply"]
    assert "能力差距分析" in reply
    assert "技术栈差距" in reply
    assert "项目经验差距" in reply
    assert "provider failed" not in reply


def test_ssl_eof_url_error_is_retryable_transient() -> None:
    error = OpenAICompatibleLLMService._llm_error_from_url_error(
        URLError(ssl.SSLError("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol")),
        timeout=25,
    )

    assert error.retryable is True
    assert error.kind == LLMErrorKind.TRANSIENT
