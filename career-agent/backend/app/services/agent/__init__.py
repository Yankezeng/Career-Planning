"""Agent package public exports.

Keep this module side-effect free so importing agent classes does not
eagerly initialize optional dependencies.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.agent.ai_interview_coach_agent.ai_interview_coach_agent import AIInterviewCoachAgent
    from app.services.agent.chat_agent.chat_agent import ChatAgent
    from app.services.agent.code_agent.code_agent import CodeAgent
    from app.services.agent.contracts import AgentReport, SupervisorDecision
    from app.services.agent.demo_guidance_agent.demo_guidance_agent import DemoGuidanceAgent
    from app.services.agent.dynamic_profile_agent.dynamic_profile_agent import DynamicProfileAgent
    from app.services.agent.factory import AgentBundle
    from app.services.agent.file_agent.file_agent import FileAgent
    from app.services.agent.governance_agent.governance_agent import GovernanceAgent
    from app.services.agent.job_package_agent.job_package_agent import JobPackageAgent
    from app.services.agent.knowledge_graph_agent.knowledge_graph_agent import KnowledgeGraphAgent
    from app.services.agent.match_optimization_agent.match_optimization_agent import MatchOptimizationAgent
    from app.services.agent.recruitment_agent.recruitment_agent import RecruitmentAgent
    from app.services.agent.student_growth_agent.student_growth_agent import StudentGrowthAgent
    from app.services.agent.supervisor_agent.supervisor_agent import SupervisorAgent
    from app.services.agent.ux_agent.ux_agent import UXAgent

__all__ = [
    "AIInterviewCoachAgent",
    "AgentReport",
    "AgentBundle",
    "ChatAgent",
    "CodeAgent",
    "DemoGuidanceAgent",
    "DynamicProfileAgent",
    "FileAgent",
    "GovernanceAgent",
    "JobPackageAgent",
    "KnowledgeGraphAgent",
    "MatchOptimizationAgent",
    "RecruitmentAgent",
    "StudentGrowthAgent",
    "SupervisorAgent",
    "SupervisorDecision",
    "UXAgent",
    "build_agent_bundle",
    "resolve_agent_key",
]

_EXPORT_MAP = {
    "AIInterviewCoachAgent": ("app.services.agent.ai_interview_coach_agent.ai_interview_coach_agent", "AIInterviewCoachAgent"),
    "AgentReport": ("app.services.agent.contracts", "AgentReport"),
    "AgentBundle": ("app.services.agent.factory", "AgentBundle"),
    "ChatAgent": ("app.services.agent.chat_agent.chat_agent", "ChatAgent"),
    "CodeAgent": ("app.services.agent.code_agent.code_agent", "CodeAgent"),
    "DemoGuidanceAgent": ("app.services.agent.demo_guidance_agent.demo_guidance_agent", "DemoGuidanceAgent"),
    "DynamicProfileAgent": ("app.services.agent.dynamic_profile_agent.dynamic_profile_agent", "DynamicProfileAgent"),
    "FileAgent": ("app.services.agent.file_agent.file_agent", "FileAgent"),
    "GovernanceAgent": ("app.services.agent.governance_agent.governance_agent", "GovernanceAgent"),
    "JobPackageAgent": ("app.services.agent.job_package_agent.job_package_agent", "JobPackageAgent"),
    "KnowledgeGraphAgent": ("app.services.agent.knowledge_graph_agent.knowledge_graph_agent", "KnowledgeGraphAgent"),
    "MatchOptimizationAgent": ("app.services.agent.match_optimization_agent.match_optimization_agent", "MatchOptimizationAgent"),
    "RecruitmentAgent": ("app.services.agent.recruitment_agent.recruitment_agent", "RecruitmentAgent"),
    "StudentGrowthAgent": ("app.services.agent.student_growth_agent.student_growth_agent", "StudentGrowthAgent"),
    "SupervisorAgent": ("app.services.agent.supervisor_agent.supervisor_agent", "SupervisorAgent"),
    "SupervisorDecision": ("app.services.agent.contracts", "SupervisorDecision"),
    "UXAgent": ("app.services.agent.ux_agent.ux_agent", "UXAgent"),
    "build_agent_bundle": ("app.services.agent.factory", "build_agent_bundle"),
    "resolve_agent_key": ("app.services.agent.registry", "resolve_agent_key"),
}


def __getattr__(name: str) -> Any:
    if name not in _EXPORT_MAP:
        raise AttributeError(name)
    module_name, attr_name = _EXPORT_MAP[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
