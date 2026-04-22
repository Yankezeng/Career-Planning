from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.services.llm_service import get_llm_service


class QueryRewriter:
    def __init__(self):
        self.llm_service = get_llm_service()

    def rewrite(self, query: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        session_state = context.get("session_state", {})
        use_llm_rewrite = bool(context.get("use_llm_rewrite"))

        original_query = query.strip()
        if not original_query:
            return {
                "original_query": "",
                "rewritten_query": "",
                "strategy": "empty",
                "expansions": [],
            }

        if use_llm_rewrite:
            try:
                rewritten = self._llm_rewrite(original_query, session_state)
                if rewritten and rewritten != original_query:
                    return {
                        "original_query": original_query,
                        "rewritten_query": rewritten,
                        "strategy": "llm_rewrite",
                        "expansions": self._extract_expansions(original_query, rewritten),
                    }
            except Exception:
                pass

        expanded = self._rule_based_expand(original_query)
        return {
            "original_query": original_query,
            "rewritten_query": expanded,
            "strategy": "rule_expand",
            "expansions": self._extract_expansions(original_query, expanded),
        }

    def _llm_rewrite(self, query: str, session_state: dict[str, Any]) -> str:
        context_info = ""
        if session_state:
            last_focus = session_state.get("last_analysis_focus")
            if last_focus:
                context_info = f"用户当前关注点: {last_focus}"

        prompt = f"""你是一个查询改写助手。请优化以下用户查询，使其更适合知识检索。

{context_info}
用户原始查询: {query}

要求:
1. 保持原意，扩展同义词
2. 添加可能的限定词（技能要求、经验要求等）
3. 使查询更加具体明确
4. 只返回改写后的查询，不要其他内容

改写后的查询:"""

        try:
            response = self.llm_service.chat(
                user_role="system",
                user_name="assistant",
                message=prompt,
                history=[],
                context={"scene": "query_rewrite"},
            )
            return response.strip().split("\n")[0].strip()
        except Exception:
            return query

    def _rule_based_expand(self, query: str) -> str:
        expansions = {
            "产品经理": "产品经理 岗位要求 技能 工作内容",
            "前端开发": "前端开发 岗位要求 技术栈 JavaScript React",
            "后端开发": "后端开发 岗位要求 技术栈 Python Java Go",
            "算法工程师": "算法工程师 岗位要求 机器学习 深度学习",
            "数据分析": "数据分析 岗位要求 SQL Python 可视化",
            "运营": "新媒体运营 用户运营 活动运营 增长",
            "简历": "简历撰写 项目经历 技能证书 自我评价",
            "面试": "面试技巧 面试题 常见问题 回答技巧",
            "成长": "职业发展 成长路径 学习计划 技能提升",
            "匹配": "人岗匹配 能力差距 技能要求",
        }

        for keyword, expansion in expansions.items():
            if keyword in query:
                return f"{query} {expansion}"

        return f"{query} 岗位要求 技能 工作内容"

    def _extract_expansions(self, original: str, rewritten: str) -> list[str]:
        original_terms = set(original.lower().split())
        rewritten_terms = set(rewritten.lower().split())
        new_terms = rewritten_terms - original_terms
        return list(new_terms)


@lru_cache(maxsize=1)
def get_query_rewriter() -> QueryRewriter:
    return QueryRewriter()
