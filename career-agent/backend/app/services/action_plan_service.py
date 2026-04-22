from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session


class ActionPlanService:
    TIMELINE_DAYS = {
        "1 month": 30,
        "3 months": 90,
        "6 months": 180,
        "12 months": 365,
    }

    def __init__(self, db: Session):
        self.db = db

    def generate_plan(
        self,
        student_id: int,
        target_job_id: int,
        timeline: str = "3 months",
    ) -> dict[str, Any]:
        days = self.TIMELINE_DAYS.get(timeline, 90)

        from app.services.job_capability_decomposer_service import get_job_capability_decomposer_service
        decomposer = get_job_capability_decomposer_service(self.db)

        job_capabilities = decomposer.decompose(target_job_id)
        if "error" in job_capabilities:
            return job_capabilities

        gap_analysis = decomposer.calculate_capability_gap(target_job_id, [])

        daily_plans = self._generate_daily_plans(gap_analysis, days)
        weekly_plans = self._generate_weekly_plans(gap_analysis, days)
        monthly_plans = self._generate_monthly_plans(gap_analysis, days)
        resources = self._generate_resource_recommendations(gap_analysis)
        milestones = self._generate_milestones(gap_analysis, days)
        checkpoints = self._generate_checkpoints(days)

        return {
            "student_id": student_id,
            "target_job_id": target_job_id,
            "target_job_name": job_capabilities.get("job_name"),
            "timeline": timeline,
            "days": days,
            "daily_plans": daily_plans,
            "weekly_plans": weekly_plans,
            "monthly_plans": monthly_plans,
            "resources": resources,
            "milestones": milestones,
            "checkpoints": checkpoints,
            "generated_at": datetime.now().isoformat(),
        }

    def _generate_daily_plans(
        self,
        gap_analysis: dict[str, Any],
        total_days: int,
    ) -> list[dict[str, Any]]:
        gap_skills = gap_analysis.get("gap_skills", [])
        if not gap_skills:
            return []

        daily_tasks = []
        tasks_per_skill = max(1, min(3, len(gap_skills)))

        for i, skill in enumerate(gap_skills[:tasks_per_skill * 7]):
            day_num = i // tasks_per_skill + 1
            task_type = i % 3

            task_templates = [
                f"学习{skill}基础知识，完成官方文档的快速入门教程",
                f"完成{skill}的实战练习题或小项目",
                f"复习{skill}当天学习内容，整理笔记和代码示例",
            ]

            daily_tasks.append({
                "day": day_num,
                "date": (datetime.now() + timedelta(days=day_num - 1)).strftime("%Y-%m-%d"),
                "skill": skill,
                "tasks": [task_templates[task_type]],
                "duration_minutes": 60 + (task_type * 30),
                "status": "pending",
            })

        return daily_tasks[:min(30, total_days)]

    def _generate_weekly_plans(
        self,
        gap_analysis: dict[str, Any],
        total_days: int,
    ) -> list[dict[str, Any]]:
        gap_skills = gap_analysis.get("gap_skills", [])
        if not gap_skills:
            return []

        weeks = min(12, total_days // 7)
        weekly_plans = []

        for week in range(weeks):
            skills_this_week = gap_skills[week % len(gap_skills)] if gap_skills else "通用技能"

            weekly_plans.append({
                "week": week + 1,
                "date_range": self._get_week_date_range(week),
                "focus_skill": skills_this_week,
                "goals": [
                    f"掌握{skills_this_week}的核心概念",
                    f"完成{skills_this_week}的实战项目",
                ],
                "milestone": f"能够独立完成{skills_this_week}相关任务" if week % 2 == 0 else None,
                "review_points": [
                    "本周学习内容是否掌握",
                    "项目实践是否完成",
                    "遇到的问题是否解决",
                ],
            })

        return weekly_plans

    def _generate_monthly_plans(
        self,
        gap_analysis: dict[str, Any],
        total_days: int,
    ) -> list[dict[str, Any]]:
        gap_skills = gap_analysis.get("gap_skills", [])
        months = min(12, total_days // 30)
        monthly_plans = []

        for month in range(months):
            skills_this_month = gap_skills[(month * 2) % len(gap_skills)] if gap_skills else "综合技能"

            monthly_plans.append({
                "month": month + 1,
                "date_range": self._get_month_date_range(month),
                "focus_skill": skills_this_month,
                "primary_goals": [
                    f"系统学习{skills_this_month}的理论知识",
                    f"完成{skills_this_month}的进阶项目",
                    f"整理{skills_this_month}的知识体系",
                ],
                "certification_plan": self._get_certification_plan(skills_this_month, month),
                "interview_prep": "开始准备面试题" if month == months - 1 else None,
            })

        return monthly_plans

    def _generate_resource_recommendations(
        self,
        gap_analysis: dict[str, Any],
    ) -> dict[str, list[dict[str, Any]]]:
        gap_skills = gap_analysis.get("gap_skills", [])

        resources = {
            "courses": [],
            "books": [],
            "projects": [],
            "communities": [],
        }

        skill_resources = {
            "Python": {
                "courses": [{"name": "Python核心编程", "platform": "慕课网", "level": "入门"}, {"name": "Python高级编程", "platform": "极客时间", "level": "进阶"}],
                "books": [{"name": "Python编程从入门到实践", "author": "Eric Matthes"}, {"name": "流畅的Python", "author": "Luciano Ramalho"}],
                "projects": [{"name": "爬虫项目", "description": "实现一个完整的爬虫系统"}, {"name": "数据分析项目", "description": "使用Pandas进行数据分析"}],
            },
            "Java": {
                "courses": [{"name": "Java核心技术", "platform": "网易云课堂", "level": "入门"}, {"name": "Spring Boot实战", "platform": "极客时间", "level": "进阶"}],
                "books": [{"name": "Effective Java", "author": "Joshua Bloch"}, {"name": "深入理解Java虚拟机", "author": "周志华"}],
                "projects": [{"name": "电商后台系统", "description": "使用Spring Boot开发"}, {"name": "RESTful API开发", "description": "实现标准REST服务"}],
            },
            "JavaScript": {
                "courses": [{"name": "JavaScript高级程序设计", "platform": "慕课网", "level": "入门"}, {"name": "Vue/React框架", "platform": "Bilibili", "level": "进阶"}],
                "books": [{"name": "JavaScript高级程序设计", "author": "Nicholas C. Zakas"}, {"name": "你不知道的JavaScript", "author": "Kyle Simpson"}],
                "projects": [{"name": "Todo List应用", "description": "前端框架实战"}, {"name": "即时通讯应用", "description": "WebSocket实战"}],
            },
        }

        for skill in gap_skills[:3]:
            if skill in skill_resources:
                res = skill_resources[skill]
                resources["courses"].extend(res.get("courses", []))
                resources["books"].extend(res.get("books", []))
                resources["projects"].extend(res.get("projects", []))
            else:
                resources["courses"].append({"name": f"{skill}入门课程", "platform": "B站/慕课网", "level": "入门"})
                resources["books"].append({"name": f"{skill}权威指南", "author": "待定"})

        resources["communities"] = [
            {"name": "GitHub", "description": "开源项目和代码学习"},
            {"name": "Stack Overflow", "description": "技术问答社区"},
            {"name": "掘金", "description": "国内技术文章平台"},
            {"name": "知乎", "description": "技术话题讨论"},
        ]

        return resources

    def _generate_milestones(
        self,
        gap_analysis: dict[str, Any],
        total_days: int,
    ) -> list[dict[str, Any]]:
        months = min(12, total_days // 30)
        gap_skills = gap_analysis.get("gap_skills", [])

        milestones = []
        milestone_types = ["基础掌握", "项目实战", "综合提升", "面试准备"]

        for i, month in enumerate(range(1, months + 1)):
            milestones.append({
                "id": i + 1,
                "month": month,
                "date": (datetime.now() + timedelta(days=month * 30)).strftime("%Y-%m-%d"),
                "title": f"{month}个月里程碑",
                "type": milestone_types[i % len(milestone_types)],
                "description": self._get_milestone_description(month, gap_skills, gap_analysis),
                "deliverables": [
                    "完成阶段性学习报告",
                    "输出实战项目作品",
                    "通过自我测评",
                ],
                "status": "pending",
            })

        return milestones

    def _generate_checkpoints(self, total_days: int) -> list[dict[str, Any]]:
        checkpoints = []

        interval = max(7, total_days // 10)
        for i in range(0, total_days, interval):
            checkpoints.append({
                "day": i + 1,
                "date": (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d"),
                "title": f"第{i // 7 + 1}周复盘",
                "check_items": [
                    "本周学习计划是否完成",
                    "遇到的问题是否解决",
                    "下周计划是否制定",
                ],
                "status": "pending",
            })

        return checkpoints

    def _get_week_date_range(self, week: int) -> str:
        start = datetime.now() + timedelta(days=week * 7)
        end = start + timedelta(days=6)
        return f"{start.strftime('%m-%d')} ~ {end.strftime('%m-%d')}"

    def _get_month_date_range(self, month: int) -> str:
        start = datetime.now() + timedelta(days=month * 30)
        end = start + timedelta(days=29)
        return f"{start.strftime('%Y-%m')} 月"

    def _get_certification_plan(self, skill: str, month: int) -> dict[str, Any] | None:
        cert_map = {
            "Python": {"name": "Python程序员认证", "provider": "Python Software Foundation"},
            "Java": {"name": "Oracle Java认证", "provider": "Oracle"},
            "AWS": {"name": "AWS认证", "provider": "Amazon"},
        }

        if skill in cert_map and month < 6:
            return {
                **cert_map[skill],
                "target_month": month + 3,
                "study_weeks": 8,
            }

        return None

    def _get_milestone_description(
        self,
        month: int,
        gap_skills: list[str],
        gap_analysis: dict[str, Any],
    ) -> str:
        skill = gap_skills[(month - 1) % len(gap_skills)] if gap_skills else "核心技能"

        descriptions = {
            1: f"完成{skill}的基础知识学习，能够进行简单开发",
            2: f"掌握{skill}的进阶内容，完成实战项目",
            3: f"深入理解{skill}的高级特性，能够解决复杂问题",
            4: f"完成{skill}的综合项目实战，准备面试",
            5: f"对{skill}知识体系进行全面复盘",
            6: f"开始{skill}相关的面试准备和模拟面试",
        }

        return descriptions.get(month, f"完成{month}个月学习目标")

    def update_progress(
        self,
        plan_id: int,
        task_id: str,
        completed: bool,
        notes: str | None = None,
    ) -> dict[str, Any]:
        try:
            from app.models.career import ActionPlanProgress

            progress = ActionPlanProgress(
                plan_id=plan_id,
                task_id=task_id,
                completed=completed,
                completed_at=datetime.now() if completed else None,
                notes=notes,
            )

            self.db.add(progress)
            self.db.commit()

            return {
                "success": True,
                "task_id": task_id,
                "completed": completed,
                "completed_at": progress.completed_at.isoformat() if progress.completed_at else None,
            }

        except Exception as e:
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def get_progress_stats(self, plan_id: int) -> dict[str, Any]:
        try:
            from app.models.career import ActionPlanProgress

            all_progress = self.db.query(ActionPlanProgress).filter(
                ActionPlanProgress.plan_id == plan_id
            ).all()

            if not all_progress:
                return {"total_tasks": 0, "completed": 0, "pending": 0, "completion_rate": 0}

            total = len(all_progress)
            completed = len([p for p in all_progress if p.completed])

            return {
                "total_tasks": total,
                "completed": completed,
                "pending": total - completed,
                "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
            }

        except Exception:
            return {"total_tasks": 0, "completed": 0, "pending": 0, "completion_rate": 0}


def get_action_plan_service(db: Session) -> ActionPlanService:
    return ActionPlanService(db)
