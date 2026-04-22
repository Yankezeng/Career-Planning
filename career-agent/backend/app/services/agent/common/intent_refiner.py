from __future__ import annotations
import json
from typing import Any
from app.services.llm_service import get_llm_service


INTENT_TEMPLATES = {
    "career_exploration": {
        "patterns": [
            "我想做{job}", "我想成为{job}", "我想转{job}",
            "{job}发展前景", "{job}需要什么", "做{job}要具备什么",
            "如何成为{job}", "{job}和{job}哪个好", "{job}方向"
        ],
        "keywords": ["职业", "方向", "发展", "规划", "目标"],
        "skill": "match-center",
        "required_slot": "target_job"
    },
    "gap_analysis": {
        "patterns": ["差距", "缺什么", "不足", "还差", "需要提升什么"],
        "keywords": ["gap", "弱项", "短板"],
        "skill": "gap-analysis",
        "required_slot": "target_job"
    },
    "growth_planning": {
        "patterns": ["成长", "学习", "计划", "路线", "阶段"],
        "keywords": ["怎么学", "如何提升", "步骤"],
        "skill": "growth-planner",
        "required_slot": "target_job"
    },
    "resume_optimization": {
        "patterns": ["简历", "优化", "润色", "改写"],
        "keywords": ["resume", "CV"],
        "skill": "resume-workbench",
        "required_slot": "resume_id"
    },
    "job_search": {
        "patterns": ["找岗位", "有什么", "推荐岗位", "匹配"],
        "keywords": ["岗位", "职位", "机会"],
        "skill": "match-center",
        "required_slot": None
    }
}

REFINE_PROMPT = """你是一个意图理解专家。分析用户消息，提取用户的真实意图。

【用户消息】: {message}
【对话历史】: {history}
【当前技能上下文】: {current_skill}

请分析：
1. 用户是否提到了明确的职业目标（如：产品经理、前端开发）？
2. 用户想知道什么？（了解要求/分析差距/制定计划/执行操作）
3. 用户当前是否有足够的上下文信息？

请以JSON格式返回：
{{
    "intent": "意图类型(career_exploration/gap_analysis/growth_planning/resume_optimization/job_search/general_chat)",
    "confidence": 0.0-1.0,
    "primary_goal": "如果用户提到了职业目标，填写具体岗位",
    "secondary_goals": ["其他相关目标"],
    "extracted_job": "从消息中提取的具体岗位名称",
    "user_intent_summary": "用户真实意图的一句话总结",
    "urgency": "high/medium/low",
    "missing_info": ["缺少的关键信息列表"],
    "recommend_skill": "推荐的技能码",
    "reasoning": "推理过程"
}}

只返回JSON，不要其他内容。"""


