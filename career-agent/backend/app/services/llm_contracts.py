from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class LLMErrorKind(StrEnum):
    TRANSIENT = "transient"
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    VALIDATION = "validation"
    PROVIDER = "provider"


@dataclass(slots=True)
class LLMErrorPayload:
    kind: LLMErrorKind
    message: str
    retryable: bool = False
    status_code: int = 0
    attempt: int = 1

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["kind"] = str(self.kind)
        return payload


@dataclass(slots=True)
class LLMCallResult:
    ok: bool
    data: dict[str, Any] | None = None
    error: LLMErrorPayload | None = None
    attempts: int = 1
    latency_ms: float = 0

    def unwrap(self) -> dict[str, Any]:
        if self.ok and self.data is not None:
            return self.data
        if self.error is not None:
            raise LLMCallError(self.error)
        raise LLMCallError(
            LLMErrorPayload(
                kind=LLMErrorKind.PROVIDER,
                message="LLM call failed without an error payload.",
                retryable=False,
                attempt=self.attempts,
            )
        )


class LLMCallError(RuntimeError):
    def __init__(self, payload: LLMErrorPayload):
        super().__init__(payload.message)
        self.payload = payload
        self.kind = payload.kind
        self.retryable = payload.retryable
        self.status_code = payload.status_code
        self.attempt = payload.attempt

    def to_dict(self) -> dict[str, Any]:
        return self.payload.to_dict()
