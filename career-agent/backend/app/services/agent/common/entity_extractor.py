from __future__ import annotations

import json
import re
from typing import Any

from app.services.assistant_skill_catalog_service import normalize_skill_code
from app.services.llm_service import get_llm_service


COMMON_CITIES = [
    "上海", "北京", "深圳", "广州", "杭州", "成都", "南京", "苏州",
    "武汉", "西安", "重庆", "天津", "郑州", "长沙", "东莞", "佛山"
]

COMMON_INDUSTRIES = [
    "互联网", "金融", "制造", "电商", "教育", "医疗", "游戏",
    "新能源", "半导体", "房地产", "汽车", "物流", "咨询", "通信"
]

COMMON_JOBS = [
    "产品经理", "产品助理", "产品策划", "产品运营",
    "前端开发", "前端工程师", "后端开发", "后端工程师",
    "Java开发", "Python开发", "全栈开发", "全栈工程师",
    "算法工程师", "数据分析师", "数据工程师",
    "UI设计师", "UX设计师", "交互设计师",
    "测试工程师", "运维工程师", "安全工程师",
    "运营", "市场营销", "销售", "人力资源", "HR",
    "项目经理", "行政", "法务", "财务"
]


class EntityExtractor:
    def __init__(self):
        self.llm_service = get_llm_service()
        self.common_cities = COMMON_CITIES
        self.common_industries = COMMON_INDUSTRIES
        self.common_jobs = COMMON_JOBS
        self._llm_extraction_prompt = """你是一个实体提取助手。从用户消息中提取以下实体：
- target_job: 目标岗位（如：产品经理、前端开发）
- target_city: 目标城市（如：上海、北京）
- target_industry: 目标行业（如：互联网、金融）
- target_skill: 相关技能（如：Python、React）

用户消息：{message}

请以JSON格式返回，格式如下：
{{
    "target_job": "提取的岗位或空字符串",
    "target_city": "提取的城市或空字符串",
    "target_industry": "提取的行业或空字符串",
    "target_skill": "提取的技能或空字符串"
}}

只返回JSON，不要其他内容。"""

    def extract(
        self,
        message: str,
        session_state: dict[str, Any] | None = None,
        context_binding: dict[str, Any] | None = None,
        client_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        text = message.strip() if message else ""
        session_state = session_state or {}
        context_binding = context_binding or {}
        client_state = client_state or {}

        slots: dict[str, Any] = {
            "target_job": "",
            "target_city": "",
            "target_industry": "",
            "target_skill": "",
            "resume_id": None,
            "resume_version_id": None,
            "selected_skill": "",
            "comparison_target": "",
            "current_focus": "",
            "use_latest_resume": False,
            "continue_previous_task": False,
        }

        rule_based_slots = self._rule_based_extract(text)
        slots.update(rule_based_slots)

        try:
            llm_slots = self._llm_extract(text)
            for key in ["target_job", "target_city", "target_industry", "target_skill"]:
                if not slots.get(key) and llm_slots.get(key):
                    slots[key] = llm_slots[key]
        except Exception:
            pass

        self._fill_from_context(slots, session_state, context_binding, client_state)

        self._validate_slots(slots)

        return slots

    def _rule_based_extract(self, text: str) -> dict[str, Any]:
        text = re.sub(r"\s+", "", text)
        result = {
            "target_job": self._extract_job(text),
            "target_city": self._extract_city(text),
            "target_industry": self._extract_industry(text),
            "target_skill": self._extract_skill(text),
            "comparison_target": self._extract_comparison(text),
            "current_focus": self._extract_focus(text),
            "use_latest_resume": any(token in text for token in ["最新简历", "最新版本", "用最近那份"]),
            "continue_previous_task": any(token in text for token in ["继续", "展开", "再看", "再分析", "接着"]) or text in {"好的", "收到"},
        }
        return result

    def _extract_job(self, text: str) -> str:
        explicit = re.findall(r"(?:按|换成|看|做|走)?([\u4e00-\u9fa5A-Za-z0-9]{2,20})(?:岗位|方向|职位|简历)", text)
        if explicit:
            return explicit[-1]

        job_keywords = {
            "产品经理": "产品经理",
            "产品助理": "产品助理",
            "产品策划": "产品策划",
            "产品运营": "产品运营",
            "前端开发": "前端开发",
            "前端工程师": "前端工程师",
            "后端开发": "后端开发",
            "后端工程师": "后端工程师",
            "Java开发": "Java开发",
            "Python开发": "Python开发",
            "全栈": "全栈开发",
            "全栈工程师": "全栈工程师",
            "算法工程师": "算法工程师",
            "数据分析师": "数据分析师",
            "数据工程师": "数据工程师",
            "运营": "运营",
            "市场营销": "市场营销",
            "测试工程师": "测试工程师",
            "运维工程师": "运维工程师",
            "安全工程师": "安全工程师",
            "UI设计": "UI设计师",
            "UX设计": "UX设计师",
            "交互设计": "交互设计师",
            "项目经理": "项目经理",
            "HR": "人力资源",
            "人力": "人力资源",
            "销售": "销售",
            "行政": "行政",
            "法务": "法务",
            "财务": "财务",
        }

        for keyword, job in job_keywords.items():
            if keyword in text:
                return job

        for job in self.common_jobs:
            if job in text:
                return job

        return ""

    def _extract_city(self, text: str) -> str:
        for city in self.common_cities:
            if city in text:
                return city
        return ""

    def _extract_industry(self, text: str) -> str:
        for industry in self.common_industries:
            if industry in text:
                return industry
        return ""

    def _extract_skill(self, text: str) -> str:
        skill_keywords = [
            "Python", "Java", "JavaScript", "Go", "Rust", "C++", "C#", "Ruby", "PHP",
            "React", "Vue", "Angular", "Node.js", "Django", "Flask", "Spring",
            "SQL", "MySQL", "PostgreSQL", "MongoDB", "Redis",
            "TensorFlow", "PyTorch", "Keras", "PaddlePaddle",
            "AWS", "Azure", "GCP", "阿里云", "腾讯云",
            "Docker", "Kubernetes", "Jenkins", "Git",
            "机器学习", "深度学习", "NLP", "CV", "推荐系统",
            "数据分析", "数据挖掘", "算法", "产品设计", "Axure", "Figma"
        ]

        for skill in skill_keywords:
            if skill.lower() in text.lower():
                return skill

        return ""

    def _extract_comparison(self, text: str) -> str:
        if "对比" not in text and "比较" not in text and "vs" not in text.lower():
            return ""
        match = re.findall(r"(?:对比|比较|vs)(.+?)(?:和|与|哪个|$)", text)
        return match[-1].strip() if match else ""

    def _extract_focus(self, text: str) -> str:
        focus_keywords = {
            "技能": "技能",
            "投递": "投递",
            "简历": "简历",
            "画像": "画像",
            "成长": "成长",
            "岗位": "岗位",
            "城市": "城市",
            "行业": "行业",
        }
        for keyword, focus in focus_keywords.items():
            if keyword in text:
                return focus
        return ""

    def _llm_extract(self, message: str) -> dict[str, Any]:
        prompt = self._llm_extraction_prompt.format(message=message)

        try:
            response = self.llm_service.chat(
                user_role="system",
                user_name="assistant",
                message=prompt,
                history=[],
                context={"scene": "entity_extraction"}
            )

            response = response.strip()
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]

            entities = json.loads(response.strip())
            return {
                "target_job": entities.get("target_job", ""),
                "target_city": entities.get("target_city", ""),
                "target_industry": entities.get("target_industry", ""),
                "target_skill": entities.get("target_skill", ""),
            }
        except (json.JSONDecodeError, Exception):
            return {}

    def _fill_from_context(
        self,
        slots: dict[str, Any],
        session_state: dict[str, Any],
        context_binding: dict[str, Any],
        client_state: dict[str, Any],
    ):
        context_map = {
            "target_job": session_state.get("current_target_job"),
            "target_city": session_state.get("current_target_city"),
            "target_industry": session_state.get("current_target_industry"),
            "resume_id": self._to_int(session_state.get("current_resume_id")),
            "resume_version_id": self._to_int(session_state.get("current_resume_version_id")),
            "selected_skill": normalize_skill_code(session_state.get("current_skill") or ""),
            "current_focus": session_state.get("last_analysis_focus"),
        }

        for key, value in context_map.items():
            if not slots.get(key) and value:
                slots[key] = value

        for key in ["target_job", "target_city", "target_industry"]:
            if not slots.get(key) and client_state.get(key):
                slots[key] = str(client_state.get(key)).strip()

        binding_resume = context_binding.get("resume") if isinstance(context_binding.get("resume"), dict) else {}
        if not slots.get("resume_id"):
            slots["resume_id"] = self._to_int(binding_resume.get("resume_id")) or self._to_int(binding_resume.get("id"))
        if not slots.get("resume_version_id"):
            slots["resume_version_id"] = self._to_int(binding_resume.get("resume_version_id")) or self._to_int(binding_resume.get("current_version_id"))

    def _validate_slots(self, slots: dict[str, Any]):
        if slots.get("target_city") and slots["target_city"] not in self.common_cities:
            slots["target_city"] = ""

        if slots.get("target_industry") and slots["target_industry"] not in self.common_industries:
            slots["target_industry"] = ""

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


def get_entity_extractor() -> EntityExtractor:
    return EntityExtractor()
