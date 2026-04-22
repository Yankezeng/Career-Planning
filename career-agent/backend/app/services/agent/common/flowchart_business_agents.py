from __future__ import annotations

from typing import Any

from app.services.agent.ai_interview_coach_agent.ai_interview_coach_agent import AIInterviewCoachAgent
from app.services.agent.common.business_agent_runtime import BusinessAgentResult, collect_actions
from app.services.agent.demo_guidance_agent.demo_guidance_agent import DemoGuidanceAgent
from app.services.agent.dynamic_profile_agent.dynamic_profile_agent import DynamicProfileAgent
from app.services.agent.governance_agent.governance_agent import GovernanceAgent
from app.services.agent.image_generator_agent.image_generator_agent import ImageGeneratorAgent
from app.services.agent.job_package_agent.job_package_agent import JobPackageAgent
from app.services.agent.knowledge_graph_agent.knowledge_graph_agent import KnowledgeGraphAgent
from app.services.agent.match_optimization_agent.match_optimization_agent import MatchOptimizationAgent
from app.services.agent.recruitment_agent.recruitment_agent import RecruitmentAgent
from app.services.agent.student_growth_agent.student_growth_agent import StudentGrowthAgent
from app.services.agent.ux_agent.ux_agent import UXAgent
from app.services.agent_tool_registry import AgentToolRegistry


class FlowchartAgentHub:
    def __init__(self, registry: AgentToolRegistry):
        self.agents = {
            "governance": GovernanceAgent(registry),
            "knowledge": KnowledgeGraphAgent(registry),
            "growth": StudentGrowthAgent(registry),
            "delivery": JobPackageAgent(registry),
            "coach": AIInterviewCoachAgent(registry),
            "profile": DynamicProfileAgent(registry),
            "match": MatchOptimizationAgent(registry),
            "recruitment": RecruitmentAgent(registry),
            "demo": DemoGuidanceAgent(registry),
            "ux": UXAgent(registry),
            "image": ImageGeneratorAgent(registry),
        }
        self.skill_pipeline_map = {
            "resume-workbench": ["knowledge", "delivery", "profile", "ux"],
            "report-builder": ["knowledge", "delivery", "ux"],
            "delivery-ready": ["profile", "delivery", "ux"],
            "growth-planner": ["knowledge", "growth", "ux"],
            "match-center": ["knowledge", "match", "ux"],
            "gap-analysis": ["knowledge", "match", "growth", "ux"],
            "profile-insight": ["profile", "match", "ux"],
            "profile-image": ["image"],
            "interview-training": ["knowledge", "coach", "ux"],
            "candidate-overview": ["recruitment", "ux"],
            "candidate-screening": ["recruitment", "ux"],
            "resume-review": ["recruitment", "coach", "ux"],
            "talent-portrait": ["recruitment", "profile", "ux"],
            "communication-script": ["recruitment", "demo", "ux"],
            "review-advice": ["recruitment", "governance", "ux"],
            "admin-metrics": ["governance", "demo", "ux"],
            "ops-review": ["governance", "demo", "ux"],
            "knowledge-governance": ["governance", "knowledge", "ux"],
            "data-governance": ["governance", "ux"],
            "demo-script": ["demo", "governance", "ux"],
        }
        self.default_pipelines = {
            "student": ["knowledge", "match", "growth", "ux"],
            "enterprise": ["recruitment", "ux"],
            "admin": ["governance", "demo", "ux"],
        }

    def select_agent(self, *, role: str, normalized_skill: str) -> str:
        pipeline = self._resolve_pipeline(role=role, normalized_skill=normalized_skill)
        agent_key = pipeline[-1] if pipeline else "ux"
        return self.agents[agent_key].name

    def execute(
        self,
        *,
        role: str,
        normalized_skill: str,
        user: Any,
        message: str,
        target_job: str,
    ) -> BusinessAgentResult:
        pipeline = self._resolve_pipeline(role=role, normalized_skill=normalized_skill)
        aggregated_outputs: list[dict[str, Any]] = []
        aggregated_steps: list[dict[str, Any]] = []
        aggregated_call_flow: list[str] = []
        aggregated_data_flow: list[str] = []
        merged_context_patch: dict[str, Any] = {}
        final_reply = ""
        final_agent_name = ""
        merged_actions: list[str] = []
        step_cursor = 1

        for agent_key in pipeline:
            agent = self.agents[agent_key]
            result = agent.execute(user=user, message=message, target_job=target_job)
            final_reply = result.reply or final_reply
            final_agent_name = result.agent_name or final_agent_name
            aggregated_outputs.extend(result.tool_outputs)
            for row in result.tool_steps:
                step_row = dict(row or {})
                step_row["step"] = step_cursor
                step_row.setdefault("agent", result.agent_name)
                aggregated_steps.append(step_row)
                step_cursor += 1
            aggregated_call_flow.extend([f"call:hub->{result.agent_name}", *result.call_flow])
            aggregated_data_flow.extend(result.data_flow)
            for action in result.actions:
                text = str(action or "").strip()
                if text and text not in merged_actions:
                    merged_actions.append(text)
            if result.context_patch:
                merged_context_patch = self._merge_context_patch(merged_context_patch, result.context_patch)

        return BusinessAgentResult(
            agent_name=final_agent_name or self.agents["ux"].name,
            reply=final_reply or "Business pipeline completed.",
            tool_outputs=aggregated_outputs,
            tool_steps=aggregated_steps,
            actions=merged_actions[:5] or collect_actions(aggregated_outputs),
            context_patch=merged_context_patch,
            call_flow=aggregated_call_flow,
            data_flow=aggregated_data_flow,
        )

    def execute_one(
        self,
        *,
        agent_key: str,
        user: Any,
        message: str,
        target_job: str,
    ) -> BusinessAgentResult:
        key = str(agent_key or "").strip()
        if key not in self.agents:
            raise ValueError(f"Unknown business agent: {key}")
        agent = self.agents[key]
        result = agent.execute(user=user, message=message, target_job=target_job)
        return BusinessAgentResult(
            agent_name=result.agent_name or agent.name,
            reply=result.reply,
            tool_outputs=list(result.tool_outputs),
            tool_steps=[{**dict(row or {}), "agent": result.agent_name or agent.name} for row in list(result.tool_steps or [])],
            actions=list(result.actions),
            context_patch=dict(result.context_patch or {}),
            call_flow=[f"call:hub->{result.agent_name or agent.name}", *list(result.call_flow or [])],
            data_flow=list(result.data_flow or []),
        )

    def _resolve_pipeline(self, *, role: str, normalized_skill: str) -> list[str]:
        role_key = str(role or "student").strip().lower() or "student"
        skill = str(normalized_skill or "").strip()
        if skill in self.skill_pipeline_map:
            return list(self.skill_pipeline_map[skill])
        return list(self.default_pipelines.get(role_key, self.default_pipelines["student"]))

    @staticmethod
    def _merge_context_patch(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base or {})
        for key, value in (incoming or {}).items():
            if key == "context_binding" and isinstance(value, dict):
                merged_binding = merged.get("context_binding") if isinstance(merged.get("context_binding"), dict) else {}
                merged_binding = dict(merged_binding)
                merged_binding.update(value)
                merged["context_binding"] = merged_binding
                continue
            merged[key] = value
        return merged
