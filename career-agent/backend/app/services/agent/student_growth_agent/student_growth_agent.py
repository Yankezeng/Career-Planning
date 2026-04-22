from __future__ import annotations

from typing import Any

from app.services.agent.common.agent_llm_profiles import build_agent_llm_service
from app.services.agent.common.business_agent_runtime import BusinessAgentResult, render_agent_reply, run_tool_pipeline
from app.services.agent_tool_registry import AgentToolRegistry
from app.services.llm_service import LLMService


class StudentGrowthAgent:
    name = "StudentGrowthPlanningAgent"

    def __init__(self, registry: AgentToolRegistry, llm_service: LLMService | None = None):
        self.registry = registry
        self.llm_service = llm_service or build_agent_llm_service("student_growth_agent")

    def execute(self, *, user: Any, message: str, target_job: str) -> BusinessAgentResult:
        tool_outputs, tool_steps, context_patch, actions = run_tool_pipeline(
            self.registry,
            user=user,
            message=message,
            target_job=target_job,
            tool_names=[
                "job_kb_search",
                "generate_gap_analysis",
                "generate_growth_path",
                "growth_checkin_plan",
                "growth_stage_review",
            ],
        )
        reply = render_agent_reply(
            self.llm_service,
            agent_name=self.name,
            user=user,
            message=message,
            target_job=target_job,
            tool_outputs=tool_outputs,
            default_reply="已完成成长路径、任务打卡计划与阶段复盘。",
        )
        return BusinessAgentResult(
            agent_name=self.name,
            reply=reply,
            tool_outputs=tool_outputs,
            tool_steps=tool_steps,
            actions=actions,
            context_patch=context_patch,
            call_flow=[
                "call:growth(job_kb_search)",
                "call:growth(generate_gap_analysis)",
                "call:growth(generate_growth_path)",
                "call:growth(growth_checkin_plan)",
                "call:growth(growth_stage_review)",
            ],
            data_flow=["data:growth->profile(task_record)", "data:growth->session(checkin_plan)", "data:growth->report(stage_review)"],
        )
