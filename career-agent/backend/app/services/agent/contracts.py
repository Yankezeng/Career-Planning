from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class AgentReport:
    report_id: str
    agent_name: str
    route: str
    task_type: str
    status: str
    requires_user_input: bool
    tool_outputs_count: int
    artifacts_count: int
    context_patch_keys: list[str]
    started_at: str
    finished_at: str
    summary: str
    handoff_hint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SupervisorDecision:
    route: str
    task_type: str
    stop_reason: str
    goal: dict[str, Any]
    next_agent_key: str = ""
    next_step_id: str = ""
    requires_replan: bool = False
    decision_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "task_type": self.task_type,
            "stop_reason": self.stop_reason,
            "goal": dict(self.goal or {}),
            "next_agent_key": self.next_agent_key,
            "next_step_id": self.next_step_id,
            "requires_replan": self.requires_replan,
            "decision_summary": self.decision_summary,
        }


@dataclass(slots=True)
class SupervisorDispatchStep:
    step_id: str
    agent_key: str
    route: str
    task_type: str
    task_summary: str
    depends_on: list[str]
    expected_output: str
    stop_condition: str
    decision_summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SupervisorAgentPlan:
    plan_id: str
    objective: str
    candidate_agents: list[str]
    selected_agents: list[str]
    steps: list[SupervisorDispatchStep]
    stop_conditions: list[str]
    decision_summary: str
    fallback_reason: str = ""
    source: str = "llm"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["steps"] = [step.to_dict() if hasattr(step, "to_dict") else dict(step) for step in self.steps]
        return payload


@dataclass(slots=True)
class SupervisorDispatchTrace:
    trace_id: str
    status: str
    events: list[dict[str, Any]]
    fallback_used: bool = False
    fallback_reason: str = ""
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
