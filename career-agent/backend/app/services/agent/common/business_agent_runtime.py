from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.services.agent_tool_registry import AgentToolRegistry
from app.services.llm_service import LLMService


@dataclass(slots=True)
class BusinessAgentResult:
    agent_name: str
    reply: str
    tool_outputs: list[dict[str, Any]]
    tool_steps: list[dict[str, Any]]
    actions: list[str]
    context_patch: dict[str, Any]
    call_flow: list[str]
    data_flow: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "reply": self.reply,
            "tool_outputs": list(self.tool_outputs),
            "tool_steps": list(self.tool_steps),
            "actions": list(self.actions),
            "context_patch": dict(self.context_patch),
            "call_flow": list(self.call_flow),
            "data_flow": list(self.data_flow),
        }


def collect_actions(tool_outputs: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    for item in tool_outputs:
        for action in item.get("next_actions") or []:
            text = str(action or "").strip()
            if text and text not in actions:
                actions.append(text)
    return actions[:5]


def merge_context_patches(tool_outputs: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    merged_binding: dict[str, Any] = {}
    for output in tool_outputs:
        patch = output.get("context_patch") if isinstance(output.get("context_patch"), dict) else {}
        for key, value in patch.items():
            if key == "context_binding" and isinstance(value, dict):
                merged_binding.update(value)
                continue
            merged[key] = value
    if merged_binding:
        merged["context_binding"] = merged_binding
    return merged


def run_tool_pipeline(
    registry: AgentToolRegistry,
    *,
    user: Any,
    message: str,
    target_job: str,
    tool_names: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[str]]:
    tool_outputs: list[dict[str, Any]] = []
    tool_steps: list[dict[str, Any]] = []

    for step, tool_name in enumerate(tool_names, start=1):
        output = registry.run(tool_name, user=user, message=message, target_job=target_job)
        tool_outputs.append(output)
        has_error = bool((output.get("data") or {}).get("error"))
        tool_steps.append(
            {
                "step": step,
                "tool": tool_name,
                "status": "failed" if has_error else "done",
                "text": ("failed: " if has_error else "done: ") + str(output.get("title") or tool_name),
            }
        )

    context_patch = merge_context_patches(tool_outputs)
    actions = collect_actions(tool_outputs)
    return tool_outputs, tool_steps, context_patch, actions


def render_agent_reply(
    llm_service: LLMService,
    *,
    agent_name: str,
    user: Any,
    message: str,
    target_job: str,
    tool_outputs: list[dict[str, Any]],
    default_reply: str,
) -> str:
    outcomes = [
        f"{str(item.get('title') or item.get('tool') or 'step')}: {str(item.get('summary') or '').strip()}"
        for item in tool_outputs
    ]
    compact_outcomes = "\n".join([row for row in outcomes if row.strip()][:8])
    if not compact_outcomes:
        return default_reply
    if not bool(get_settings().ENABLE_BUSINESS_AGENT_LLM_SUMMARY):
        key_points = " | ".join([row for row in outcomes if row.strip()][:3])
        return f"{default_reply} Key results: {key_points}" if key_points else default_reply

    user_role = str(getattr(getattr(user, "role", None), "code", "") or "student")
    user_name = str(getattr(user, "real_name", "") or "assistant")
    prompt = (
        f"你是 {agent_name}。\n"
        "请基于工具执行结果，输出简洁可执行结论。\n"
        f"用户消息：{message}\n"
        f"目标岗位：{target_job or '未指定'}\n"
        f"工具结果：\n{compact_outcomes}\n"
        "输出格式：1) 结论 2) 关键证据 3) 下一步建议（最多 3 条）"
    )
    try:
        reply = llm_service.chat(
            user_role=user_role,
            user_name=user_name,
            message=prompt,
            history=[],
            context={"scene": "business_agent_summary", "tool_outputs": tool_outputs, "reply_mode": "structured"},
        )
        return str(reply or default_reply).strip() or default_reply
    except Exception:
        return default_reply


def run_tools(
    registry: AgentToolRegistry,
    *,
    user: Any,
    message: str,
    target_job: str,
    tool_names: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    tool_outputs, tool_steps, context_patch, _ = run_tool_pipeline(
        registry,
        user=user,
        message=message,
        target_job=target_job,
        tool_names=tool_names,
    )
    return tool_outputs, tool_steps, context_patch
