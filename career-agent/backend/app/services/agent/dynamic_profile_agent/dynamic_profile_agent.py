from __future__ import annotations

from typing import Any

from app.services.agent.common.agent_llm_profiles import build_agent_llm_service
from app.services.agent.common.business_agent_runtime import BusinessAgentResult, render_agent_reply, run_tool_pipeline
from app.services.agent_tool_registry import AgentToolRegistry
from app.services.llm_service import LLMService


class DynamicProfileAgent:
    name = "DynamicProfileAgent"

    def __init__(self, registry: AgentToolRegistry, llm_service: LLMService | None = None):
        self.registry = registry
        self.llm_service = llm_service or build_agent_llm_service("dynamic_profile_agent")

    def execute(self, *, user: Any, message: str, target_job: str) -> BusinessAgentResult:
        tool_outputs, tool_steps, context_patch, actions = run_tool_pipeline(
            self.registry,
            user=user,
            message=message,
            target_job=target_job,
            tool_names=[
                "generate_profile",
                "profile_insight",
                "profile_trend_refresh",
                "competitiveness_snapshot",
            ],
        )
        reply = render_agent_reply(
            self.llm_service,
            agent_name=self.name,
            user=user,
            message=message,
            target_job=target_job,
            tool_outputs=tool_outputs,
            default_reply="已完成动态画像生成、洞察刷新和竞争力快照输出。",
        )
        return BusinessAgentResult(
            agent_name=self.name,
            reply=reply,
            tool_outputs=tool_outputs,
            tool_steps=tool_steps,
            actions=actions,
            context_patch=context_patch,
            call_flow=[
                "call:profile(generate_profile)",
                "call:profile(profile_insight)",
                "call:profile(profile_trend_refresh)",
                "call:profile(competitiveness_snapshot)",
            ],
            data_flow=["data:profile->session(trend_state)", "data:profile->match(competitiveness)"],
        )
