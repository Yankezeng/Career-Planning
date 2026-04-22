from __future__ import annotations

import json
from typing import Any
from enum import Enum

from sqlalchemy.orm import Session

from app.models.auth import User
from app.services.agent_tool_registry import AgentToolRegistry
from app.services.llm_service import get_llm_service, truncate_history_by_tokens
from app.services.vector_search_service import VectorSearchService


class AgentAction(Enum):
    RETRIEVE_KNOWLEDGE = "retrieve_knowledge"
    EXECUTE_TOOL = "execute_tool"
    GENERATE_REPLY = "generate_reply"
    ASK_CLARIFICATION = "ask_clarification"
    FINISH = "finish"


MAX_ITERATIONS = 5


class ReActAgent:
    def __init__(self, db: Session):
        self.db = db
        self.llm_service = get_llm_service()
        self.vector_search_service = VectorSearchService()
        self.tool_registry = AgentToolRegistry(db, self.vector_search_service)
        self.max_iterations = MAX_ITERATIONS

    def run(
        self,
        user: User,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = context or {}
        history = context.get("history", [])
        session_state = context.get("session_state", {})

        observations = []
        thought_chain = []
        selected_skill = context.get("selected_skill", "general-chat")

        for iteration in range(self.max_iterations):
            thought = self._think(user, message, history, session_state, observations, selected_skill)
            thought_chain.append(thought)

            if not thought.get("action"):
                break

            action = thought["action"]
            action_type = action.get("type")

            if action_type == AgentAction.RETRIEVE_KNOWLEDGE.value:
                observation = self._retrieve_knowledge(action)
                observations.append(observation)

            elif action_type == AgentAction.EXECUTE_TOOL.value:
                observation = self._execute_tool(user, action, message)
                observations.append(observation)

            elif action_type == AgentAction.ASK_CLARIFICATION.value:
                return {
                    "reply": action.get("question", "请补充更多信息"),
                    "reply_mode": "brief",
                    "needs_clarification": True,
                    "thought_chain": thought_chain,
                }

            elif action_type == AgentAction.FINISH.value:
                final_reply = self._generate_final_reply(
                    user, message, history, session_state, observations, thought
                )
                return {
                    "reply": final_reply,
                    "reply_mode": "structured",
                    "needs_clarification": False,
                    "thought_chain": thought_chain,
                    "observations": observations,
                }

        max_iterations_reply = self._generate_final_reply(
            user, message, history, session_state, observations,
            {"reasoning": "已达到最大迭代次数，自动生成回复"}
        )
        return {
            "reply": max_iterations_reply,
            "reply_mode": "brief",
            "needs_clarification": False,
            "thought_chain": thought_chain,
            "observations": observations,
            "truncated": True,
        }

    def _think(
        self,
        user: User,
        message: str,
        history: list[dict],
        session_state: dict[str, Any],
        observations: list[dict],
        selected_skill: str,
    ) -> dict[str, Any]:
        prompt = self._build_thinking_prompt(
            user, message, history, session_state, observations, selected_skill
        )

        try:
            response = self.llm_service.chat(
                user_role=user.role.code if user.role else "student",
                user_name=user.real_name,
                message=prompt,
                history=truncate_history_by_tokens(history) if history else [],
                context={"scene": "react_thinking"}
            )

            return self._parse_thinking_response(response, observations)
        except Exception as e:
            return {
                "reasoning": f"思考过程异常: {str(e)}",
                "action": {"type": AgentAction.FINISH.value},
            }

    def _build_thinking_prompt(
        self,
        user: User,
        message: str,
        history: list[dict],
        session_state: dict[str, Any],
        observations: list[dict],
        selected_skill: str,
    ) -> str:
        history_text = ""
        if history:
            history_text = "对话历史:\n" + "\n".join([
                f"{h.get('role', 'user')}: {h.get('content', '')[:100]}"
                for h in truncate_history_by_tokens(history)
            ])

        observations_text = ""
        if observations:
            observations_text = "已有信息:\n" + "\n".join([
                f"- {obs.get('type', 'info')}: {obs.get('content', '')[:200]}"
                for obs in observations
            ])

        session_text = ""
        if session_state:
            session_text = f"当前状态: {json.dumps(session_state, ensure_ascii=False)[:200]}"

        prompt = f"""你是一个智能助手，需要决定下一步做什么来完成用户的职业规划请求。

【用户消息】: {message}
【对话历史】: {history_text}
【已有信息】: {observations_text}
【当前状态】: {session_text}
【当前技能】: {selected_skill}

【重要指导】
1. 如果用户提到了职业目标（如"产品经理"、"前端开发"），优先检索该岗位的相关知识
2. 如果用户问"该做什么"或"需要什么"，需要先检索岗位要求，再结合用户背景分析差距
3. 如果工具执行失败，记录错误原因，尝试替代方案或询问用户
4. 支持多轮推理：如果用户追问，先基于已有 observations 继续分析

【可选动作】
1. retrieve_knowledge - 需要检索知识库（当需要了解岗位要求时）
2. execute_tool - 需要执行某个工具（画像生成、匹配、差距分析等）
3. ask_clarification - 需要向用户确认信息（当缺少关键上下文时）
4. finish - 已收集足够信息，可以生成最终回复

请以JSON格式返回你的思考过程和下一步动作：
{{
    "reasoning": "你的推理过程，包括对用户意图的理解",
    "action": {{
        "type": "动作类型",
        "detail": "具体说明",
        "tool_name": "工具名称（如果需要执行工具）",
        "question": "问题（如果需要确认）",
        "target_job": "如果涉及岗位检索，填写目标岗位"
    }}
}}

只返回JSON，不要其他内容。"""

        return prompt

    def _parse_thinking_response(self, response: str, observations: list[dict]) -> dict[str, Any]:
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            parsed = json.loads(response.strip())
            return {
                "reasoning": parsed.get("reasoning", ""),
                "action": parsed.get("action", {"type": AgentAction.FINISH.value}),
            }
        except (json.JSONDecodeError, Exception):
            if any(keyword in response.lower() for keyword in ["完成", "结束", "生成"]):
                return {
                    "reasoning": "根据上下文决定完成",
                    "action": {"type": AgentAction.FINISH.value},
                }
            return {
                "reasoning": response[:200],
                "action": {"type": AgentAction.FINISH.value},
            }

    def _retrieve_knowledge(self, action: dict) -> dict[str, Any]:
        query = action.get("detail", "")
        top_k = action.get("top_k", 4)

        try:
            hits = self.vector_search_service.search(query, top_k=top_k)
            return {
                "type": "knowledge",
                "content": f"检索到 {len(list(hits or []))} 条相关知识",
                "hits": list(hits or [])[:top_k],
            }
        except Exception as e:
            return {
                "type": "knowledge",
                "content": f"知识检索失败: {str(e)}",
                "error": str(e),
            }

    def _execute_tool(self, user: User, action: dict, message: str) -> dict[str, Any]:
        tool_name = action.get("tool_name", "")
        if not tool_name:
            return {
                "type": "tool",
                "content": "未指定工具",
                "error": "no_tool_specified",
                "success": False,
            }

        try:
            result = self.tool_registry.run(tool_name, user=user, message=message, top_k=4)
            success = not bool(result.get("data", {}).get("error"))

            if not success:
                error_msg = result.get("data", {}).get("error", "unknown")
                result["反思"] = f"工具{tool_name}执行失败: {error_msg}，建议尝试替代方案或询问用户补充信息"

            return {
                "type": "tool",
                "tool": tool_name,
                "content": result.get("summary", "工具执行完成"),
                "data": result.get("data", {}),
                "success": success,
                "反思": result.get("反思"),
            }
        except Exception as e:
            return {
                "type": "tool",
                "tool": tool_name,
                "content": f"工具执行失败: {str(e)}",
                "error": str(e),
                "success": False,
                "反思": f"工具{tool_name}异常: {str(e)}，建议询问用户是否有其他需求"
            }

    def _generate_final_reply(
        self,
        user: User,
        message: str,
        history: list[dict],
        session_state: dict[str, Any],
        observations: list[dict],
        final_thought: dict[str, Any],
    ) -> str:
        tool_outputs = []
        retrieval_chunks = []
        reflections = []

        for obs in observations:
            if obs.get("type") == "tool":
                tool_outputs.append(obs)
                if obs.get("反思"):
                    reflections.append(obs["反思"])
            elif obs.get("type") == "knowledge":
                hits = obs.get("hits", [])
                for hit in hits:
                    retrieval_chunks.append({
                        "job_name": hit.get("metadata", {}).get("job_name", "岗位"),
                        "snippet": hit.get("content", "")[:200],
                    })

        context = {
            "scene": "react_final",
            "tool_outputs": tool_outputs,
            "retrieval_chunks": retrieval_chunks,
            "session_state": session_state,
            "reply_principle": "结论先出：先给结论，再给依据，最后给建议",
        }

        try:
            reply = self.llm_service.chat(
                user_role=user.role.code if user.role else "student",
                user_name=user.real_name,
                message=message,
                history=truncate_history_by_tokens(history) if history else [],
                context=context,
            )
            return reply
        except Exception as e:
            if tool_outputs:
                first = tool_outputs[0]
                conclusion = first.get("content", "已完成处理")
                return f"结论：{conclusion}\n依据：已完成本轮分析。\n下一步：你可以继续追问细节。"
            return f"结论：已收到你的请求（{message[:20]}）。\n下一步：告诉我更具体的目标，我可以给你执行建议。"

    def set_max_iterations(self, max_iterations: int):
        self.max_iterations = max_iterations


def get_react_agent(db: Session) -> ReActAgent:
    return ReActAgent(db)