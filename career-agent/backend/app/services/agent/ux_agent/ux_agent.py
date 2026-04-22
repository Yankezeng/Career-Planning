from __future__ import annotations

from typing import Any

from app.services.agent.common.agent_llm_profiles import build_agent_llm_service
from app.services.agent.common.business_agent_runtime import BusinessAgentResult, render_agent_reply, run_tool_pipeline
from app.services.agent_tool_registry import AgentToolRegistry
from app.services.llm_service import LLMService


class UXAgent:
    name = "InteractionExperienceAgent"

    def __init__(self, registry: AgentToolRegistry | None = None, llm_service: LLMService | None = None):
        self.registry = registry
        self.llm_service = llm_service or build_agent_llm_service("ux_agent")

    def execute(self, *, user: Any, message: str, target_job: str) -> BusinessAgentResult:
        if self.registry is None:
            return BusinessAgentResult(
                agent_name=self.name,
                reply=f"interaction guidance ready: {message}",
                tool_outputs=[],
                tool_steps=[],
                actions=[],
                context_patch={},
                call_flow=["call:demo->ui"],
                data_flow=["data:ui->profile(user_behavior)", "data:ui->match(preference)"],
            )

        tool_outputs, tool_steps, context_patch, actions = run_tool_pipeline(
            self.registry,
            user=user,
            message=message,
            target_job=target_job,
            tool_names=["role_onboarding", "quick_entry_recommendation", "progress_feedback", "operation_suggestion"],
        )
        reply = render_agent_reply(
            self.llm_service,
            agent_name=self.name,
            user=user,
            message=message,
            target_job=target_job,
            tool_outputs=tool_outputs,
            default_reply="已完成角色引导、快捷入口建议、进度反馈和操作建议。",
        )
        return BusinessAgentResult(
            agent_name=self.name,
            reply=reply,
            tool_outputs=tool_outputs,
            tool_steps=tool_steps,
            actions=actions,
            context_patch=context_patch,
            call_flow=["call:ux(role_onboarding)", "call:ux(quick_entry_recommendation)", "call:ux(progress_feedback)", "call:ux(operation_suggestion)"],
            data_flow=["data:ui->profile(user_behavior)", "data:ui->match(preference)", "data:ui->session(progress_state)"],
        )
