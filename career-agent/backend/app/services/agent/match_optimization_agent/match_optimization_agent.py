from __future__ import annotations

from typing import Any

from app.services.agent.common.agent_llm_profiles import build_agent_llm_service
from app.services.agent.common.business_agent_runtime import BusinessAgentResult, render_agent_reply, run_tool_pipeline
from app.services.agent_tool_registry import AgentToolRegistry
from app.services.llm_service import LLMService


class MatchOptimizationAgent:
    name = "MatchOptimizationAgent"

    def __init__(self, registry: AgentToolRegistry, llm_service: LLMService | None = None):
        self.registry = registry
        self.llm_service = llm_service or build_agent_llm_service("match_optimization_agent")

    def execute(self, *, user: Any, message: str, target_job: str) -> BusinessAgentResult:
        tool_outputs, tool_steps, context_patch, actions = run_tool_pipeline(
            self.registry,
            user=user,
            message=message,
            target_job=target_job,
            tool_names=[
                "generate_matches",
                "generate_gap_analysis",
                "explainable_ranking",
                "feedback_weight_update",
            ],
        )
        reply = render_agent_reply(
            self.llm_service,
            agent_name=self.name,
            user=user,
            message=message,
            target_job=target_job,
            tool_outputs=tool_outputs,
            default_reply="已完成匹配生成、差距分析、可解释排序和反馈权重更新。",
        )
        return BusinessAgentResult(
            agent_name=self.name,
            reply=reply,
            tool_outputs=tool_outputs,
            tool_steps=tool_steps,
            actions=actions,
            context_patch=context_patch,
            call_flow=[
                "call:match(generate_matches)",
                "call:match(generate_gap_analysis)",
                "call:match(explainable_ranking)",
                "call:match(feedback_weight_update)",
            ],
            data_flow=["data:match->session(explained_rank)", "data:match->profile(weight_update)"],
        )
