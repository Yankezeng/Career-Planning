from __future__ import annotations

from typing import Final

FILE_AGENT_ENABLED: bool = True

ROUTE_TO_AGENT_KEY: Final[dict[str, str]] = {
    "simple": "chat_agent",
    "complex": "chat_agent",
    "code": "code_agent",
    "file": "file_agent",
    "file_unavailable": "chat_agent",
}


def is_file_agent_enabled() -> bool:
    return FILE_AGENT_ENABLED


def resolve_agent_key(route: str) -> str:
    return ROUTE_TO_AGENT_KEY.get(str(route or "").strip(), "chat_agent")