class IntentRefiner:
    def __init__(self):
        self.llm_service = get_llm_service()

    def refine(self, message: str, history: list | None = None,
               session_state: dict | None = None) -> dict[str, Any]:
        rule_result = self._rule_based_refine(message)
        if rule_result["confidence"] >= 0.85:
            return rule_result

        try:
            llm_result = self._llm_refine(message, history, session_state)
            if llm_result["confidence"] >= 0.7:
                return llm_result
        except Exception:
            pass

        return rule_result

    def _rule_based_refine(self, message: str) -> dict[str, Any]:
        text = message.strip().lower().replace(" ", "")

        # 检测职业目标词（支持部分匹配）
        career_goal_keywords = {
            "产品经理": ["产品经理", "产品助理", "产品策划", "产品运营"],
            "前端开发": ["前端开发", "前端工程师", "前端", "web开发"],
            "后端开发": ["后端开发", "后端工程师", "后端", "服务器开发"],
            "Java开发": ["Java开发", "Java工程师", "Java"],
            "Python开发": ["Python开发", "Python工程师", "Python"],
            "全栈开发": ["全栈开发", "全栈工程师", "全栈"],
            "算法工程师": ["算法工程师", "算法工程师"],
            "数据分析师": ["数据分析师", "数据分析"],
            "数据工程师": ["数据工程师", "数据工程"],
            "UI设计": ["UI设计", "UI设计师"],
            "UX设计": ["UX设计", "UX设计师"],
            "交互设计": ["交互设计", "交互设计师"],
            "测试工程师": ["测试工程师"],
            "运维工程师": ["运维工程师"],
            "运营": ["运营", "运营专员", "运营经理"],
            "市场营销": ["市场营销", "市场专员", "市场经理"],
            "销售": ["销售", "销售经理"],
            "人力资源": ["人力资源", "HR"],
            "项目经理": ["项目经理"],
        }

        extracted_job = None
        for job, aliases in career_goal_keywords.items():
            for alias in aliases:
                if alias in text:
                    extracted_job = job
                    break
            if extracted_job:
                break

        action_query_patterns = ["该做什么", "怎么", "如何", "应该做什么",
                                 "需要什么", "要具备什么", "具备什么",
                                 "发展前景", "方向"]
        is_action_query = any(p in text for p in action_query_patterns)

        # 特殊句式处理："X没有目标，我的/其实...就是想做Y"
        # 这种情况下应该从后半句提取目标，而不是被"没有目标"误导
        goal_assertion_patterns = [
            "就是",           # "我的目标就是产品经理"
            "其实",           # "其实我想做产品经理"
            "主要",           # "我主要想做产品经理"
            "其实主要",       # "其实主要想做"
            "就是想",         # "我就是想"
            "目标就是",       # "目标就是产品经理"
        ]

        for pattern in goal_assertion_patterns:
            if pattern in text:
                # 从特殊句式后的内容中提取目标
                for job, aliases in career_goal_keywords.items():
                    for alias in aliases:
                        # 检查关键词是否在特殊句式之后（alias也需要转小写比较）
                        pos = text.find(pattern)
                        remaining = text[pos + len(pattern):] if pos >= 0 else text
                        alias_lower = alias.lower()
                        if alias_lower in remaining or alias_lower in text:
                            # 如果"没有"出现在关键词前面，且特殊句式在"没有"后面，说明是"没有X，我的Y就是Z"结构
                            neg_pos = text.find("没有")
                            pos_assert = text.find(pattern)
                            if neg_pos < 0 or neg_pos < pos_assert:
                                # "没有"不存在，或者"没有"在"就是"前面，以后半句为准
                                return {
                                    "intent": "career_exploration",
                                    "confidence": 0.95,  # 高置信度，因为有明确的"就是"声明
                                    "primary_goal": job,
                                    "extracted_job": job,
                                    "user_intent_summary": f"目标明确：{job}",
                                    "recommend_skill": "match-center",
                                    "missing_info": [],
                                    "reasoning": f"检测到'没有X，我的Y就是Z'结构，提取{job}作为目标"
                                }

        if extracted_job and is_action_query:
            return {
                "intent": "career_exploration",
                "confidence": 0.9,
                "primary_goal": extracted_job,
                "extracted_job": extracted_job,
                "user_intent_summary": f"想知道成为{extracted_job}需要什么",
                "recommend_skill": "match-center",
                "missing_info": [],
                "reasoning": "检测到职业目标和action query"
            }

        if extracted_job:
            return {
                "intent": "career_exploration",
                "confidence": 0.7,
                "primary_goal": extracted_job,
                "extracted_job": extracted_job,
                "user_intent_summary": f"对{extracted_job}方向感兴趣",
                "recommend_skill": "match-center",
                "missing_info": [],
                "reasoning": "检测到职业目标"
            }

        return {
            "intent": "general_chat",
            "confidence": 0.5,
            "primary_goal": None,
            "extracted_job": None,
            "user_intent_summary": "一般性聊天或询问",
            "recommend_skill": "general-chat",
            "missing_info": [],
            "reasoning": "未检测到明确职业目标"
        }

    def _llm_refine(self, message: str, history: list | None,
                     session_state: dict | None) -> dict[str, Any]:
        history_text = ""
        if history:
            history_text = "\n".join([
                f"{h.get('role', 'user')}: {h.get('content', '')[:100]}"
                for h in history[-3:]
            ])

        current_skill = ""
        if session_state:
            current_skill = session_state.get("current_skill", "")

        prompt = REFINE_PROMPT.format(
            message=message,
            history=history_text or "无历史对话",
            current_skill=current_skill or "无"
        )

        response = self.llm_service.chat(
            user_role="system",
            user_name="assistant",
            message=prompt,
            history=[],
            context={"scene": "intent_refinement"}
        )

        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            result = json.loads(response.strip())
            return result
        except (json.JSONDecodeError, Exception):
            return self._rule_based_refine(message)


def get_intent_refiner() -> IntentRefiner:
    return IntentRefiner()
