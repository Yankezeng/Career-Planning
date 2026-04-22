from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.auth import User
from app.services.agent.chat_agent.chat_agent import ChatAgent
from app.services.agent.common.flowchart_business_agents import FlowchartAgentHub
from app.services.agent.common.rag.enhanced_rag import get_enhanced_rag
from app.services.agent.supervisor_agent.supervisor_agent import SupervisorAgent
from app.services.agent_tool_registry import AgentToolRegistry
from app.services.agent.common.intent_classifier import get_intent_classifier
from app.services.agent.common.intent_refiner import get_intent_refiner
from app.services.agent.common.entity_extractor import get_entity_extractor
from app.services.graph.job_knowledge_graph import get_job_knowledge_graph
from app.services.assistant_orchestration_graph import AssistantOrchestrationGraph
from app.services.assistant_card_factory import AssistantCardFactory
from app.services.assistant_intent_service import AssistantIntentService
from app.services.assistant_plan_service import AssistantPlanService
from app.services.assistant_profile_intent import is_profile_image_intent, is_profile_insight_intent
from app.services.assistant_session_state_service import AssistantSessionStateService
from app.services.assistant_skill_catalog_service import normalize_skill_code
from app.services.assistant_slot_service import AssistantSlotService
from app.services.llm_service import LLMService
from app.services.vector_search_service import VectorSearchService


