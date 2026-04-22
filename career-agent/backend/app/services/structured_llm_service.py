"""Structured LLM service canonical export.

This module keeps historical import paths stable while routing all logic
through structured_llm_service_clean to avoid dual implementations.
"""

from app.services.structured_llm_service_clean import (
    MockStructuredLLMService,
    OpenAICompatibleStructuredLLMService,
    StructuredLLMService,
    get_official_job_family,
    get_structured_llm_service,
    get_structured_llm_service_for_profile,
)

__all__ = [
    "StructuredLLMService",
    "MockStructuredLLMService",
    "OpenAICompatibleStructuredLLMService",
    "get_structured_llm_service",
    "get_structured_llm_service_for_profile",
    "get_official_job_family",
]
