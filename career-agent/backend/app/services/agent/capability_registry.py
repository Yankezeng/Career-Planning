from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AgentCapability:
    agent_key: str
    routes: tuple[str, ...]
    task_types: tuple[str, ...]
    input_contract: str
    output_contract: str
    timeout_seconds: int = 25
    requires_llm: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["routes"] = list(self.routes)
        payload["task_types"] = list(self.task_types)
        return payload


AGENT_CAPABILITIES: dict[str, AgentCapability] = {
    "chat": AgentCapability(
        agent_key="chat",
        routes=("simple", "chat", "complex"),
        task_types=("*",),
        input_contract="message, history, context",
        output_contract="reply, reply_blocks, actions",
    ),
    "file": AgentCapability(
        agent_key="file",
        routes=("file",),
        task_types=("parse_file", "optimize_resume", "generate_report", "generate_document", "generate_chart", "generate_image"),
        input_contract="attachment context or file task context",
        output_contract="file_task, tool_outputs, artifacts, context_patch",
        timeout_seconds=90,
    ),
    "code": AgentCapability(
        agent_key="code",
        routes=("code",),
        task_types=("python", "c", "cpp", "javascript", "html", "css", "vue", "vbs", "mermaid", "*"),
        input_contract="code generation request or controlled file/render request",
        output_contract="code_task, verification, generated files",
    ),
    "knowledge": AgentCapability("knowledge", ("business",), ("*",), "career query context", "knowledge hits and evidence"),
    "match": AgentCapability("match", ("business",), ("*",), "student profile and target role", "match analysis"),
    "growth": AgentCapability("growth", ("business",), ("*",), "skill gaps and goal", "growth plan"),
    "delivery": AgentCapability("delivery", ("business",), ("*",), "career assets and task context", "delivery package advice"),
    "profile": AgentCapability("profile", ("business",), ("*",), "student or candidate context", "profile insight"),
    "recruitment": AgentCapability("recruitment", ("business",), ("*",), "enterprise hiring context", "recruitment analysis"),
    "governance": AgentCapability("governance", ("business",), ("*",), "admin and data context", "governance advice"),
    "demo": AgentCapability("demo", ("business",), ("*",), "demo scenario context", "demo script or guidance"),
    "ux": AgentCapability("ux", ("business",), ("*",), "workflow output context", "user-facing UX summary"),
    "image": AgentCapability(
        "image",
        ("business",),
        ("*",),
        "student profile, evidence, target role",
        "persona analysis, profile image url, visual report metadata",
        timeout_seconds=90,
    ),
}


BUSINESS_AGENT_KEYS = frozenset(
    key for key, capability in AGENT_CAPABILITIES.items() if "business" in capability.routes
)
ALLOWED_DYNAMIC_AGENT_KEYS = frozenset(AGENT_CAPABILITIES)


def get_capability(agent_key: str) -> AgentCapability:
    key = str(agent_key or "").strip()
    if key not in AGENT_CAPABILITIES:
        raise ValueError(f"Unknown agent capability: {key}")
    return AGENT_CAPABILITIES[key]


def list_candidate_agent_keys(*, role: str, selected_skill: str, message: str) -> list[str]:
    skill = str(selected_skill or "").strip()
    role_key = str(role or "student").strip().lower()
    skill_pipeline_map = {
        "resume-workbench": ["knowledge", "delivery", "profile", "ux"],
        "report-builder": ["knowledge", "delivery", "ux"],
        "delivery-ready": ["profile", "delivery", "ux"],
        "growth-planner": ["knowledge", "growth", "ux"],
        "match-center": ["knowledge", "match", "ux"],
        "gap-analysis": ["knowledge", "match", "growth", "ux"],
        "profile-insight": ["profile", "match", "ux"],
        "profile-image": ["image"],
        "candidate-overview": ["recruitment", "ux"],
        "candidate-screening": ["recruitment", "ux"],
        "talent-portrait": ["recruitment", "profile", "ux"],
        "communication-script": ["recruitment", "demo", "ux"],
        "review-advice": ["recruitment", "governance", "ux"],
        "admin-metrics": ["governance", "demo", "ux"],
        "ops-review": ["governance", "demo", "ux"],
        "knowledge-governance": ["governance", "knowledge", "ux"],
        "data-governance": ["governance", "ux"],
        "demo-script": ["demo", "governance", "ux"],
    }
    if skill in skill_pipeline_map:
        return skill_pipeline_map[skill]
    if role_key == "enterprise":
        return ["recruitment", "profile", "ux"]
    if role_key == "admin":
        return ["governance", "demo", "ux"]
    compact = str(message or "").lower()
    if any(
        token in compact
        for token in (
            "画图",
            "图片",
            "image",
            "cbti",
            "mbti",
            "人格",
            "人格分析",
            "画像图",
            "人物画像",
            "画像表格",
            "职业画像报告",
            "简历画像",
            "海报",
            "职业画像图",
        )
    ):
        return ["image"]
    if any(token in compact for token in ("匹配", "match", "gap", "差距")):
        return ["knowledge", "match", "growth", "ux"]
    if any(token in compact for token in ("报告", "投递", "交付", "delivery", "report")):
        return ["knowledge", "delivery", "ux"]
    return ["knowledge", "match", "growth", "ux"]


def validate_agent_step(*, agent_key: str, route: str, task_type: str) -> None:
    capability = get_capability(agent_key)
    if route not in capability.routes:
        raise ValueError(f"Agent {agent_key} does not support route: {route}")
    normalized_task = str(task_type or "").strip()
    if "*" not in capability.task_types and normalized_task not in capability.task_types:
        raise ValueError(f"Agent {agent_key} does not support task_type: {normalized_task}")
