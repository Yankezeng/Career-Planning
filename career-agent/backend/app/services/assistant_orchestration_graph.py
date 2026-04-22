from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from app.services.assistant_fallback_service import build_career_guidance_fallback
from app.services.assistant_profile_intent import is_profile_image_intent, is_profile_insight_intent
from app.services.assistant_skill_catalog_service import normalize_skill_code
from app.services.assistant_turn_intent_guard import (
    extract_target_job_from_text,
    has_explicit_continue_request,
    infer_explicit_student_skill,
    is_profile_image_skill,
    should_ignore_stale_profile_skill,
)
from app.services.agent.context_manager import AgentContextManager
from app.services.agent.event_bus import InMemoryAgentEventBus

class AssistantOrchestrationGraph:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    def run(self, initial_state: dict[str, Any]) -> dict[str, Any]:
        state = dict(initial_state or {})
        state.setdefault("agent_flow", [])
        state.setdefault("agent_reports", [])
        state.setdefault("supervisor_decisions", [])
        state.setdefault("supervisor_plan", {})
        state.setdefault("dispatch_trace", self._new_dispatch_trace())
        state.setdefault("decision_trace", [])
        state.setdefault(
            "_context_manager",
            AgentContextManager(
                session_state=dict(state.get("session_state") or {}),
                context_binding=dict(state.get("binding_in") or {}),
                client_state=dict(state.get("client_state") or {}),
            ),
        )
        state.setdefault("_agent_event_bus", InMemoryAgentEventBus(trace_id=str((state.get("dispatch_trace") or {}).get("trace_id") or "")))

        entry = self._supervisor_entry(state)
        state.update(entry)
        state["supervisor_goal"] = self._init_supervisor_goal(state)

        decision: dict[str, Any] | None = None
        while True:
            route = str(state.get("route") or "complex")
            runtime: dict[str, Any]
            report_route = route

            if route == "simple":
                runtime = self._run_simple_route(state)
                state["simple_runtime"] = runtime
            elif route == "file":
                runtime = self._run_file_route(state)
                state["file_runtime"] = runtime
                report_route = "file"
            elif route == "file_unavailable":
                runtime = self._run_file_unavailable_route(state)
                state["file_runtime"] = runtime
                report_route = "file"
            elif route == "code":
                runtime = self._run_code_route(state)
                state["code_runtime"] = runtime
            elif route == "business":
                runtime = self._run_business_agent_route(state)
                state["business_runtime"] = runtime
                report_route = "business"
            elif route == "dispatch_failed":
                runtime = self._run_dispatch_failed_route(state)
                state["complex_runtime"] = runtime
                report_route = "dispatch_failed"
            else:
                runtime = self._run_complex_route(state)
                state["complex_runtime"] = runtime
                report_route = "complex"

            report = self._supervisor_collect_report(state=state, route=report_route, runtime=runtime)
            decision = self._supervisor_control(state=state, report=report)
            next_route = str(decision.get("route") or "")
            if next_route.startswith("pack_"):
                break
            state["route"] = next_route or "complex"
            state["task_type"] = str(decision.get("task_type") or "")

        return self._pack_response(state=state, decision=decision or {})

    def _supervisor_entry(self, state: dict[str, Any]) -> dict[str, Any]:
        supervisor = self.orchestrator.supervisor
        message = str(state.get("message") or "")
        selected_skill = str(state.get("selected_skill_normalized") or "")
        session_state = dict(state.get("session_state") or {})
        binding_in = dict(state.get("binding_in") or {})
        client_state = dict(state.get("client_state") or {})

        self._apply_current_turn_skill_override(state)
        selected_skill = str(state.get("selected_skill_normalized") or "")

        file_task_type = supervisor._detect_file_intent(
            message=message,
            selected_skill=selected_skill,
            session_state=session_state,
            context_binding=binding_in,
            client_state=client_state,
        )
        if file_task_type:
            route = "file" if self._is_file_agent_enabled() else "file_unavailable"
            return {
                "route": route,
                "task_type": str(file_task_type),
                "agent_flow": self._build_agent_flow(route=route, task_type=str(file_task_type)),
            }

        selected_route = self._route_from_selected_skill(
            selected_skill=selected_skill,
            message=message,
            state=state,
            supervisor=supervisor,
        )
        if selected_route:
            if str(selected_route.get("route") or "") == "complex":
                if self._should_attempt_dynamic_dispatch(selected_skill=selected_skill):
                    dynamic_route = self._try_dynamic_entry(state=state, fallback_entry=selected_route)
                    if dynamic_route:
                        return dynamic_route
            return selected_route

        simple_intent_info = supervisor.chat_agent.classify_simple_intent(message=message)
        if bool(simple_intent_info.get("is_simple")):
            simple_intent = str(simple_intent_info.get("intent") or "small_talk")
            return {
                "route": "simple",
                "task_type": simple_intent,
                "simple_intent": simple_intent,
                "agent_flow": self._build_agent_flow(route="simple", task_type=simple_intent),
            }

        code_task = supervisor.code_agent.detect_task(message=message, selected_skill=selected_skill)
        if bool(code_task.get("is_code_task")):
            language = str(code_task.get("language") or "python")
            return {
                "route": "code",
                "task_type": language,
                "agent_flow": self._build_agent_flow(route="code", task_type=language),
            }

        fallback_entry = {
            "route": "complex",
            "task_type": "",
            "agent_flow": self._build_agent_flow(route="complex", task_type=""),
        }
        if not self._should_attempt_dynamic_dispatch(selected_skill=selected_skill):
            return fallback_entry
        dynamic_route = self._try_dynamic_entry(state=state, fallback_entry=fallback_entry)
        return dynamic_route

    def _try_dynamic_entry(self, *, state: dict[str, Any], fallback_entry: dict[str, Any]) -> dict[str, Any] | None:
        supervisor = self.orchestrator.supervisor
        if not hasattr(supervisor, "plan_agent_workflow"):
            return self._dynamic_dispatch_failed_entry(state=state, reason="Supervisor does not expose plan_agent_workflow.")
        start = perf_counter()
        self._append_trace_event(
            state,
            event="分析任务",
            status="running",
            summary="Supervisor 正在判断是否需要动态调度业务 Agent。",
        )
        try:
            plan = supervisor.plan_agent_workflow(
                user=state.get("user"),
                message=str(state.get("message") or ""),
                selected_skill=str(state.get("selected_skill_normalized") or ""),
                session_state=dict(state.get("session_state") or {}),
                context_binding=dict(state.get("binding_in") or {}),
                client_state=dict(state.get("client_state") or {}),
            )
            plan_dict = plan.to_dict() if hasattr(plan, "to_dict") else dict(plan)
            steps = [dict(item) for item in list(plan_dict.get("steps") or []) if isinstance(item, dict)]
            first_step = next(
                (
                    step
                    for step in steps
                    if str(step.get("agent_key") or "") in getattr(supervisor, "BUSINESS_AGENT_KEYS", set())
                    and not list(step.get("depends_on") or [])
                ),
                None,
            )
            if not first_step:
                raise ValueError("dynamic plan has no executable first business agent step")
            state["supervisor_plan"] = plan_dict
            self._append_trace_event(
                state,
                event="选择候选 Agent",
                status="done",
                summary=f"候选 Agent：{', '.join(plan_dict.get('candidate_agents') or [])}",
                decision_summary=str(plan_dict.get("decision_summary") or ""),
                duration_ms=self._elapsed_ms(start),
            )
            self._append_trace_event(
                state,
                event="确定执行顺序",
                status="done",
                summary=" -> ".join(str(step.get("agent_key") or "") for step in steps),
                decision_summary=str(plan_dict.get("decision_summary") or ""),
            )
            return {
                "route": "business",
                "task_type": str(first_step.get("agent_key") or ""),
                "agent_flow": self._build_dynamic_agent_flow(plan_dict),
                "supervisor_plan": plan_dict,
                "dynamic_start_step_id": str(first_step.get("step_id") or ""),
                "supervisor_context_patch": fallback_entry.get("supervisor_context_patch") if isinstance(fallback_entry, dict) else {},
            }
        except (RuntimeError, ValueError, KeyError, TypeError) as exc:
            reason = str(exc)
            self._append_trace_event(
                state,
                event="切换稳妥回复",
                status="done",
                summary="复杂问题的动态调度未完整完成，已切换为稳定回复模式。",
                fallback_reason="",
                duration_ms=self._elapsed_ms(start),
            )
            trace = state.get("dispatch_trace") if isinstance(state.get("dispatch_trace"), dict) else {}
            trace["fallback_used"] = True
            trace["fallback_reason"] = "dynamic_dispatch_unavailable"
            trace["status"] = "fallback"
            state["dispatch_trace"] = trace
            state["dispatch_failure_reason"] = reason
            state["supervisor_plan"] = {}
            return dict(fallback_entry or {"route": "complex", "task_type": "", "agent_flow": self._build_agent_flow(route="complex", task_type="")})

    def _dynamic_dispatch_failed_entry(self, *, state: dict[str, Any], reason: str) -> dict[str, Any]:
        state["dispatch_failure_reason"] = str(reason or "Supervisor dynamic dispatch failed.")
        return {
            "route": "dispatch_failed",
            "task_type": "supervisor_dynamic_dispatch",
            "agent_flow": self._build_agent_flow(route="complex", task_type="supervisor_dynamic_dispatch"),
        }

    def _build_dynamic_agent_flow(self, plan: dict[str, Any]) -> list[dict[str, Any]]:
        flow = [{"step": 1, "agent": "chat", "action": "forward_intent_to_supervisor"}]
        flow.append({"step": 2, "agent": "supervisor", "action": "plan_dynamic_dispatch"})
        for item in list(plan.get("steps") or []):
            if not isinstance(item, dict):
                continue
            flow.append(
                {
                    "step": len(flow) + 1,
                    "agent": str(item.get("agent_key") or ""),
                    "action": str(item.get("task_summary") or item.get("task_type") or "execute_dynamic_step"),
                    "step_id": str(item.get("step_id") or ""),
                    "depends_on": list(item.get("depends_on") or []),
                    "decision_summary": str(item.get("decision_summary") or ""),
                }
            )
        flow.append({"step": len(flow) + 1, "agent": "chat", "action": "format_dynamic_dispatch_result"})
        return flow

    def _init_supervisor_goal(self, state: dict[str, Any]) -> dict[str, Any]:
        route = str(state.get("route") or "")
        task_type = str(state.get("task_type") or "")
        simple_intent = str(state.get("simple_intent") or "")
        max_hops = int(getattr(self.orchestrator.supervisor, "MAX_AGENT_HOPS", 3))
        supervisor_plan = dict(state.get("supervisor_plan") or {})
        dynamic_steps = [dict(item) for item in list(supervisor_plan.get("steps") or []) if isinstance(item, dict)]
        supervisor_settings = getattr(self.orchestrator.supervisor, "settings", None)
        if dynamic_steps:
            max_hops = min(
                int(getattr(supervisor_settings, "SUPERVISOR_DYNAMIC_MAX_STEPS", max_hops) or max_hops),
                max(len(dynamic_steps) + 1, max_hops),
            )
        return {
            "need_code": route == "code",
            "need_file": route in {"file", "file_unavailable"},
            "done_code": False,
            "done_file": False,
            "code_language": task_type if route == "code" else "",
            "file_task_type": task_type if route in {"file", "file_unavailable"} else "",
            "simple_intent": simple_intent if route == "simple" else "",
            "final_route": "",
            "stop_output": False,
            "hop_count": 0,
            "max_hops": max_hops,
            "dynamic_plan_id": str(supervisor_plan.get("plan_id") or ""),
            "dynamic_plan_steps": dynamic_steps,
            "current_step_id": str(state.get("dynamic_start_step_id") or (dynamic_steps[0] if dynamic_steps else {}).get("step_id") or ""),
            "completed_step_ids": [],
            "replan_count": 0,
            "max_replans": int(getattr(supervisor_settings, "SUPERVISOR_DYNAMIC_REPLAN_LIMIT", 1) or 1),
        }

    def _run_simple_route(self, state: dict[str, Any]) -> dict[str, Any]:
        runtime = self.orchestrator.supervisor.run_simple_task(
            user=state.get("user"),
            message=str(state.get("message") or ""),
            simple_intent=str(state.get("task_type") or state.get("simple_intent") or ""),
            agent_flow=list(state.get("agent_flow") or []),
        )
        state["agent_flow"] = list(runtime.get("agent_flow") or state.get("agent_flow") or [])
        return runtime

    def _run_file_route(self, state: dict[str, Any]) -> dict[str, Any]:
        supervisor = self.orchestrator.supervisor
        if hasattr(supervisor, "run_file_task"):
            runtime = supervisor.run_file_task(
                user=state.get("user"),
                message=str(state.get("message") or ""),
                task_type=str(state.get("task_type") or "generate_document"),
                session_state=dict(state.get("session_state") or {}),
                context_binding=dict(state.get("binding_in") or {}),
                client_state=dict(state.get("client_state") or {}),
                agent_flow=list(state.get("agent_flow") or []),
            )
        else:
            file_result = supervisor.file_agent.execute(
                user=state.get("user"),
                message=str(state.get("message") or ""),
                task_type=str(state.get("task_type") or "generate_document"),
                session_state=dict(state.get("session_state") or {}),
                context_binding=dict(state.get("binding_in") or {}),
                client_state=dict(state.get("client_state") or {}),
            )
            chat_result = supervisor.chat_agent.reply_for_file_result(file_result)
            flow = list(state.get("agent_flow") or [])
            flow.append({"step": len(flow) + 1, "agent": "chat", "action": "format_file_result"})
            runtime = {
                "agent_route": "file",
                "file_result": file_result,
                "chat_result": chat_result,
                "agent_flow": flow,
            }
        state["agent_flow"] = list(runtime.get("agent_flow") or state.get("agent_flow") or [])
        return runtime

    def _run_file_unavailable_route(self, state: dict[str, Any]) -> dict[str, Any]:
        supervisor = self.orchestrator.supervisor
        if hasattr(supervisor, "run_file_unavailable_task"):
            runtime = supervisor.run_file_unavailable_task(
                user=state.get("user"),
                task_type=str(state.get("task_type") or "generate_document"),
                agent_flow=list(state.get("agent_flow") or []),
            )
        else:
            flow = list(state.get("agent_flow") or [])
            flow.append({"step": len(flow) + 1, "agent": "chat", "action": "format_file_unavailable_reply"})
            runtime = {
                "agent_route": "file_unavailable",
                "file_task": {"type": str(state.get("task_type") or "file_task"), "status": "unavailable"},
                "chat_result": {
                    "reply": "File agent is unavailable now.",
                    "reply_mode": "brief",
                    "reply_blocks": [{"type": "summary", "text": "File agent is unavailable now."}],
                    "actions": [],
                },
                "agent_flow": flow,
            }
        state["agent_flow"] = list(runtime.get("agent_flow") or state.get("agent_flow") or [])
        return runtime

    def _run_code_route(self, state: dict[str, Any]) -> dict[str, Any]:
        supervisor = self.orchestrator.supervisor
        if hasattr(supervisor, "run_code_task"):
            runtime = supervisor.run_code_task(
                user=state.get("user"),
                message=str(state.get("message") or ""),
                selected_skill=str(state.get("selected_skill_normalized") or ""),
                session_state=dict(state.get("session_state") or {}),
                context_binding=dict(state.get("binding_in") or {}),
                client_state=dict(state.get("client_state") or {}),
                agent_flow=list(state.get("agent_flow") or []),
            )
        else:
            code_result = supervisor.code_agent.execute(
                user=state.get("user"),
                message=str(state.get("message") or ""),
                selected_skill=str(state.get("selected_skill_normalized") or ""),
                session_state=dict(state.get("session_state") or {}),
                context_binding=dict(state.get("binding_in") or {}),
                client_state=dict(state.get("client_state") or {}),
            )
            chat_result = supervisor.chat_agent.reply_for_code_result(code_result)
            flow = list(state.get("agent_flow") or [])
            flow.append({"step": len(flow) + 1, "agent": "chat", "action": "format_code_result"})
            runtime = {
                "agent_route": "code",
                "code_result": code_result,
                "chat_result": chat_result,
                "agent_flow": flow,
            }
        state["agent_flow"] = list(runtime.get("agent_flow") or state.get("agent_flow") or [])
        return runtime

    def _run_business_agent_route(self, state: dict[str, Any]) -> dict[str, Any]:
        self._prepare_dynamic_complex_context(state)
        if bool(state.get("dynamic_requires_user_input")):
            return {"requires_user_input": True, "agent_key": str(state.get("task_type") or "")}

        agent_key = str(state.get("task_type") or "").strip()
        current_step = self._current_dynamic_step(state, agent_key=agent_key)
        step_id = str(current_step.get("step_id") or state.get("current_step_id") or "")
        step_summary = str(current_step.get("task_summary") or f"调用 {agent_key} Agent")
        self._append_trace_event(
            state,
            event="调用 Agent",
            status="running",
            agent_key=agent_key,
            step_id=step_id,
            summary=step_summary,
            decision_summary=str(current_step.get("decision_summary") or ""),
        )
        started = perf_counter()
        result = self.orchestrator.flowchart_agents.execute_one(
            agent_key=agent_key,
            user=state.get("user"),
            message=str(state.get("message") or ""),
            target_job=str((state.get("slots") or {}).get("target_job") or ""),
        )
        duration_ms = self._elapsed_ms(started)
        state["dynamic_last_reply"] = result.reply or state.get("dynamic_last_reply") or ""
        state["dynamic_last_agent"] = result.agent_name or agent_key

        tool_outputs = list(state.get("tool_outputs") or [])
        tool_outputs.extend(list(result.tool_outputs or []))
        if result.context_patch:
            context_manager = state.get("_context_manager")
            if isinstance(context_manager, AgentContextManager):
                snapshot = context_manager.apply_context_patch({"context_binding": dict(result.context_patch)})
                state["session_state"] = snapshot["session_state"]
                state["binding_in"] = snapshot["context_binding"]
                state["client_state"] = snapshot["client_state"]
            tool_outputs.append(
                {
                    "tool": "flowchart_agent_context",
                    "title": "Flowchart agent context",
                    "summary": "Flowchart agent context patch",
                    "data": {},
                    "next_actions": [],
                    "context_patch": dict(result.context_patch),
                }
            )
        state["tool_outputs"] = tool_outputs

        tool_steps = list(state.get("tool_steps") or [])
        step_cursor = len(tool_steps) + 1
        for row in list(result.tool_steps or []):
            step_row = dict(row or {})
            step_row["step"] = step_cursor
            step_row.setdefault("agent", result.agent_name or agent_key)
            tool_steps.append(step_row)
            step_cursor += 1
        state["tool_steps"] = tool_steps

        actions = list(state.get("actions") or [])
        for action in list(result.actions or []):
            text = str(action or "").strip()
            if text and text not in actions:
                actions.append(text)
        state["actions"] = actions[:5]

        for action in [*list(result.call_flow or []), *list(result.data_flow or [])]:
            state["agent_flow"].append({"step": len(state["agent_flow"]) + 1, "agent": agent_key, "action": str(action)})

        self._append_trace_event(
            state,
            event="等待 Agent 报告",
            status="done",
            agent_key=agent_key,
            step_id=step_id,
            summary=result.reply or f"{agent_key} Agent 已完成。",
            output_summary=self._summarize_business_result(result),
            duration_ms=duration_ms,
        )
        return {"requires_user_input": False, "business_result": result, "agent_key": agent_key, "step_id": step_id}

    def _run_dispatch_failed_route(self, state: dict[str, Any]) -> dict[str, Any]:
        reason = str(state.get("dispatch_failure_reason") or "Supervisor dynamic dispatch failed.")
        fallback = self._build_student_fallback_response(state=state, reason=reason)
        state.update(
            {
                "reply": fallback["reply"],
                    "reply_mode": "brief",
                    "reply_blocks": list(fallback["reply_blocks"]),
                    "actions": list(fallback["actions"]),
                    "context_binding": fallback.get("context_binding") or {},
                    "binding_in": {**dict(state.get("binding_in") or {}), **dict(fallback.get("context_binding") or {})},
                    "session_state": {**dict(state.get("session_state") or {}), **dict(fallback.get("session_state") or {})},
                    "tool_outputs": [],
                    "tool_steps": [{"tool": "supervisor_dynamic_dispatch", "status": "failed", "text": "复杂问题已自动切换为稳妥建议模式"}],
                }
        )
        return {"requires_user_input": False, "error": fallback["error_message"], "reply": fallback["reply"]}

    def _prepare_dynamic_complex_context(self, state: dict[str, Any]) -> None:
        if bool(state.get("dynamic_complex_context_prepared")):
            return
        state["dynamic_complex_context_prepared"] = True
        message = str(state.get("message") or "")
        role = str(state.get("role") or "student")
        session_state = dict(state.get("session_state") or {})
        binding_in = dict(state.get("binding_in") or {})

        intent_info, slots = self._build_intent_and_slots(state)
        confidence = self.orchestrator._to_float(intent_info.get("confidence"), 0.0)
        allow_carryover = self._allow_skill_carryover(message=message, slots=slots)
        selected_skill_for_plan = self._selected_skill_for_plan(
            state=state,
            message=message,
            allow_carryover=allow_carryover,
        )
        fallback_skill = (
            self.orchestrator._infer_skill_enhanced(
                role=role,
                text=message,
                intent_info=intent_info,
                slots=slots,
                session_state=session_state,
                allow_carryover=allow_carryover,
            )
            if bool(getattr(self.orchestrator, "use_enhanced_mode", False))
            else (selected_skill_for_plan or "general-chat")
        )
        plan = self.orchestrator.plan_service.build(
            role=role,
            message=message,
            intent=str(intent_info.get("intent") or "ask_advice"),
            slots=slots,
            selected_skill=selected_skill_for_plan,
            fallback_skill=fallback_skill,
            session_state=session_state,
            context_binding=binding_in,
        )

        need_clarify = self.orchestrator._should_clarify_by_confidence(
            intent_info=intent_info,
            slots=slots,
            confidence=confidence,
        )
        if need_clarify:
            plan = dict(plan)
            plan["intent"] = "clarify_required"
            plan["reply_mode"] = "brief"
            plan["clarify_question"] = str(plan.get("clarify_question") or "请先补充关键信息。")
            state.update(
                {
                    "plan": plan,
                    "slots": slots,
                    "intent_info": intent_info,
                    "intent_confidence": confidence,
                    "tool_outputs": [],
                    "tool_steps": [],
                    "retrieval_chunks": [],
                    "knowledge_hits": [],
                    "actions": [],
                    "reply": str(plan.get("clarify_question") or "请先补充关键信息。"),
                    "reply_mode": "brief",
                    "reply_blocks": [{"type": "summary", "text": str(plan.get("clarify_question") or "请先补充关键信息。")}],
                    "dynamic_requires_user_input": True,
                }
            )
            return

        plan_result = self.orchestrator._execute_plan(
            user=state.get("user"),
            message=message,
            plan=plan,
            slots=slots,
            intent_info=intent_info,
            session_state=session_state,
        )
        state.update(
            {
                "plan": plan,
                "slots": slots,
                "intent_info": intent_info,
                "intent_confidence": confidence,
                "tool_outputs": list(plan_result.get("tool_outputs") or []),
                "tool_steps": list(plan_result.get("tool_steps") or []),
                "retrieval_chunks": list(plan_result.get("retrieval_chunks") or []),
                "knowledge_hits": list(plan_result.get("knowledge_hits") or []),
                "actions": [],
                "reply_mode": str(plan.get("reply_mode") or "structured"),
            }
        )

    def _finalize_dynamic_complex_response(self, state: dict[str, Any]) -> None:
        if bool(state.get("dynamic_final_response_ready")):
            return
        if not state.get("supervisor_plan"):
            return
        state["dynamic_final_response_ready"] = True
        if bool(state.get("dynamic_requires_user_input")):
            return

        message = str(state.get("message") or "")
        role = str(state.get("role") or "student")
        history = list(state.get("history") or [])
        plan = dict(state.get("plan") or {})
        tool_outputs = list(state.get("tool_outputs") or [])
        retrieval_chunks = list(state.get("retrieval_chunks") or [])
        reply_mode = str(state.get("reply_mode") or plan.get("reply_mode") or "structured")
        reply = self._profile_image_reply_from_tool_outputs(tool_outputs) or self.orchestrator.llm_service.chat(
            user_role=role,
            user_name=str(getattr(state.get("user"), "real_name", "") or "assistant"),
            message=message,
            history=history,
            context={
                "scene": "assistant_chat",
                "tool_outputs": tool_outputs,
                "retrieval_chunks": retrieval_chunks,
                "reply_mode": reply_mode,
                "supervisor_plan": dict(state.get("supervisor_plan") or {}),
                "dispatch_trace": dict(state.get("dispatch_trace") or {}),
            },
        )
        actions = list(state.get("actions") or self.orchestrator._collect_actions(tool_outputs))
        followups = self.orchestrator.llm_service.generate_followup_actions(
            role=role,
            normalized_skill=str(plan.get("normalized_skill") or "general-chat"),
            tool_outputs=tool_outputs,
            user_message=message,
        )
        for item in followups:
            text = str(item or "").strip()
            if text and text not in actions:
                actions.append(text)
        actions = actions[:5]
        reply_blocks = self.orchestrator._build_reply_blocks(
            reply=reply,
            reply_mode=reply_mode,
            tool_outputs=tool_outputs,
            retrieval_chunks=retrieval_chunks,
            actions=actions,
        )
        state.update({"reply": reply, "reply_mode": reply_mode, "reply_blocks": reply_blocks, "actions": actions})
        self._append_trace_event(
            state,
            event="完成",
            status="done",
            summary="Supervisor 动态调度已完成，正在返回最终回复。",
        )

    @staticmethod
    def _profile_image_reply_from_tool_outputs(tool_outputs: list[dict[str, Any]]) -> str:
        for item in tool_outputs:
            if not isinstance(item, dict) or item.get("tool") != "generate_profile_image":
                continue
            data = item.get("data") if isinstance(item.get("data"), dict) else {}
            reply = str(data.get("assistant_reply") or "").strip()
            if reply:
                return reply
        return ""

    def _current_dynamic_step(self, state: dict[str, Any], *, agent_key: str) -> dict[str, Any]:
        step_id = str((state.get("supervisor_goal") or {}).get("current_step_id") or state.get("current_step_id") or "")
        for step in list((state.get("supervisor_goal") or {}).get("dynamic_plan_steps") or []):
            if not isinstance(step, dict):
                continue
            if step_id and str(step.get("step_id") or "") == step_id:
                return dict(step)
        for step in list((state.get("supervisor_plan") or {}).get("steps") or []):
            if isinstance(step, dict) and str(step.get("agent_key") or "") == agent_key:
                return dict(step)
        return {"agent_key": agent_key, "task_summary": f"调用 {agent_key} Agent"}

    @staticmethod
    def _summarize_business_result(result: Any) -> str:
        output_count = len(list(getattr(result, "tool_outputs", []) or []))
        step_count = len(list(getattr(result, "tool_steps", []) or []))
        return f"产物 {output_count} 项，工具步骤 {step_count} 项。"

    def _run_complex_route(self, state: dict[str, Any]) -> dict[str, Any]:
        message = str(state.get("message") or "")
        role = str(state.get("role") or "student")
        session_state = dict(state.get("session_state") or {})
        binding_in = dict(state.get("binding_in") or {})
        client_state = dict(state.get("client_state") or {})
        history = list(state.get("history") or [])

        intent_info, slots = self._build_intent_and_slots(state)
        confidence = self.orchestrator._to_float(intent_info.get("confidence"), 0.0)
        allow_carryover = self._allow_skill_carryover(message=message, slots=slots)
        selected_skill_for_plan = self._selected_skill_for_plan(
            state=state,
            message=message,
            allow_carryover=allow_carryover,
        )
        fallback_skill = (
            self.orchestrator._infer_skill_enhanced(
                role=role,
                text=message,
                intent_info=intent_info,
                slots=slots,
                session_state=session_state,
                allow_carryover=allow_carryover,
            )
            if bool(getattr(self.orchestrator, "use_enhanced_mode", False))
            else (
                self.orchestrator._infer_skill(role, message, session_state, allow_carryover=allow_carryover)
                if hasattr(self.orchestrator, "_infer_skill")
                else (selected_skill_for_plan or "general-chat")
            )
        )
        plan = self.orchestrator.plan_service.build(
            role=role,
            message=message,
            intent=str(intent_info.get("intent") or "ask_advice"),
            slots=slots,
            selected_skill=selected_skill_for_plan,
            fallback_skill=fallback_skill,
            session_state=session_state,
            context_binding=binding_in,
        )

        need_clarify = self.orchestrator._should_clarify_by_confidence(
            intent_info=intent_info,
            slots=slots,
            confidence=confidence,
        )
        if need_clarify:
            plan = dict(plan)
            plan["intent"] = "clarify_required"
            plan["reply_mode"] = "brief"
            plan["clarify_question"] = str(plan.get("clarify_question") or "请先告诉我目标岗位。")

        tool_outputs: list[dict[str, Any]] = []
        tool_steps: list[dict[str, Any]] = []
        retrieval_chunks: list[dict[str, Any]] = []
        knowledge_hits: list[dict[str, Any]] = []
        requires_user_input = plan.get("intent") == "clarify_required"

        if not requires_user_input:
            plan_result = self.orchestrator._execute_plan(
                user=state.get("user"),
                message=message,
                plan=plan,
                slots=slots,
                intent_info=intent_info,
                session_state=session_state,
            )
            tool_outputs = list(plan_result.get("tool_outputs") or [])
            tool_steps = list(plan_result.get("tool_steps") or [])
            retrieval_chunks = list(plan_result.get("retrieval_chunks") or [])
            knowledge_hits = list(plan_result.get("knowledge_hits") or [])

            supervisor_context_patch = state.get("supervisor_context_patch")
            if isinstance(supervisor_context_patch, dict) and supervisor_context_patch:
                tool_outputs.append(
                    {
                        "tool": "supervisor_demo_control",
                        "title": "Supervisor Demo Control",
                        "summary": "Supervisor demo control state was updated.",
                        "data": {"selected_skill": str(state.get("selected_skill_normalized") or "")},
                        "next_actions": ["继续执行当前演示流程", "切换手动或自动模式"],
                        "context_patch": supervisor_context_patch,
                    }
                )
                state["agent_flow"].append(
                    {"step": len(state["agent_flow"]) + 1, "agent": "supervisor", "action": "sync_demo_control_state"}
                )

            if bool(getattr(self.orchestrator, "flowchart_agent_split_v2", False)):
                business_result = self.orchestrator.flowchart_agents.execute(
                    role=role,
                    normalized_skill=str(plan.get("normalized_skill") or state.get("selected_skill_normalized") or "general-chat"),
                    user=state.get("user"),
                    message=message,
                    target_job=str(slots.get("target_job") or ""),
                )
                tool_outputs.extend(list(business_result.tool_outputs))
                tool_steps.extend(list(business_result.tool_steps))
                if business_result.context_patch:
                    tool_outputs.append(
                        {
                            "tool": "flowchart_agent_context",
                            "title": "Flowchart agent context",
                            "summary": "Flowchart agent context patch",
                            "data": {},
                            "next_actions": [],
                            "context_patch": dict(business_result.context_patch),
                        }
                    )
                for action in [*business_result.call_flow, *business_result.data_flow]:
                    state["agent_flow"].append(
                        {"step": len(state["agent_flow"]) + 1, "agent": "flowchart", "action": str(action)}
                    )

        reply_mode = "brief" if requires_user_input else str(plan.get("reply_mode") or "structured")
        if requires_user_input:
            reply = str(plan.get("clarify_question") or "请先补充关键信息。")
            actions: list[str] = []
        else:
            reply = self._profile_image_reply_from_tool_outputs(tool_outputs) or self.orchestrator.llm_service.chat(
                user_role=role,
                user_name=str(getattr(state.get("user"), "real_name", "") or "assistant"),
                message=message,
                history=history,
                context={
                    "scene": "assistant_chat",
                    "tool_outputs": tool_outputs,
                    "retrieval_chunks": retrieval_chunks,
                    "reply_mode": reply_mode,
                },
            )
            actions = self.orchestrator._collect_actions(tool_outputs)
            followups = self.orchestrator.llm_service.generate_followup_actions(
                role=role,
                normalized_skill=str(plan.get("normalized_skill") or "general-chat"),
                tool_outputs=tool_outputs,
                user_message=message,
            )
            for item in followups:
                text = str(item or "").strip()
                if text and text not in actions:
                    actions.append(text)
            actions = actions[:5]

        reply_blocks = self.orchestrator._build_reply_blocks(
            reply=reply,
            reply_mode=reply_mode,
            tool_outputs=tool_outputs,
            retrieval_chunks=retrieval_chunks,
            actions=actions,
        )

        state.update(
            {
                "plan": plan,
                "slots": slots,
                "intent_info": intent_info,
                "intent_confidence": confidence,
                "tool_outputs": tool_outputs,
                "tool_steps": tool_steps,
                "retrieval_chunks": retrieval_chunks,
                "knowledge_hits": knowledge_hits,
                "actions": actions,
                "reply": reply,
                "reply_mode": reply_mode,
                "reply_blocks": reply_blocks,
            }
        )
        return {"requires_user_input": requires_user_input}

    def _build_intent_and_slots(self, state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        message = str(state.get("message") or "")
        session_state = dict(state.get("session_state") or {})
        binding_in = dict(state.get("binding_in") or {})
        client_state = dict(state.get("client_state") or {})
        selected_skill = str(state.get("selected_skill_normalized") or "")
        history = list(state.get("history") or [])

        intent_info = dict(self.orchestrator.intent_service.detect(message, session_state=session_state))
        slots = dict(
            self.orchestrator.slot_service.extract(
                message=message,
                selected_skill=selected_skill,
                session_state=session_state,
                context_binding=binding_in,
                client_state=client_state,
            )
        )
        if not bool(getattr(self.orchestrator, "use_enhanced_mode", False)):
            return intent_info, slots

        classifier_intent = dict(self.orchestrator.intent_classifier.classify(message, session_state=session_state))
        refined_intent = dict(self.orchestrator.intent_refiner.refine(message, history=history, session_state=session_state))
        extracted_slots = dict(
            self.orchestrator.entity_extractor.extract(
                message,
                session_state=session_state,
                context_binding=binding_in,
                client_state=client_state,
            )
        )

        intent_info.update(classifier_intent)
        intent_info.update(refined_intent)
        for key, value in extracted_slots.items():
            if value:
                slots[key] = value
        explicit_job = extract_target_job_from_text(message)
        if explicit_job:
            slots["target_job"] = explicit_job
            intent_info["extracted_job"] = explicit_job
        explicit_skill = infer_explicit_student_skill(message, slots=slots, intent_info=intent_info)
        if explicit_skill:
            slots["selected_skill"] = explicit_skill
            intent_info["recommend_skill"] = explicit_skill
            if explicit_skill == "growth-planner":
                intent_info["intent"] = "growth_planning"
        if not intent_info.get("extracted_job") and slots.get("target_job"):
            intent_info["extracted_job"] = slots.get("target_job")
        return intent_info, slots

    def _supervisor_collect_report(self, *, state: dict[str, Any], route: str, runtime: dict[str, Any]) -> Any:
        supervisor = self.orchestrator.supervisor

        if route == "simple":
            chat_result = runtime.get("chat_result") or {}
            payload = {
                "agent_name": "ChatAgent",
                "route": "simple",
                "task_type": str(runtime.get("simple_intent") or state.get("task_type") or "small_talk"),
                "status": "success",
                "requires_user_input": False,
                "tool_outputs_count": 0,
                "artifacts_count": 0,
                "context_patch_keys": [],
                "summary": str(chat_result.get("reply") or ""),
                "handoff_hint": "pack_simple",
            }
            report = supervisor.create_agent_report(**payload) if hasattr(supervisor, "create_agent_report") else payload
        elif route == "file":
            file_result = runtime.get("file_result") or {}
            chat_result = runtime.get("chat_result") or {}
            context_patch = file_result.get("context_patch") if isinstance(file_result.get("context_patch"), dict) else {}
            payload = {
                "agent_name": "FileAgent",
                "route": "file",
                "task_type": str((file_result.get("file_task") or {}).get("type") or state.get("task_type") or ""),
                "status": str(file_result.get("status") or "success"),
                "requires_user_input": bool(file_result.get("requires_user_input")),
                "tool_outputs_count": len(list(file_result.get("tool_outputs") or [])),
                "artifacts_count": len(list(file_result.get("artifacts") or [])),
                "context_patch_keys": sorted(context_patch.keys()),
                "summary": str(chat_result.get("reply") or file_result.get("reply") or ""),
                "handoff_hint": "pack_file",
            }
            report = supervisor.create_agent_report(**payload) if hasattr(supervisor, "create_agent_report") else payload
        elif route == "code":
            code_result = runtime.get("code_result") or {}
            chat_result = runtime.get("chat_result") or {}
            context_patch = code_result.get("context_patch") if isinstance(code_result.get("context_patch"), dict) else {}
            payload = {
                "agent_name": "CodeAgent",
                "route": "code",
                "task_type": str((code_result.get("code_task") or {}).get("language") or state.get("task_type") or "python"),
                "status": str(code_result.get("status") or "success"),
                "requires_user_input": bool(code_result.get("requires_user_input")),
                "tool_outputs_count": len(list(code_result.get("tool_outputs") or [])),
                "artifacts_count": len(list(code_result.get("artifacts") or [])),
                "context_patch_keys": sorted(context_patch.keys()),
                "summary": str(chat_result.get("reply") or code_result.get("reply") or ""),
                "handoff_hint": "pack_code",
            }
            report = supervisor.create_agent_report(**payload) if hasattr(supervisor, "create_agent_report") else payload
        elif route == "business":
            result = runtime.get("business_result")
            agent_key = str(runtime.get("agent_key") or state.get("task_type") or "business")
            payload = {
                "agent_name": str(getattr(result, "agent_name", "") or agent_key),
                "route": "business",
                "task_type": agent_key,
                "status": "success",
                "requires_user_input": bool(runtime.get("requires_user_input")),
                "tool_outputs_count": len(list(getattr(result, "tool_outputs", []) or [])),
                "artifacts_count": 0,
                "context_patch_keys": sorted((getattr(result, "context_patch", {}) or {}).keys()) if result else [],
                "summary": str(getattr(result, "reply", "") or state.get("reply") or ""),
                "handoff_hint": "continue_dynamic_dispatch",
            }
            report = supervisor.create_agent_report(**payload) if hasattr(supervisor, "create_agent_report") else payload
        elif route == "dispatch_failed":
            payload = {
                "agent_name": "SupervisorAgent",
                "route": "dispatch_failed",
                "task_type": "supervisor_dynamic_dispatch",
                "status": "failed",
                "requires_user_input": False,
                "tool_outputs_count": 0,
                "artifacts_count": 0,
                "context_patch_keys": [],
                "summary": str(runtime.get("error") or state.get("dispatch_failure_reason") or ""),
                "handoff_hint": "pack_complex",
            }
            report = supervisor.create_agent_report(**payload) if hasattr(supervisor, "create_agent_report") else payload
        else:
            payload = {
                "agent_name": "ComplexAgent",
                "route": "complex",
                "task_type": str((state.get("plan") or {}).get("normalized_skill") or ""),
                "status": "success",
                "requires_user_input": bool(runtime.get("requires_user_input")),
                "tool_outputs_count": len(list(state.get("tool_outputs") or [])),
                "artifacts_count": 0,
                "context_patch_keys": [],
                "summary": str(state.get("reply") or ""),
                "handoff_hint": "pack_complex",
            }
            report = supervisor.create_agent_report(**payload) if hasattr(supervisor, "create_agent_report") else payload

        state["agent_reports"].append(report.to_dict() if hasattr(report, "to_dict") else dict(report))
        return report

    def _supervisor_control(self, *, state: dict[str, Any], report: Any) -> dict[str, Any]:
        supervisor = self.orchestrator.supervisor
        if hasattr(supervisor, "decide_after_report"):
            decision = supervisor.decide_after_report(
                goal=dict(state.get("supervisor_goal") or {}),
                report=report,
            )
            decision_dict = decision.to_dict()
        else:
            report_route = str((report.to_dict() if hasattr(report, "to_dict") else report).get("route") or "complex")
            task_type = str((report.to_dict() if hasattr(report, "to_dict") else report).get("task_type") or "")
            pack_route = (
                "pack_file"
                if report_route == "file"
                else "pack_code"
                if report_route == "code"
                else "pack_simple"
                if report_route == "simple"
                else "pack_complex"
            )
            decision_dict = {
                "route": pack_route,
                "task_type": task_type,
                "stop_reason": "completed",
                "goal": dict(state.get("supervisor_goal") or {}),
            }
        if bool(decision_dict.get("requires_replan")) and str(decision_dict.get("route") or "") == "pack_complex":
            replan_decision = self._try_dynamic_replan(state=state, report=report)
            if replan_decision:
                decision_dict = replan_decision
        if str(decision_dict.get("route") or "") == "pack_complex":
            self._finalize_dynamic_complex_response(state)
        state["supervisor_goal"] = dict(decision_dict.get("goal") or {})
        state["supervisor_decisions"].append(decision_dict)
        state["decision_trace"].append(
            {
                "route": str(decision_dict.get("route") or ""),
                "task_type": str(decision_dict.get("task_type") or ""),
                "next_agent_key": str(decision_dict.get("next_agent_key") or ""),
                "next_step_id": str(decision_dict.get("next_step_id") or ""),
                "requires_replan": bool(decision_dict.get("requires_replan")),
                "decision_summary": str(decision_dict.get("decision_summary") or ""),
                "stop_reason": str(decision_dict.get("stop_reason") or ""),
            }
        )
        return decision_dict

    def _try_dynamic_replan(self, *, state: dict[str, Any], report: Any) -> dict[str, Any] | None:
        goal = dict(state.get("supervisor_goal") or {})
        replan_count = int(goal.get("replan_count") or 0)
        max_replans = int(goal.get("max_replans") or 0)
        if replan_count >= max_replans:
            return None

        supervisor = self.orchestrator.supervisor
        report_payload = report.to_dict() if hasattr(report, "to_dict") else dict(report or {})
        started = perf_counter()
        self._append_trace_event(
            state,
            event="重规划",
            status="running",
            agent_key=str(report_payload.get("agent_name") or ""),
            summary="Supervisor 正在基于失败报告重新规划一次 Agent 调度。",
        )
        try:
            client_state = dict(state.get("client_state") or {})
            client_state["previous_dispatch_trace"] = dict(state.get("dispatch_trace") or {})
            client_state["last_agent_report"] = report_payload
            plan = supervisor.plan_agent_workflow(
                user=state.get("user"),
                message=str(state.get("message") or ""),
                selected_skill=str(state.get("selected_skill_normalized") or ""),
                session_state=dict(state.get("session_state") or {}),
                context_binding=dict(state.get("binding_in") or {}),
                client_state=client_state,
            )
            plan_dict = plan.to_dict() if hasattr(plan, "to_dict") else dict(plan)
            steps = [dict(item) for item in list(plan_dict.get("steps") or []) if isinstance(item, dict)]
            first_step = next(
                (
                    step
                    for step in steps
                    if str(step.get("agent_key") or "") in getattr(supervisor, "BUSINESS_AGENT_KEYS", set())
                    and not list(step.get("depends_on") or [])
                ),
                None,
            )
            if not first_step:
                raise ValueError("replan has no executable first business agent step")
            replan_count += 1
            goal.update(
                {
                    "dynamic_plan_id": str(plan_dict.get("plan_id") or ""),
                    "dynamic_plan_steps": steps,
                    "current_step_id": str(first_step.get("step_id") or ""),
                    "completed_step_ids": [],
                    "replan_count": replan_count,
                    "hop_count": int(goal.get("hop_count") or 0),
                    "final_route": "complex",
                }
            )
            state["supervisor_plan"] = plan_dict
            state["supervisor_goal"] = goal
            self._append_trace_event(
                state,
                event="重规划",
                status="done",
                agent_key=str(first_step.get("agent_key") or ""),
                step_id=str(first_step.get("step_id") or ""),
                summary="Supervisor 已完成唯一一次动态重规划。",
                decision_summary=str(plan_dict.get("decision_summary") or ""),
                duration_ms=self._elapsed_ms(started),
            )
            return {
                "route": "business",
                "task_type": str(first_step.get("agent_key") or ""),
                "stop_reason": "replan",
                "goal": goal,
                "next_agent_key": str(first_step.get("agent_key") or ""),
                "next_step_id": str(first_step.get("step_id") or ""),
                "requires_replan": False,
                "decision_summary": str(plan_dict.get("decision_summary") or "Supervisor 已完成唯一一次动态重规划。"),
            }
        except (ValueError, RuntimeError, KeyError, TypeError) as exc:
            reason = str(exc)
            fallback = self._build_student_fallback_response(state=state, reason=reason)
            state.update(
                {
                    "reply": fallback["reply"],
                    "reply_mode": "brief",
                    "reply_blocks": list(fallback["reply_blocks"]),
                    "actions": list(fallback["actions"]),
                    "context_binding": fallback.get("context_binding") or {},
                    "binding_in": {**dict(state.get("binding_in") or {}), **dict(fallback.get("context_binding") or {})},
                    "session_state": {**dict(state.get("session_state") or {}), **dict(fallback.get("session_state") or {})},
                    "dynamic_final_response_ready": True,
                }
            )
            trace = state.get("dispatch_trace") if isinstance(state.get("dispatch_trace"), dict) else {}
            trace["fallback_used"] = True
            trace["fallback_reason"] = "dynamic_replan_failed"
            trace["status"] = "fallback"
            state["dispatch_trace"] = trace
            self._append_trace_event(
                state,
                event="切换稳妥回复",
                status="done",
                summary="复杂问题的重规划未完整完成，已切换为稳定回复模式。",
                duration_ms=self._elapsed_ms(started),
            )
            return None

    def _pack_response(self, *, state: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
        pack_route = str(decision.get("route") or "pack_complex")
        result: dict[str, Any]
        if pack_route == "pack_simple":
            result = self.orchestrator._pack_simple_response(state=state, runtime=dict(state.get("simple_runtime") or {}))
        elif pack_route == "pack_code":
            runtime = dict(state.get("code_runtime") or {})
            result = self.orchestrator._pack_code_response(
                state=state,
                code_result=dict(runtime.get("code_result") or {}),
                chat_result=dict(runtime.get("chat_result") or {}),
            )
        elif pack_route == "pack_file":
            runtime = dict(state.get("file_runtime") or {})
            file_result = dict(runtime.get("file_result") or {})
            if not file_result:
                file_result = {
                    "status": "unavailable",
                    "reply": str((runtime.get("chat_result") or {}).get("reply") or ""),
                    "tool_outputs": [],
                    "tool_steps": [],
                    "file_task": dict(runtime.get("file_task") or {"type": state.get("task_type") or "", "status": "unavailable"}),
                    "artifacts": [],
                    "requires_user_input": False,
                }
            result = self.orchestrator._pack_file_response(
                state=state,
                file_result=file_result,
                chat_result=dict(runtime.get("chat_result") or {}),
            )
        else:
            result = self.orchestrator._pack_complex_response(state=state)
        result = self._filter_mismatched_profile_image_outputs(result=result, state=state)
        if not result.get("agent_flow"):
            result["agent_flow"] = list(state.get("agent_flow") or [])
        trace = state.get("dispatch_trace") if isinstance(state.get("dispatch_trace"), dict) else {}
        if trace:
            trace = dict(trace)
            trace["finished_at"] = trace.get("finished_at") or self._now_iso()
            if trace.get("status") not in {"fallback", "failed"}:
                trace["status"] = "done"
            state["dispatch_trace"] = trace
        result["supervisor_plan"] = dict(state.get("supervisor_plan") or {})
        result["dispatch_trace"] = dict(state.get("dispatch_trace") or {})
        result["decision_trace"] = list(state.get("decision_trace") or state.get("supervisor_decisions") or [])
        return result

    @staticmethod
    def _filter_mismatched_profile_image_outputs(*, result: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        role = str(state.get("role") or "student")
        effective_skill = normalize_skill_code(
            result.get("normalized_skill") or result.get("used_skill") or state.get("selected_skill_normalized") or "",
            role,
        )
        if effective_skill == "profile-image":
            return result

        filtered = dict(result)
        filtered["cards"] = [
            item
            for item in list(filtered.get("cards") or [])
            if not AssistantOrchestrationGraph._is_profile_image_payload(item)
        ]
        filtered["tool_outputs"] = [
            item
            for item in list(filtered.get("tool_outputs") or [])
            if not AssistantOrchestrationGraph._is_profile_image_payload(item)
        ]
        filtered["tool_steps"] = [
            item
            for item in list(filtered.get("tool_steps") or [])
            if not (isinstance(item, dict) and str(item.get("tool") or "") == "generate_profile_image")
        ]
        return filtered

    @staticmethod
    def _is_profile_image_payload(item: Any) -> bool:
        if not isinstance(item, dict):
            return False
        card = item.get("card") if isinstance(item.get("card"), dict) else {}
        return (
            str(item.get("tool") or "") == "generate_profile_image"
            or str(item.get("type") or "") == "profile_image_card"
            or str(card.get("type") or "") == "profile_image_card"
            or str(card.get("tool") or "") == "generate_profile_image"
        )

    def _new_dispatch_trace(self) -> dict[str, Any]:
        now = self._now_iso()
        return {
            "trace_id": f"trace_{uuid4().hex[:10]}",
            "status": "running",
            "events": [],
            "fallback_used": False,
            "fallback_reason": "",
            "started_at": now,
            "finished_at": "",
        }

    def _append_trace_event(
        self,
        state: dict[str, Any],
        *,
        event: str,
        status: str,
        summary: str,
        agent_key: str = "",
        step_id: str = "",
        decision_summary: str = "",
        output_summary: str = "",
        fallback_reason: str = "",
        duration_ms: int | None = None,
    ) -> None:
        trace = state.get("dispatch_trace") if isinstance(state.get("dispatch_trace"), dict) else self._new_dispatch_trace()
        event_bus = state.get("_agent_event_bus")
        if not isinstance(event_bus, InMemoryAgentEventBus):
            event_bus = InMemoryAgentEventBus(trace_id=str(trace.get("trace_id") or ""))
            state["_agent_event_bus"] = event_bus
        events = list(trace.get("events") or [])
        event_row = event_bus.publish(
            event=event,
            status=status,
            agent_key=agent_key,
            step_id=step_id,
            summary=summary,
            decision_summary=decision_summary,
            output_summary=output_summary,
            failure_reason=fallback_reason,
            duration_ms=duration_ms if duration_ms is not None else 0,
        )
        event_row["fallback_reason"] = fallback_reason
        events.append(event_row)
        trace["events"] = events
        if status == "failed":
            trace["status"] = "failed"
        state["dispatch_trace"] = trace

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    @staticmethod
    def _elapsed_ms(start: float) -> int:
        return max(0, round((perf_counter() - start) * 1000))

    @staticmethod
    def _build_agent_flow(*, route: str, task_type: str) -> list[dict[str, Any]]:
        if route in {"file", "file_unavailable"}:
            action = "dispatch_file_task" if route == "file" else "dispatch_file_unavailable"
            return [
                {"step": 1, "agent": "chat", "action": "forward_intent_to_supervisor"},
                {"step": 2, "agent": "supervisor", "action": f"{action}:{task_type or 'file_task'}"},
                {"step": 3, "agent": "file" if route == "file" else "chat", "action": f"execute:{task_type or 'file_task'}"},
            ]
        if route == "code":
            return [
                {"step": 1, "agent": "chat", "action": "forward_intent_to_supervisor"},
                {"step": 2, "agent": "supervisor", "action": f"dispatch_code_task:{task_type or 'python'}"},
                {"step": 3, "agent": "code", "action": f"execute:{task_type or 'python'}"},
            ]
        if route == "simple":
            return [
                {"step": 1, "agent": "chat", "action": "forward_intent_to_supervisor"},
                {"step": 2, "agent": "supervisor", "action": f"dispatch_simple_task:{task_type or 'small_talk'}"},
                {"step": 3, "agent": "chat", "action": "format_simple_reply"},
            ]
        return [
            {"step": 1, "agent": "chat", "action": "forward_intent_to_supervisor"},
            {"step": 2, "agent": "supervisor", "action": "dispatch_complex_task"},
            {"step": 3, "agent": "complex", "action": "intent_slot_plan_tool_llm"},
            {"step": 4, "agent": "chat", "action": "format_complex_result"},
        ]

    def _apply_current_turn_skill_override(self, state: dict[str, Any]) -> None:
        if str(state.get("role") or "student") != "student":
            return
        message = str(state.get("message") or "")
        selected_skill = str(state.get("selected_skill_normalized") or "")
        if is_profile_image_intent(message):
            return
        slots = {"target_job": extract_target_job_from_text(message)}
        explicit_skill = infer_explicit_student_skill(message, slots=slots)
        if explicit_skill:
            state["selected_skill_normalized"] = explicit_skill
            state["current_turn_skill_override"] = explicit_skill
            self._append_trace_event(
                state,
                event="识别当前意图",
                status="done",
                summary=f"当前请求已明确切换到 {explicit_skill}，优先使用本轮意图。",
            )
            return
        if should_ignore_stale_profile_skill(selected_skill=selected_skill, text=message):
            state["selected_skill_normalized"] = ""
            state["current_turn_skill_override"] = "general-chat"
            self._append_trace_event(
                state,
                event="清理旧技能状态",
                status="done",
                summary="检测到画像生成技能与当前请求不匹配，已取消旧技能粘连。",
            )

    @staticmethod
    def _allow_skill_carryover(*, message: str, slots: dict[str, Any]) -> bool:
        return bool(slots.get("continue_previous_task")) or has_explicit_continue_request(message)

    @staticmethod
    def _selected_skill_for_plan(*, state: dict[str, Any], message: str, allow_carryover: bool) -> str:
        override = str(state.get("current_turn_skill_override") or "")
        if override and override != "general-chat":
            return override
        selected_skill = str(state.get("selected_skill_normalized") or "")
        if not allow_carryover and is_profile_image_skill(selected_skill) and not is_profile_image_intent(message):
            return ""
        return selected_skill

    @staticmethod
    def _should_attempt_dynamic_dispatch(*, selected_skill: str) -> bool:
        skill = str(selected_skill or "").strip()
        return bool(skill and skill != "general-chat")

    def _build_student_fallback_response(self, *, state: dict[str, Any], reason: str = "") -> dict[str, Any]:
        return build_career_guidance_fallback(
            message=str(state.get("message") or ""),
            selected_skill=str(state.get("selected_skill_normalized") or ""),
            session_state=dict(state.get("session_state") or {}),
            context_binding=dict(state.get("binding_in") or {}),
            client_state=dict(state.get("client_state") or {}),
            reason=reason,
        )

    def _is_file_agent_enabled(self) -> bool:
        from app.services.agent.registry import is_file_agent_enabled

        return bool(is_file_agent_enabled())

    def _route_from_selected_skill(
        self,
        *,
        selected_skill: str,
        message: str,
        state: dict[str, Any],
        supervisor,
    ) -> dict[str, Any] | None:
        skill = str(selected_skill or "").strip()
        if not skill or skill == "general-chat":
            return None

        session_state = dict(state.get("session_state") or {})
        binding_in = dict(state.get("binding_in") or {})
        client_state = dict(state.get("client_state") or {})

        if skill == "code-agent":
            code_task = supervisor.code_agent.detect_task(message=message, selected_skill=selected_skill)
            language = str(code_task.get("language") or "python")
            return {
                "route": "code",
                "task_type": language,
                "agent_flow": self._build_agent_flow(route="code", task_type=language),
            }

        file_skill_task_map = {
            "resume-workbench": "parse_file",
            "report-builder": "generate_report",
            "delivery-ready": "generate_document",
        }
        if skill in file_skill_task_map:
            task_type = self._selected_file_skill_task(
                skill=skill,
                message=message,
                client_state=client_state,
                context_binding=binding_in,
                session_state=session_state,
            )
            if task_type:
                route = "file" if self._is_file_agent_enabled() else "file_unavailable"
                return {
                    "route": route,
                    "task_type": task_type,
                    "agent_flow": self._build_agent_flow(route=route, task_type=task_type),
                }

        patch = supervisor.build_demo_control_context_patch(
            selected_skill=selected_skill,
            message=message,
            session_state=session_state,
            context_binding=binding_in,
            client_state=client_state,
        )
        result: dict[str, Any] = {
            "route": "complex",
            "task_type": skill,
            "agent_flow": self._build_agent_flow(route="complex", task_type=skill),
        }
        if patch:
            result["supervisor_context_patch"] = patch
        return result

    @staticmethod
    def _selected_file_skill_task(
        *,
        skill: str,
        message: str,
        client_state: dict[str, Any],
        context_binding: dict[str, Any] | None = None,
        session_state: dict[str, Any] | None = None,
    ) -> str:
        text = str(message or "").strip().lower()
        compact = "".join(text.split())
        context_binding = context_binding or {}
        session_state = session_state or {}
        state_binding = session_state.get("context_binding") if isinstance(session_state.get("context_binding"), dict) else {}

        current_upload_id = AssistantOrchestrationGraph._first_context_value(
            "attachment_id",
            client_state,
            context_binding,
            state_binding,
            session_state,
        )
        has_current_upload = str(current_upload_id or "").strip() not in {"", "0", "none", "null"}
        if is_profile_image_intent(text) or is_profile_insight_intent(text):
            return ""
        if skill in ("resume-workbench", "delivery-ready") and any(
            token in compact for token in ("生成", "导出", "下载", "保存", "generate", "export", "download", "save")
        ) and any(
            token in compact for token in ("word", "doc", "docx", "文件", "文档", "file", "document")
        ) and (
            session_state.get("last_resume_optimization") or session_state.get("resume_optimization_result")
        ):
            return "export_optimized_resume"
        if has_current_upload:
            return {
                "resume-workbench": "parse_file",
                "report-builder": "generate_report",
                "delivery-ready": "generate_document",
            }.get(skill, "")

        if skill == "resume-workbench":
            if any(token in compact for token in ("优化简历", "简历优化", "简历修改", "optimize resume", "optimizeresume")):
                return "optimize_resume"
            if any(token in compact for token in ("优化", "修改", "改写", "润色", "optimize", "rewrite")) and any(
                token in compact for token in ("简历", "resume", "cv")
            ):
                return "optimize_resume"
            if any(token in compact for token in ("解析", "识别", "提取", "读取", "查看", "parse", "extract")) and any(
                token in compact for token in ("简历", "文件", "附件", "pdf", "word", "doc", "docx", "resume", "file")
            ):
                return "parse_file"
            has_resume_context = bool(
                AssistantOrchestrationGraph._first_context_value(
                    "resume_id",
                    client_state,
                    context_binding,
                    state_binding,
                    session_state,
                )
                or AssistantOrchestrationGraph._first_context_value(
                    "resume_version_id",
                    client_state,
                    context_binding,
                    state_binding,
                    session_state,
                )
            )
            if has_resume_context and any(token in compact for token in ("开始", "继续", "处理", "执行", "start", "continue", "run", "go")):
                return "optimize_resume"
            return ""

        if skill == "report-builder":
            if any(token in compact for token in ("生成", "导出", "下载", "创建", "generate", "export", "download", "create")) and any(
                token in compact for token in ("报告", "report")
            ):
                return "generate_report"
            return ""

        if skill == "delivery-ready":
            if any(token in compact for token in ("生成", "导出", "下载", "创建", "打包", "generate", "export", "download", "create")) and any(
                token in compact for token in ("文档", "材料", "word", "doc", "docx", "document", "投递", "交付")
            ):
                return "generate_document"
            return ""

        return ""

    @staticmethod
    def _first_context_value(field: str, *sources: dict[str, Any]) -> Any:
        for source in sources:
            if not isinstance(source, dict):
                continue
            value = source.get(field)
            if value not in (None, "", 0, "0", "none", "null"):
                return value
            resume = source.get("resume") if isinstance(source.get("resume"), dict) else {}
            value = resume.get(field)
            if value not in (None, "", 0, "0", "none", "null"):
                return value
        return None
