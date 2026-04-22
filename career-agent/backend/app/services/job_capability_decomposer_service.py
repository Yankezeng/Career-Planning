from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.job import Job


class JobCapabilityDecomposerService:
    HARD_SKILL_KEYWORDS = {
        "编程语言": ["Python", "Java", "JavaScript", "Go", "Rust", "C++", "C#", "Ruby", "PHP", "TypeScript", "Swift", "Kotlin"],
        "前端框架": ["React", "Vue", "Angular", "Node.js", "Next.js", "Nuxt", "HTML", "CSS", "Sass"],
        "后端框架": ["Django", "Flask", "Spring", "Spring Boot", "FastAPI", "Express", "NestJS", "Rails"],
        "数据库": ["SQL", "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch", "Oracle", "SQLite"],
        "数据处理": ["Pandas", "NumPy", "Spark", "Hadoop", "Kafka", "Flink"],
        "机器学习": ["TensorFlow", "PyTorch", "Keras", "Scikit-learn", "XGBoost", "LightGBM"],
        "云平台": ["AWS", "Azure", "GCP", "阿里云", "腾讯云", "华为云"],
        "DevOps": ["Docker", "Kubernetes", "Jenkins", "GitLab CI", "GitHub Actions", "Ansible"],
    }

    SOFT_SKILL_KEYWORDS = {
        "沟通能力": ["沟通", "表达", "协作", "团队"],
        "问题解决": ["问题解决", "逻辑思维", "分析", "调试"],
        "学习能力": ["学习", "成长", "自驱动", "主动"],
        "项目管理": ["项目管理", "协调", "进度", "规划"],
        "创新能力": ["创新", "创意", "突破", "优化"],
    }

    TOOL_CATEGORIES = {
        "开发工具": ["Git", "VS Code", "IntelliJ", "Eclipse", "Vim", "PyCharm"],
        "协作工具": ["Slack", "钉钉", "飞书", "企业微信", "Notion", "Confluence"],
        "原型设计": ["Figma", "Sketch", "Axure", "Adobe XD", "Mockplus"],
        "文档工具": ["Markdown", "Word", "PPT", "Excel", "Google Docs"],
    }

    def __init__(self, db: Session):
        self.db = db

    def decompose(self, job_id: int) -> dict[str, Any]:
        job = self.db.query(Job).filter(Job.id == job_id, Job.deleted.is_(False)).first()
        if not job:
            return {"error": "Job not found"}

        description = job.description or ""
        requirements = job.requirements or ""

        hard_skills = self._decompose_hard_skills(description, requirements)
        soft_skills = self._decompose_soft_skills(description, requirements)
        experience_req = self._decompose_experience(description, requirements)
        certifications = self._decompose_certifications(description, requirements)
        tools = self._decompose_tools(description, requirements)
        difficulty = self._assess_difficulty(description, requirements, hard_skills)

        return {
            "job_id": job_id,
            "job_name": job.name,
            "hard_skills": hard_skills,
            "soft_skills": soft_skills,
            "experience_requirements": experience_req,
            "certification_requirements": certifications,
            "tool_requirements": tools,
            "difficulty_level": difficulty,
            "learning_suggestions": self._generate_learning_suggestions(hard_skills, difficulty),
        }

    def _decompose_hard_skills(self, description: str, requirements: str) -> dict[str, list[str]]:
        text = f"{description} {requirements}".lower()

        result = {}
        for category, keywords in self.HARD_SKILL_KEYWORDS.items():
            found = []
            for keyword in keywords:
                if keyword.lower() in text:
                    found.append(keyword)
            if found:
                result[category] = found

        return result

    def _decompose_soft_skills(self, description: str, requirements: str) -> dict[str, list[str]]:
        text = f"{description} {requirements}".lower()

        result = {}
        for skill, keywords in self.SOFT_SKILL_KEYWORDS.items():
            found = []
            for keyword in keywords:
                if keyword.lower() in text:
                    found.append(skill)
                    break
            if found:
                result[skill] = found

        return result

    def _decompose_experience(self, description: str, requirements: str) -> dict[str, Any]:
        text = f"{description} {requirements}"

        years_pattern = r"(\d+)[\-到](\d+)年|以上|经验"
        years_match = re.search(years_pattern, text)

        years_required = 0
        if years_match:
            if "以上" in years_match.group():
                match = re.search(r"(\d+)年以上", text)
                if match:
                    years_required = int(match.group(1))
            else:
                match = re.search(r"(\d+)[\-到](\d+)年", text)
                if match:
                    years_required = int(match.group(2))

        project_pattern = r"(\d+)[\+个]?(?:以上)?项目"
        project_match = re.search(project_pattern, text)

        projects_required = project_match.group(1) if project_match else "不限"

        industry_pattern = r"(?:行业|领域)(\w+)"
        industry_match = re.search(industry_pattern, text)
        industry_required = industry_match.group(1) if industry_match else "不限"

        return {
            "years_required": years_required,
            "projects_required": projects_required,
            "industry_experience": industry_required,
            "description": "需要具备相关工作经验和项目积累" if years_required > 0 else "对经验要求相对宽松，适合应届生",
        }

    def _decompose_certifications(self, description: str, requirements: str) -> list[dict[str, str]]:
        text = f"{description} {requirements}"

        certs = []

        cert_patterns = {
            "PMP": r"PMP|项目管理专业人士",
            "AWS": r"AWS|亚马逊云|云架构师",
            "阿里云": r"阿里云|ACP|ACE",
            "腾讯云": r"腾讯云|TCP|ACE",
            "华为云": r"华为云|HCIP|HCIE",
            "CFA": r"CFA|特许金融分析师",
            "CPA": r"CPA|注册会计师",
            "司法考试": r"法律职业资格|司法考试",
        }

        for cert_name, pattern in cert_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                certs.append({
                    "name": cert_name,
                    "priority": "优先" if "优先" in text else "加分",
                })

        return certs

    def _decompose_tools(self, description: str, requirements: str) -> dict[str, list[str]]:
        text = f"{description} {requirements}".lower()

        result = {}
        for category, tools in self.TOOL_CATEGORIES.items():
            found = []
            for tool in tools:
                if tool.lower() in text:
                    found.append(tool)
            if found:
                result[category] = found

        return result

    def _assess_difficulty(self, description: str, requirements: str, hard_skills: dict) -> str:
        score = 0

        if re.search(r"高级|资深|专家|lead|senior", description, re.IGNORECASE):
            score += 3
        if re.search(r"中级|3[\-到]5|5[\-到]10", description, re.IGNORECASE):
            score += 2
        if re.search(r"应届|实习|入门|初级|junior|entry", description, re.IGNORECASE):
            score += 0

        skill_count = sum(len(skills) for skills in hard_skills.values())
        if skill_count >= 8:
            score += 2
        elif skill_count >= 5:
            score += 1

        if score >= 5:
            return "高级"
        elif score >= 2:
            return "中级"
        else:
            return "入门"

    def _generate_learning_suggestions(self, hard_skills: dict, difficulty: str) -> list[dict[str, Any]]:
        suggestions = []

        for category, skills in hard_skills.items():
            for skill in skills[:3]:
                suggestions.append({
                    "skill": skill,
                    "category": category,
                    "priority": "高" if difficulty == "入门" else ("中" if difficulty == "中级" else "低"),
                    "suggestion": f"建议系统学习{skill}，通过实战项目加深理解",
                    "resources": self._get_default_resources(skill),
                })

        return suggestions

    def _get_default_resources(self, skill: str) -> list[dict[str, str]]:
        resources = {
            "Python": [{"type": "文档", "name": "Python官方文档", "url": "https://docs.python.org"}],
            "Java": [{"type": "文档", "name": "Spring官方文档", "url": "https://spring.io/projects/spring-boot"}],
            "JavaScript": [{"type": "文档", "name": "MDN Web Docs", "url": "https://developer.mozilla.org/zh-CN/docs/Web/JavaScript"}],
        }

        default = [{"type": "视频", "name": f"{skill}入门教程", "url": ""}]

        return resources.get(skill, default)

    def get_skill_learning_priority(
        self,
        job_id: int,
        student_skills: list[str],
    ) -> list[dict[str, Any]]:
        job_capabilities = self.decompose(job_id)
        if "error" in job_capabilities:
            return []

        all_job_skills = []
        for skills in job_capabilities.get("hard_skills", {}).values():
            all_job_skills.extend(skills)

        priority_list = []
        for skill in all_job_skills:
            has_skill = skill in student_skills
            priority_list.append({
                "skill": skill,
                "has_skill": has_skill,
                "priority": "低" if has_skill else "高",
                "category": self._get_skill_category(skill, job_capabilities),
            })

        priority_list.sort(key=lambda x: (0 if x["has_skill"] else 1, 0 if x["priority"] == "高" else 1))

        return priority_list

    def _get_skill_category(self, skill: str, job_capabilities: dict) -> str:
        for category, skills in job_capabilities.get("hard_skills", {}).items():
            if skill in skills:
                return category
        return "其他"

    def calculate_capability_gap(
        self,
        job_id: int,
        student_skills: list[str],
        student_ability_scores: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        job_capabilities = self.decompose(job_id)
        if "error" in job_capabilities:
            return {"error": "Job not found"}

        all_job_skills = []
        for skills in job_capabilities.get("hard_skills", {}).values():
            all_job_skills.extend(skills)

        gap_skills = [s for s in all_job_skills if s not in student_skills]
        matched_skills = [s for s in all_job_skills if s in student_skills]

        gap_percentage = len(gap_skills) / len(all_job_skills) * 100 if all_job_skills else 0
        match_percentage = 100 - gap_percentage

        return {
            "job_id": job_id,
            "job_name": job_capabilities.get("job_name"),
            "total_skills_required": len(all_job_skills),
            "skills_matched": len(matched_skills),
            "skills_gap": len(gap_skills),
            "match_percentage": round(match_percentage, 1),
            "gap_percentage": round(gap_percentage, 1),
            "gap_skills": gap_skills,
            "matched_skills": matched_skills,
            "difficulty_level": job_capabilities.get("difficulty_level"),
            "overall_assessment": self._assess_overall(match_percentage),
        }

    def _assess_overall(self, match_percentage: float) -> str:
        if match_percentage >= 80:
            return "优秀 - 您已基本满足该岗位的能力要求"
        elif match_percentage >= 60:
            return "良好 - 您与该岗位要求较匹配，有少量技能需要提升"
        elif match_percentage >= 40:
            return "一般 - 您与该岗位要求存在一定差距，需要系统学习"
        else:
            return "不足 - 该岗位对您来说挑战较大，建议先补充基础知识"


def get_job_capability_decomposer_service(db: Session) -> JobCapabilityDecomposerService:
    return JobCapabilityDecomposerService(db)
