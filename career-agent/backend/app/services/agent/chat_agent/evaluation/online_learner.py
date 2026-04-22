from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session


class OnlineLearner:
    def __init__(self, db: Session):
        self.db = db
        self._feedback_buffer = []
        self._intent_samples = {}
        self._min_samples_for_update = 5

    def add_feedback(
        self,
        user_id: int,
        session_id: int,
        message: str,
        predicted_intent: str,
        corrected_intent: str | None = None,
        is_helpful: bool | None = None,
    ) -> dict[str, Any]:
        feedback = {
            "user_id": user_id,
            "session_id": session_id,
            "message": message,
            "predicted_intent": predicted_intent,
            "corrected_intent": corrected_intent,
            "is_helpful": is_helpful,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._feedback_buffer.append(feedback)

        if corrected_intent and corrected_intent != predicted_intent:
            self._add_intent_sample(corrected_intent, message)

        return feedback

    def _add_intent_sample(self, intent: str, message: str):
        if intent not in self._intent_samples:
            self._intent_samples[intent] = []

        self._intent_samples[intent].append({
            "text": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        self._intent_samples[intent] = self._intent_samples[intent][-100:]

    def should_update_model(self) -> bool:
        for intent, samples in self._intent_samples.items():
            if len(samples) >= self._min_samples_for_update:
                return True
        return False

    def get_new_samples_for_intent(self, intent: str) -> list[dict[str, Any]]:
        return self._intent_samples.get(intent, [])

    def get_all_new_samples(self) -> dict[str, list[dict[str, Any]]]:
        return {
            intent: samples
            for intent, samples in self._intent_samples.items()
            if len(samples) >= self._min_samples_for_update
        }

    def generate_improved_prompt(
        self,
        intent: str,
        original_prompt: str,
    ) -> str:
        samples = self.get_new_samples_for_intent(intent)

        if not samples:
            return original_prompt

        examples_text = "\n".join([
            f"- {s['text']}" for s in samples[-5:]
        ])

        improved_prompt = f"""{original_prompt}

补充学习样本（基于用户反馈）：
{examples_text}

请参考以上样本进行意图识别。"""

        return improved_prompt

    def calculate_confidence_adjustment(
        self,
        intent: str,
        current_confidence: float,
    ) -> float:
        samples = self._intent_samples.get(intent, [])

        if len(samples) < self._min_samples_for_update:
            return current_confidence

        helpful_count = sum(1 for s in samples if s.get("is_helpful") is True)
        neutral_count = sum(1 for s in samples if s.get("is_helpful") is None)
        unhelpful_count = sum(1 for s in samples if s.get("is_helpful") is False)

        total = helpful_count + neutral_count + unhelpful_count
        if total == 0:
            return current_confidence

        helpful_ratio = helpful_count / total

        adjustment = (helpful_ratio - 0.5) * 0.1
        new_confidence = current_confidence + adjustment

        return max(0.3, min(1.0, new_confidence))

    def get_intent_quality_score(self, intent: str) -> dict[str, Any]:
        samples = self._intent_samples.get(intent, [])

        if not samples:
            return {
                "intent": intent,
                "sample_count": 0,
                "quality_score": 0.0,
                "status": "insufficient_data",
            }

        helpful_count = sum(1 for s in samples if s.get("is_helpful") is True)
        neutral_count = sum(1 for s in samples if s.get("is_helpful") is None)
        unhelpful_count = sum(1 for s in samples if s.get("is_helpful") is False)

        quality_score = (helpful_count * 1.0 + neutral_count * 0.5) / len(samples)

        if len(samples) >= 20 and quality_score >= 0.8:
            status = "high_quality"
        elif len(samples) >= 10 and quality_score >= 0.6:
            status = "moderate"
        elif len(samples) >= 5:
            status = "learning"
        else:
            status = "insufficient_data"

        return {
            "intent": intent,
            "sample_count": len(samples),
            "quality_score": round(quality_score, 3),
            "helpful_count": helpful_count,
            "neutral_count": neutral_count,
            "unhelpful_count": unhelpful_count,
            "status": status,
        }

    def get_all_quality_scores(self) -> list[dict[str, Any]]:
        return [
            self.get_intent_quality_score(intent)
            for intent in self._intent_samples.keys()
        ]

    def export_training_data(self) -> dict[str, Any]:
        training_data = {}

        for intent, samples in self._intent_samples.items():
            if len(samples) >= self._min_samples_for_update:
                training_data[intent] = [
                    {"text": s["text"], "label": intent}
                    for s in samples
                ]

        return {
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "intents_count": len(training_data),
            "total_samples": sum(len(v) for v in training_data.values()),
            "training_data": training_data,
        }

    def clear_buffer(self):
        self._feedback_buffer.clear()

    def get_feedback_stats(self) -> dict[str, Any]:
        if not self._feedback_buffer:
            return {
                "total_feedback": 0,
                "correction_count": 0,
                "helpfulness_count": 0,
            }

        correction_count = sum(
            1 for f in self._feedback_buffer
            if f.get("corrected_intent") and f.get("corrected_intent") != f.get("predicted_intent")
        )

        help_count = sum(
            1 for f in self._feedback_buffer
            if f.get("is_helpful") is not None
        )

        return {
            "total_feedback": len(self._feedback_buffer),
            "correction_count": correction_count,
            "helpfulness_count": help_count,
            "intents_with_samples": len(self._intent_samples),
        }


def get_online_learner(db: Session) -> OnlineLearner:
    return OnlineLearner(db)
