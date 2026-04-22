from __future__ import annotations

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.models.career import OptimizationRecord
from app.models.student import GrowthRecord, ReviewRecord
from app.services.graph.career_path_neo4j import CareerPathService
from app.services.job_match_service_clean import JobMatchService
from app.services.student_profile_service_clean import StudentProfileService
from app.utils.serializers import to_dict


class OptimizationService:
    def __init__(self, db: Session):
        self.db = db
        self.profile_service = StudentProfileService(db)
        self.match_service = JobMatchService(db)
        self.path_service = CareerPathService(db)

    def re_optimize(self, student_id: int) -> dict:
        profile = self.profile_service.generate_profile(student_id)
        matches = self.match_service.generate_matches(student_id)
        path = self.path_service.generate_path(student_id)
        latest_growth = self._get_latest_growth(student_id)
        latest_review = self._get_latest_review(student_id)
        focus_actions = self._build_focus_actions(matches, path, latest_review)
        summary = self._build_summary(matches, latest_growth, latest_review)

        record = OptimizationRecord(
            student_id=student_id,
            based_on_growth_id=latest_growth.id if latest_growth else None,
            based_on_review_id=latest_review.id if latest_review else None,
            summary=summary,
            suggestions=focus_actions,
            new_profile_snapshot=jsonable_encoder(profile),
            new_match_snapshot=jsonable_encoder(
                {
                    "top_matches": matches[:3],
                    "career_path": path,
                    "focus_actions": focus_actions,
                    "growth_summary": self._serialize_growth(latest_growth),
                    "review_summary": self._serialize_review(latest_review),
                }
            ),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return self.serialize_record(record)

    def get_latest_optimization(self, student_id: int) -> dict | None:
        record = (
            self.db.query(OptimizationRecord)
            .filter(OptimizationRecord.student_id == student_id, OptimizationRecord.deleted.is_(False))
            .order_by(OptimizationRecord.id.desc())
            .first()
        )
        return self.serialize_record(record) if record else None

    def serialize_record(self, record: OptimizationRecord | None) -> dict | None:
        if not record:
            return None

        data = to_dict(record)
        profile_snapshot = data.get("new_profile_snapshot") or {}
        match_snapshot = data.get("new_match_snapshot") or {}
        career_path = match_snapshot.get("career_path") or {}
        top_matches = match_snapshot.get("top_matches") or []

        data["top_matches"] = top_matches
        data["career_path"] = career_path
        data["career_tasks"] = (career_path.get("tasks") or [])[:8]
        data["focus_actions"] = match_snapshot.get("focus_actions") or data.get("suggestions") or []
        data["growth_summary"] = match_snapshot.get("growth_summary")
        data["review_summary"] = match_snapshot.get("review_summary")
        data["profile_summary"] = profile_snapshot.get("summary")
        data["profile_scores"] = [
            {"label": "专业能力", "value": profile_snapshot.get("professional_score", 0)},
            {"label": "实践能力", "value": profile_snapshot.get("practice_score", 0)},
            {"label": "沟通协作", "value": profile_snapshot.get("communication_score", 0)},
            {"label": "学习成长", "value": profile_snapshot.get("learning_score", 0)},
            {"label": "创新能力", "value": profile_snapshot.get("innovation_score", 0)},
            {"label": "职业素养", "value": profile_snapshot.get("professionalism_score", 0)},
        ]
        return data

    def _get_latest_growth(self, student_id: int) -> GrowthRecord | None:
        return (
            self.db.query(GrowthRecord)
            .filter(GrowthRecord.student_id == student_id, GrowthRecord.deleted.is_(False))
            .order_by(GrowthRecord.id.desc())
            .first()
        )

    def _get_latest_review(self, student_id: int) -> ReviewRecord | None:
        return (
            self.db.query(ReviewRecord)
            .filter(ReviewRecord.student_id == student_id, ReviewRecord.deleted.is_(False))
            .order_by(ReviewRecord.id.desc())
            .first()
        )

    def _build_summary(self, matches: list[dict], growth: GrowthRecord | None, review: ReviewRecord | None) -> str:
        top_match = matches[0] if matches else {}
        top_job = top_match.get("job_name") or "目标岗位"
        top_score = round(float(top_match.get("total_score") or 0), 1)
        growth_part = f"最近阶段成果为“{growth.stage_label}”" if growth else "最近暂无新的阶段成果"
        review_part = f"，并结合企业复评得分 {review.score} 分" if review else ""
        return (
            f"系统已根据最新成长反馈重新生成优化方案。{growth_part}{review_part}，"
            f"当前最值得优先冲刺的岗位方向是 {top_job}，最新匹配度约为 {top_score} 分。"
        )

    def _build_focus_actions(self, matches: list[dict], path: dict | None, review: ReviewRecord | None) -> list[str]:
        actions: list[str] = []
        top_match = matches[0] if matches else {}
        for gap in (top_match.get("gaps") or [])[:4]:
            description = gap.get("description") or gap.get("gap_item")
            if description:
                actions.append(description)
        for task in (path or {}).get("tasks", [])[:4]:
            title = task.get("title")
            if title:
                actions.append(f"优先推进：{title}")
        if review:
            actions.extend(review.suggestions[:3])

        deduplicated: list[str] = []
        seen: set[str] = set()
        for item in actions:
            key = item.strip().lower()
            if key and key not in seen:
                seen.add(key)
                deduplicated.append(item)
        return deduplicated[:6]

    @staticmethod
    def _serialize_growth(growth: GrowthRecord | None) -> dict | None:
        if not growth:
            return None
        return {
            "stage_label": growth.stage_label,
            "completion_rate": growth.completion_rate,
            "weekly_summary": growth.weekly_summary,
            "new_skills": growth.new_skills,
            "new_certificates": growth.new_certificates,
            "new_projects": growth.new_projects,
            "new_internships": growth.new_internships,
        }

    @staticmethod
    def _serialize_review(review: ReviewRecord | None) -> dict | None:
        if not review:
            return None
        return {
            "comment": review.comment,
            "score": review.score,
            "suggestions": review.suggestions,
        }
