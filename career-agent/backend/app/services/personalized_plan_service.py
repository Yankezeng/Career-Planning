from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.services.llm_service import get_llm_service


class PersonalizedPlanService:
    def __init__(self, db: Session):
        self.db = db
        self.llm_service = get_llm_service()

    def generate(
        self,
        student_id: int,
        target_job_id: int | None = None,
    ) -> dict[str, Any]:
        student_profile = self._get_full_profile(student_id)
        ability_profile = self._get_ability_profile(student_id)

        strengths = self._identify_strengths(ability_profile)
        weaknesses = self._identify_weaknesses(ability_profile, target_job_id)

        strengths_strategy = self._build_strengths_strategy(strengths, student_profile)
        weaknesses_strategy = self._build_weaknesses_strategy(weaknesses, student_profile)
        avoid_suggestions = self._generate_avoid_suggestions(weaknesses)

        recommended_jobs = []
        if strengths:
            recommended_jobs = self._recommend_jobs_by_strengths(strengths, target_job_id)

        personalized_report = self._generate_report(
            student_id, strengths, weaknesses, strengths_strategy, weaknesses_strategy
        )

        return {
            "student_id": student_id,
            "target_job_id": target_job_id,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "strengths_strategy": strengths_strategy,
            "weaknesses_strategy": weaknesses_strategy,
            "avoid_suggestions": avoid_suggestions,
            "recommended_jobs": recommended_jobs,
            "personalized_report": personalized_report,
            "generated_at": datetime.now().isoformat(),
        }

    def _get_full_profile(self, student_id: int) -> dict[str, Any]:
        try:
            from app.models.student import Student, StudentProfile

            student = self.db.query(Student).filter(Student.id == student_id).first()
            if not student:
                return {}

            profile = self.db.query(StudentProfile).filter(
                StudentProfile.student_id == student_id
            ).first()

            profile_data = {
                "student_id": student_id,
                "name": student.real_name if student else "",
                "education": profile.education if profile else None,
                "skills": profile.skills if profile else None,
                "career_objective": profile.career_objective if profile else None,
                "self_evaluation": profile.self_evaluation if profile else None,
            }

            return profile_data

        except Exception:
            return {"student_id": student_id}

    def _get_ability_profile(self, student_id: int) -> dict[str, Any]:
        try:
            from app.models.career import StudentAbilityScore

            ability_scores = self.db.query(StudentAbilityScore).filter(
                StudentAbilityScore.student_id == student_id
            ).all()

            if ability_scores:
                return {
                    "scores": {
                        "专业能力": ability_scores[0].technical_score if hasattr(ability_scores[0], 'technical_score') else 70,
                        "项目经验": ability_scores[0].project_score if hasattr(ability_scores[0], 'project_score') else 65,
                        "学习能力": ability_scores[0].learning_score if hasattr(ability_scores[0], 'learning_score') else 75,
                        "沟通能力": ability_scores[0].communication_score if hasattr(ability_scores[0], 'communication_score') else 70,
                        "创新能力": ability_scores[0].innovation_score if hasattr(ability_scores[0], 'innovation_score') else 60,
                        "执行力": ability_scores[0].execution_score if hasattr(ability_scores[0], 'execution_score') else 75,
                    },
                    "total_score": sum(
                        getattr(s, 'total_score', 70) for s in ability_scores
                    ) / len(ability_scores) if ability_scores else 70,
                }

        except Exception:
            pass

        return {
            "scores": {
                "专业能力": 70,
                "项目经验": 65,
                "学习能力": 75,
                "沟通能力": 70,
                "创新能力": 60,
                "执行力": 75,
            },
            "total_score": 69.2,
        }

    def _identify_strengths(self, ability_profile: dict[str, Any]) -> list[dict[str, Any]]:
        scores = ability_profile.get("scores", {})
        if not scores:
            return []

        strengths = []
        for ability, score in scores.items():
            if score >= 75:
                strength_level = "强项" if score >= 80 else "较好"
                descriptions = {
                    "专业能力": "具备扎实的专业理论基础，能够处理复杂技术问题",
                    "项目经验": "有丰富的项目实战经验，能够快速融入团队",
                    "学习能力": "学习能力强，能够快速掌握新技术",
                    "沟通能力": "沟通表达能力良好，能够清晰表达观点",
                    "创新能力": "具有创新思维，能够提出新方案",
                    "执行力": "执行力强，能够高效完成任务",
                }
                strengths.append({
                    "ability": ability,
                    "score": score,
                    "level": strength_level,
                    "description": descriptions.get(ability, f"{ability}表现良好"),
                    "leverage_suggestion": self._get_leverage_suggestion(ability),
                })

        strengths.sort(key=lambda x: x["score"], reverse=True)
        return strengths

    def _identify_weaknesses(
        self,
        ability_profile: dict[str, Any],
        target_job_id: int | None = None,
    ) -> list[dict[str, Any]]:
        scores = ability_profile.get("scores", {})
        if not scores:
            return []

        weaknesses = []
        for ability, score in scores.items():
            if score < 70:
                weakness_level = "较弱" if score >= 60 else "明显短板"
                descriptions = {
                    "专业能力": "专业能力有待提升，需要加强理论知识学习和实践",
                    "项目经验": "项目经验相对不足，需要更多实战锻炼",
                    "学习能力": "学习能力需要加强，需要更系统的学习方法",
                    "沟通能力": "沟通能力需要提升，需要更多表达机会",
                    "创新能力": "创新能力有待提高，需要培养创新思维",
                    "执行力": "执行力需要加强，需要提高时间管理能力",
                }
                weaknesses.append({
                    "ability": ability,
                    "score": score,
                    "level": weakness_level,
                    "description": descriptions.get(ability, f"{ability}需要提升"),
                    "improvement_suggestion": self._get_improvement_suggestion(ability),
                })

        if target_job_id and weaknesses:
            job_gap_skills = self._get_job_gap_skills(target_job_id)
            for weakness in weaknesses:
                weakness["related_job_skills"] = job_gap_skills.get(weakness["ability"], [])

        weaknesses.sort(key=lambda x: x["score"])
        return weaknesses

    def _get_leverage_suggestion(self, ability: str) -> str:
        suggestions = {
            "专业能力": "在面试中突出你的技术深度，准备相关项目作品展示",
            "项目经验": "详细梳理项目经验，准备项目经历的深入讲解",
            "学习能力": "展示你快速学习的案例，如自学新技术并应用",
            "沟通能力": "在团队合作中主动承担沟通协调角色",
            "创新能力": "准备几个创新想法或优化案例，展示创新价值",
            "执行力": "强调你高效完成任务的案例，如提前交付",
        }
        return suggestions.get(ability, "继续发挥这一优势")

    def _get_improvement_suggestion(self, ability: str) -> str:
        suggestions = {
            "专业能力": "建议参加专业培训，完成相关认证，系统性提升",
            "项目经验": "建议主动参与更多项目，或自己完成side project",
            "学习能力": "建议使用费曼学习法，每周输出学习笔记",
            "沟通能力": "建议多参与团队讨论，尝试做技术分享",
            "创新能力": "建议每天记录一个创新想法，并思考可行性",
            "执行力": "建议使用番茄工作法，设置明确的deadline",
        }
        return suggestions.get(ability, "建议针对性练习提升")

    def _get_job_gap_skills(self, job_id: int) -> dict[str, list[str]]:
        try:
            from app.models.job import Job

            job = self.db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return {}

            skills_map = {
                "专业能力": ["技术深度", "架构设计", "代码质量"],
                "项目经验": ["实战项目", "团队协作", "需求分析"],
                "学习能力": ["快速学习", "知识总结", "分享传递"],
                "沟通能力": ["表达陈述", "文档撰写", "会议主持"],
                "创新能力": ["方案设计", "优化改进", "突破创新"],
                "执行力": ["时间管理", "任务分配", "结果导向"],
            }

            return skills_map

        except Exception:
            return {}

    def _build_strengths_strategy(
        self,
        strengths: list[dict[str, Any]],
        student_profile: dict[str, Any],
    ) -> dict[str, Any]:
        if not strengths:
            return {"message": "暂无明显优势，建议先提升基础能力"}

        strategy = {
            "overview": f"你的主要优势是{', '.join([s['ability'] for s in strengths[:3]])}，建议在求职中重点突出这些能力。",
            "key_strengths": strengths[:3],
            "job_recommendations": [],
            "interview_tips": [],
        }

        for strength in strengths[:3]:
            ability = strength["ability"]
            tips = {
                "专业能力": ["准备技术深度问答", "展示代码作品集", "讲解技术选型思路"],
                "项目经验": ["用STAR法则描述项目", "突出个人贡献", "准备项目演示"],
                "学习能力": ["展示自学路线图", "准备学习总结笔记", "分享学习方法"],
                "沟通能力": ["准备自我介绍", "练习结构化表达", "模拟面试演练"],
                "创新能力": ["准备创新案例", "展示优化成果", "提出新想法"],
                "执行力": ["展示高效率案例", "说明任务管理方法", "突出成果导向"],
            }
            strategy["interview_tips"].extend(tips.get(ability, []))

        strategy["interview_tips"] = list(dict.fromkeys(strategy["interview_tips"]))

        return strategy

    def _build_weaknesses_strategy(
        self,
        weaknesses: list[dict[str, Any]],
        student_profile: dict[str, Any],
    ) -> dict[str, Any]:
        if not weaknesses:
            return {"message": "你的能力结构比较均衡，继续保持"}

        strategy = {
            "overview": f"建议重点提升{', '.join([w['ability'] for w in weaknesses[:2]])}，以下是具体提升方案。",
            "key_weaknesses": weaknesses[:3],
            "improvement_plans": [],
            "alternative_approaches": [],
        }

        for weakness in weaknesses[:3]:
            ability = weakness["ability"]
            plans = {
                "专业能力": ["参加在线课程", "完成认证考试", "阅读专业书籍", "参与开源项目"],
                "项目经验": ["主动承接项目", "完成个人项目", "参与实习", "参加竞赛"],
                "学习能力": ["费曼学习法", "每周复盘", "知识体系构建", "输出博客"],
                "沟通能力": ["技术分享", "团队讨论", "演讲练习", "写作锻炼"],
                "创新能力": ["每日创新", "方案评审参与", "跨领域学习", "设计思维训练"],
                "执行力": ["番茄工作法", "GTD时间管理", "优先级矩阵", "习惯养成"],
            }
            strategy["improvement_plans"].append({
                "ability": ability,
                "current_score": weakness["score"],
                "target_score": 70,
                "actions": plans.get(ability, ["针对性练习"]),
                "timeline": "1-3个月",
            })

        strategy["alternative_approaches"] = [
            {"ability": "专业能力", "alternative": "通过认证证书证明能力", "proof": "AWS认证、PMP等"},
            {"ability": "项目经验", "alternative": "用高质量的个人项目弥补", "proof": "GitHub作品集"},
            {"ability": "沟通能力", "alternative": "用书面表达能力弥补", "proof": "技术博客、文档"},
        ]

        return strategy

    def _generate_avoid_suggestions(
        self,
        weaknesses: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not weaknesses:
            return {"message": "暂无明显需要规避的方向"}

        suggestions = {
            "job_types_to_avoid": [],
            "company_cultures_to_note": [],
            "risk_warnings": [],
        }

        weak_abilities = [w["ability"] for w in weaknesses]

        if "沟通能力" in weak_abilities:
            suggestions["company_cultures_to_note"].append("避免选择强调频繁公开演讲的岗位")

        if "执行力" in weak_abilities:
            suggestions["job_types_to_avoid"].append("高压deadline型岗位")

        if "创新能力" in weak_abilities:
            suggestions["job_types_to_avoid"].append("需要持续创新的研究型岗位")

        for ability in weak_abilities:
            warnings = {
                "专业能力": "避免面试中深入讨论技术细节，以免暴露不足",
                "项目经验": "避免被问及项目中的具体困难和个人贡献",
                "学习能力": "避免被问及学习方法论",
                "沟通能力": "避免需要大量对外沟通的岗位",
                "创新能力": "避免创新要求极高的创业公司",
                "执行力": "避免多任务并发的高压环境",
            }
            if ability in warnings:
                suggestions["risk_warnings"].append(warnings[ability])

        return suggestions

    def _recommend_jobs_by_strengths(
        self,
        strengths: list[dict[str, Any]],
        target_job_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if not strengths:
            return []

        try:
            from app.models.job import Job

            strength_abilities = [s["ability"] for s in strengths]

            query = self.db.query(Job).filter(Job.deleted.is_(False))

            if target_job_id:
                query = query.filter(Job.id != target_job_id)

            jobs = query.limit(10).all()

            recommendations = []
            for job in jobs:
                match_score = 70
                match_reasons = []

                for ability in strength_abilities[:2]:
                    if ability == "专业能力" and any(kw in job.name for kw in ["工程师", "开发", "技术"]):
                        match_score += 10
                        match_reasons.append("专业技术岗位匹配")
                    elif ability == "沟通能力" and any(kw in job.name for kw in ["产品", "运营", "经理"]):
                        match_score += 10
                        match_reasons.append("沟通能力需求高")
                    elif ability == "创新能力" and any(kw in job.name for kw in ["设计", "策划", "创新"]):
                        match_score += 10
                        match_reasons.append("创新要求岗位")

                recommendations.append({
                    "job_id": job.id,
                    "job_name": job.name,
                    "category": job.category,
                    "match_score": min(100, match_score),
                    "match_reasons": match_reasons if match_reasons else ["综合能力匹配"],
                    "highlight": strengths[0]["ability"] if strengths else "综合能力",
                })

            recommendations.sort(key=lambda x: x["match_score"], reverse=True)
            return recommendations[:5]

        except Exception:
            return []

    def _generate_report(
        self,
        student_id: int,
        strengths: list[dict[str, Any]],
        weaknesses: list[dict[str, Any]],
        strengths_strategy: dict[str, Any],
        weaknesses_strategy: dict[str, Any],
    ) -> dict[str, str]:
        student_name = ""
        try:
            from app.models.student import Student
            student = self.db.query(Student).filter(Student.id == student_id).first()
            if student:
                student_name = student.real_name or ""
        except Exception:
            pass

        report_sections = []

        report_sections.append(f"# {student_name}个性化职业发展报告\n")
        report_sections.append(f"生成时间: {datetime.now().strftime('%Y年%m月%d日')}\n")

        report_sections.append("## 一、优势分析\n")
        if strengths:
            for s in strengths[:3]:
                report_sections.append(f"### {s['ability']} ({s['score']}分)\n")
                report_sections.append(f"{s['description']}\n")
                report_sections.append(f"**利用建议**: {s['leverage_suggestion']}\n")
        else:
            report_sections.append("暂无明显优势，建议全面提升基础能力。\n")

        report_sections.append("## 二、短板分析\n")
        if weaknesses:
            for w in weaknesses[:3]:
                report_sections.append(f"### {w['ability']} ({w['score']}分)\n")
                report_sections.append(f"{w['description']}\n")
                report_sections.append(f"**提升建议**: {w['improvement_suggestion']}\n")
        else:
            report_sections.append("能力结构均衡，继续保持。\n")

        report_sections.append("## 三、发展策略\n")
        report_sections.append("### 优势利用策略\n")
        report_sections.append(f"{strengths_strategy.get('overview', '')}\n")
        if strengths_strategy.get("interview_tips"):
            report_sections.append("**面试技巧**:\n")
            for tip in strengths_strategy["interview_tips"][:5]:
                report_sections.append(f"- {tip}\n")

        report_sections.append("\n### 短板提升策略\n")
        report_sections.append(f"{weaknesses_strategy.get('overview', '')}\n")
        if weaknesses_strategy.get("improvement_plans"):
            for plan in weaknesses_strategy["improvement_plans"][:2]:
                report_sections.append(f"\n#### {plan['ability']}提升计划\n")
                report_sections.append(f"目标分数: {plan['target_score']}分\n")
                report_sections.append(f"时间周期: {plan['timeline']}\n")
                report_sections.append("具体行动:\n")
                for action in plan["actions"][:3]:
                    report_sections.append(f"- {action}\n")

        report_sections.append("\n## 四、求职建议\n")
        if strengths and weaknesses:
            report_sections.append("1. **简历优化**: 重点突出您的优势能力，如专业能力和项目经验\n")
            report_sections.append("2. **岗位选择**: 优先匹配您的优势领域，如技术开发类岗位\n")
            report_sections.append("3. **面试准备**: 扬长避短，展示优势同时准备改进短板的计划\n")
            report_sections.append("4. **持续发展**: 入职后继续保持学习，快速弥补能力短板\n")

        full_report = "\n".join(report_sections)

        return {
            "title": f"{student_name}个性化职业发展报告",
            "content": full_report,
            "summary": f"优势: {', '.join([s['ability'] for s in strengths[:2]]) if strengths else '暂无'} | "
                      f"短板: {', '.join([w['ability'] for w in weaknesses[:2]]) if weaknesses else '暂无'}",
        }


def get_personalized_plan_service(db: Session) -> PersonalizedPlanService:
    return PersonalizedPlanService(db)
