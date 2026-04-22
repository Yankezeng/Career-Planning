from __future__ import annotations

from typing import Any

from app.services.agent.common.agent_llm_profiles import build_agent_llm_service
from app.services.agent.common.business_agent_runtime import BusinessAgentResult, render_agent_reply, run_tool_pipeline
from app.services.agent_tool_registry import AgentToolRegistry
from app.services.llm_service import LLMService


class GovernanceAgent:
    name = "PlatformGovernanceAgent"

    def __init__(self, registry: AgentToolRegistry, llm_service: LLMService | None = None):
        self.registry = registry
        self.llm_service = llm_service or build_agent_llm_service("governance_agent")

    def execute(self, *, user: Any, message: str, target_job: str) -> BusinessAgentResult:
        tool_outputs, tool_steps, context_patch, actions = run_tool_pipeline(
            self.registry,
            user=user,
            message=message,
            target_job=target_job,
            tool_names=[
                "summarize_admin_metrics",
                "summarize_ops_review",
                "llm_cost_latency_scan",
                "knowledge_governance_scan",
                "data_governance_scan",
            ],
        )
        reply = render_agent_reply(
            self.llm_service,
            agent_name=self.name,
            user=user,
            message=message,
            target_job=target_job,
            tool_outputs=tool_outputs,
            default_reply="已完成平台指标、运营复盘、LLM 成本时延与知识/数据治理扫描。",
        )
        return BusinessAgentResult(
            agent_name=self.name,
            reply=reply,
            tool_outputs=tool_outputs,
            tool_steps=tool_steps,
            actions=actions,
            context_patch=context_patch,
            call_flow=[
                "call:governance(summarize_admin_metrics)",
                "call:governance(summarize_ops_review)",
                "call:governance(llm_cost_latency_scan)",
                "call:governance(knowledge_governance_scan)",
                "call:governance(data_governance_scan)",
            ],
            data_flow=["data:governance->dashboard(metrics)", "data:governance->session(governance_snapshot)"],
        )
