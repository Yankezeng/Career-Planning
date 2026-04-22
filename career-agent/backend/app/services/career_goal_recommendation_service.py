from __future__ import annotations

from statistics import mean
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models.job import Job
from app.models.student import Student
from app.services.job_match_service_clean import JobMatchService
from app.services.student_profile_service_clean import StudentProfileService


class CareerGoalRecommendationService:
    def __init__(self, db: Session):
        self.db = db
        self.match_service = JobMatchService(db)
        self.profile_service = StudentProfileService(db)

    def get_recommendations(self, student_id: int, top_k: int = 5) -> list[dict[str, Any]]:
        student = (
            self.db.query(Student)
            .options(
                joinedload(Student.skills),
                joinedload(Student.certificates),
                joinedload(Student.projects),
                joinedload(Student.internships),
                joinedload(Student.campus_experiences),
            )
            .filter(Student.id == student_id, Student.deleted.is_(False))
            .first()
        )
        if not student:
            raise ValueError("学生不存在")

        profile = self.profile_service.get_latest_profile(student_id)
        if not profile:
            profile = self.profile_service.generate_profile(student_id)

        matches = self.match_service.get_matches(student_id)
        if not matches:
            matches = self.match_service.generate_matches(student_id)

        if not matches:
            return []

        dimension_scores = self._extract_dimension_scores(profile)
        interest_tags = set((student.interests or []) + [student.target_industry or "", student.target_city or ""])
        interest_tags.discard("")

        recommendations: list[dict[str, Any]] = []
        for match in matches[:20]:
            job = match.get("job", {})
            match_score = match.get("total_score", 0)
            dimension_scores_match = match.get("dimension_scores", [])
            ability_dimension_scores = {item["key"]: item["score"] for item in dimension_scores_match}

            ability_fit = self._calculate_ability_fit(dimension_scores, ability_dimension_scores)
            interest_fit = self._calculate_interest_fit(job, interest_tags)

            recommendation_score = round(
                match_score * 0.4 + ability_fit * 0.3 + interest_fit * 0.3,
                1,
            )

            strengths = self._identify_strengths(match, dimension_scores)
            gaps = self._identify_gaps(match)

            recommendations.append(
                {
                    "job_id": job.get("id"),
                    "job_name": job.get("name"),
                    "job_category": job.get("category"),
                    "job_industry": job.get("industry"),
                    "match_score": match_score,
                    "ability_fit_score": ability_fit,
                    "interest_fit_score": interest_fit,
                    "recommendation_score": recommendation_score,
                    "strengths": strengths,
                    "gaps": gaps,
                    "reason": self._generate_recommendation_reason(
                        job.get("name"), recommendation_score, strengths, gaps
                    ),
                }
            )

        recommendations.sort(key=lambda x: x["recommendation_score"], reverse=True)
        return recommendations[:top_k]

    def _extract_dimension_scores(self, profile: dict) -> dict[str, float]:
        raw_metrics = profile.get("raw_metrics") or {}
        dimension_items = raw_metrics.get("dimension_scores") or []
        scores: dict[str, float] = {}
        for item in dimension_items:
            if item.get("key"):
                scores[item["key"]] = float(item["score"])
        scores["professional_skill"] = scores.get("professional_skill", float(profile.get("professional_score", 60.0)))
        scores["learning"] = scores.get("learning", float(profile.get("learning_score", 60.0)))
        scores["innovation"] = scores.get("innovation", float(profile.get("innovation_score", 60.0)))
        scores["communication"] = scores.get("communication", float(profile.get("communication_score", 60.0)))
        scores["stress_resistance"] = scores.get("stress_resistance", float(profile.get("professionalism_score", 60.0)))
        scores["internship"] = scores.get("internship", float(profile.get("practice_score", 60.0)))
        return scores

    def _calculate_ability_fit(
        self, student_scores: dict[str, float], job_scores: dict[str, float]
    ) -> float:
        common_keys = set(student_scores.keys()) & set(job_scores.keys())
        if not common_keys:
            return 60.0
        diffs = []
        for key in common_keys:
            diff = abs(student_scores[key] - job_scores[key])
            diffs.append(max(0, 100 - diff))
        return round(mean(diffs), 1) if diffs else 60.0

    def _calculate_interest_fit(self, job: dict, interest_tags: set[str]) -> float:
        if not interest_tags:
            return 60.0
        job_text = " ".join(
            [
                str(job.get("name") or ""),
                str(job.get("category") or ""),
                str(job.get("industry") or ""),
            ]
        ).lower()
        hit_count = sum(1 for tag in interest_tags if tag.lower() in job_text)
        return round(min(100.0, 40 + hit_count * 20), 1)

    def _identify_strengths(self, match: dict, student_scores: dict[str, float]) -> list[str]:
        strengths: list[str] = []
        dimension_scores = match.get("dimension_scores", [])
        for dim in dimension_scores:
            if dim.get("score", 0) >= 75:
                strengths.append(f"{dim.get('label')}表现突出（{dim.get('score')}分）")
        sub_scores = match.get("sub_scores", [])
        for sub in sub_scores:
            if sub.get("score", 0) >= 75:
                strengths.append(f"{sub.get('label')}储备充足（{sub.get('score')}分）")
        if match.get("key_skill_hit_rate", 0) >= 60:
            strengths.append(f"核心技能命中率较高（{match['key_skill_hit_rate']}%）")
        return strengths[:3]

    def _identify_gaps(self, match: dict) -> list[str]:
        gaps: list[str] = []
        dimension_scores = match.get("dimension_scores", [])
        for dim in dimension_scores:
            if dim.get("score", 0) < 65:
                gaps.append(f"{dim.get('label')}需要提升（当前{dim.get('score')}分）")
        match_gaps = match.get("gaps", [])
        for gap in match_gaps[:2]:
            gaps.append(f"缺少：{gap.get('gap_item', '')}")
        return gaps[:3]

    def _generate_recommendation_reason(
        self, job_name: str, score: float, strengths: list[str], gaps: list[str]
    ) -> str:
        reason_parts: list[str] = []
        if score >= 80:
            reason_parts.append(f"综合推荐度较高（{score}分）")
        elif score >= 65:
            reason_parts.append(f"有一定匹配度（{score}分）")
        else:
            reason_parts.append(f"匹配度一般（{score}分），可作为备选方向")
        if strengths:
            reason_parts.append(f"优势：{strengths[0]}")
        if gaps:
            reason_parts.append(f"需关注：{gaps[0]}")
        return f"推荐 {job_name}：{'；'.join(reason_parts)}。"
