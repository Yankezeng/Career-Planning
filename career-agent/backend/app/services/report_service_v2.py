from __future__ import annotations

from pathlib import Path

from fastapi.encoders import jsonable_encoder
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.career import Report, ReportVersion
from app.models.job import Job, JobMatchGap, JobMatchResult
from app.models.student import Student
from app.services.graph.career_path_neo4j import CareerPathService
from app.services.job_match_service import JobMatchService
from app.services.pdf_export_service import PdfExportService
from app.services.student_profile_service import StudentProfileService
from app.services.structured_llm_service import get_structured_llm_service
from app.utils.serializers import to_dict


REQUIRED_REPORT_SECTIONS = [
    "exploration_match",
    "goal_and_path",
    "action_plan",
    "industry_trend",
    "edit_export",
]


class ReportService:
    def __init__(self, db: Session):
        self.db = db
        template_dir = Path(__file__).resolve().parents[1] / "templates"
        self.jinja = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=select_autoescape())
        self.llm_service = get_structured_llm_service()
        self.profile_service = StudentProfileService(db)
        self.match_service = JobMatchService(db)
        self.path_service = CareerPathService(db)
        self.pdf_service = PdfExportService()

    def generate_report(self, student_id: int, target_job_id: int | None = None):
        student = self._get_student(student_id)
        profile = self.profile_service.get_latest_profile(student_id) or self.profile_service.generate_profile(student_id)
        matches = self.match_service.get_matches(student_id) or self.match_service.generate_matches(student_id)
        selected_match = self._select_match(matches, target_job_id)
        selected_match = self.match_service.get_match(student_id, selected_match["job_id"]) or selected_match
        career_path = self.path_service.generate_path(student_id, selected_match["job_id"])
        trend = self._build_industry_trend(selected_match["job_id"])
        summary = self.llm_service.generate_report_summary(
            {
                "student_name": student.name,
                "top_job_name": selected_match["job"]["name"],
                "total_score": selected_match["total_score"],
                "industry_trend": trend,
            }
        )
        content = self._build_report_content(student, profile, selected_match, matches, career_path, summary, trend)

        report = Report(
            student_id=student_id,
            career_path_id=career_path.get("id") if career_path else None,
            match_result_id=selected_match.get("id"),
            title=f"{student.name}职业规划报告",
            summary=summary["summary"],
            content_json=jsonable_encoder(content),
            content_html=self._render_html(content),
        )
        self.db.add(report)
        self.db.flush()
        self._save_version(report, "generate")
        report.pdf_path = self.pdf_service.export(report.id, report.title, self._build_pdf_sections(content))
        self.db.commit()
        self.db.refresh(report)
        return self.serialize_report(report)

    def get_latest_report(self, student_id: int):
        report = (
            self.db.query(Report)
            .filter(Report.student_id == student_id, Report.deleted.is_(False))
            .order_by(Report.id.desc())
            .first()
        )
        return self.serialize_report(report) if report else None

    def get_report(self, report_id: int):
        report = self.db.query(Report).filter(Report.id == report_id, Report.deleted.is_(False)).first()
        if not report:
            raise ValueError("报告不存在")
        return report

    def update_report(self, report_id: int, payload: dict):
        report = self.get_report(report_id)
        content = dict(report.content_json or {})
        if payload.get("title"):
            report.title = payload["title"]
        if payload.get("summary"):
            report.summary = payload["summary"]
            content["summary"] = payload["summary"]
        if payload.get("sections"):
            content["sections"] = [dict(item) for item in payload["sections"]]
        report.content_json = jsonable_encoder(content)
        report.content_html = self._render_html(content)
        report.pdf_path = self.pdf_service.export(report.id, report.title, self._build_pdf_sections(content))
        self._save_version(report, "update")
        self.db.commit()
        self.db.refresh(report)
        return self.serialize_report(report)

    def polish_report(self, report_id: int):
        report = self.get_report(report_id)
        content = dict(report.content_json or {})
        polished_sections = []
        for section in content.get("sections", []):
            polished_sections.append(
                {
                    **section,
                    "content": self.llm_service.polish_report_section(section.get("title", "报告章节"), section.get("content", "")),
                }
            )
        content["sections"] = polished_sections
        report.summary = self.llm_service.polish_report_summary(content.get("summary", report.summary or ""))
        content["summary"] = report.summary
        report.content_json = jsonable_encoder(content)
        report.content_html = self._render_html(content)
        report.pdf_path = self.pdf_service.export(report.id, report.title, self._build_pdf_sections(content))
        self._save_version(report, "polish")
        self.db.commit()
        self.db.refresh(report)
        return self.serialize_report(report)

    def check_report(self, report_id: int):
        report = self.get_report(report_id)
        content = report.content_json or {}
        sections = {item.get("key"): item for item in content.get("sections", [])}
        items = []
        for key in REQUIRED_REPORT_SECTIONS:
            section = sections.get(key, {})
            section_text = str(section.get("content") or "").strip()
            passed = len(section_text) >= 30
            items.append(
                {
                    "key": key,
                    "label": section.get("title") or key,
                    "passed": passed,
                    "message": "内容完整" if passed else "内容不足，需补充可执行描述",
                }
            )
        top_jobs = content.get("top_jobs") or []
        tasks = (content.get("career_path") or {}).get("tasks") or []
        trend = content.get("industry_trend") or {}
        items.append({"key": "top_jobs", "label": "岗位匹配结果", "passed": len(top_jobs) >= 3, "message": "已包含岗位匹配结果" if len(top_jobs) >= 3 else "至少保留3个匹配岗位"})
        items.append({"key": "action_tasks", "label": "行动计划", "passed": len(tasks) >= 3, "message": "已包含阶段任务" if len(tasks) >= 3 else "至少保留3个阶段任务"})
        trend_passed = bool(trend.get("industry_demand") and trend.get("job_heat") and trend.get("skill_gap_trend"))
        items.append({"key": "trend", "label": "行业趋势与社会需求", "passed": trend_passed, "message": "趋势数据完整" if trend_passed else "缺少行业需求/岗位热度/能力缺口趋势"})
        passed_count = sum(1 for item in items if item["passed"])
        score = round((passed_count / len(items)) * 100, 1) if items else 0
        return {"report_id": report.id, "passed": all(item["passed"] for item in items), "score": score, "items": items}

    def ensure_export_ready(self, report_id: int):
        check_result = self.check_report(report_id)
        if not check_result["passed"]:
            raise ValueError("报告完整性检查未通过，不能导出")
        return check_result

    def list_versions(self, report_id: int):
        versions = (
            self.db.query(ReportVersion)
            .filter(ReportVersion.report_id == report_id, ReportVersion.deleted.is_(False))
            .order_by(ReportVersion.version_no.desc())
            .all()
        )
        return [to_dict(item) for item in versions]

    def restore_version(self, report_id: int, version_no: int):
        report = self.get_report(report_id)
        version = (
            self.db.query(ReportVersion)
            .filter(ReportVersion.report_id == report_id, ReportVersion.version_no == version_no, ReportVersion.deleted.is_(False))
            .first()
        )
        if not version:
            raise ValueError("报告版本不存在")
        report.title = version.title
        report.summary = version.summary
        report.content_json = jsonable_encoder(version.content_json or {})
        report.content_html = self._render_html(report.content_json or {})
        report.pdf_path = self.pdf_service.export(report.id, report.title, self._build_pdf_sections(report.content_json or {}))
        self._save_version(report, f"restore_v{version_no}")
        self.db.commit()
        self.db.refresh(report)
        return self.serialize_report(report)

    def serialize_report(self, report: Report):
        data = to_dict(report)
        data["check_result"] = self.check_report(report.id)
        data["versions"] = self.list_versions(report.id)[:20]
        data["export_ready"] = data["check_result"]["passed"]
        return data

    def _get_student(self, student_id: int):
        student = self.db.query(Student).filter(Student.id == student_id, Student.deleted.is_(False)).first()
        if not student:
            raise ValueError("学生不存在")
        return student

    @staticmethod
    def _select_match(matches: list[dict], target_job_id: int | None):
        if not matches:
            raise ValueError("当前没有可用的人岗匹配结果")
        if target_job_id:
            selected = next((item for item in matches if item["job_id"] == target_job_id), None)
            if selected:
                return selected
        return matches[0]

    def _build_report_content(
        self,
        student: Student,
        profile: dict,
        selected_match: dict,
        matches: list[dict],
        career_path: dict,
        summary: dict,
        trend: dict,
    ) -> dict:
        profile_dimensions = (profile.get("raw_metrics") or {}).get("dimension_scores") or []
        sections = [
            {
                "key": "exploration_match",
                "title": "一、职业探索与岗位匹配",
                "content": f"目标岗位为{selected_match['job']['name']}，综合匹配度{selected_match['total_score']}分，匹配依据覆盖基础要求、职业技能、职业素养、发展潜力四维度。",
                "highlights": [f"{item['label']} {item['score']}分" for item in selected_match.get("dimension_scores", [])],
            },
            {
                "key": "goal_and_path",
                "title": "二、职业目标设定与职业路径规划",
                "content": f"结合岗位匹配与个人画像，建议以{selected_match['job']['name']}为主线推进，并沿垂直晋升路径持续积累岗位证据。",
                "highlights": [f"{item.get('level')}：{item.get('job_name')}" for item in career_path.get("vertical_path", [])],
            },
            {
                "key": "action_plan",
                "title": "三、行动计划与成果展示",
                "content": "已生成短期与中期行动任务，建议按双周检查、月度复盘节奏推进，并持续沉淀项目和实习成果。",
                "highlights": [f"[{task.get('stage_label')}] {task.get('title')}" for task in career_path.get("tasks", [])[:8]],
            },
            {
                "key": "industry_trend",
                "title": "四、行业趋势与社会需求",
                "content": trend.get("summary", ""),
                "highlights": [
                    f"行业需求指数：{trend.get('industry_demand', {}).get('demand_index', 0)}",
                    *[f"岗位热度：{item['job_name']}({item['value']})" for item in trend.get("job_heat", [])[:3]],
                ],
            },
            {
                "key": "edit_export",
                "title": "五、编辑优化与导出",
                "content": "报告支持编辑、润色、完整性检查、版本回溯与导出前检查，确保输出内容可直接交付。",
                "highlights": ["支持报告编辑器", "支持版本保存", "支持智能润色", "支持导出前检查"],
            },
        ]
        return {
            "title": f"{student.name}职业规划报告",
            "summary": summary["summary"],
            "summary_highlights": summary.get("highlights", []),
            "student": to_dict(student),
            "profile": profile,
            "profile_dimensions": profile_dimensions,
            "top_jobs": matches[:5],
            "selected_match": selected_match,
            "career_path": career_path,
            "industry_trend": trend,
            "sections": sections,
        }

    def _build_industry_trend(self, job_id: int) -> dict:
        job = self.db.query(Job).filter(Job.id == job_id, Job.deleted.is_(False)).first()
        if not job:
            return {"summary": "未获取到岗位趋势数据。", "industry_demand": {}, "job_heat": [], "skill_gap_trend": []}

        industry_job_count = self.db.query(Job).filter(Job.deleted.is_(False), Job.industry == job.industry).count()
        category_job_count = self.db.query(Job).filter(Job.deleted.is_(False), Job.category == job.category).count()
        demand_index = round(min(100.0, industry_job_count * 4 + category_job_count * 6), 1)

        heat_rows = (
            self.db.query(Job.name, func.count(JobMatchResult.id))
            .join(JobMatchResult, JobMatchResult.job_id == Job.id)
            .filter(Job.deleted.is_(False), JobMatchResult.deleted.is_(False))
            .group_by(Job.name)
            .order_by(func.count(JobMatchResult.id).desc())
            .limit(8)
            .all()
        )
        gap_rows = (
            self.db.query(JobMatchGap.gap_item, func.count(JobMatchGap.id))
            .join(JobMatchResult, JobMatchResult.id == JobMatchGap.match_result_id)
            .filter(JobMatchGap.deleted.is_(False), JobMatchResult.deleted.is_(False))
            .group_by(JobMatchGap.gap_item)
            .order_by(func.count(JobMatchGap.id).desc())
            .limit(8)
            .all()
        )
        return {
            "summary": f"当前行业需求指数 {demand_index}，同产业岗位 {industry_job_count} 个，同类别岗位 {category_job_count} 个，建议围绕高热岗位能力缺口优先补齐。",
            "industry_demand": {"industry": job.industry, "category": job.category, "industry_job_count": industry_job_count, "category_job_count": category_job_count, "demand_index": demand_index},
            "job_heat": [{"job_name": name, "value": int(count)} for name, count in heat_rows],
            "skill_gap_trend": [{"gap_item": item, "value": int(count)} for item, count in gap_rows],
        }

    def _save_version(self, report: Report, action: str):
        next_version = (
            (self.db.query(func.max(ReportVersion.version_no)).filter(ReportVersion.report_id == report.id).scalar() or 0)
            + 1
        )
        self.db.add(
            ReportVersion(
                report_id=report.id,
                version_no=next_version,
                action=action,
                title=report.title,
                summary=report.summary,
                content_json=jsonable_encoder(report.content_json or {}),
                check_result=self.check_report(report.id),
            )
        )

    def _render_html(self, content: dict) -> str:
        return self.jinja.get_template("report_template.html").render(report=content)

    @staticmethod
    def _build_pdf_sections(content: dict):
        student = content.get("student") or {}
        selected_match = content.get("selected_match") or {}
        career_path = content.get("career_path") or {}
        trend = content.get("industry_trend") or {}
        return [
            f"一、学生基础档案\n姓名：{student.get('name', '-')}; 专业：{student.get('major', '-')}; 目标行业：{student.get('target_industry', '-')}",
            "二、学生就业能力画像\n" + "；".join([f"{item['label']} {item['score']}分" for item in content.get("profile_dimensions", [])]),
            "三、职业探索与岗位匹配\n"
            + f"目标岗位：{(selected_match.get('job') or {}).get('name', '-')}; 综合匹配：{selected_match.get('total_score', 0)}分",
            "四、职业路径规划\n" + "；".join([f"{item.get('level')} {item.get('job_name')}" for item in career_path.get("vertical_path", [])]),
            "五、行业趋势与社会需求\n"
            + f"需求指数：{(trend.get('industry_demand') or {}).get('demand_index', 0)}; "
            + "；".join([f"{item['job_name']}({item['value']})" for item in trend.get("job_heat", [])[:5]]),
            "六、综合建议\n" + str(content.get("summary") or ""),
        ]


from app.services.report_service_v2_clean import ReportService  # noqa: E402,F401
