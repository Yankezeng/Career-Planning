from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models.auth import Role, User
from app.models.career import Report, ResumeDelivery
from app.models.job import JobMatchResult
from app.models.student import Student, StudentAttachment
from app.services.resume_delivery_service import ResumeDeliveryService
from app.services.resume_optimizer_service import ResumeOptimizerService
from app.services.resume_parser_service import ResumeParserService
from app.services.resume_profile_pipeline_service import ResumeProfilePipelineService
from app.services.vector_search_service import VectorSearchService
from app.utils.upload_paths import resolve_upload_reference

try:
    from app.services.job_match_service_clean import JobMatchService
except Exception:  # pragma: no cover - optional graph backend dependency
    class JobMatchService:
        def __init__(self, db):
            self.db = db

        def generate_matches(self, student_id: int):
            return []

        def get_matches(self, student_id: int):
            return []


try:
    from app.services.student_profile_service_clean import StudentProfileService
except Exception:  # pragma: no cover - optional dependency chain
    class StudentProfileService:
        def __init__(self, db):
            self.db = db

        def generate_profile(self, student_id: int):
            return {}

        def get_latest_profile(self, student_id: int):
            return {}


try:
    from app.services.report_service_v2_clean import ReportService
except Exception:  # pragma: no cover - optional dependency chain
    class ReportService:
        def __init__(self, db):
            self.db = db

        def generate_report(self, student_id: int, target_job_id: int | None = None):
            return {}


try:
    from app.services.review_service import ReviewService
except Exception:  # pragma: no cover - optional dependency chain
    class ReviewService:
        def __init__(self, db):
            self.db = db


try:
    from app.services.optimization_service_clean import OptimizationService
except Exception:  # pragma: no cover - optional dependency chain
    class OptimizationService:
        def __init__(self, db):
            self.db = db


try:
    from app.services.graph.career_path_neo4j import CareerPathService
except Exception:  # pragma: no cover - optional graph backend dependency
    class CareerPathService:
        def __init__(self, db):
            self.db = db

        def generate_path(self, student_id: int, target_job_id: int):
            return []


