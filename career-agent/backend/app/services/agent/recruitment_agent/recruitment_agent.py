from __future__ import annotations

from typing import Any

from app.services.agent.common.agent_llm_profiles import build_agent_llm_service
from app.services.agent.common.business_agent_runtime import BusinessAgentResult, render_agent_reply, run_tool_pipeline
from app.services.agent_tool_registry import AgentToolRegistry
from app.services.llm_service import LLMService


class RecruitmentAgent:
    name = "EnterpriseRecruitmentProcessAgent"

    def __init__(self, registry: AgentToolRegistry, llm_service: LLMService | None = None):
        self.registry = registry
        self.llm_service = llm_service or build_agent_llm_service("recruitment_agent")

    def execute(self, *, user: Any, message: str, target_job: str) -> BusinessAgentResult:
        tool_outputs, tool_steps, context_patch, actions = run_tool_pipeline(
            self.registry,
            user=user,
            message=message,
            target_job=target_job,
            tool_names=[
                "build_candidate_overview",
                "rank_candidates",
                "generate_resume_review",
                "generate_interview_questions",
                "manage_offer_pipeline",
            ],
        )
        reply = render_agent_reply(
            self.llm_service,
            agent_name=self.name,
            user=user,
            message=message,
            target_job=target_job,
            tool_outputs=tool_outputs,
            default_reply="已完成候选人概览、排序、简历评审、面试题和 Offer 流程管理。",
        )
        return BusinessAgentResult(
            agent_name=self.name,
            reply=reply,
            tool_outputs=tool_outputs,
            tool_steps=tool_steps,
            actions=actions,
            context_patch=context_patch,
            call_flow=[
                "call:recruit(build_candidate_overview)",
                "call:recruit(rank_candidates)",
                "call:recruit(generate_resume_review)",
                "call:recruit(generate_interview_questions)",
                "call:recruit(manage_offer_pipeline)",
            ],
            data_flow=["data:recruit->platform(candidate_pipeline)", "data:recruit->session(offer_state)"],
        )
