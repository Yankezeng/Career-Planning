from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.student import Student, StudentProfile
from app.services.job_match_service_clean import JobMatchService


BENCHMARK_PATH = Path(__file__).resolve().parents[1] / "data" / "quality_benchmark_clean.json"


class QualityEvaluationService:
    def __init__(self, db: Session):
        self.db = db
        self.benchmark = self._load_benchmark()

    def evaluate(self) -> dict[str, Any]:
        job_portrait = self._evaluate_job_portrait()
        student_portrait = self._evaluate_student_portrait()
        job_match = self._evaluate_job_match()
        overall_accuracy = round((job_portrait["accuracy"] + student_portrait["accuracy"] + job_match["accuracy"]) / 3, 1)
        overall_hit_rate = round((job_portrait["hit_rate"] + student_portrait["hit_rate"] + job_match["hit_rate"]) / 3, 1)
        overall_explain_rate = round((job_portrait["explain_rate"] + student_portrait["explain_rate"] + job_match["explain_rate"]) / 3, 1)
        return {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "job_portrait": job_portrait,
            "student_portrait": student_portrait,
            "job_match": job_match,
            "overall": {
                "accuracy": overall_accuracy,
                "hit_rate": overall_hit_rate,
                "explain_rate": overall_explain_rate,
                "benchmark": {
                    "job_portrait_accuracy_target": 90,
                    "student_portrait_accuracy_target": 90,
                    "job_match_skill_hit_target": 80,
                },
            },
        }

    def _evaluate_job_portrait(self) -> dict[str, Any]:
        samples = self.benchmark.get("job_portrait_samples", [])
        records = []
        for sample in samples:
            job = self._find_job(sample.get("job_keyword", ""))
            if not job:
                continue
            profile = job.job_profile if isinstance(job.job_profile, dict) else {}
            skills = {item.lower() for item in (profile.get("core_skills") or job.core_skill_tags or [])}
            expected_skills = sample.get("must_have_skills") or []
            skill_hit = self._ratio(sum(1 for item in expected_skills if any(item in skill for skill in skills)), len(expected_skills))
            dimensions = {item.get("key") for item in (profile.get("portrait_dimensions") or []) if item.get("key")}
            required_dimensions = set(sample.get("must_have_dimensions") or [])
            dimension_hit = self._ratio(len(dimensions & required_dimensions), len(required_dimensions))
            transfer_paths = profile.get("transfer_paths") or []
            vertical_path = profile.get("vertical_path") or []
            transfer_hit = 1.0 if len(transfer_paths) >= 2 else 0.0
            vertical_hit = 1.0 if len(vertical_path) >= 3 and all(item.get("promotion_condition") and item.get("path_note") for item in vertical_path) else 0.0
            explain_hit = 1.0 if profile.get("summary") and profile.get("work_content") else 0.0
            records.append(
                {
                    "accuracy": round((skill_hit * 0.45 + dimension_hit * 0.35 + transfer_hit * 0.1 + vertical_hit * 0.1) * 100, 1),
                    "hit_rate": round(skill_hit * 100, 1),
                    "explain_rate": round(explain_hit * 100, 1),
                }
            )
        return self._aggregate(records)

    def _evaluate_student_portrait(self) -> dict[str, Any]:
        samples = self.benchmark.get("student_portrait_samples", [])
        records = []
        for sample in samples:
            student = self.db.query(Student).filter(Student.student_no == sample.get("student_no"), Student.deleted.is_(False)).first()
            if not student:
                continue
            profile = (
                self.db.query(StudentProfile)
                .filter(StudentProfile.student_id == student.id, StudentProfile.deleted.is_(False))
                .order_by(StudentProfile.id.desc())
                .first()
            )
            if not profile:
                continue
            raw_metrics = profile.raw_metrics if isinstance(profile.raw_metrics, dict) else {}
            dimensions = {item.get("key") for item in (raw_metrics.get("dimension_scores") or []) if item.get("key")}
            required_dimensions = set(sample.get("must_have_dimensions") or [])
            dimension_hit = self._ratio(len(dimensions & required_dimensions), len(required_dimensions))
            expected_strengths = set(sample.get("expected_strengths") or [])
            actual_strengths = {item for item in (profile.strengths or [])}
            strength_hit = self._ratio(len(expected_strengths & actual_strengths), len(expected_strengths))
            completeness = float(raw_metrics.get("completeness_score") or 0) / 100
            explain_hit = 1.0 if profile.summary and profile.weaknesses else 0.0
            records.append(
                {
                    "accuracy": round((dimension_hit * 0.45 + strength_hit * 0.35 + completeness * 0.2) * 100, 1),
                    "hit_rate": round(strength_hit * 100, 1),
                    "explain_rate": round(explain_hit * 100, 1),
                }
            )
        return self._aggregate(records)

    def _evaluate_job_match(self) -> dict[str, Any]:
        samples = self.benchmark.get("job_match_samples", [])
        records = []
        for sample in samples:
            student = self.db.query(Student).filter(Student.student_no == sample.get("student_no"), Student.deleted.is_(False)).first()
            if not student:
                continue
            matches = JobMatchService(self.db).get_matches(student.id) or JobMatchService(self.db).generate_matches(student.id)
            if not matches:
                continue
            top_match = matches[0]
            top_job_name = ((top_match.get("job") or {}).get("name") or "").lower()
            top_keywords = [str(item).lower() for item in (sample.get("expected_top_job_keywords") or [])]
            top_hit = 1.0 if any(keyword in top_job_name for keyword in top_keywords) else 0.0
            dimensions = {item.get("key") for item in (top_match.get("dimension_scores") or []) if item.get("key")}
            required_dimensions = set(sample.get("must_have_match_dimensions") or [])
            dimension_hit = self._ratio(len(dimensions & required_dimensions), len(required_dimensions))
            weights = top_match.get("match_weights") or {}
            weight_valid = 1.0 if round(sum(float(value) for value in weights.values()), 6) == 1.0 and len(weights) == 4 else 0.0
            analyses = top_match.get("dimension_analysis") or []
            explain_hit = self._ratio(sum(1 for item in analyses if item.get("description")), len(analyses))
            records.append(
                {
                    "accuracy": round((dimension_hit * 0.45 + weight_valid * 0.25 + top_hit * 0.3) * 100, 1),
                    "hit_rate": round(top_hit * 100, 1),
                    "explain_rate": round(explain_hit * 100, 1),
                }
            )
        return self._aggregate(records)

    def _find_job(self, keyword: str) -> Job | None:
        normalized = str(keyword or "").strip().lower()
        if not normalized:
            return None
        jobs = self.db.query(Job).filter(Job.deleted.is_(False)).all()
        for job in jobs:
            if normalized in (job.name or "").lower():
                return job
        return None

    @staticmethod
    def _aggregate(records: list[dict[str, float]]) -> dict[str, Any]:
        if not records:
            return {"sample_size": 0, "accuracy": 0.0, "hit_rate": 0.0, "explain_rate": 0.0}
        sample_size = len(records)
        return {
            "sample_size": sample_size,
            "accuracy": round(sum(item["accuracy"] for item in records) / sample_size, 1),
            "hit_rate": round(sum(item["hit_rate"] for item in records) / sample_size, 1),
            "explain_rate": round(sum(item["explain_rate"] for item in records) / sample_size, 1),
        }

    @staticmethod
    def _ratio(hit: int, total: int) -> float:
        if total <= 0:
            return 0.0
        return hit / total

    @staticmethod
    def _load_benchmark() -> dict[str, Any]:
        if not BENCHMARK_PATH.exists():
            return {}
        return json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
