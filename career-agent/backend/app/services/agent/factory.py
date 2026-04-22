from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.services.agent.chat_agent.chat_agent import ChatAgent
    from app.services.agent.code_agent.code_agent import CodeAgent
    from app.services.agent.file_agent.file_agent import FileAgent
    from app.services.agent.supervisor_agent.supervisor_agent import SupervisorAgent


@dataclass(slots=True)
class AgentBundle:
    supervisor: "SupervisorAgent"
    chat: "ChatAgent"
    file: "FileAgent"
    code: "CodeAgent"


def build_agent_bundle(db: Session) -> AgentBundle:
    from app.services.agent.supervisor_agent.supervisor_agent import SupervisorAgent

    supervisor = SupervisorAgent(db)
    return AgentBundle(
        supervisor=supervisor,
        chat=supervisor.chat_agent,
        file=supervisor.file_agent,
        code=supervisor.code_agent,
    )
