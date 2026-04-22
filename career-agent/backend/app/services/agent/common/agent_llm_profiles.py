from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings
from app.services.llm_service import LLMService, get_llm_service


@dataclass(slots=True)
class AgentLLMProfile:
    api_key: str
    base_url: str
    module_name: str


def _build_profiles() -> dict[str, AgentLLMProfile]:
    settings = get_settings()
    return {
        "chat_agent": AgentLLMProfile(
            api_key=settings.CHAT_AGENT_API_KEY,
            base_url=settings.CHAT_AGENT_BASE_URL,
            module_name=settings.CHAT_AGENT_MODULE_NAME,
        ),
        "code_agent": AgentLLMProfile(
            api_key=settings.CODE_AGENT_API_KEY,
            base_url=settings.CODE_AGENT_BASE_URL,
            module_name=settings.CODE_AGENT_MODULE_NAME,
        ),
        "file_agent": AgentLLMProfile(
            api_key=settings.FILE_AGENT_API_KEY,
            base_url=settings.FILE_AGENT_BASE_URL,
            module_name=settings.FILE_AGENT_MODULE_NAME,
        ),
        "supervisor_agent": AgentLLMProfile(
            api_key=settings.SUPERVISOR_AGENT_API_KEY,
            base_url=settings.SUPERVISOR_AGENT_BASE_URL,
            module_name=settings.SUPERVISOR_AGENT_MODULE_NAME,
        ),
        "ux_agent": AgentLLMProfile(
            api_key=settings.UX_AGENT_API_KEY,
            base_url=settings.UX_AGENT_BASE_URL,
            module_name=settings.UX_AGENT_MODULE_NAME,
        ),
        "student_growth_agent": AgentLLMProfile(
            api_key=settings.STUDENT_GROWTH_AGENT_API_KEY,
            base_url=settings.STUDENT_GROWTH_AGENT_BASE_URL,
            module_name=settings.STUDENT_GROWTH_AGENT_MODULE_NAME,
        ),
        "job_package_agent": AgentLLMProfile(
            api_key=settings.JOB_PACKAGE_AGENT_API_KEY,
            base_url=settings.JOB_PACKAGE_AGENT_BASE_URL,
            module_name=settings.JOB_PACKAGE_AGENT_MODULE_NAME,
        ),
        "recruitment_agent": AgentLLMProfile(
            api_key=settings.RECRUITMENT_AGENT_API_KEY,
            base_url=settings.RECRUITMENT_AGENT_BASE_URL,
            module_name=settings.RECRUITMENT_AGENT_MODULE_NAME,
        ),
        "dynamic_profile_agent": AgentLLMProfile(
            api_key=settings.DYNAMIC_PROFILE_AGENT_API_KEY,
            base_url=settings.DYNAMIC_PROFILE_AGENT_BASE_URL,
            module_name=settings.DYNAMIC_PROFILE_AGENT_MODULE_NAME,
        ),
        "match_optimization_agent": AgentLLMProfile(
            api_key=settings.MATCH_OPTIMIZATION_AGENT_API_KEY,
            base_url=settings.MATCH_OPTIMIZATION_AGENT_BASE_URL,
            module_name=settings.MATCH_OPTIMIZATION_AGENT_MODULE_NAME,
        ),
        "ai_interview_coach_agent": AgentLLMProfile(
            api_key=settings.AI_INTERVIEW_COACH_AGENT_API_KEY,
            base_url=settings.AI_INTERVIEW_COACH_AGENT_BASE_URL,
            module_name=settings.AI_INTERVIEW_COACH_AGENT_MODULE_NAME,
        ),
        "knowledge_graph_agent": AgentLLMProfile(
            api_key=settings.KNOWLEDGE_GRAPH_AGENT_API_KEY,
            base_url=settings.KNOWLEDGE_GRAPH_AGENT_BASE_URL,
            module_name=settings.KNOWLEDGE_GRAPH_AGENT_MODULE_NAME,
        ),
        "governance_agent": AgentLLMProfile(
            api_key=settings.GOVERNANCE_AGENT_API_KEY,
            base_url=settings.GOVERNANCE_AGENT_BASE_URL,
            module_name=settings.GOVERNANCE_AGENT_MODULE_NAME,
        ),
        "demo_guidance_agent": AgentLLMProfile(
            api_key=settings.DEMO_GUIDANCE_AGENT_API_KEY,
            base_url=settings.DEMO_GUIDANCE_AGENT_BASE_URL,
            module_name=settings.DEMO_GUIDANCE_AGENT_MODULE_NAME,
        ),
        "image_generator_agent": AgentLLMProfile(
            api_key=settings.IMAGE_GENERATOR_AGENT_API_KEY,
            base_url=settings.IMAGE_GENERATOR_AGENT_BASE_URL,
            module_name=settings.IMAGE_GENERATOR_AGENT_MODULE_NAME,
        ),
    }


def get_agent_llm_profile(agent_key: str) -> AgentLLMProfile:
    return _build_profiles()[agent_key]


def build_agent_llm_service(agent_key: str) -> LLMService:
    profile = get_agent_llm_profile(agent_key)
    return get_llm_service(
        api_key=profile.api_key,
        base_url=profile.base_url,
        module_name=profile.module_name,
    )