class AgentOrchestratorService:
    def __init__(self, db: Session, llm_service: LLMService, vector_search_service: VectorSearchService):
        self.db = db
        self.settings = get_settings()
        self.llm_service = llm_service
        self.vector_search_service = vector_search_service
        self.tool_registry = AgentToolRegistry(db, vector_search_service)
        self.flowchart_agents = FlowchartAgentHub(self.tool_registry)
        self.card_factory = AssistantCardFactory()
        self.state_service = AssistantSessionStateService()
        self.intent_service = AssistantIntentService()
        self.slot_service = AssistantSlotService()
        self.plan_service = AssistantPlanService()
        self.intent_classifier = get_intent_classifier()
        self.entity_extractor = get_entity_extractor()
        self.intent_refiner = get_intent_refiner()
        self.enhanced_rag = get_enhanced_rag()
        self.chat_agent = ChatAgent()
        self.supervisor = SupervisorAgent(db)
        self.job_graph = get_job_knowledge_graph()
        self.orchestration_graph = AssistantOrchestrationGraph(self)
        self.use_enhanced_mode = True
        self.supervisor_report_strict = bool(self.settings.SUPERVISOR_REPORT_STRICT)
        self.flowchart_agent_split_v2 = bool(self.settings.FLOWCHART_AGENT_SPLIT_V2)
        self._init_logger()

    def _init_logger(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    @staticmethod
    def _normalize_skill(skill_code: str | None, role: str | None = None) -> str:
        return normalize_skill_code(skill_code, role)

    @staticmethod
    def _build_supervisor_summary(state: dict[str, Any]) -> dict[str, Any]:
        goal = dict(state.get("supervisor_goal") or {})
        reports = list(state.get("agent_reports") or [])
        decisions = list(state.get("supervisor_decisions") or [])
        final_route = str((decisions[-1] if decisions else {}).get("route") or state.get("route") or "")
        stop_reason = str((decisions[-1] if decisions else {}).get("stop_reason") or "")
        return {
            "goal": goal,
            "reports": reports,
            "decision_trace": decisions,
            "supervisor_plan": dict(state.get("supervisor_plan") or {}),
            "dispatch_trace": dict(state.get("dispatch_trace") or {}),
            "final_route": final_route,
            "stop_reason": stop_reason,
        }

    def _pack_simple_response(self, *, state: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
        chat_result = runtime.get("chat_result") or {}
        simple_intent = str(runtime.get("simple_intent") or state.get("simple_intent") or "small_talk")
        reply = str(chat_result.get("reply") or "I have received your message.")
        reply_mode = str(chat_result.get("reply_mode") or "brief")
        reply_blocks = list(chat_result.get("reply_blocks") or [{"type": "summary", "text": reply}])
        actions = list(chat_result.get("actions") or [])

        plan_skill = "general-chat"
        plan = {
            "intent": simple_intent,
            "selected_skill": plan_skill,
            "normalized_skill": plan_skill,
            "steps": [{"step": 1, "tool": "chat_direct_reply", "purpose": "Handle simple user intent"}],
            "tool_plan": [],
            "need_retrieval": False,
            "reply_mode": reply_mode,
            "small_talk": simple_intent == "small_talk",
            "required_bindings": list((state.get("binding_in") or {}).keys()),
            "slots": {},
            "intent_confidence": 1.0,
        }

        tool_outputs: list[dict[str, Any]] = []
        binding_out = self._merge_binding(
            state.get("session_state") or {},
            state.get("binding_in") or {},
            tool_outputs,
            {},
        )
        task_patch = self._build_task_patch(
            session_state=state.get("session_state") or {},
            plan=plan,
            slots={},
            tool_steps=[],
        )
        next_state = self.state_service.merge(
            state.get("session_state") or {},
            context_binding=binding_out,
            context_patch={
                "last_plan": plan,
                "last_intent": simple_intent,
                "slots": {},
                "last_analysis_focus": (state.get("session_state") or {}).get("last_analysis_focus"),
                "task_state": task_patch,
                "supervisor_state": self._build_supervisor_summary(state),
            },
            selected_skill=(state.get("session_state") or {}).get("current_skill"),
        )
        return {
            "reply": reply,
            "reply_mode": reply_mode,
            "reply_blocks": reply_blocks,
            "used_skill": plan_skill,
            "normalized_skill": plan_skill,
            "plan": plan,
            "tool_steps": [],
            "cards": [],
            "actions": actions,
            "knowledge_hits": [],
            "context_binding": binding_out,
            "session_state": next_state,
            "task_patch": task_patch,
            "tool_outputs": tool_outputs,
            "context": {
                "intent": simple_intent,
                "slots": {},
                "reply_mode": reply_mode,
                "intent_confidence": 1.0,
                "task_patch": task_patch,
            },
            "agent_route": "chat",
            "requires_user_input": False,
            "artifacts": [],
            "file_task": {},
            "code_task": {},
            "supervisor_summary": self._build_supervisor_summary(state),
            "agent_flow": list(state.get("agent_flow") or []),
        }

    def _pack_file_response(
        self,
        *,
        state: dict[str, Any],
        file_result: dict[str, Any],
        chat_result: dict[str, Any],
    ) -> dict[str, Any]:
        role = str(state.get("role") or "student")
        selected_skill_normalized = str(state.get("selected_skill_normalized") or "")
        task_type = str(state.get("task_type") or "")

        task_tool_outputs = list(file_result.get("tool_outputs") or [])
        tool_outputs = list(state.get("supervisor_tool_outputs") or task_tool_outputs)
        file_level_patch = file_result.get("context_patch") if isinstance(file_result.get("context_patch"), dict) else {}
        binding_tool_outputs = list(tool_outputs)
        if file_level_patch:
            binding_tool_outputs.append({"context_patch": file_level_patch})
        task_tool_steps = list(file_result.get("tool_steps") or [])
        tool_steps = list(state.get("supervisor_tool_steps") or task_tool_steps)
        cards = self.card_factory.build_many(tool_outputs)
        reply = str(chat_result.get("reply") or file_result.get("reply") or "File task completed.")
        reply_mode = str(chat_result.get("reply_mode") or "structured")
        reply_blocks = list(chat_result.get("reply_blocks") or [{"type": "summary", "text": reply}])
        actions = list(chat_result.get("actions") or [])

        task_skill_map = {
            "parse_file": "resume-workbench",
            "optimize_resume": "resume-workbench",
            "generate_report": "report-builder",
            "generate_document": "resume-workbench",
            "generate_chart": "resume-workbench",
            "generate_image": "resume-workbench",
        }
        selected_skill_candidate = selected_skill_normalized
        if not selected_skill_candidate or selected_skill_candidate == "general-chat":
            selected_skill_candidate = task_skill_map.get(task_type, "general-chat")
        plan_skill = normalize_skill_code(selected_skill_candidate, role)
        plan = {
            "intent": "file_task",
            "selected_skill": plan_skill,
            "normalized_skill": plan_skill,
            "steps": [{"step": 1, "tool": task_type or "file_task", "purpose": "澶勭悊鏂囦欢浠诲姟"}],
            "tool_plan": [step.get("tool") for step in tool_steps if isinstance(step, dict) and step.get("tool")],
            "need_retrieval": False,
            "reply_mode": reply_mode,
            "small_talk": False,
            "required_bindings": list((state.get("binding_in") or {}).keys()),
            "slots": {},
        }

        binding_out = self._merge_binding(
            state.get("session_state") or {},
            state.get("binding_in") or {},
            binding_tool_outputs,
            {},
        )
        task_patch = self._build_task_patch(
            session_state=state.get("session_state") or {},
            plan=plan,
            slots={},
            tool_steps=tool_steps,
        )
        next_state = self.state_service.merge(
            state.get("session_state") or {},
            context_binding=binding_out,
            context_patch={
                "last_plan": plan,
                "last_intent": "file_task",
                "slots": {},
                "last_analysis_focus": (state.get("session_state") or {}).get("last_analysis_focus"),
                "task_state": task_patch,
                "supervisor_state": self._build_supervisor_summary(state),
            },
            selected_skill=plan.get("normalized_skill"),
        )
        return {
            "reply": reply,
            "reply_mode": reply_mode,
            "reply_blocks": reply_blocks,
            "used_skill": plan_skill,
            "normalized_skill": plan_skill,
            "plan": plan,
            "tool_steps": tool_steps,
            "cards": cards,
            "actions": actions,
            "knowledge_hits": [],
            "context_binding": binding_out,
            "session_state": next_state,
            "task_patch": task_patch,
            "tool_outputs": tool_outputs,
            "context": {
                "intent": "file_task",
                "slots": {},
                "reply_mode": reply_mode,
                "intent_confidence": 1.0,
                "task_patch": task_patch,
            },
            "agent_route": "file",
            "requires_user_input": bool(file_result.get("requires_user_input")),
            "artifacts": list(state.get("supervisor_artifacts") or file_result.get("artifacts") or []),
            "file_task": file_result.get("file_task") or {"type": task_type, "status": file_result.get("status") or "unknown"},
            "background_job": dict(file_result.get("background_job") or {}),
            "code_task": {},
            "supervisor_summary": self._build_supervisor_summary(state),
            "agent_flow": list(state.get("agent_flow") or []),
        }

    def _pack_code_response(
        self,
        *,
        state: dict[str, Any],
        code_result: dict[str, Any],
        chat_result: dict[str, Any],
    ) -> dict[str, Any]:
        role = str(state.get("role") or "student")
        selected_skill_normalized = str(state.get("selected_skill_normalized") or "")
        code_task = code_result.get("code_task") or {}
        language = str(code_task.get("language") or state.get("task_type") or "python")
        task_tool_outputs = list(code_result.get("tool_outputs") or [])
        tool_outputs = list(state.get("supervisor_tool_outputs") or task_tool_outputs)
        task_tool_steps = list(code_result.get("tool_steps") or [])
        tool_steps = list(state.get("supervisor_tool_steps") or task_tool_steps)
        cards = self.card_factory.build_many(tool_outputs)

        reply = str(chat_result.get("reply") or code_result.get("reply") or "Code task completed.")
        reply_mode = str(chat_result.get("reply_mode") or "structured")
        reply_blocks = list(chat_result.get("reply_blocks") or [{"type": "summary", "text": reply}])
        actions = list(chat_result.get("actions") or [])

        plan_skill = normalize_skill_code(
            selected_skill_normalized if selected_skill_normalized and selected_skill_normalized != "general-chat" else "code-agent",
            role,
        )
        slots_for_code = {"selected_skill": plan_skill, "target_job": language}
        plan = {
            "intent": "code_task",
            "selected_skill": plan_skill,
            "normalized_skill": plan_skill,
            "steps": [{"step": 1, "tool": "code_agent", "purpose": "Generate and verify code with strict checks"}],
            "tool_plan": [step.get("tool") for step in tool_steps if isinstance(step, dict) and step.get("tool")],
            "need_retrieval": False,
            "reply_mode": reply_mode,
            "small_talk": False,
            "required_bindings": list((state.get("binding_in") or {}).keys()),
            "slots": slots_for_code,
        }

        binding_out = self._merge_binding(
            state.get("session_state") or {},
            state.get("binding_in") or {},
            tool_outputs,
            slots_for_code,
        )
        task_patch = self._build_task_patch(
            session_state=state.get("session_state") or {},
            plan=plan,
            slots=slots_for_code,
            tool_steps=tool_steps,
        )
        next_state = self.state_service.merge(
            state.get("session_state") or {},
            context_binding=binding_out,
            context_patch={
                "last_plan": plan,
                "last_intent": "code_task",
                "slots": slots_for_code,
                "last_analysis_focus": (state.get("session_state") or {}).get("last_analysis_focus"),
                "task_state": task_patch,
                "supervisor_state": self._build_supervisor_summary(state),
            },
            selected_skill=plan.get("normalized_skill"),
        )
        return {
            "reply": reply,
            "reply_mode": reply_mode,
            "reply_blocks": reply_blocks,
            "used_skill": plan_skill,
            "normalized_skill": plan_skill,
            "plan": plan,
            "tool_steps": tool_steps,
            "cards": cards,
            "actions": actions,
            "knowledge_hits": [],
            "context_binding": binding_out,
            "session_state": next_state,
            "task_patch": task_patch,
            "tool_outputs": tool_outputs,
            "context": {
                "intent": "code_task",
                "slots": slots_for_code,
                "reply_mode": reply_mode,
                "intent_confidence": 1.0,
                "task_patch": task_patch,
            },
            "agent_route": "code",
            "requires_user_input": bool(code_result.get("requires_user_input")),
            "artifacts": list(state.get("supervisor_artifacts") or code_result.get("artifacts") or []),
            "file_task": {},
            "code_task": code_task,
            "supervisor_summary": self._build_supervisor_summary(state),
            "agent_flow": list(state.get("agent_flow") or []),
        }

    def _pack_complex_response(self, *, state: dict[str, Any]) -> dict[str, Any]:
        plan = state.get("plan") or {}
        slots = state.get("slots") or {}
        reply = str(state.get("reply") or "I have received your message.")
        reply_mode = str(state.get("reply_mode") or plan.get("reply_mode") or "structured")
        tool_outputs = list(state.get("tool_outputs") or [])
        artifacts = self._dedupe_artifacts(
            [
                *[item for item in list(state.get("artifacts") or []) if isinstance(item, dict)],
                *self._extract_artifacts_from_tool_outputs(tool_outputs),
            ]
        )
        reply = self._strip_artifact_download_section(reply, artifacts)
        tool_steps = list(state.get("tool_steps") or [])
        retrieval_chunks = list(state.get("retrieval_chunks") or [])
        knowledge_hits = list(state.get("knowledge_hits") or [])
        actions = list(state.get("actions") or [])
        cards = list(state.get("cards") or self.card_factory.build_many(tool_outputs))
        reply_blocks = list(
            state.get("reply_blocks")
            or self._build_reply_blocks(
                reply=reply,
                reply_mode=reply_mode,
                tool_outputs=tool_outputs,
                retrieval_chunks=retrieval_chunks,
                actions=actions,
            )
        )
        binding_out = dict(
            state.get("binding_out")
            or self._merge_binding(state.get("session_state") or {}, state.get("binding_in") or {}, tool_outputs, slots)
        )
        task_patch = dict(
            state.get("task_patch")
            or self._build_task_patch(
                session_state=state.get("session_state") or {},
                plan=plan,
                slots=slots,
                tool_steps=tool_steps,
            )
        )
        next_state = dict(
            state.get("next_state")
            or self.state_service.merge(
                state.get("session_state") or {},
                context_binding=binding_out,
                context_patch={
                    "last_plan": plan,
                    "last_intent": plan.get("intent"),
                    "slots": slots,
                    "last_analysis_focus": slots.get("current_focus") or (state.get("session_state") or {}).get("last_analysis_focus"),
                    "task_state": task_patch,
                    "supervisor_state": self._build_supervisor_summary(state),
                },
                selected_skill=plan.get("normalized_skill") if not plan.get("small_talk") else (state.get("session_state") or {}).get("current_skill"),
            )
        )
        return {
            "reply": reply,
            "reply_mode": reply_mode,
            "reply_blocks": reply_blocks,
            "used_skill": plan.get("selected_skill"),
            "normalized_skill": plan.get("normalized_skill"),
            "plan": plan,
            "tool_steps": tool_steps,
            "cards": cards,
            "actions": actions,
            "knowledge_hits": knowledge_hits,
            "context_binding": binding_out,
            "session_state": next_state,
            "task_patch": task_patch,
            "tool_outputs": tool_outputs,
            "context": {
                "intent": plan.get("intent"),
                "slots": slots,
                "reply_mode": reply_mode,
                "intent_confidence": state.get("intent_confidence") or 0.0,
                "task_patch": task_patch,
            },
            "agent_route": "complex",
            "requires_user_input": False,
            "artifacts": artifacts,
            "file_task": {},
            "code_task": {},
            "supervisor_summary": self._build_supervisor_summary(state),
            "agent_flow": list(state.get("agent_flow") or []),
        }

    def orchestrate(
        self,
        *,
        user: User,
        message: str,
        history: list[dict[str, Any]] | None = None,
        selected_skill: str | None = None,
        session_state: dict[str, Any] | None = None,
        context_binding: dict[str, Any] | None = None,
        client_state: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
        db: Session | None = None,
    ) -> dict[str, Any]:
        start_time = datetime.now(timezone.utc)

        self.logger.info(f"[Agent] Session started - user: {user.id}, message: {message[:50]}...")
        self.logger.info(f"[Intent] Using enhanced mode: {self.use_enhanced_mode}")
        role = user.role.code if user.role else "student"
        text = str(message or "").strip()
        history = history or []
        session_state = self.state_service.normalize_state(session_state)
        binding_in = context_binding or {}
        client_state = client_state or {}
        selected_skill_normalized = normalize_skill_code(selected_skill or "", role)

        graph_state: dict[str, Any] = {
            "user": user,
            "role": role,
            "message": message,
            "text": text,
            "history": history,
            "selected_skill_normalized": selected_skill_normalized,
            "session_state": session_state,
            "binding_in": binding_in,
            "client_state": client_state,
            "options": options or {},
            "start_time": start_time,
            "agent_flow": [],
        }
        result = self.orchestration_graph.run(graph_state)
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        self.logger.info(f"[Agent] Graph route completed in {duration_ms:.2f}ms, route: {result.get('agent_route')}")
        return result

    def _execute_plan(
        self,
        *,
        user: User,
        message: str,
        plan: dict[str, Any],
        slots: dict,
        intent_info: dict,
        session_state: dict[str, Any],
    ) -> dict[str, Any]:
        tool_outputs: list[dict[str, Any]] = []
        tool_steps: list[dict[str, Any]] = []
        retrieval_chunks: list[dict[str, Any]] = []
        knowledge_hits: list[dict[str, Any]] = []

        if plan.get("need_retrieval"):
            target_job = slots.get("target_job") or intent_info.get("extracted_job")
            retrieval_query = self._build_retrieval_query(message=message, target_job=target_job)
            rag_result = self.enhanced_rag.search(
                query=retrieval_query,
                top_k=4,
                context={"session_state": session_state, "target_job": target_job},
            )
            retrieval_chunks = rag_result.get("retrieval_chunks") or []
            knowledge_hits = self._to_knowledge_hits(rag_result.get("results") or [], target_job)
            kb = {
                "tool": "job_kb_search",
                "title": "Job Knowledge Search",
                "summary": f"Hit {len(knowledge_hits)} job knowledge records.",
                "data": {
                    "query": retrieval_query,
                    "hits": knowledge_hits,
                    "retrieval_chunks": retrieval_chunks,
                },
                "next_actions": ["缁х画鏌ョ湅鍖归厤寤鸿", "缁х画鏌ョ湅宸窛鍒嗘瀽"],
                "context_patch": {},
            }
            tool_outputs.append(kb)
            tool_steps.append({"tool": "job_kb_search", "status": "done", "text": "knowledge search completed"})
            self.logger.info(f"[KB] Retrieved {len(knowledge_hits)} hits for target_job: {slots.get('target_job') or 'unknown'}")

        for tool in plan.get("tool_plan") or []:
            output = self._run_tool(tool, user=user, message=message, top_k=4, target_job=slots.get("target_job") or intent_info.get("extracted_job"))
            tool_outputs.append(output)
            failed = bool(output.get("data", {}).get("error"))
            tool_steps.append(
                {
                    "tool": tool,
                    "status": "failed" if failed else "done",
                    "text": ("failed: " if failed else "done: ") + (output.get("title") or tool),
                }
            )

        return {
            "tool_outputs": tool_outputs,
            "tool_steps": tool_steps,
            "retrieval_chunks": retrieval_chunks,
            "knowledge_hits": knowledge_hits,
        }

    def _run_tool(self, tool: str, *, user: User, message: str, top_k: int, target_job: str = None) -> dict[str, Any]:
        try:
            return self.tool_registry.run(tool, user=user, message=message, top_k=top_k, target_job=target_job)
        except Exception as exc:
            return {
                "tool": tool,
                "title": tool,
                "summary": "tool failed, fallback to normal chat",
                "data": {"error": str(exc)},
                "card": {
                    "type": "action_checklist_card",
                    "tool": tool,
                    "title": tool,
                    "summary": "tool failed, fallback to normal chat",
                    "data": {"error": str(exc)},
                },
                "next_actions": ["缁х画鎻愰棶锛屾垜浼氭敼鐢ㄩ€氱敤鍒嗘瀽"],
                "context_patch": {},
            }

    @staticmethod
    def _collect_actions(tool_outputs: list[dict[str, Any]]) -> list[str]:
        actions: list[str] = []
        for item in tool_outputs:
            for action in item.get("next_actions") or []:
                text = str(action or "").strip()
                if text and text not in actions:
                    actions.append(text)
        return actions[:5]

    @classmethod
    def _extract_artifacts_from_tool_outputs(cls, tool_outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []
        for item in tool_outputs:
            if not isinstance(item, dict):
                continue
            data = item.get("data") if isinstance(item.get("data"), dict) else {}
            raw_artifacts = data.get("artifacts")
            if isinstance(raw_artifacts, list):
                artifacts.extend(raw for raw in raw_artifacts if isinstance(raw, dict))
            artifacts.extend(cls._resume_export_artifacts_from_data(data))
        return cls._dedupe_artifacts(artifacts)

    @classmethod
    def _resume_export_artifacts_from_data(cls, data: dict[str, Any]) -> list[dict[str, Any]]:
        if not isinstance(data, dict):
            return []

        source_stem = cls._safe_stem(data.get("attachment_name") or "optimized_resume")
        candidates = [
            (
                data.get("editable_word_url"),
                data.get("editable_word_path"),
                f"{source_stem}-优化版.docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            (
                data.get("optimized_pdf_url"),
                data.get("optimized_pdf_path"),
                f"{source_stem}-优化版.pdf",
                "application/pdf",
            ),
        ]

        artifacts: list[dict[str, Any]] = []
        for url_value, path_value, name, mime_type in candidates:
            download_url = str(url_value or "").strip() or cls._upload_url_from_pathish(path_value)
            if not download_url:
                continue
            artifacts.append(
                {
                    "name": name,
                    "type": "document",
                    "download_url": download_url,
                    "mime_type": mime_type,
                }
            )
        return artifacts

    @staticmethod
    def _dedupe_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for item in artifacts:
            if not isinstance(item, dict):
                continue
            key = str(item.get("id") or item.get("download_url") or item.get("url") or item.get("path") or item.get("name") or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    @staticmethod
    def _safe_stem(value: Any) -> str:
        text = str(value or "").strip().split("?", 1)[0].split("#", 1)[0].rstrip("/\\")
        if not text:
            return "optimized_resume"
        name = re.split(r"[\\/]", text)[-1] or text
        if "." in name:
            name = name.rsplit(".", 1)[0]
        return name.strip() or "optimized_resume"

    @staticmethod
    def _upload_url_from_pathish(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        normalized = text.replace("\\", "/")
        marker = "/uploads/"
        if marker in normalized:
            return marker + normalized.split(marker, 1)[1].lstrip("/")
        if normalized.startswith("uploads/"):
            return "/" + normalized
        return ""

    @staticmethod
    def _strip_artifact_download_section(reply: str, artifacts: list[dict[str, Any]]) -> str:
        text = str(reply or "")
        if not text or not artifacts:
            return text

        cleaned: list[str] = []
        skipping_download_section = False
        for line in text.splitlines():
            stripped = line.strip()
            is_download_heading = bool(re.search(r"(文件获取方式|下载链接|导出文件)", stripped))
            has_download_reference = bool(
                re.search(r"(/uploads/resume_exports/|/api/students/me/resume/export/|editable_word_url|optimized_pdf_url)", stripped)
            )
            if is_download_heading:
                skipping_download_section = True
                continue
            if has_download_reference:
                continue
            if skipping_download_section:
                if not stripped:
                    continue
                if stripped.startswith("#"):
                    skipping_download_section = False
                    cleaned.append(line)
                elif stripped.startswith("---"):
                    skipping_download_section = False
                elif re.match(r"^[-*]\s*(Word|PDF|DOCX|DOC|文件|下载)", stripped, flags=re.IGNORECASE):
                    continue
                else:
                    skipping_download_section = False
                    cleaned.append(line)
                continue
            cleaned.append(line)

        result = "\n".join(cleaned)
        result = re.sub(r"\n{3,}", "\n\n", result).strip()
        return result or "文件已生成，可在下方下载卡片中获取。"

    @staticmethod
    def _merge_binding(
        session_state: dict[str, Any],
        context_binding: dict[str, Any],
        tool_outputs: list[dict[str, Any]],
        slots: dict[str, Any],
    ) -> dict[str, Any]:
        merged = dict(session_state.get("context_binding") or {})
        merged.update(context_binding or {})
        for key in ["target_job", "target_city", "target_industry", "resume_id", "resume_version_id", "selected_skill"]:
            if slots.get(key):
                merged[key] = slots[key]
        if slots.get("resume_id") or slots.get("resume_version_id"):
            merged["resume"] = {
                "resume_id": slots.get("resume_id"),
                "resume_version_id": slots.get("resume_version_id"),
            }
        for item in tool_outputs:
            patch = item.get("context_patch") or {}
            if isinstance(patch.get("context_binding"), dict):
                merged.update(patch["context_binding"])
        return merged

    def _infer_skill(self, role: str, message: str, session_state: dict[str, Any], allow_carryover: bool = True) -> str:
        text = str(message or "")
        lowered = text.lower()

        if role == "student":
            if is_profile_image_intent(text):
                return "profile-image"
            if is_profile_insight_intent(text):
                return "profile-insight"
            if any(k in lowered for k in ["resume", "cv", "简历", "优化简历"]):
                return "resume-workbench"
            if any(k in lowered for k in ["profile", "画像", "能力分析", "优势", "短板"]):
                return "profile-insight"
            if any(k in lowered for k in ["match", "岗位", "职位", "job", "推荐"]):
                return "match-center"
            if any(k in lowered for k in ["gap", "差距", "缺什么"]):
                return "gap-analysis"
            if any(k in lowered for k in ["growth", "成长", "成长路径", "学习计划", "学习路线", "职业路径", "规划路径", "路径规划"]):
                return "growth-planner"
            if any(k in lowered for k in ["report", "报告"]):
                return "report-builder"
            if any(k in lowered for k in ["deliver", "投递"]):
                return "delivery-ready"
            if any(k in lowered for k in ["interview", "面试", "笔试"]):
                return "interview-training"

        if role == "enterprise":
            if any(k in lowered for k in ["screen", "筛选", "排序", "前3", "优先级"]):
                return "candidate-screening"
            if any(k in lowered for k in ["overview", "候选人概览", "候选人池", "候选人"]):
                return "candidate-overview"
            if any(k in lowered for k in ["resume review", "简历评审", "简历分析"]):
                return "resume-review"
            if any(k in lowered for k in ["portrait", "画像"]):
                return "talent-portrait"
            if any(k in lowered for k in ["script", "沟通话术", "邀约", "反馈"]):
                return "communication-script"
            if any(k in lowered for k in ["review", "复评"]):
                return "review-advice"
            if any(k in lowered for k in ["interview eval", "面试评估"]):
                return "interview-eval"

        if role == "admin":
            if any(k in lowered for k in ["metrics", "监控", "看板", "指标"]):
                return "admin-metrics"
            if any(k in lowered for k in ["ops", "运营复盘", "复盘"]):
                return "ops-review"
            if any(k in lowered for k in ["overview", "角色总览"]):
                return "role-overview"
            if any(k in lowered for k in ["knowledge governance", "知识治理", "知识库"]):
                return "knowledge-governance"
            if any(k in lowered for k in ["data governance", "数据治理", "数据质量"]):
                return "data-governance"
            if any(k in lowered for k in ["demo", "答辩", "演示"]):
                return "demo-script"

        if allow_carryover and session_state.get("last_skill"):
            return normalize_skill_code(session_state.get("last_skill"), role)
        return "general-chat"

    def _infer_skill_enhanced(self, *, role: str, text: str, intent_info: dict, slots: dict,
                              session_state: dict, allow_carryover: bool = True) -> str:
        if intent_info.get("recommend_skill") and intent_info["recommend_skill"] != "general-chat":
            skill = normalize_skill_code(intent_info["recommend_skill"], role)
            if skill != "general-chat":
                return skill

        if slots.get("target_job"):
            job_info = self.job_graph.get_job_info(slots["target_job"])
            if job_info:
                intent = intent_info.get("intent", "")
                if intent in ["career_exploration", "gap_analysis"]:
                    if session_state.get("context_binding", {}).get("profile"):
                        return "gap-analysis"
                    return "match-center"
                elif intent == "growth_planning":
                    return "growth-planner"

        return self._infer_skill(role, text, session_state, allow_carryover)

    def _build_reply_blocks(
        self,
        *,
        reply: str,
        reply_mode: str,
        tool_outputs: list[dict[str, Any]],
        retrieval_chunks: list[dict[str, Any]],
        actions: list[str],
    ) -> list[dict[str, Any]]:
        summary = str(reply or "").strip().split("\n")[0].strip() or "This round has been completed."

        if reply_mode == "brief":
            return [{"type": "summary", "text": summary}]

        reason_items: list[str] = []
        for item in tool_outputs[:3]:
            title = str(item.get("title") or item.get("tool") or "analysis result").strip()
            text = str(item.get("summary") or "").strip()
            reason_items.append(f"{title}: {text}" if text else title)

        if not reason_items and retrieval_chunks:
            for chunk in retrieval_chunks[:3]:
                job_name = str(chunk.get("job_name") or "job info").strip()
                snippet = str(chunk.get("snippet") or "").strip()
                reason_items.append(f"{job_name}: {snippet}" if snippet else job_name)

        blocks: list[dict[str, Any]] = [{"type": "summary", "text": summary}]
        if reason_items:
            blocks.append({"type": "bullets", "title": "Evidence", "items": reason_items[:4]})
        if actions:
            blocks.append({"type": "actions", "items": actions[:4]})
        return blocks

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
    @staticmethod
    def _should_clarify_by_confidence(*, intent_info: dict[str, Any], slots: dict[str, Any], confidence: float) -> bool:
        if confidence >= 0.6:
            return False
        if slots.get("target_job"):
            return False
        intent = str(intent_info.get("intent") or "")
        return intent in {"career_exploration", "gap_analysis", "growth_planning", "ask_advice", "execute", "planning"}

    def _build_retrieval_query(self, *, message: str, target_job: str | None) -> str:
        if not target_job:
            return str(message or "").strip()
        related_jobs = self.job_graph.get_related_jobs(target_job)[:3]
        skill_tree = self.job_graph.get_skill_tree(target_job)
        core_skills = (skill_tree.get("core") or [])[:3]
        terms = [target_job, *related_jobs, *core_skills, str(message or "").strip()]
        return " ".join([term for term in terms if term]).strip()

    @staticmethod
    def _to_knowledge_hits(results: list[dict[str, Any]], target_job: str | None) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        for item in results:
            metadata = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
            hits.append(
                {
                    "id": item.get("id"),
                    "job_name": metadata.get("job_name") or target_job or "unknown_job",
                    "company_name": metadata.get("company_name") or "",
                    "score": item.get("fused_score") or item.get("rerank_score") or item.get("score") or 0,
                    "snippet": str(item.get("content") or "")[:200],
                }
            )
        return hits

    @staticmethod
    def _build_task_patch(
        *,
        session_state: dict[str, Any],
        plan: dict[str, Any],
        slots: dict[str, Any],
        tool_steps: list[dict[str, Any]],
    ) -> dict[str, Any]:
        previous = session_state.get("task_state") if isinstance(session_state.get("task_state"), dict) else {}
        goal = slots.get("target_job") or previous.get("goal") or plan.get("normalized_skill") or ""
        if plan.get("intent") == "clarify_required":
            return {
                "goal": goal,
                "steps": previous.get("steps") if isinstance(previous.get("steps"), list) else [],
                "current": int(previous.get("current") or 0),
                "status": "waiting",
            }

        tool_plan = list(plan.get("tool_plan") or [])
        done_tools = {str(item.get("tool") or "") for item in tool_steps if str(item.get("status") or "") == "done"}
        steps = [{"key": tool, "title": tool, "status": "done" if tool in done_tools else "pending"} for tool in tool_plan]
        if not steps:
            return {"goal": goal, "steps": [], "current": 0, "status": "idle"}

        current_index = 0
        for index, item in enumerate(steps):
            if item["status"] != "done":
                current_index = index
                break
            current_index = index

        status = "completed" if all(item["status"] == "done" for item in steps) else "in_progress"
        return {"goal": goal, "steps": steps, "current": current_index, "status": status}







