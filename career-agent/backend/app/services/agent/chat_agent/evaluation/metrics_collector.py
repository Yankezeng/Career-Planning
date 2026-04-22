from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from collections import defaultdict

from sqlalchemy.orm import Session


class MetricsCollector:
    def __init__(self, db: Session):
        self.db = db
        self._session_metrics = defaultdict(dict)
        self._metrics_buffer = []

    def record_intent_classification(
        self,
        user_id: int,
        session_id: int,
        predicted_intent: str,
        actual_intent: str | None = None,
        confidence: float = 1.0,
    ) -> dict[str, Any]:
        record = {
            "user_id": user_id,
            "session_id": session_id,
            "type": "intent_classification",
            "predicted": predicted_intent,
            "actual": actual_intent,
            "confidence": confidence,
            "correct": predicted_intent == actual_intent if actual_intent else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._metrics_buffer.append(record)
        return record

    def record_slot_extraction(
        self,
        user_id: int,
        session_id: int,
        extracted_slots: dict[str, Any],
        validated_slots: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if validated_slots is None:
            validated_slots = extracted_slots

        missing_slots = []
        for key, value in extracted_slots.items():
            if not value and key in ["target_job", "target_city", "target_industry"]:
                missing_slots.append(key)

        record = {
            "user_id": user_id,
            "session_id": session_id,
            "type": "slot_extraction",
            "extracted_count": len([v for v in extracted_slots.values() if v]),
            "missing_slots": missing_slots,
            "complete": len(missing_slots) == 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._metrics_buffer.append(record)
        return record

    def record_tool_execution(
        self,
        user_id: int,
        session_id: int,
        tool_name: str,
        success: bool,
        error: str | None = None,
        duration_ms: float = 0,
    ) -> dict[str, Any]:
        record = {
            "user_id": user_id,
            "session_id": session_id,
            "type": "tool_execution",
            "tool_name": tool_name,
            "success": success,
            "error": error,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._metrics_buffer.append(record)
        return record

    def record_retrieval(
        self,
        user_id: int,
        session_id: int,
        query: str,
        result_count: int,
        reranked: bool = False,
    ) -> dict[str, Any]:
        record = {
            "user_id": user_id,
            "session_id": session_id,
            "type": "retrieval",
            "query_length": len(query),
            "result_count": result_count,
            "reranked": reranked,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._metrics_buffer.append(record)
        return record

    def record_user_feedback(
        self,
        user_id: int,
        session_id: int,
        message_id: int,
        feedback: str,
        rating: int | None = None,
    ) -> dict[str, Any]:
        record = {
            "user_id": user_id,
            "session_id": session_id,
            "message_id": message_id,
            "type": "user_feedback",
            "feedback": feedback,
            "rating": rating,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._metrics_buffer.append(record)
        self._persist_feedback(record)
        return record

    def get_session_metrics(self, session_id: int) -> dict[str, Any]:
        session_records = [r for r in self._metrics_buffer if r.get("session_id") == session_id]

        intent_correct = [r for r in session_records if r["type"] == "intent_classification" and r.get("correct") is not None]
        tool_success = [r for r in session_records if r["type"] == "tool_execution"]

        metrics = {
            "session_id": session_id,
            "total_turns": len(session_records),
            "intent_accuracy": len(intent_correct) / len(session_records) * 100 if session_records else 0,
            "tool_success_rate": len([r for r in tool_success if r["success"]]) / len(tool_success) * 100 if tool_success else 0,
            "avg_retrieval_results": 0,
        }

        retrieval_records = [r for r in session_records if r["type"] == "retrieval"]
        if retrieval_records:
            total_results = sum(r.get("result_count", 0) for r in retrieval_records)
            metrics["avg_retrieval_results"] = total_results / len(retrieval_records)

        return metrics

    def get_global_metrics(self, days: int = 7) -> dict[str, Any]:
        all_records = self._metrics_buffer

        intent_records = [r for r in all_records if r["type"] == "intent_classification"]
        tool_records = [r for r in all_records if r["type"] == "tool_execution"]
        slot_records = [r for r in all_records if r["type"] == "slot_extraction"]

        metrics = {
            "period_days": days,
            "total_interactions": len(all_records),
            "intent_classification": {
                "total": len(intent_records),
                "with_feedback": len([r for r in intent_records if r.get("correct") is not None]),
                "accuracy": 0,
            },
            "tool_execution": {
                "total": len(tool_records),
                "success": len([r for r in tool_records if r.get("success")]),
                "success_rate": 0,
            },
            "slot_extraction": {
                "total": len(slot_records),
                "complete": len([r for r in slot_records if r.get("complete")]),
                "completion_rate": 0,
            },
        }

        if intent_records:
            correct = len([r for r in intent_records if r.get("correct")])
            metrics["intent_classification"]["accuracy"] = correct / len(intent_records) * 100

        if tool_records:
            success = len([r for r in tool_records if r.get("success")])
            metrics["tool_execution"]["success_rate"] = success / len(tool_records) * 100

        if slot_records:
            complete = len([r for r in slot_records if r.get("complete")])
            metrics["slot_extraction"]["completion_rate"] = complete / len(slot_records) * 100

        return metrics

    def _persist_feedback(self, record: dict[str, Any]):
        try:
            from app.models.career import LLMRequestLog

            feedback_log = LLMRequestLog(
                provider="metrics",
                model_name="feedback",
                scene="user_feedback",
                user_id=record.get("user_id"),
                session_id=record.get("session_id"),
                status="feedback",
                latency_ms=0,
                request_id=str(record.get("timestamp", "")),
                raw_meta_json={"feedback": record.get("feedback"), "rating": record.get("rating")},
            )
            self.db.add(feedback_log)
            self.db.commit()
        except Exception:
            self.db.rollback()

    def flush(self):
        self._metrics_buffer.clear()

    def get_intent_distribution(self) -> dict[str, int]:
        distribution = defaultdict(int)
        for record in self._metrics_buffer:
            if record["type"] == "intent_classification":
                intent = record.get("predicted", "unknown")
                distribution[intent] += 1
        return dict(distribution)


def get_metrics_collector(db: Session) -> MetricsCollector:
    return MetricsCollector(db)
