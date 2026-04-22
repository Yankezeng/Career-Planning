from __future__ import annotations

from typing import Any

from app.services.agent.common.agent_llm_profiles import build_agent_llm_service
from app.services.agent.common.business_agent_runtime import BusinessAgentResult, render_agent_reply, run_tool_pipeline
from app.services.agent_tool_registry import AgentToolRegistry
from app.services.llm_service import LLMService


class JobPackageAgent:
    name = "JobDeliveryPackageAgent"

    def __init__(self, registry: AgentToolRegistry, llm_service: LLMService | None = None):
        self.registry = registry
        self.llm_service = llm_service or build_agent_llm_service("job_package_agent")

    def execute(self, *, user: Any, message: str, target_job: str) -> BusinessAgentResult:
        tool_outputs, tool_steps, context_patch, actions = run_tool_pipeline(
            self.registry,
            user=user,
            message=message,
            target_job=target_job,
            tool_names=[
                "parse_resume_attachment",
                "optimize_resume",
                "generate_report",
                "prepare_delivery",
                "assemble_job_package",
            ],
        )
        reply = render_agent_reply(
            self.llm_service,
            agent_name=self.name,
            user=user,
            message=message,
            target_job=target_job,
            tool_outputs=tool_outputs,
            default_reply="已完成求职交付包组装并给出导出建议。",
        )
        return BusinessAgentResult(
            agent_name=self.name,
            reply=reply,
            tool_outputs=tool_outputs,
            tool_steps=tool_steps,
            actions=actions,
            context_patch=context_patch,
            call_flow=[
                "call:package(parse_resume_attachment)",
                "call:package(optimize_resume)",
                "call:package(generate_report)",
                "call:package(prepare_delivery)",
                "call:package(assemble_job_package)",
            ],
            data_flow=["data:file->package", "data:report->package", "data:delivery->package(export_payload)"],
        )