class AgentToolRegistry:
    def __init__(self, db, vector_search_service=None):
        self.db: Session = db
        self.settings = get_settings()
        self.vector_search_service = vector_search_service or VectorSearchService()
        self.resume_parser = ResumeParserService()
        self.resume_optimizer = ResumeOptimizerService(db, resume_parser=self.resume_parser)
        self.resume_pipeline = ResumeProfilePipelineService(db)
        self.profile_service = StudentProfileService(db)
        self.match_service = JobMatchService(db)
        self.path_service = CareerPathService(db)
        self.report_service = ReportService(db)
        self.delivery_service = ResumeDeliveryService(db)
        self.review_service = ReviewService(db)
        self.optimization_service = OptimizationService(db)
        from app.services.agent.image_generator_agent.image_generator_agent import ImageGeneratorAgent

        self.image_generator_agent = ImageGeneratorAgent(self)

    def run(
        self,
        tool: str,
        *,
        user,
        message: str = "",
        top_k: int = 4,
        payload: dict[str, Any] | None = None,
        target_job: str | None = None,
    ) -> dict[str, Any]:
        payload = dict(payload or {})
        if target_job and not payload.get("target_job"):
            payload["target_job"] = target_job

        alias = {
            "candidate_overview": "build_candidate_overview",
            "candidate_screening": "rank_candidates",
            "review_advice": "generate_review_advice",
            "admin_metrics": "summarize_admin_metrics",
            "admin_demo_script": "generate_demo_script",
            "resume_workbench": "parse_resume_attachment",
            "report_builder": "generate_report",
            "growth_planner": "generate_growth_path",
        }
        name = alias.get(str(tool or "").strip(), str(tool or "").strip())
        handlers = {
            "parse_resume_attachment": self._parse_resume_attachment,
            "ingest_resume_attachment": self._ingest_resume_attachment,
            "generate_profile": self._generate_profile,
            "generate_profile_image": self._generate_profile_image,
            "profile_insight": self._profile_insight,
            "profile_trend_refresh": self._profile_trend_refresh,
            "competitiveness_snapshot": self._competitiveness_snapshot,
            "generate_matches": self._generate_matches,
            "match_center": self._match_center,
            "generate_gap_analysis": self._generate_gap_analysis,
            "explainable_ranking": self._explainable_ranking,
            "feedback_weight_update": self._feedback_weight_update,
            "generate_growth_path": self._generate_growth_path,
            "growth_checkin_plan": self._growth_checkin_plan,
            "growth_stage_review": self._growth_stage_review,
            "generate_report": self._generate_report,
            "optimize_resume": self._optimize_resume,
            "prepare_delivery": self._prepare_delivery,
            "assemble_job_package": self._assemble_job_package,
            "role_onboarding": self._role_onboarding,
            "quick_entry_recommendation": self._quick_entry_recommendation,
            "progress_feedback": self._progress_feedback,
            "operation_suggestion": self._operation_suggestion,
            "build_candidate_overview": self._build_candidate_overview,
            "rank_candidates": self._rank_candidates,
            "generate_resume_review": self._generate_resume_review,
            "generate_talent_portrait": self._generate_talent_portrait,
            "generate_interview_questions": self._generate_interview_questions,
            "followup_simulation": self._followup_simulation,
            "answer_evaluation": self._answer_evaluation,
            "interview_report": self._interview_report,
            "manage_offer_pipeline": self._manage_offer_pipeline,
            "build_communication_script": self._build_communication_script,
            "generate_review_advice": self._generate_review_advice,
            "summarize_admin_metrics": self._summarize_admin_metrics,
            "summarize_ops_review": self._summarize_ops_review,
            "llm_cost_latency_scan": self._llm_cost_latency_scan,
            "knowledge_governance_scan": self._knowledge_governance_scan,
            "data_governance_scan": self._data_governance_scan,
            "build_role_overview": self._build_role_overview,
            "inspect_knowledge_governance": self._inspect_knowledge_governance,
            "inspect_data_governance": self._inspect_data_governance,
            "generate_demo_script": self._generate_demo_script,
            "demo_timeline": self._demo_timeline,
            "keypoint_annotation": self._keypoint_annotation,
            "job_kb_search": self._job_kb_search,
            "skill_graph_view": self._skill_graph_view,
            "learning_sequence": self._learning_sequence,
            "transfer_path_recommendation": self._transfer_path_recommendation,
        }
        if name not in handlers:
            return self._tool_output(name, "Unsupported Tool", f"Tool `{name}` is not supported.", {"error": "tool_not_supported"}, ["Choose another tool"])
        if name == "generate_profile_image":
            return handlers[name](user=user, message=message, top_k=top_k, payload=payload)
        try:
            return handlers[name](user=user, message=message, top_k=top_k, payload=payload)
        except Exception as exc:
            return self._tool_output(name, "Tool Error", f"{name} failed: {exc}", {"error": str(exc)}, ["Retry"])

    def build_business_snapshot(self, user):
        role = str(getattr(getattr(user, "role", None), "code", "") or "student")
        if role == "student":
            student = self._student_by_user(user.id)
            return {"role": role, "student": {"id": student.id, "name": student.name} if student else None}
        if role == "enterprise":
            rows = self.delivery_service.list_enterprise_deliveries(user.id)
            return {"role": role, "delivery_count": len(rows)}
        return self._summarize_admin_metrics(user=user).get("data", {})

    def _parse_resume_attachment(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        student = self._student_by_user(user.id)
        if not student:
            return self._tool_output("parse_resume_attachment", "Resume Parse", "Student profile was not found.", {}, ["Complete student profile first"], card_type="resume_card")
        attachment = self._latest_attachment(student.id)
        if not attachment:
            return self._tool_output("parse_resume_attachment", "Resume Parse", "No resume attachment is available.", {"attachments": []}, ["Upload resume attachment first"], card_type="resume_card")
        file_path = resolve_upload_reference(upload_root=self.settings.upload_path, reference=attachment.file_path, must_exist=True)
        if not file_path:
            return self._tool_output("parse_resume_attachment", "Resume Parse", "Resume file was not found.", {"attachments": []}, ["Upload resume attachment first"], card_type="resume_card")
        parsed = self.resume_parser.parse(attachment.file_name, str(file_path))
        if self.resume_parser.is_low_quality(parsed, attachment_chain=True):
            return self._tool_output(
                "parse_resume_attachment",
                "Resume Parse",
                "Resume parse quality is too low.",
                {"attachment": {"id": attachment.id, "file_name": attachment.file_name, "file_type": attachment.file_type}, "parsed_resume": {}},
                ["Re-upload resume", "Profile ingest"],
                card_type="resume_card",
            )
        return self._tool_output(
            "parse_resume_attachment",
            "Resume Parse",
            f"Parsed resume attachment: {attachment.file_name}.",
            {"attachment": {"id": attachment.id, "file_name": attachment.file_name, "file_type": attachment.file_type}, "parsed_resume": parsed},
            ["Profile ingest", "Profile insight"],
            card_type="resume_card",
            context_patch={"context_binding": {"resume": {"attachment_id": attachment.id, "file_name": attachment.file_name}}},
        )

    def _ingest_resume_attachment(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        student = self._student_by_user(user.id)
        if not student:
            return self._tool_output("ingest_resume_attachment", "Profile Ingest", "Student profile was not found.", {"error": "student_not_found"}, ["Complete profile"])
        attachment = self._latest_attachment(student.id)
        if not attachment:
            return self._tool_output("ingest_resume_attachment", "Profile Ingest", "No attachment available.", {"error": "attachment_not_found"}, ["Upload attachment"])
        result = self.resume_pipeline.ingest_resume(student.id, attachment.id)
        return self._tool_output("ingest_resume_attachment", "Profile Ingest", "Resume content synced.", result, ["Generate profile", "Generate matches"], card_type="profile_card")

    def _generate_profile(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        student = self._student_by_user(user.id)
        if not student:
            return self._tool_output("generate_profile", "Profile", "Student profile was not found.", {"error": "student_not_found"}, ["Complete profile"])
        profile = self.profile_service.generate_profile(student.id)
        return self._tool_output("generate_profile", "Profile", "Student profile generated.", {"profile": profile}, ["Profile insight", "Generate matches"], card_type="profile_card")

    def _generate_profile_image(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        student = self._student_by_user(user.id)
        if not student:
            return self._tool_output(
                "generate_profile_image",
                "Profile Image",
                "Student profile was not found.",
                {"error": "student_not_found"},
                ["Complete profile"],
                card_type=None,
            )
        data = self.image_generator_agent.generate_for_student(
            student_id=student.id,
            message=message,
            target_job=str((payload or {}).get("target_job") or ""),
        )
        return self._tool_output(
            "generate_profile_image",
            "Profile Image",
            data["analysis_summary"],
            data,
            [],
            card_type=None,
            context_patch={"context_binding": {"profile_image": data}},
        )

    def _profile_insight(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        student = self._student_by_user(user.id)
        if not student:
            return self._tool_output("profile_insight", "Profile Insight", "Student profile was not found.", {"error": "student_not_found"}, ["Complete profile"])
        profile = self.profile_service.get_latest_profile(student.id) or self.profile_service.generate_profile(student.id)
        return self._tool_output("profile_insight", "Profile Insight", "Latest profile insight ready.", {"profile": profile}, ["Generate matches", "Gap analysis"], card_type="profile_card")

    def _profile_trend_refresh(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        student = self._student_by_user(user.id)
        if not student:
            return self._tool_output("profile_trend_refresh", "Profile Trend", "Student profile was not found.", {"error": "student_not_found"}, ["Complete profile"])
        profile = self.profile_service.get_latest_profile(student.id) or self.profile_service.generate_profile(student.id)
        dimensions = profile.get("dimensions") if isinstance(profile, dict) and isinstance(profile.get("dimensions"), list) else []
        sorted_dims = sorted(dimensions, key=lambda item: float((item or {}).get("score") or 0), reverse=True)
        trend = {
            "strengths": sorted_dims[:3],
            "watch_items": sorted_dims[-3:] if len(sorted_dims) >= 3 else sorted_dims,
            "refresh_at": str(payload.get("refresh_at") or "now"),
        }
        return self._tool_output(
            "profile_trend_refresh",
            "Profile Trend",
            "Profile trend refresh completed.",
            {"profile": profile, "trend": trend},
            ["Competitiveness snapshot", "Generate matches"],
            card_type="profile_card",
            context_patch={"context_binding": {"profile_trend": trend}},
        )

    def _competitiveness_snapshot(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        student = self._student_by_user(user.id)
        if not student:
            return self._tool_output("competitiveness_snapshot", "Competitiveness", "Student profile was not found.", {"error": "student_not_found"}, ["Complete profile"])
        matches = self.match_service.get_matches(student.id) or self.match_service.generate_matches(student.id)
        top_matches = matches[: max(1, top_k)]
        avg_score = round(sum(float(item.get("total_score") or item.get("match_score") or 0) for item in top_matches) / max(len(top_matches), 1), 1)
        snapshot = {
            "top_matches": top_matches,
            "avg_top_score": avg_score,
            "score_band": "high" if avg_score >= 80 else "medium" if avg_score >= 60 else "low",
        }
        return self._tool_output(
            "competitiveness_snapshot",
            "Competitiveness",
            "Competitiveness snapshot is ready.",
            snapshot,
            ["Generate gap analysis", "Generate growth path"],
            card_type="match_card",
            context_patch={"context_binding": {"competitiveness_snapshot": snapshot}},
        )

    def _generate_matches(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        student = self._student_by_user(user.id)
        if not student:
            return self._tool_output("generate_matches", "Job Matches", "Student profile was not found.", {"error": "student_not_found"}, ["Complete profile"])
        matches = self.match_service.generate_matches(student.id)
        return self._tool_output("generate_matches", "Job Matches", f"Generated {len(matches)} matches.", {"matches": matches[: max(1, top_k)]}, ["Match center", "Gap analysis"], card_type="match_card")

    def _match_center(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        student = self._student_by_user(user.id)
        if not student:
            return self._tool_output("match_center", "Match Center", "Student profile was not found.", {"error": "student_not_found"}, ["Complete profile"])
        matches = self.match_service.get_matches(student.id) or self.match_service.generate_matches(student.id)
        return self._tool_output("match_center", "Match Center", "Top matches are ready.", {"matches": matches[: max(1, top_k)]}, ["Gap analysis", "Growth path"], card_type="match_card")

    def _generate_gap_analysis(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        student = self._student_by_user(user.id)
        if not student:
            return self._tool_output("generate_gap_analysis", "Gap Analysis", "Student profile was not found.", {"error": "student_not_found"}, ["Complete profile"])
        matches = self.match_service.get_matches(student.id) or self.match_service.generate_matches(student.id)
        top_match = matches[0] if matches else {}
        gaps = top_match.get("gaps") or []
        return self._tool_output("generate_gap_analysis", "Gap Analysis", f"Found {len(gaps)} key gaps.", {"top_match": top_match, "gaps": gaps[:8]}, ["Growth path", "Optimize resume"], card_type="gap_card")

    def _explainable_ranking(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        student = self._student_by_user(user.id)
        if not student:
            return self._tool_output("explainable_ranking", "Explainable Ranking", "Student profile was not found.", {"error": "student_not_found"}, ["Complete profile"])
        matches = self.match_service.get_matches(student.id) or self.match_service.generate_matches(student.id)
        ranked = sorted(matches, key=lambda item: float(item.get("total_score") or item.get("match_score") or 0), reverse=True)[: max(1, top_k)]
        explain_rows = [
            {
                "job_id": item.get("job_id"),
                "job_name": item.get("job_name"),
                "score": float(item.get("total_score") or item.get("match_score") or 0),
                "reason": item.get("reason") or "score based on profile and required skills",
            }
            for item in ranked
        ]
        return self._tool_output(
            "explainable_ranking",
            "Explainable Ranking",
            f"Built explanations for {len(explain_rows)} ranked jobs.",
            {"ranked_jobs": explain_rows},
            ["Feedback weight update", "Generate growth path"],
            card_type="match_card",
            context_patch={"context_binding": {"rank_explanations": explain_rows}},
        )

    def _feedback_weight_update(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        feedback = payload.get("feedback") if isinstance(payload, dict) and isinstance(payload.get("feedback"), dict) else {}
        current_weights = payload.get("weights") if isinstance(payload, dict) and isinstance(payload.get("weights"), dict) else {}
        merged_weights = {
            "basic_requirement": float(current_weights.get("basic_requirement") or 0.25),
            "professional_skill": float(current_weights.get("professional_skill") or 0.40),
            "professional_literacy": float(current_weights.get("professional_literacy") or 0.20),
            "development_potential": float(current_weights.get("development_potential") or 0.15),
        }
        for key in merged_weights:
            delta = float(feedback.get(key) or 0)
            merged_weights[key] = round(max(0.0, min(1.0, merged_weights[key] + delta)), 3)
        total = sum(merged_weights.values()) or 1.0
        normalized = {key: round(value / total, 3) for key, value in merged_weights.items()}
        return self._tool_output(
            "feedback_weight_update",
            "Feedback Weight Update",
            "Preference feedback has been merged into ranking weights.",
            {"feedback": feedback, "updated_weights": normalized},
            ["Regenerate matches", "Explainable ranking"],
            card_type="match_card",
            context_patch={"context_binding": {"match_weights": normalized}},
        )

    def _generate_growth_path(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        student = self._student_by_user(user.id)
        if not student:
            return self._tool_output("generate_growth_path", "Growth Path", "Student profile was not found.", {"error": "student_not_found"}, ["Complete profile"])
        matches = self.match_service.get_matches(student.id) or self.match_service.generate_matches(student.id)
        job_id = int(payload.get("target_job_id") or 0) or int((matches[0] if matches else {}).get("job_id") or 0)
        if not job_id:
            return self._tool_output("generate_growth_path", "Growth Path", "No target job is available.", {"error": "target_job_not_found"}, ["Generate matches"])
        path = self.path_service.generate_path(student.id, job_id)
        return self._tool_output("generate_growth_path", "Growth Path", "Growth path generated.", {"path": path, "target_job_id": job_id}, ["Generate report", "Optimize resume"], card_type="growth_card")

    def _growth_checkin_plan(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        student = self._student_by_user(user.id)
        if not student:
            return self._tool_output("growth_checkin_plan", "Growth Checkin", "Student profile was not found.", {"error": "student_not_found"}, ["Complete profile"])
        stages = [
            {"week": 1, "task": "补齐岗位核心技能知识点", "checkin": "完成学习笔记"},
            {"week": 2, "task": "完成一个岗位相关小项目", "checkin": "提交项目演示"},
            {"week": 3, "task": "优化简历与项目表述", "checkin": "通过一次模拟评审"},
            {"week": 4, "task": "完成面试问答演练", "checkin": "输出改进清单"},
        ]
        plan = stages[: max(1, min(len(stages), top_k))]
        return self._tool_output(
            "growth_checkin_plan",
            "Growth Checkin",
            "Growth check-in plan has been generated.",
            {"student_id": student.id, "plan": plan},
            ["Growth stage review", "Interview training"],
            card_type="growth_card",
            context_patch={"context_binding": {"growth_checkin_plan": plan}},
        )

    def _growth_stage_review(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        plan = payload.get("plan") if isinstance(payload, dict) and isinstance(payload.get("plan"), list) else []
        review = {
            "overall_progress": payload.get("overall_progress") or "on_track",
            "completed_tasks": payload.get("completed_tasks") or len(plan),
            "pending_risks": payload.get("pending_risks") or ["项目证据量化不足", "岗位关键词覆盖不全"],
            "next_focus": payload.get("next_focus") or "强化项目成果量化表达与面试追问应对",
        }
        return self._tool_output(
            "growth_stage_review",
            "Growth Stage Review",
            "Stage review summary is ready.",
            review,
            ["Update growth path", "Run interview coaching"],
            card_type="growth_card",
            context_patch={"context_binding": {"growth_stage_review": review}},
        )

    def _generate_report(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        student = self._student_by_user(user.id)
        if not student:
            return self._tool_output("generate_report", "Report", "Student profile was not found.", {"error": "student_not_found"}, ["Complete profile"])
        matches = self.match_service.get_matches(student.id) or self.match_service.generate_matches(student.id)
        target_job_id = int(payload.get("target_job_id") or 0) or int((matches[0] if matches else {}).get("job_id") or 0)
        report = self.report_service.generate_report(student.id, target_job_id or None)
        return self._tool_output("generate_report", "Report", "Career report generated.", {"report": report}, ["Preview report", "Export PDF"], card_type="report_card")

    def _optimize_resume(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        student = self._student_by_user(user.id)
        if not student:
            return self._tool_output("optimize_resume", "Resume Optimize", "Student profile was not found.", {"error": "student_not_found"}, ["Complete profile"])
        attachment = self._latest_attachment(student.id)
        if not attachment:
            return self._tool_output("optimize_resume", "Resume Optimize", "No attachment available.", {"error": "attachment_not_found"}, ["Upload resume"])
        optimized = self.resume_optimizer.optimize_resume(student.id, attachment.id)
        return self._tool_output("optimize_resume", "Resume Optimize", "Resume optimization completed.", optimized, ["Prepare delivery", "Generate report"], card_type="resume_card")

    def _prepare_delivery(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        student = self._student_by_user(user.id)
        if not student:
            return self._tool_output("prepare_delivery", "Delivery", "Student profile was not found.", {"error": "student_not_found"}, ["Complete profile"])
        targets = self.delivery_service.list_targets(student.id, limit=max(5, top_k * 2))
        attachment = self._latest_attachment(student.id)
        if attachment and (payload.get("knowledge_doc_id") or payload.get("company_name")):
            create_payload = dict(payload)
            create_payload.setdefault("attachment_id", attachment.id)
            delivery = self.delivery_service.create_delivery(student.id, create_payload)
            return self._tool_output("prepare_delivery", "Delivery", "Delivery created.", {"delivery": delivery, "suggested_targets": targets[: top_k]}, ["View delivery"])
        return self._tool_output("prepare_delivery", "Delivery", f"Found {len(targets)} targets.", {"targets": targets[: max(1, top_k)]}, ["Choose target", "Optimize resume"])

    def _assemble_job_package(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        student = self._student_by_user(user.id)
        if not student:
            return self._tool_output("assemble_job_package", "Job Package", "Student profile was not found.", {"error": "student_not_found"}, ["Complete profile"])
        attachment = self._latest_attachment(student.id)
        deliveries = self.delivery_service.list_targets(student.id, limit=max(5, top_k * 2))
        package = {
            "student_id": student.id,
            "resume_attachment": {
                "id": int(getattr(attachment, "id", 0) or 0),
                "name": str(getattr(attachment, "file_name", "") or ""),
                "type": str(getattr(attachment, "file_type", "") or ""),
            }
            if attachment
            else {},
            "delivery_targets": deliveries[: max(1, top_k)],
            "export_suggestion": ["导出简历 PDF", "导出岗位匹配摘要", "导出面试问答清单"],
        }
        return self._tool_output(
            "assemble_job_package",
            "Job Package",
            "Job delivery package has been assembled.",
            package,
            ["Export package", "Generate interview questions"],
            context_patch={"context_binding": {"job_package": package}},
        )

    def _role_onboarding(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        role = str(getattr(getattr(user, "role", None), "code", "") or "student")
        onboarding = {
            "role": role,
            "welcome": f"{role} onboarding ready",
            "first_steps": ["确认目标岗位", "补齐基础资料", "选择技能入口"],
        }
        return self._tool_output(
            "role_onboarding",
            "Role Onboarding",
            "Role onboarding guidance is ready.",
            onboarding,
            ["Quick entry recommendation", "Progress feedback"],
            context_patch={"context_binding": {"onboarding": onboarding}},
        )

    def _quick_entry_recommendation(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        role = str(getattr(getattr(user, "role", None), "code", "") or "student")
        entries = {
            "student": ["resume-workbench", "match-center", "growth-planner"],
            "enterprise": ["candidate-overview", "candidate-screening", "resume-review"],
            "admin": ["admin-metrics", "ops-review", "demo-script"],
        }
        recommended = entries.get(role, entries["student"])
        return self._tool_output(
            "quick_entry_recommendation",
            "Quick Entry",
            "Quick entry recommendations are ready.",
            {"role": role, "recommended_entries": recommended},
            ["Progress feedback", "Operation suggestion"],
            context_patch={"context_binding": {"quick_entries": recommended}},
        )

    def _progress_feedback(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        feedback = {
            "progress": payload.get("progress") or "running",
            "completed": int(payload.get("completed") or 0),
            "todo": int(payload.get("todo") or 3),
            "risk": payload.get("risk") or "none",
        }
        return self._tool_output(
            "progress_feedback",
            "Progress Feedback",
            "Progress feedback is ready.",
            feedback,
            ["Operation suggestion", "Continue current plan"],
            context_patch={"context_binding": {"progress_feedback": feedback}},
        )

    def _operation_suggestion(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        suggestions = payload.get("suggestions") if isinstance(payload, dict) and isinstance(payload.get("suggestions"), list) else []
        if not suggestions:
            suggestions = ["继续当前技能链路", "补齐缺失资料后重新执行", "切换到更具体的任务入口"]
        return self._tool_output(
            "operation_suggestion",
            "Operation Suggestion",
            "Operation suggestions are ready.",
            {"suggestions": suggestions[: max(1, top_k)]},
            ["Apply first suggestion", "Switch skill"],
            context_patch={"context_binding": {"operation_suggestion": suggestions[: max(1, top_k)]}},
        )

    def _build_candidate_overview(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        rows = self.delivery_service.list_enterprise_deliveries(user.id)
        avg_score = round(sum(float(item.get("match_score") or 0) for item in rows) / max(len(rows), 1), 1)
        return self._tool_output("build_candidate_overview", "Candidate Overview", f"Loaded {len(rows)} deliveries.", {"total": len(rows), "avg_match_score": avg_score, "deliveries": rows[: max(1, top_k)]}, ["Rank candidates", "Resume review"])

    def _rank_candidates(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        rows = self.delivery_service.list_enterprise_deliveries(user.id)
        ranked = sorted(rows, key=lambda row: float(row.get("match_score") or 0), reverse=True)
        return self._tool_output("rank_candidates", "Candidate Ranking", f"Ranked {len(ranked)} candidates.", {"ranked_candidates": ranked[: max(1, top_k)]}, ["Resume review", "Communication script"], card_type="candidate_rank_card")

    def _generate_resume_review(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        delivery_id = int(payload.get("delivery_id") or 0)
        if not delivery_id:
            rows = self.delivery_service.list_enterprise_deliveries(user.id)
            if not rows:
                return self._tool_output("generate_resume_review", "Resume Review", "No delivery is available.", {"error": "delivery_not_found"}, ["Create delivery"])
            delivery_id = int(rows[0].get("id") or 0)
        analysis = self.delivery_service.get_enterprise_resume_analysis(user.id, delivery_id)
        return self._tool_output("generate_resume_review", "Resume Review", "Resume review is ready.", {"delivery_id": delivery_id, "analysis": analysis}, ["Interview questions", "Review advice"])

    def _generate_talent_portrait(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        student_id = int(payload.get("student_id") or 0)
        if not student_id:
            rows = self.delivery_service.list_enterprise_deliveries(user.id)
            if rows:
                student_id = int((rows[0].get("student") or {}).get("id") or 0)
        if not student_id:
            return self._tool_output("generate_talent_portrait", "Talent Portrait", "No candidate found.", {"error": "student_not_found"}, ["Candidate overview"])
        profile = self.profile_service.get_latest_profile(student_id) or self.profile_service.generate_profile(student_id)
        return self._tool_output("generate_talent_portrait", "Talent Portrait", "Talent portrait is ready.", {"student_id": student_id, "profile": profile}, ["Interview questions", "Review advice"])

    def _generate_interview_questions(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        role_hint = str(payload.get("target_job") or "目标岗位").strip()
        questions = [
            f"请介绍你在 {role_hint} 方向最有代表性的项目贡献。",
            "面对需求变更时，你如何平衡交付速度与质量？",
            "请举例说明你如何使用数据验证你的方案有效性。",
            "你最近一次失败复盘是什么？后续如何改进？",
            "如果加入团队，前两周你会如何开展工作？",
        ]
        return self._tool_output(
            "generate_interview_questions",
            "Interview Questions",
            f"Generated {len(questions)} interview questions.",
            {"target_role": role_hint, "questions": questions[: max(3, top_k + 1)]},
            ["Followup simulation", "Review advice"],
            card_type="interview_question_card",
            context_patch={"context_binding": {"interview_questions": questions[: max(3, top_k + 1)]}},
        )

    def _followup_simulation(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        base_answer = str(payload.get("answer") or message or "").strip()
        prompts = ["你提到的结果是如何量化的？", "如果资源减半，你会如何调整方案？", "这段经历中你个人承担了哪些关键决策？"]
        return self._tool_output(
            "followup_simulation",
            "Followup Simulation",
            "Follow-up simulation prompts are ready.",
            {"base_answer": base_answer, "followups": prompts[: max(1, top_k)]},
            ["Answer evaluation", "Interview report"],
            card_type="interview_question_card",
            context_patch={"context_binding": {"interview_followups": prompts[: max(1, top_k)]}},
        )

    def _answer_evaluation(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        answer = str(payload.get("answer") or message or "").strip()
        dimensions = [
            {"dimension": "结构化表达", "score": 78, "comment": "主线清楚，但证据可再量化"},
            {"dimension": "业务理解", "score": 81, "comment": "能结合岗位场景，但缺少指标闭环"},
            {"dimension": "问题解决", "score": 75, "comment": "思路完整，缺少风险预案说明"},
        ]
        return self._tool_output(
            "answer_evaluation",
            "Answer Evaluation",
            "Answer evaluation completed.",
            {"answer": answer, "dimensions": dimensions[: max(1, top_k)], "overall_score": 78},
            ["Interview report", "Retry simulation"],
            card_type="interview_question_card",
            context_patch={"context_binding": {"answer_evaluation": {"overall_score": 78, "dimensions": dimensions}}},
        )

    def _interview_report(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        report = {
            "summary": "模拟面试完成，建议优先提升量化表达与追问应对。",
            "strengths": ["回答结构清晰", "岗位理解较完整"],
            "improvements": ["补充结果数据", "增加风险应对示例"],
            "next_plan": ["完成 3 道追问训练", "更新项目成果量化表述"],
        }
        return self._tool_output(
            "interview_report",
            "Interview Report",
            "Interview report is ready.",
            report,
            ["Continue interview training", "Update resume bullets"],
            card_type="report_card",
            context_patch={"context_binding": {"interview_report": report}},
        )

    def _manage_offer_pipeline(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        rows = self.delivery_service.list_enterprise_deliveries(user.id)
        pipeline = []
        for item in rows[: max(1, top_k)]:
            status = str(item.get("status") or "screening")
            pipeline.append(
                {
                    "delivery_id": item.get("id"),
                    "candidate_name": (item.get("student") or {}).get("name"),
                    "target_company": item.get("company_name") or "",
                    "status": status,
                }
            )
        return self._tool_output(
            "manage_offer_pipeline",
            "Offer Pipeline",
            f"Offer pipeline refreshed with {len(pipeline)} candidates.",
            {"pipeline": pipeline},
            ["Generate communication script", "Summarize ops review"],
            card_type="candidate_rank_card",
            context_patch={"context_binding": {"offer_pipeline": pipeline}},
        )

    def _build_communication_script(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        candidate_name = str(payload.get("candidate_name") or "候选人").strip()
        target_role = str(payload.get("target_role") or "目标岗位").strip()
        scripts = {
            "invite": f"你好，{candidate_name}，我们邀请你参加 {target_role} 岗位面试。",
            "follow_up": f"你好，{candidate_name}，欢迎补充 {target_role} 相关项目材料。",
            "feedback": f"你好，{candidate_name}，建议你继续强化 {target_role} 方向的成果量化表达。",
        }
        return self._tool_output("build_communication_script", "Communication Script", "Communication scripts are ready.", {"scripts": scripts}, ["Review advice", "Resume review"])

    def _generate_review_advice(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        advice = ["优先核对项目真实性和结果量化。", "反馈尽量具体到行为和产出。", "给出下一阶段可执行改进任务。"]
        return self._tool_output("generate_review_advice", "Review Advice", "Review advice is ready.", {"advice": advice}, ["Communication script", "Ops review"])

    def _summarize_admin_metrics(self, *, user=None, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        students = self.db.query(func.count(Student.id)).filter(Student.deleted.is_(False)).scalar() or 0
        enterprises = self.db.query(func.count(User.id)).join(Role, Role.id == User.role_id).filter(User.deleted.is_(False), Role.code == "enterprise").scalar() or 0
        deliveries = self.db.query(func.count(ResumeDelivery.id)).filter(ResumeDelivery.deleted.is_(False)).scalar() or 0
        reports = self.db.query(func.count(Report.id)).filter(Report.deleted.is_(False)).scalar() or 0
        matches = self.db.query(func.count(JobMatchResult.id)).filter(JobMatchResult.deleted.is_(False)).scalar() or 0
        data = {"students": int(students), "enterprises": int(enterprises), "deliveries": int(deliveries), "reports": int(reports), "matches": int(matches)}
        return self._tool_output("summarize_admin_metrics", "Admin Metrics", "Administrative metrics summary is ready.", data, ["Ops review", "Data governance"], card_type="metrics_card")

    def _summarize_ops_review(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        metrics = self._summarize_admin_metrics(user=user).get("data", {})
        deliveries = float(metrics.get("deliveries") or 0)
        reports = float(metrics.get("reports") or 0)
        report_rate = round((reports / deliveries * 100) if deliveries else 0.0, 1)
        return self._tool_output("summarize_ops_review", "Ops Review", "Operations review summary is ready.", {"metrics": metrics, "report_coverage_rate": report_rate}, ["Knowledge governance", "Data governance"])

    def _llm_cost_latency_scan(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        scan = {
            "provider": str(self.settings.LLM_PROVIDER or ""),
            "model": str(self.settings.LANGCHAIN_MODEL or ""),
            "temperature": float(self.settings.LLM_TEMPERATURE),
            "estimated_latency_ms": int(payload.get("estimated_latency_ms") or 850),
            "estimated_cost_level": payload.get("estimated_cost_level") or "medium",
        }
        return self._tool_output(
            "llm_cost_latency_scan",
            "LLM Cost & Latency",
            "LLM cost/latency scan is ready.",
            scan,
            ["Ops review", "Adjust model strategy"],
            card_type="metrics_card",
            context_patch={"context_binding": {"llm_scan": scan}},
        )

    def _knowledge_governance_scan(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        documents = self.vector_search_service.list_documents(limit=500)
        missing_job_name = sum(1 for item in documents if not str(item.get("job_name") or "").strip())
        missing_company = sum(1 for item in documents if not str(item.get("company_name") or "").strip())
        data = {
            "backend": self.vector_search_service.backend_name,
            "document_count": len(documents),
            "missing_job_name": missing_job_name,
            "missing_company_name": missing_company,
        }
        return self._tool_output(
            "knowledge_governance_scan",
            "Knowledge Governance",
            "Knowledge governance scan is ready.",
            data,
            ["Data governance", "Job KB search"],
            card_type="metrics_card",
            context_patch={"context_binding": {"knowledge_governance": data}},
        )

    def _data_governance_scan(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        student_total = self.db.query(func.count(Student.id)).filter(Student.deleted.is_(False)).scalar() or 0
        delivery_total = self.db.query(func.count(ResumeDelivery.id)).filter(ResumeDelivery.deleted.is_(False)).scalar() or 0
        match_total = self.db.query(func.count(JobMatchResult.id)).filter(JobMatchResult.deleted.is_(False)).scalar() or 0
        data = {"student_total": int(student_total), "delivery_total": int(delivery_total), "match_total": int(match_total)}
        return self._tool_output(
            "data_governance_scan",
            "Data Governance",
            "Data governance scan is ready.",
            data,
            ["Ops review", "Demo script"],
            card_type="metrics_card",
            context_patch={"context_binding": {"data_governance": data}},
        )

    def _build_role_overview(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        rows = self.db.query(Role.code, func.count(User.id)).join(User, User.role_id == Role.id).filter(User.deleted.is_(False), Role.deleted.is_(False)).group_by(Role.code).all()
        role_counts = {str(code or "unknown"): int(count or 0) for code, count in rows}
        return self._tool_output("build_role_overview", "Role Overview", "Cross-role overview is ready.", {"role_counts": role_counts}, ["Admin metrics", "Ops review"])

    def _inspect_knowledge_governance(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        return self._knowledge_governance_scan(user=user, message=message, top_k=top_k, payload=payload)

    def _inspect_data_governance(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        return self._data_governance_scan(user=user, message=message, top_k=top_k, payload=payload)

    def _generate_demo_script(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        metrics = self._summarize_admin_metrics(user=user).get("data", {})
        script = [
            "1) 学生侧：上传简历 -> 解析 -> 画像 -> 匹配 -> 报告",
            "2) 企业侧：候选人概览 -> 排序 -> 简历评审 -> 面试问题",
            "3) 管理侧：指标看板 -> 知识治理 -> 数据治理",
            f"4) 当前样本：学生 {metrics.get('students', 0)} 人，投递 {metrics.get('deliveries', 0)} 次，报告 {metrics.get('reports', 0)} 份",
        ]
        return self._tool_output(
            "generate_demo_script",
            "Demo Script",
            "Demo script is ready.",
            {"script": script},
            ["Build demo timeline", "Annotate key points"],
            context_patch={"context_binding": {"demo_script": script}},
        )

    def _demo_timeline(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        timeline = [
            {"minute": 1, "topic": "平台价值与角色入口"},
            {"minute": 3, "topic": "学生闭环：简历到报告"},
            {"minute": 5, "topic": "企业闭环：筛选到 Offer"},
            {"minute": 7, "topic": "治理闭环：指标与风险"},
        ]
        return self._tool_output(
            "demo_timeline",
            "Demo Timeline",
            "Demo timeline is ready.",
            {"timeline": timeline[: max(1, top_k)]},
            ["Keypoint annotation", "Generate communication script"],
            context_patch={"context_binding": {"demo_timeline": timeline[: max(1, top_k)]}},
        )

    def _keypoint_annotation(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        points = [
            "强调 selected_skill 优先路由，避免误判闲聊。",
            "展示每个 Agent 专属模型接线与职责闭环。",
            "说明 tool_outputs/context_patch 如何跨 Agent 互通。",
            "总结治理指标与后续优化路径。",
        ]
        return self._tool_output(
            "keypoint_annotation",
            "Keypoint Annotation",
            "Demo keypoint annotations are ready.",
            {"annotations": points[: max(1, top_k)]},
            ["Start demo", "Switch to manual mode"],
            context_patch={"context_binding": {"demo_keypoints": points[: max(1, top_k)]}},
        )

    def _job_kb_search(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        query = str(payload.get("query") or payload.get("target_job") or message or "").strip()
        if not query:
            return self._tool_output("job_kb_search", "Job KB Search", "No search query provided.", {"error": "query_required"}, ["Provide role or keyword"])
        hits = self.vector_search_service.search(query=query, top_k=max(1, top_k))
        rows = [self._to_retrieval_chunk(hit) for hit in (hits or [])]
        return self._tool_output("job_kb_search", "Job KB Search", f"Retrieved {len(rows)} hits.", {"query": query, "hits": rows}, ["Skill graph view", "Generate matches"])

    def _skill_graph_view(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        query = str(payload.get("query") or payload.get("target_job") or message or "").strip()
        hits = self.vector_search_service.search(query=query, top_k=max(1, top_k))
        graph_nodes = []
        for hit in hits or []:
            graph_nodes.append(
                {
                    "job_name": str(hit.get("job_name") or ""),
                    "core_skills": hit.get("core_skills") if isinstance(hit.get("core_skills"), list) else [],
                    "recommended_courses": hit.get("recommended_courses") if isinstance(hit.get("recommended_courses"), list) else [],
                }
            )
        return self._tool_output(
            "skill_graph_view",
            "Skill Graph",
            f"Skill graph view is ready with {len(graph_nodes)} nodes.",
            {"query": query, "nodes": graph_nodes},
            ["Learning sequence", "Transfer path recommendation"],
            context_patch={"context_binding": {"skill_graph": graph_nodes}},
        )

    def _learning_sequence(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        target_job = str(payload.get("target_job") or message or "目标岗位").strip()
        sequence = [
            {"stage": "基础", "task": "补齐岗位核心知识与术语"},
            {"stage": "实战", "task": "完成 1-2 个可展示项目"},
            {"stage": "求职", "task": "优化简历并完成面试模拟"},
        ]
        return self._tool_output(
            "learning_sequence",
            "Learning Sequence",
            "Learning sequence is ready.",
            {"target_job": target_job, "sequence": sequence[: max(1, top_k)]},
            ["Transfer path recommendation", "Growth checkin plan"],
            context_patch={"context_binding": {"learning_sequence": sequence[: max(1, top_k)]}},
        )

    def _transfer_path_recommendation(self, *, user, message: str = "", top_k: int = 4, payload: dict[str, Any] | None = None):
        target_job = str(payload.get("target_job") or message or "目标岗位").strip()
        paths = [
            {"from": "前端开发", "to": target_job, "bridge_skills": ["业务理解", "数据分析", "项目表达"]},
            {"from": "测试工程", "to": target_job, "bridge_skills": ["自动化能力", "质量指标", "问题复盘"]},
            {"from": "运营岗位", "to": target_job, "bridge_skills": ["增长分析", "用户洞察", "跨团队协作"]},
        ]
        return self._tool_output(
            "transfer_path_recommendation",
            "Transfer Path",
            "Transfer path recommendations are ready.",
            {"target_job": target_job, "paths": paths[: max(1, top_k)]},
            ["Generate growth path", "Interview training"],
            context_patch={"context_binding": {"transfer_paths": paths[: max(1, top_k)]}},
        )

    @staticmethod
    def _to_retrieval_chunk(hit):
        metadata = hit.get("metadata") if isinstance(hit, dict) and isinstance(hit.get("metadata"), dict) else {}
        return {
            "job_name": str(hit.get("job_name") or metadata.get("job_name") or "").strip(),
            "job_category": str(hit.get("job_category") or metadata.get("job_category") or "").strip(),
            "company_name": str(hit.get("company_name") or metadata.get("company_name") or "").strip(),
            "score": float(hit.get("score") or 0),
            "snippet": str(hit.get("content") or "")[:220],
        }

    def _student_by_user(self, user_id):
        return (
            self.db.query(Student)
            .options(
                joinedload(Student.skills),
                joinedload(Student.certificates),
                joinedload(Student.projects),
                joinedload(Student.internships),
            )
            .filter(Student.user_id == user_id, Student.deleted.is_(False))
            .first()
        )

    def _latest_attachment(self, student_id):
        return (
            self.db.query(StudentAttachment)
            .filter(StudentAttachment.student_id == student_id, StudentAttachment.deleted.is_(False))
            .order_by(StudentAttachment.updated_at.desc(), StudentAttachment.id.desc())
            .first()
        )

    @staticmethod
    def _tool_output(tool, title, summary, data, next_actions, *, card_type="action_checklist_card", context_patch=None):
        settings = get_settings()
        output = {
            "tool": tool,
            "title": title,
            "summary": summary,
            "data": data or {},
            "next_actions": list(next_actions or []),
            "context_patch": context_patch or {},
        }
        if card_type and settings.ENABLE_ASSISTANT_TOOL_CARDS:
            output["card"] = {"type": card_type, "tool": tool, "title": title, "summary": summary, "data": data or {}}
        return output
