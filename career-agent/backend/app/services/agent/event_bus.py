from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class AgentEvent:
    event_id: str
    trace_id: str
    event: str
    status: str
    agent_key: str
    step_id: str
    summary: str
    decision_summary: str
    output_summary: str
    failure_reason: str
    duration_ms: int
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class InMemoryAgentEventBus:
    def __init__(self, *, trace_id: str):
        self.trace_id = str(trace_id or f"trace_{uuid4().hex[:10]}")
        self._events: list[AgentEvent] = []

    def publish(
        self,
        *,
        event: str,
        status: str,
        summary: str,
        agent_key: str = "",
        step_id: str = "",
        decision_summary: str = "",
        output_summary: str = "",
        failure_reason: str = "",
        duration_ms: int = 0,
    ) -> dict[str, Any]:
        row = AgentEvent(
            event_id=f"evt_{uuid4().hex[:12]}",
            trace_id=self.trace_id,
            event=str(event or ""),
            status=str(status or "running"),
            agent_key=str(agent_key or ""),
            step_id=str(step_id or ""),
            summary=str(summary or ""),
            decision_summary=str(decision_summary or ""),
            output_summary=str(output_summary or ""),
            failure_reason=str(failure_reason or ""),
            duration_ms=max(0, int(duration_ms or 0)),
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self._events.append(row)
        return row.to_dict()

    def events(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self._events]
