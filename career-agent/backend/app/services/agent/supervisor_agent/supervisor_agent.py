from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.auth import User
from app.services.agent.chat_agent.chat_agent import ChatAgent
from app.services.agent.capability_registry import (
    ALLOWED_DYNAMIC_AGENT_KEYS,
    BUSINESS_AGENT_KEYS,
    list_candidate_agent_keys,
    validate_agent_step,
)
from app.services.agent.common.agent_llm_profiles import build_agent_llm_service, get_agent_llm_profile
from app.services.agent.contracts import AgentReport, SupervisorAgentPlan, SupervisorDecision, SupervisorDispatchStep
from app.services.agent.registry import is_file_agent_enabled
from app.services.assistant_profile_intent import is_profile_image_intent, is_profile_insight_intent

if TYPE_CHECKING:
    from app.services.agent.code_agent.code_agent import CodeAgent
    from app.services.agent.file_agent.file_agent import FileAgent

class SupervisorAgent:
    MAX_AGENT_HOPS = 3
    ALLOWED_DYNAMIC_AGENT_KEYS = set(ALLOWED_DYNAMIC_AGENT_KEYS)
    BUSINESS_AGENT_KEYS = set(BUSINESS_AGENT_KEYS)
    DEMO_CONTROL_SKILLS = {"demo-script", "admin-metrics", "ops-review"}
    FILE_SKILL_TASK_MAP = {
        "resume-workbench": "parse_file",
        "report-builder": "generate_report",
        "delivery-ready": "generate_document",
    }

    def __init__(self, db: Session):
        from app.services.agent.code_agent.code_agent import CodeAgent
        from app.services.agent.file_agent.file_agent import FileAgent

        self.db = db
        self.settings = get_settings()
        self.llm_service = build_agent_llm_service("supervisor_agent")
        self.file_agent = FileAgent(db, llm_profile=get_agent_llm_profile("file_agent"))
        self.code_agent = CodeAgent(db, llm_service=build_agent_llm_service("code_agent"))
        self.chat_agent = ChatAgent(llm_service=build_agent_llm_service("chat_agent"))

    def route(
        self,
        *,
        user: User,
        message: str,
        selected_skill: str = "",
        session_state: dict[str, Any] | None = None,
        context_binding: dict[str, Any] | None = None,
        client_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session_state = session_state or {}
        context_binding = context_binding or {}
        client_state = client_state or {}
        selected_skill = str(selected_skill or "").strip()

        if selected_skill == "code-agent":
            code_task = self.code_agent.detect_task(message=message, selected_skill=selected_skill)
            language = str(code_task.get("language") or "python")
            return {
                "agent_route": "code",
                "task_type": language,
                "code_task": code_task,
                "agent_flow": self._build_code_flow(language),
            }

        if selected_skill in self.FILE_SKILL_TASK_MAP:
            task_type = self._detect_file_intent(
                message=message,
                selected_skill=selected_skill,
                session_state=session_state,
                context_binding=context_binding,
                client_state=client_state,
            )
            if task_type:
                if is_file_agent_enabled():
                    return {
                        "agent_route": "file",
                        "task_type": task_type,
                        "agent_flow": self._build_file_flow(task_type),
                    }
                return {
                    "agent_route": "file_unavailable",
                    "task_type": task_type,
                    "agent_flow": self._build_file_unavailable_flow(task_type),
                }

        if selected_skill and selected_skill != "general-chat":
            patch = self.build_demo_control_context_patch(
                selected_skill=selected_skill,
                message=message,
                session_state=session_state,
                context_binding=context_binding,
                client_state=client_state,
            )
            payload = {
                "agent_route": "complex",
                "task_type": selected_skill,
                "agent_flow": self._build_complex_flow(),
            }
            if patch:
                payload["supervisor_context_patch"] = patch
            return payload

        simple_intent_info = self.chat_agent.classify_simple_intent(message=message)
        if bool(simple_intent_info.get("is_simple")):
            simple_intent = str(simple_intent_info.get("intent") or "small_talk")
            return {
                "agent_route": "simple",
                "task_type": simple_intent,
                "simple_intent": simple_intent,
                "agent_flow": self._build_simple_flow(simple_intent),
            }

        file_task_type = self._detect_file_intent(
            message=message,
            selected_skill=selected_skill,
            session_state=session_state,
            context_binding=context_binding,
            client_state=client_state,
        )
        if file_task_type:
            if is_file_agent_enabled():
                return {
                    "agent_route": "file",
                    "task_type": file_task_type,
                    "agent_flow": self._build_file_flow(file_task_type),
                }
            return {
                "agent_route": "file_unavailable",
                "task_type": file_task_type,
                "agent_flow": self._build_file_unavailable_flow(file_task_type),
            }

        code_task = self.code_agent.detect_task(message=message, selected_skill=selected_skill)
        if bool(code_task.get("is_code_task")):
            language = str(code_task.get("language") or "python")
            return {
                "agent_route": "code",
                "task_type": language,
                "code_task": code_task,
                "agent_flow": self._build_code_flow(language),
            }

        return {
            "agent_route": "complex",
            "task_type": "",
            "agent_flow": self._build_complex_flow(),
        }

    def plan_agent_workflow(
        self,
        *,
        user: User,
        message: str,
        selected_skill: str = "",
        session_state: dict[str, Any] | None = None,
        context_binding: dict[str, Any] | None = None,
        client_state: dict[str, Any] | None = None,
    ) -> SupervisorAgentPlan:
        if not bool(getattr(self.settings, "SUPERVISOR_DYNAMIC_DISPATCH", True)):
            raise RuntimeError("SUPERVISOR_DYNAMIC_DISPATCH is disabled")
        if not str(getattr(self.llm_service, "api_key", "") or "").strip():
            raise RuntimeError("Supervisor dynamic dispatch model API key is not configured")
        if not hasattr(self.llm_service, "_request_chat_completion"):
            raise RuntimeError("Supervisor LLM service does not support structured planning")

        role = str(getattr(getattr(user, "role", None), "code", "") or "student")
        selected_skill = str(selected_skill or "").strip()
        candidate_agents = self._candidate_dynamic_agents(role=role, selected_skill=selected_skill, message=message)
        system_prompt = (
            "You are a Supervisor Agent that creates an auditable agent dispatch plan. "
            "Return ONLY one strict JSON object. Do not reveal hidden chain-of-thought. "
            "Use concise user-visible decision summaries instead of private reasoning. "
            f"Allowed agent_key values: {', '.join(sorted(self.ALLOWED_DYNAMIC_AGENT_KEYS))}. "
            "Prefer business agents for complex career-planning workflows; use chat/file/code only when they are clearly necessary. "
            "Each step must include step_id, agent_key, route, task_type, task_summary, depends_on, expected_output, stop_condition, and decision_summary."
        )
        payload = {
            "objective": message,
            "role": role,
            "selected_skill": selected_skill,
            "candidate_agents": candidate_agents,
            "session_state_keys": sorted((session_state or {}).keys()),
            "context_binding_keys": sorted((context_binding or {}).keys()),
            "client_state_keys": sorted((client_state or {}).keys()),
            "max_steps": int(getattr(self.settings, "SUPERVISOR_DYNAMIC_MAX_STEPS", 6) or 6),
            "required_output_schema": {
                "objective": "string",
                "candidate_agents": ["agent_key"],
                "selected_agents": ["agent_key"],
                "steps": [
                    {
                        "step_id": "string",
                        "agent_key": "agent_key",
                        "route": "business|chat|file|code",
                        "task_type": "string",
                        "task_summary": "string",
                        "depends_on": ["step_id"],
                        "expected_output": "string",
                        "stop_condition": "string",
                        "decision_summary": "string",
                    }
                ],
                "stop_conditions": ["string"],
                "decision_summary": "string",
            },
        }
        body = self.llm_service._request_chat_completion(
            {
                "model": str(getattr(self.llm_service, "model_name", "") or self.settings.SUPERVISOR_AGENT_MODULE_NAME),
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
            },
            timeout=int(getattr(self.settings, "SUPERVISOR_DYNAMIC_PLAN_TIMEOUT_SECONDS", 12) or 12),
        )
        content = ((body.get("choices") or [{}])[0].get("message") or {}).get("content")
        if isinstance(content, list):
            content = "".join(str(item.get("text") or "") for item in content if isinstance(item, dict))
        raw_plan = json.loads(self._extract_json_object(str(content or "")))
        return self._coerce_supervisor_plan(raw_plan, candidate_agents=candidate_agents)

    def _coerce_supervisor_plan(self, raw_plan: dict[str, Any], *, candidate_agents: list[str]) -> SupervisorAgentPlan:
        if not isinstance(raw_plan, dict):
            raise ValueError("Supervisor plan is not a JSON object")
        max_steps = int(getattr(self.settings, "SUPERVISOR_DYNAMIC_MAX_STEPS", 6) or 6)
        steps_raw = raw_plan.get("steps")
        if not isinstance(steps_raw, list) or not steps_raw:
            raise ValueError("Supervisor plan has no dispatch steps")
        if len(steps_raw) > max_steps:
            raise ValueError(f"Supervisor plan exceeds max steps: {len(steps_raw)} > {max_steps}")

        steps: list[SupervisorDispatchStep] = []
        seen_step_ids: set[str] = set()
        selected_agents: list[str] = []
        for index, item in enumerate(steps_raw, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"Supervisor plan step {index} is not an object")
            step_id = str(item.get("step_id") or f"step_{index}").strip()
            agent_key = str(item.get("agent_key") or "").strip()
            route = str(item.get("route") or ("business" if agent_key in self.BUSINESS_AGENT_KEYS else agent_key)).strip()
            task_type = str(item.get("task_type") or agent_key).strip() or agent_key
            validate_agent_step(agent_key=agent_key, route=route, task_type=task_type)
            if step_id in seen_step_ids:
                raise ValueError(f"Supervisor plan duplicates step id: {step_id}")
            depends_on = [str(value or "").strip() for value in (item.get("depends_on") or []) if str(value or "").strip()]
            missing_dependencies = [value for value in depends_on if value not in seen_step_ids]
            if missing_dependencies:
                raise ValueError(f"Supervisor plan step {step_id} has unresolved dependencies: {', '.join(missing_dependencies)}")
            steps.append(
                SupervisorDispatchStep(
                    step_id=step_id,
                    agent_key=agent_key,
                    route=route,
                    task_type=task_type,
                    task_summary=str(item.get("task_summary") or item.get("summary") or f"Call {agent_key} agent").strip(),
                    depends_on=depends_on,
                    expected_output=str(item.get("expected_output") or "").strip(),
                    stop_condition=str(item.get("stop_condition") or "step_completed").strip(),
                    decision_summary=str(item.get("decision_summary") or "").strip(),
                )
            )
            seen_step_ids.add(step_id)
            if agent_key not in selected_agents:
                selected_agents.append(agent_key)

        if not any(step.agent_key in self.BUSINESS_AGENT_KEYS for step in steps):
            raise ValueError("Supervisor plan has no executable business agent step")

        raw_candidates = raw_plan.get("candidate_agents") if isinstance(raw_plan.get("candidate_agents"), list) else candidate_agents
        normalized_candidates = []
        for agent_key in raw_candidates:
            text = str(agent_key or "").strip()
            if text in self.ALLOWED_DYNAMIC_AGENT_KEYS and text not in normalized_candidates:
                normalized_candidates.append(text)
        if not normalized_candidates:
            normalized_candidates = list(candidate_agents)

        return SupervisorAgentPlan(
            plan_id=f"sup_plan_{uuid4().hex[:10]}",
            objective=str(raw_plan.get("objective") or "").strip() or "处理用户任务",
            candidate_agents=normalized_candidates,
            selected_agents=selected_agents,
            steps=steps,
            stop_conditions=[
                str(item or "").strip()
                for item in (raw_plan.get("stop_conditions") if isinstance(raw_plan.get("stop_conditions"), list) else [])
                if str(item or "").strip()
            ]
            or ["all_selected_agents_completed", "requires_user_input", "max_dispatch_steps"],
            decision_summary=str(raw_plan.get("decision_summary") or "已生成可审计的 Agent 调度计划。").strip(),
            source="llm",
        )

    def _candidate_dynamic_agents(self, *, role: str, selected_skill: str, message: str) -> list[str]:
        return list_candidate_agent_keys(role=role, selected_skill=selected_skill, message=message)
        skill = str(selected_skill or "").strip()
        skill_pipeline_map = {
            "resume-workbench": ["knowledge", "delivery", "profile", "ux"],
            "report-builder": ["knowledge", "delivery", "ux"],
            "delivery-ready": ["profile", "delivery", "ux"],
            "growth-planner": ["knowledge", "growth", "ux"],
            "match-center": ["knowledge", "match", "ux"],
            "gap-analysis": ["knowledge", "match", "growth", "ux"],
            "profile-insight": ["profile", "match", "ux"],
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
        role_key = str(role or "student").strip().lower()
        if role_key == "enterprise":
            return ["recruitment", "profile", "ux"]
        if role_key == "admin":
            return ["governance", "demo", "ux"]
        compact = str(message or "").lower()
        if any(token in compact for token in ("匹配", "match", "gap", "差距")):
            return ["knowledge", "match", "growth", "ux"]
        if any(token in compact for token in ("报告", "投递", "交付", "delivery", "report")):
            return ["knowledge", "delivery", "ux"]
        return ["knowledge", "match", "growth", "ux"]

    @staticmethod
    def _extract_json_object(text: str) -> str:
        stripped = str(text or "").strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return stripped
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Supervisor plan response does not contain JSON")
        return stripped[start : end + 1]

    def init_agent_goal(
        self,
        *,
        message: str,
        selected_skill: str = "",
        session_state: dict[str, Any] | None = None,
        context_binding: dict[str, Any] | None = None,
        client_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session_state = session_state or {}
        context_binding = context_binding or {}
        client_state = client_state or {}

        code_task = self.code_agent.detect_task(message=message, selected_skill=selected_skill)
        file_task_type = self._detect_file_intent(
            message=message,
            selected_skill=selected_skill,
            session_state=session_state,
            context_binding=context_binding,
            client_state=client_state,
        )
        need_code = bool(code_task.get("is_code_task"))
        code_language = str(code_task.get("language") or "python") if need_code else ""
        need_file = bool(file_task_type)

        return {
            "need_code": need_code,
            "need_file": need_file,
            "done_code": False,
            "done_file": False,
            "code_language": code_language,
            "file_task_type": str(file_task_type or ""),
            "final_route": "",
            "stop_output": False,
            "hop_count": 0,
            "max_hops": self.MAX_AGENT_HOPS,
        }

    def create_agent_report(
        self,
        *,
        agent_name: str,
        route: str,
        task_type: str,
        status: str,
        requires_user_input: bool,
        tool_outputs_count: int,
        artifacts_count: int,
        context_patch_keys: list[str],
        summary: str,
        handoff_hint: str,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> AgentReport:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return AgentReport(
            report_id=f"rpt_{uuid4().hex[:12]}",
            agent_name=str(agent_name or "unknown"),
            route=str(route or ""),
            task_type=str(task_type or ""),
            status=str(status or "success"),
            requires_user_input=bool(requires_user_input),
            tool_outputs_count=int(tool_outputs_count or 0),
            artifacts_count=int(artifacts_count or 0),
            context_patch_keys=[str(item) for item in (context_patch_keys or [])],
            started_at=str(started_at or now),
            finished_at=str(finished_at or now),
            summary=str(summary or ""),
            handoff_hint=str(handoff_hint or ""),
        )

    def decide_after_report(
        self,
        *,
        goal: dict[str, Any],
        report: AgentReport | None,
    ) -> SupervisorDecision:
        state = dict(goal or {})
        hop_count = int(state.get("hop_count") or 0)

        if state.get("dynamic_plan_steps"):
            return self._decide_dynamic_after_report(state=state, report=report)

        if report:
            hop_count += 1
            state["hop_count"] = hop_count
            report_status = str(report.status or "")

            match report.route:
                case "code":
                    state["done_code"] = True
                    state["final_route"] = "code"
                case "file":
                    state["done_file"] = True
                    state["final_route"] = "file"
                case "complex":
                    state["final_route"] = "complex"
                case "simple":
                    state["final_route"] = "simple"
                case _:
                    state["final_route"] = str(state.get("final_route") or "complex")

            if report_status in {"failed", "error"}:
                state["stop_output"] = True

            if report.requires_user_input:
                state["stop_output"] = True

        if hop_count >= int(state.get("max_hops") or self.MAX_AGENT_HOPS):
            state["stop_output"] = True
            return self._build_pack_decision(state=state, stop_reason="max_hops")

        if bool(state.get("stop_output")):
            return self._build_pack_decision(state=state, stop_reason="needs_input")

        if bool(state.get("need_code")) and not bool(state.get("done_code")):
            return SupervisorDecision(
                route="code",
                task_type=str(state.get("code_language") or "python"),
                stop_reason="continue",
                goal=state,
            )

        if bool(state.get("need_file")) and not bool(state.get("done_file")):
            return SupervisorDecision(
                route="file",
                task_type=str(state.get("file_task_type") or "generate_document"),
                stop_reason="continue",
                goal=state,
            )

        return self._build_pack_decision(state=state, stop_reason="completed")

    def _decide_dynamic_after_report(self, *, state: dict[str, Any], report: AgentReport | None) -> SupervisorDecision:
        steps = [dict(item) for item in list(state.get("dynamic_plan_steps") or []) if isinstance(item, dict)]
        hop_count = int(state.get("hop_count") or 0)
        completed = {str(item or "") for item in list(state.get("completed_step_ids") or []) if str(item or "").strip()}
        current_step_id = str(state.get("current_step_id") or "")

        if report:
            hop_count += 1
            state["hop_count"] = hop_count
            report_status = str(report.status or "")
            if current_step_id and report_status in {"success", "done", "completed"}:
                completed.add(current_step_id)
                state["completed_step_ids"] = sorted(completed)
            if report.requires_user_input:
                state["stop_output"] = True
                state["final_route"] = "complex"
                return self._build_pack_decision(state=state, stop_reason="needs_input")
            if report_status in {"failed", "error"}:
                state["stop_output"] = True
                state["final_route"] = "complex"
                return SupervisorDecision(
                    route="pack_complex",
                    task_type="",
                    stop_reason="agent_failed",
                    goal=state,
                    requires_replan=True,
                    decision_summary=f"Agent {report.agent_name} 执行失败，停止动态调度并打包当前结果。",
                )

        if hop_count >= int(state.get("max_hops") or self.MAX_AGENT_HOPS):
            state["stop_output"] = True
            state["final_route"] = "complex"
            return SupervisorDecision(
                route="pack_complex",
                task_type="",
                stop_reason="max_hops",
                goal=state,
                decision_summary="达到最大动态调度步数，停止继续调用下属 Agent。",
            )

        for step in steps:
            step_id = str(step.get("step_id") or "")
            if not step_id or step_id in completed:
                continue
            depends_on = [str(item or "") for item in list(step.get("depends_on") or [])]
            if all(dep in completed for dep in depends_on):
                agent_key = str(step.get("agent_key") or "")
                state["current_step_id"] = step_id
                state["final_route"] = "complex"
                return SupervisorDecision(
                    route="business",
                    task_type=agent_key,
                    stop_reason="continue",
                    goal=state,
                    next_agent_key=agent_key,
                    next_step_id=step_id,
                    decision_summary=str(step.get("decision_summary") or step.get("task_summary") or f"继续调用 {agent_key} Agent。"),
                )

        state["stop_output"] = True
        state["final_route"] = "complex"
        return SupervisorDecision(
            route="pack_complex",
            task_type="",
            stop_reason="completed",
            goal=state,
            decision_summary="动态调度计划已完成，进入最终回复打包。",
        )

    def decide_next_agent(
        self,
        *,
        goal: dict[str, Any],
        last_agent: str = "",
        last_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        report = self._legacy_report(last_agent=last_agent, last_result=last_result or {})
        decision = self.decide_after_report(goal=goal, report=report)
        return {
            "goal": decision.goal,
            "route": decision.route,
            "task_type": decision.task_type,
            "stop_reason": decision.stop_reason,
        }

    def run_simple_task(
        self,
        *,
        user: User | None = None,
        message: str,
        simple_intent: str = "",
        agent_flow: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        resolved_intent = str(simple_intent or "").strip()
        if not resolved_intent:
            intent_info = self.chat_agent.classify_simple_intent(message=message)
            resolved_intent = str(intent_info.get("intent") or "small_talk")

        chat_result = self.chat_agent.reply_for_simple_intent(
            message=message,
            intent=resolved_intent,
            role=str(getattr(getattr(user, "role", None), "code", "") or "student"),
        )
        return {
            "agent_route": "simple",
            "simple_intent": resolved_intent,
            "chat_result": chat_result,
            "agent_flow": list(agent_flow or self._build_simple_flow(resolved_intent)),
        }

    def run_file_unavailable_task(
        self,
        *,
        user: User | None = None,
        task_type: str,
        agent_flow: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        normalized_task_type = str(task_type or "file_task")
        chat_result = self.chat_agent.reply_for_file_unavailable(
            task_type=normalized_task_type,
            role=str(getattr(getattr(user, "role", None), "code", "") or "student"),
        )
        return {
            "agent_route": "file_unavailable",
            "file_task": {"type": normalized_task_type, "status": "unavailable"},
            "chat_result": chat_result,
            "agent_flow": list(agent_flow or self._build_file_unavailable_flow(normalized_task_type)),
        }

    def run_code_task(
        self,
        *,
        user: User,
        message: str,
        selected_skill: str = "",
        session_state: dict[str, Any] | None = None,
        context_binding: dict[str, Any] | None = None,
        client_state: dict[str, Any] | None = None,
        agent_flow: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        code_result = self.code_agent.execute(
            user=user,
            message=message,
            selected_skill=selected_skill,
            session_state=session_state or {},
            context_binding=context_binding or {},
            client_state=client_state or {},
        )
        chat_result = self.chat_agent.reply_for_code_result(
            code_result,
            role=str(getattr(getattr(user, "role", None), "code", "") or "student"),
        )
        language = str((code_result.get("code_task") or {}).get("language") or "")
        flow = list(agent_flow or self._build_code_flow(language))
        flow.append({"step": len(flow) + 1, "agent": "chat", "action": "format_code_result"})
        return {
            "agent_route": "code",
            "code_result": code_result,
            "chat_result": chat_result,
            "agent_flow": flow,
        }

    def run_file_task(
        self,
        *,
        user: User,
        message: str,
        task_type: str,
        session_state: dict[str, Any] | None = None,
        context_binding: dict[str, Any] | None = None,
        client_state: dict[str, Any] | None = None,
        agent_flow: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if not is_file_agent_enabled():
            return self.run_file_unavailable_task(user=user, task_type=task_type, agent_flow=agent_flow)

        file_result = self.file_agent.execute(
            user=user,
            message=message,
            task_type=task_type,
            session_state=session_state or {},
            context_binding=context_binding or {},
            client_state=client_state or {},
        )
        if task_type == "optimize_resume" and self._file_result_requested_document(file_result):
            file_result = self._check_file_document_result(file_result)
        chat_result = self.chat_agent.reply_for_file_result(
            file_result,
            role=str(getattr(getattr(user, "role", None), "code", "") or "student"),
        )
        flow = list(agent_flow or self._build_file_flow(task_type))
        for step in list(file_result.get("agent_flow_patch") or []):
            if isinstance(step, dict):
                flow.append({"step": len(flow) + 1, "agent": str(step.get("agent") or ""), "action": str(step.get("action") or "")})
        flow.append({"step": len(flow) + 1, "agent": "chat", "action": "format_file_result"})
        return {
            "agent_route": "file",
            "file_result": file_result,
            "chat_result": chat_result,
            "agent_flow": flow,
        }

    def _check_file_document_result(self, file_result: dict[str, Any]) -> dict[str, Any]:
        if str(file_result.get("status") or "") != "success":
            return file_result

        artifacts = list(file_result.get("artifacts") or [])
        has_docx_artifact = any(
            str(item.get("type") or "") == "document"
            or str(item.get("type") or "") == "docx"
            or str(item.get("mime_type") or "") == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            for item in artifacts
            if isinstance(item, dict)
        )
        if not has_docx_artifact:
            return self._file_document_check_failed(file_result, "Supervisor 检查失败：未找到 DOCX document artifact。")

        tool_data = self._first_tool_output_data(file_result)
        spec = tool_data.get("document_build_spec")
        render_report = tool_data.get("code_render_report")
        if not isinstance(spec, dict):
            return self._file_document_check_failed(file_result, "Supervisor 检查失败：缺少 DocumentBuildSpec。")
        if not isinstance(render_report, dict) or str(render_report.get("status") or "") != "success":
            return self._file_document_check_failed(file_result, "Supervisor 检查失败：CodeAgent 渲染测试未通过。")

        missing = [
            field
            for field in (
                "document_type",
                "target_role",
                "enterprise_alignment",
                "career_planning",
                "revision_suggestions",
                "optimized_resume_document",
                "document_style",
                "sections",
                "supervisor_checklist",
            )
            if field not in spec or spec[field] in ("", None, [], {})
        ]
        if missing:
            return self._file_document_check_failed(file_result, f"Supervisor 检查失败：DocumentBuildSpec 缺少字段 {', '.join(missing)}。")

        section_text = json.dumps(spec["sections"], ensure_ascii=False)
        for title in ("企业匹配分析", "职业规划", "修改建议"):
            if title not in section_text:
                return self._file_document_check_failed(file_result, f"Supervisor 检查失败：sections 缺少 {title}。")

        suggestions = spec["revision_suggestions"]
        if not isinstance(suggestions, list) or not suggestions:
            return self._file_document_check_failed(file_result, "Supervisor 检查失败：revision_suggestions 为空。")
        for index, item in enumerate(suggestions, start=1):
            if (
                not isinstance(item, dict)
                or not str(item.get("field") or "").strip()
                or not str(item.get("suggestion") or "").strip()
                or not str(item.get("enterprise_reason") or "").strip()
                or not str(item.get("career_reason") or "").strip()
                or not str(item.get("evidence_boundary") or "").strip()
            ):
                return self._file_document_check_failed(file_result, f"Supervisor 检查失败：第 {index} 条修改建议缺少必要字段。")

        checked = dict(file_result)
        tool_steps = list(checked.get("tool_steps") or [])
        tool_steps.append({"tool": "supervisor_document_check", "status": "done", "text": "done: DOCX artifact and required sections passed"})
        checked["tool_steps"] = tool_steps
        return checked

    @staticmethod
    def _file_result_requested_document(file_result: dict[str, Any]) -> bool:
        artifacts = [item for item in list(file_result.get("artifacts") or []) if isinstance(item, dict)]
        if artifacts:
            return True
        for item in list(file_result.get("tool_outputs") or []):
            if isinstance(item, dict) and isinstance(item.get("data"), dict) and item["data"].get("export_requested") is True:
                return True
        return False

    @staticmethod
    def _first_tool_output_data(file_result: dict[str, Any]) -> dict[str, Any]:
        for item in list(file_result.get("tool_outputs") or []):
            if isinstance(item, dict) and isinstance(item.get("data"), dict):
                return item["data"]
        return {}

    @staticmethod
    def _file_document_check_failed(file_result: dict[str, Any], reason: str) -> dict[str, Any]:
        failed = dict(file_result)
        tool_steps = list(failed.get("tool_steps") or [])
        tool_steps.append({"tool": "supervisor_document_check", "status": "failed", "text": f"failed: {reason}"})
        failed.update(
            {
                "status": "failed",
                "reply": reason,
                "question": reason,
                "failure_reason": reason,
                "artifacts": [],
                "requires_user_input": False,
                "tool_steps": tool_steps,
                "file_task": {"type": "optimize_resume", "status": "failed", "failure_reason": reason},
            }
        )
        return failed

    def _detect_file_intent(
        self,
        *,
        message: str,
        selected_skill: str,
        session_state: dict[str, Any],
        context_binding: dict[str, Any],
        client_state: dict[str, Any],
    ) -> str:
        if is_profile_image_intent(message) or is_profile_insight_intent(message):
            return ""
        pending_file_offer = self._resolve_pending_file_offer(
            session_state=session_state,
            context_binding=context_binding,
            client_state=client_state,
        )
        if pending_file_offer:
            if self._is_file_offer_no(message):
                return ""
            if self._is_file_offer_yes(message):
                task_type = self.file_agent.detect_task(message=message, selected_skill=selected_skill)
                return task_type or "generate_document"

        task_type = self.file_agent.detect_task(message=message, selected_skill=selected_skill)
        return str(task_type or "")

    def _build_pack_decision(self, *, state: dict[str, Any], stop_reason: str) -> SupervisorDecision:
        final_route = str(state.get("final_route") or "")
        if not final_route:
            if bool(state.get("done_file")):
                final_route = "file"
            elif bool(state.get("done_code")):
                final_route = "code"
            else:
                final_route = "complex"

        match final_route:
            case "file":
                return SupervisorDecision(
                    route="pack_file",
                    task_type=str(state.get("file_task_type") or "generate_document"),
                    stop_reason=stop_reason,
                    goal=state,
                )
            case "code":
                return SupervisorDecision(
                    route="pack_code",
                    task_type=str(state.get("code_language") or "python"),
                    stop_reason=stop_reason,
                    goal=state,
                )
            case "simple":
                return SupervisorDecision(
                    route="pack_simple",
                    task_type=str(state.get("simple_intent") or "small_talk"),
                    stop_reason=stop_reason,
                    goal=state,
                )
            case _:
                return SupervisorDecision(
                    route="pack_complex",
                    task_type="",
                    stop_reason=stop_reason,
                    goal=state,
                )

    def _legacy_report(self, *, last_agent: str, last_result: dict[str, Any]) -> AgentReport | None:
        if not last_agent:
            return None

        route = "file" if last_agent == "file" else "code" if last_agent == "code" else str(last_agent or "")
        status = str(last_result.get("status") or "success")
        task_type = ""
        if route == "file":
            task_type = str((last_result.get("file_task") or {}).get("type") or "")
        if route == "code":
            task_type = str((last_result.get("code_task") or {}).get("language") or "")

        context_patch = last_result.get("context_patch") if isinstance(last_result.get("context_patch"), dict) else {}
        return self.create_agent_report(
            agent_name=last_agent,
            route=route,
            task_type=task_type,
            status=status,
            requires_user_input=bool(last_result.get("requires_user_input")),
            tool_outputs_count=len(list(last_result.get("tool_outputs") or [])),
            artifacts_count=len(list(last_result.get("artifacts") or [])),
            context_patch_keys=sorted(context_patch.keys()),
            summary=str(last_result.get("reply") or ""),
            handoff_hint="legacy_reconcile",
        )

    @staticmethod
    def _resolve_pending_file_offer(
        *,
        session_state: dict[str, Any],
        context_binding: dict[str, Any],
        client_state: dict[str, Any],
    ) -> dict[str, Any]:
        state_binding = session_state.get("context_binding") if isinstance(session_state.get("context_binding"), dict) else {}
        candidates = (
            client_state.get("pending_file_offer"),
            context_binding.get("pending_file_offer"),
            state_binding.get("pending_file_offer"),
            session_state.get("pending_file_offer"),
        )
        for item in candidates:
            if isinstance(item, dict) and str(item.get("source") or "") == "code_agent":
                return item
        return {}

    @staticmethod
    def _is_file_offer_yes(message: str) -> bool:
        compact = "".join(str(message or "").strip().lower().split())
        if not compact:
            return False
        short_yes_tokens = {"yes", "y", "ok", "okay", "好的", "可以", "是", "需要"}
        if compact in short_yes_tokens:
            return True
        file_action_tokens = ("导出", "下载", "文件", "word", "doc", "docx", "pdf", "zip", "打包")
        return any(token in compact for token in file_action_tokens)

    @staticmethod
    def _is_file_offer_no(message: str) -> bool:
        compact = "".join(str(message or "").strip().lower().split())
        if not compact:
            return False
        no_tokens = ("不用", "不需要", "先不用", "暂时不用", "no", "n")
        return any(token in compact for token in no_tokens)

    @staticmethod
    def _build_file_flow(task_type: str) -> list[dict[str, Any]]:
        return [
            {"step": 1, "agent": "chat", "action": "forward_intent_to_supervisor"},
            {"step": 2, "agent": "supervisor", "action": f"dispatch_file_task:{task_type or 'file_task'}"},
            {"step": 3, "agent": "file", "action": f"execute:{task_type or 'file_task'}"},
        ]

    @staticmethod
    def _build_file_unavailable_flow(task_type: str) -> list[dict[str, Any]]:
        return [
            {"step": 1, "agent": "chat", "action": "forward_intent_to_supervisor"},
            {"step": 2, "agent": "supervisor", "action": f"dispatch_file_unavailable:{task_type or 'file_task'}"},
            {"step": 3, "agent": "chat", "action": "format_file_unavailable_reply"},
        ]

    @staticmethod
    def _build_code_flow(language: str) -> list[dict[str, Any]]:
        return [
            {"step": 1, "agent": "chat", "action": "forward_intent_to_supervisor"},
            {"step": 2, "agent": "supervisor", "action": f"dispatch_code_task:{language or 'code_task'}"},
            {"step": 3, "agent": "code", "action": f"execute:{language or 'code_task'}"},
        ]

    @staticmethod
    def _build_simple_flow(simple_intent: str) -> list[dict[str, Any]]:
        return [
            {"step": 1, "agent": "chat", "action": "forward_intent_to_supervisor"},
            {"step": 2, "agent": "supervisor", "action": f"dispatch_simple_task:{simple_intent or 'small_talk'}"},
            {"step": 3, "agent": "chat", "action": "format_simple_reply"},
        ]

    @staticmethod
    def _build_complex_flow() -> list[dict[str, Any]]:
        return [
            {"step": 1, "agent": "chat", "action": "forward_intent_to_supervisor"},
            {"step": 2, "agent": "supervisor", "action": "dispatch_complex_task"},
            {"step": 3, "agent": "complex", "action": "intent_slot_plan_tool_llm"},
            {"step": 4, "agent": "chat", "action": "format_complex_result"},
        ]

    def build_demo_control_context_patch(
        self,
        *,
        selected_skill: str,
        message: str,
        session_state: dict[str, Any],
        context_binding: dict[str, Any],
        client_state: dict[str, Any],
    ) -> dict[str, Any]:
        skill = str(selected_skill or "").strip()
        if skill not in self.DEMO_CONTROL_SKILLS:
            return {}

        compact = "".join(str(message or "").strip().lower().split())
        state_binding = session_state.get("context_binding") if isinstance(session_state.get("context_binding"), dict) else {}
        previous_control = (
            client_state.get("demo_control")
            if isinstance(client_state.get("demo_control"), dict)
            else context_binding.get("demo_control")
            if isinstance(context_binding.get("demo_control"), dict)
            else state_binding.get("demo_control")
            if isinstance(state_binding.get("demo_control"), dict)
            else {}
        )
        auto_mode = bool(
            client_state.get("demo_auto_mode")
            if client_state.get("demo_auto_mode") is not None
            else previous_control.get("auto_mode", True)
        )
        if any(token in compact for token in ("手动", "manual")):
            auto_mode = False
        if any(token in compact for token in ("自动", "auto", "一键演示")):
            auto_mode = True

        scene = str(
            client_state.get("demo_scene")
            or context_binding.get("demo_scene")
            or previous_control.get("scene")
            or "career_defense"
        )
        if any(token in compact for token in ("切换", "switch")):
            scene = str(client_state.get("next_demo_scene") or "targeted_case")

        action = "monitor"
        if any(token in compact for token in ("启动", "start", "开始")):
            action = "start"
        elif any(token in compact for token in ("切换", "switch")):
            action = "switch"
        elif any(token in compact for token in ("暂停", "pause")):
            action = "pause"

        mode = "auto_play" if auto_mode else "manual_override"
        return {
            "context_binding": {
                "demo_control": {
                    "skill": skill,
                    "scene": scene,
                    "mode": mode,
                    "auto_mode": auto_mode,
                    "action": action,
                    "status": "active",
                    "narration": "enabled",
                }
            }
        }

