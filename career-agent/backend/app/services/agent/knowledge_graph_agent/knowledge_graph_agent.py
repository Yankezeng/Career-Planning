from __future__ import annotations

from typing import Any

from app.services.agent.common.agent_llm_profiles import build_agent_llm_service
from app.services.agent.common.business_agent_runtime import BusinessAgentResult, render_agent_reply, run_tool_pipeline
from app.services.agent_tool_registry import AgentToolRegistry
from app.services.llm_service import LLMService


class KnowledgeGraphAgent:
    name = "KnowledgeGraphRecommendationAgent"

    def __init__(self, registry: AgentToolRegistry, llm_service: LLMService | None = None):
        self.registry = registry
        self.llm_service = llm_service or build_agent_llm_service("knowledge_graph_agent")

    def execute(self, *, user: Any, message: str, target_job: str) -> BusinessAgentResult:
        tool_outputs, tool_steps, context_patch, actions = run_tool_pipeline(
            self.registry,
            user=user,
            message=message,
            target_job=target_job,
            tool_names=[
                "job_kb_search",
                "skill_graph_view",
                "learning_sequence",
                "transfer_path_recommendation",
            ],
        )
        reply = render_agent_reply(
            self.llm_service,
            agent_name=self.name,
            user=user,
            message=message,
            target_job=target_job,
            tool_outputs=tool_outputs,
            default_reply="已完成岗位知识检索、技能图谱、学习序列和迁移路径推荐。",
        )
        return BusinessAgentResult(
            agent_name=self.name,
            reply=reply,
            tool_outputs=tool_outputs,
            tool_steps=tool_steps,
            actions=actions,
            context_patch=context_patch,
            call_flow=[
                "call:knowledge(job_kb_search)",
                "call:knowledge(skill_graph_view)",
                "call:knowledge(learning_sequence)",
                "call:knowledge(transfer_path_recommendation)",
            ],
            data_flow=["data:knowledge->growth(learning_sequence)", "data:knowledge->match(transfer_paths)"],
        )
