from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from app.core.project_paths import PROJECT_ROOT

try:
    from langchain.agents import create_agent
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnableLambda
except ImportError:  # pragma: no cover
    create_agent = None
    ChatPromptTemplate = None
    RunnableLambda = None

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover
    ChatOpenAI = None


def _load_env_file(file_path: Path) -> None:
    if not file_path.exists():
        return

    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_agent_env() -> None:
    backend_dir = PROJECT_ROOT / "backend"
    for env_name in (".env", ".env.example"):
        _load_env_file(backend_dir / env_name)


class LangChainCareerAgent:
    def __init__(self, knowledge_searcher: Callable[[str, int], list[dict[str, Any]]] | None = None):
        load_agent_env()
        self.knowledge_searcher = knowledge_searcher
        self.provider = os.getenv("LANGCHAIN_PROVIDER", "dashscope-compatible")
        self.model_name = os.getenv("LANGCHAIN_MODEL", "qwen-plus")
        self.temperature = float(os.getenv("LANGCHAIN_TEMPERATURE", "0.2"))
        self.base_url = os.getenv("LANGCHAIN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")

    def invoke(
        self,
        user_role: str,
        user_name: str,
        message: str,
        history: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        history = history or []
        context = context or {}
        knowledge_hits = self._search_knowledge(message)

        if create_agent and ChatOpenAI and self.api_key:
            try:
                return self._invoke_real_agent(user_role, user_name, message, history, context, knowledge_hits)
            except Exception:
                pass

        if ChatPromptTemplate and RunnableLambda:
            return self._invoke_langchain_fallback(user_role, user_name, message, history, context, knowledge_hits)

        return self._compose_answer(message, context, knowledge_hits)

    def _invoke_real_agent(
        self,
        user_role: str,
        user_name: str,
        message: str,
        history: list[dict[str, Any]],
        context: dict[str, Any],
        knowledge_hits: list[dict[str, Any]],
    ) -> str:
        model = ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature,
            api_key=self.api_key,
            base_url=self.base_url,
        )
        system_prompt = self._build_system_prompt(user_role)
        agent = create_agent(model=model, tools=[], system_prompt=system_prompt)
        result = agent.invoke(
            {
                "messages": history
                + [
                    {
                        "role": "user",
                        "content": (
                            f"用户：{user_name}\n"
                            f"当前问题：{message}\n\n"
                            f"系统上下文：\n{self._build_tool_context(user_role, context, knowledge_hits)}\n\n"
                            "请输出中文，先给结论，再给可执行建议。"
                        ),
                    }
                ]
            }
        )
        messages = result.get("messages", [])
        if not messages:
            return self._compose_answer(message, context, knowledge_hits)
        last_message = messages[-1]
        if isinstance(last_message, dict):
            return str(last_message.get("content", ""))
        return str(getattr(last_message, "content", ""))

    def _invoke_langchain_fallback(
        self,
        user_role: str,
        user_name: str,
        message: str,
        history: list[dict[str, Any]],
        context: dict[str, Any],
        knowledge_hits: list[dict[str, Any]],
    ) -> str:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self._build_system_prompt(user_role)),
                (
                    "human",
                    (
                        "用户：{user_name}\n"
                        "历史对话：\n{history_text}\n\n"
                        "当前问题：{message}\n\n"
                        "上下文与知识库检索：\n{tool_context}\n\n"
                        "请输出中文，结构清晰、可执行。"
                    ),
                ),
            ]
        )
        chain = prompt | RunnableLambda(lambda _: self._compose_answer(message, context, knowledge_hits))
        return chain.invoke(
            {
                "user_name": user_name,
                "history_text": self._history_to_text(history),
                "message": message,
                "tool_context": self._build_tool_context(user_role, context, knowledge_hits),
            }
        )

    def _compose_answer(self, message: str, context: dict[str, Any], knowledge_hits: list[dict[str, Any]]) -> str:
        role = (context.get("role") or "student").lower()
        if role == "enterprise":
            return self._compose_enterprise_answer(message, context, knowledge_hits)
        return self._compose_student_admin_answer(message, context, knowledge_hits)

    def _compose_student_admin_answer(self, message: str, context: dict[str, Any], knowledge_hits: list[dict[str, Any]]) -> str:
        top_job = (context.get("top_jobs") or [{}])[0]
        top_job_name = top_job.get("job_name") or "目标岗位"
        strengths = context.get("strengths") or []
        weaknesses = context.get("weaknesses") or []
        latest_path = context.get("latest_path_summary") or "建议先完成画像与匹配，再生成成长路径。"
        kb_lines = [
            f"- {item.get('job_name') or '岗位'} / {item.get('industry') or '行业未标注'}"
            for item in knowledge_hits[:3]
        ]

        if any(keyword in message for keyword in ["岗位", "方向", "适合", "职业"]):
            return (
                f"结论：建议优先围绕“{top_job_name}”推进。\n\n"
                f"优势：{('、'.join(strengths[:3]) if strengths else '已有基础能力，可继续放大项目证据')}\n"
                f"待补齐：{('、'.join(weaknesses[:3]) if weaknesses else '项目结果表达、岗位关键词映射、实战经历')}\n\n"
                f"下一步：{latest_path}\n"
                f"岗位参考：\n{chr(10).join(kb_lines) if kb_lines else '- 当前暂无岗位样本'}"
            )

        return (
            "我已结合当前画像、匹配结果与岗位知识库给出建议。\n\n"
            f"当前主方向：{top_job_name}\n"
            f"推荐动作：{latest_path}\n"
            f"岗位参考：\n{chr(10).join(kb_lines) if kb_lines else '- 当前暂无岗位样本'}"
        )

    def _compose_enterprise_answer(self, message: str, context: dict[str, Any], knowledge_hits: list[dict[str, Any]]) -> str:
        recent_candidates = context.get("recent_candidates") or []
        candidate_count = int(context.get("candidate_count") or len(recent_candidates) or 0)
        high_match_count = int(context.get("high_match_count") or 0)
        active_job_names = context.get("active_job_names") or []
        selected_skill = context.get("selected_skill") or "未指定"

        sorted_candidates = sorted(
            recent_candidates,
            key=lambda item: float(item.get("match_score") or 0),
            reverse=True,
        )
        top_candidate = sorted_candidates[0] if sorted_candidates else {}
        top_name = top_candidate.get("student_name") or "暂无"
        top_score = float(top_candidate.get("match_score") or 0)
        top_summary = top_candidate.get("profile_summary") or "暂无画像摘要"

        if top_score >= 85:
            match_judgement = "高匹配，可优先推进约面"
            action = "建议在 24 小时内发起面试邀约，并围绕项目成果做深问。"
        elif top_score >= 70:
            match_judgement = "中高匹配，建议进入重点跟进"
            action = "建议先电话沟通验证岗位意向，再决定是否约面。"
        elif top_score > 0:
            match_judgement = "匹配度一般，建议保留观察"
            action = "建议要求补充项目证据或岗位相关材料后再判断。"
        else:
            match_judgement = "暂无可判定匹配样本"
            action = "建议先补齐候选人数据，再进行排序和推进。"

        highlights = []
        if top_candidate:
            highlights.append(f"当前最高优先候选人为 {top_name}（匹配 {top_score:.1f}）")
            highlights.append(f"候选人摘要：{top_summary}")
        if active_job_names:
            highlights.append(f"活跃招聘岗位：{'、'.join(active_job_names[:4])}")

        risks = []
        if candidate_count == 0:
            risks.append("当前企业人才池为空，无法形成招聘排序。")
        if candidate_count > 0 and high_match_count == 0:
            risks.append("暂无高匹配候选人，需扩大筛选范围或调整岗位要求。")
        if not risks:
            risks.append("暂无显著系统性风险，可进入常规招聘节奏。")

        kb_lines = [
            f"- {item.get('job_name') or '岗位'} / {item.get('industry') or '行业未标注'}"
            for item in knowledge_hits[:3]
        ]

        return (
            f"结论：{match_judgement}。\n"
            f"候选人池规模：{candidate_count}，高匹配候选人：{high_match_count}，当前技能上下文：{selected_skill}。\n\n"
            f"候选人亮点：\n{chr(10).join(f'- {item}' for item in highlights) if highlights else '- 暂无亮点摘要'}\n\n"
            f"风险项：\n{chr(10).join(f'- {item}' for item in risks)}\n\n"
            f"人岗匹配判断：{match_judgement}。\n"
            f"推荐动作：{action}\n"
            "推荐追问：\n"
            f"- 请候选人复盘一个最相关项目，说明目标、角色、结果与指标。\n"
            f"- 请候选人说明入职前两周能独立承担的任务边界。\n"
            f"- 请候选人描述与岗位最匹配的技能证据和可验证成果。\n\n"
            f"岗位知识参考：\n{chr(10).join(kb_lines) if kb_lines else '- 当前暂无岗位知识命中'}"
        )

    def _search_knowledge(self, query: str) -> list[dict[str, Any]]:
        if not self.knowledge_searcher:
            return []
        try:
            return self.knowledge_searcher(query, top_k=4)
        except Exception:
            return []

    def _build_tool_context(self, user_role: str, context: dict[str, Any], knowledge_hits: list[dict[str, Any]]) -> str:
        role = (user_role or "student").lower()
        if role == "enterprise":
            lines = [
                f"角色：{role}",
                f"企业：{context.get('company_name') or '未绑定'}",
                f"行业：{context.get('industry') or '未标注'}",
                f"候选人数量：{context.get('candidate_count') or 0}",
                f"高匹配候选人：{context.get('high_match_count') or 0}",
                f"活跃岗位：{'、'.join(context.get('active_job_names') or []) or '暂无'}",
                f"当前技能：{context.get('selected_skill') or '未启用'}",
            ]
            pipeline_summary = context.get("pipeline_summary") or []
            if pipeline_summary:
                lines.append(
                    "招聘管道："
                    + "；".join(f"{item.get('stage')}={int(item.get('value') or 0)}" for item in pipeline_summary)
                )
            if knowledge_hits:
                lines.append("知识库命中：")
                lines.extend(
                    [
                        f"- {item.get('job_name') or '岗位'} / {item.get('industry') or '行业未标注'} / 分数 {float(item.get('score') or 0):.4f}"
                        for item in knowledge_hits[:4]
                    ]
                )
            return "\n".join(lines)

        lines = [
            f"角色：{role}",
            f"专业：{context.get('major') or '未填写'}",
            f"目标行业：{context.get('target_industry') or '未填写'}",
            f"目标城市：{context.get('target_city') or '未填写'}",
            f"兴趣方向：{'、'.join(context.get('interests') or []) or '未填写'}",
            f"画像总结：{context.get('profile_summary') or '暂无画像'}",
            f"优势：{'、'.join(context.get('strengths') or []) or '暂无'}",
            f"短板：{'、'.join(context.get('weaknesses') or []) or '暂无'}",
            f"路径总结：{context.get('latest_path_summary') or '暂无成长路径'}",
            f"当前技能：{context.get('selected_skill') or '未启用'}",
        ]
        top_jobs = context.get("top_jobs") or []
        if top_jobs:
            lines.append(
                "推荐岗位："
                + "；".join(f"{item.get('job_name', '岗位')}({float(item.get('score') or 0):.1f})" for item in top_jobs[:3])
            )
        if knowledge_hits:
            lines.append("知识库检索结果：")
            lines.extend(
                [
                    f"- {item.get('job_name') or '岗位'} / {item.get('industry') or '行业未标注'} / 分数 {float(item.get('score') or 0):.4f}"
                    for item in knowledge_hits[:4]
                ]
            )
        return "\n".join(lines)

    @staticmethod
    def _history_to_text(history: list[dict[str, Any]]) -> str:
        if not history:
            return "暂无历史对话"
        return "\n".join([f"{item.get('role', 'user')}: {item.get('content', '')}" for item in history[-6:]])

    @staticmethod
    def _build_system_prompt(user_role: str) -> str:
        common = "你是 Career Agent 智能体，回答要求：中文、先结论后建议、内容可执行、避免空话。"
        if user_role == "enterprise":
            return (
                common
                + " 当前服务对象是企业招聘人员。"
                + " 你必须从招聘筛选、简历解读、人岗匹配、面试追问、推进优先级角度回答。"
                + " 禁止输出学生成长路径、学习计划、职业规划辅导等学生视角内容。"
            )
        if user_role == "admin":
            return common + " 当前服务对象是平台管理端，请强调系统运营、数据质量和管理决策。"
        return common + " 当前服务对象是学生端，请强调岗位方向、差距分析、行动计划和简历优化。"
