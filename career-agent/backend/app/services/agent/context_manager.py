from __future__ import annotations

from copy import deepcopy
from typing import Any


class AgentContextManager:
    def __init__(
        self,
        *,
        session_state: dict[str, Any] | None = None,
        context_binding: dict[str, Any] | None = None,
        client_state: dict[str, Any] | None = None,
    ) -> None:
        self.session_state = deepcopy(session_state or {})
        self.context_binding = deepcopy(context_binding or {})
        self.client_state = deepcopy(client_state or {})

    def apply_context_patch(self, patch: dict[str, Any] | None) -> dict[str, Any]:
        value = patch or {}
        binding_patch = value.get("context_binding")
        session_patch = value.get("session_state")
        client_patch = value.get("client_state")
        if isinstance(binding_patch, dict):
            self.context_binding = self._merge_dicts(self.context_binding, binding_patch)
        if isinstance(session_patch, dict):
            self.session_state = self._merge_dicts(self.session_state, session_patch)
        if isinstance(client_patch, dict):
            self.client_state = self._merge_dicts(self.client_state, client_patch)
        return self.snapshot()

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {
            "session_state": deepcopy(self.session_state),
            "context_binding": deepcopy(self.context_binding),
            "client_state": deepcopy(self.client_state),
        }

    @classmethod
    def _merge_dicts(cls, base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
        merged = deepcopy(base)
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = cls._merge_dicts(merged[key], value)
            else:
                merged[key] = deepcopy(value)
        return merged
