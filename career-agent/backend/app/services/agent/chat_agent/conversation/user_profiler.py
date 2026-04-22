from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.auth import User


class UserProfiler:
    def __init__(self, db: Session):
        self.db = db
        self._profile_cache = {}

    def get_profile(self, user_id: int) -> dict[str, Any]:
        if user_id in self._profile_cache:
            return self._profile_cache[user_id]

        profile = {
            "user_id": user_id,
            "preferred_style": "brief",
            "frequent_intents": [],
            "skill_interests": [],
            "query_history": [],
            "last_active": None,
            "interaction_count": 0,
        }

        self._load_from_history(profile, user_id)

        self._profile_cache[user_id] = profile
        return profile

    def update_profile(
        self,
        user_id: int,
        intent: str | None = None,
        query: str | None = None,
        style_preference: str | None = None,
    ) -> dict[str, Any]:
        profile = self.get_profile(user_id)

        if intent:
            frequent_intents = profile.get("frequent_intents", [])
            if intent in frequent_intents:
                pass
            else:
                frequent_intents.append(intent)
            profile["frequent_intents"] = frequent_intents[-10:]

        if query:
            query_history = profile.get("query_history", [])
            query_history.append({
                "query": query,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            profile["query_history"] = query_history[-20:]

        if style_preference:
            profile["preferred_style"] = style_preference

        profile["last_active"] = datetime.now(timezone.utc).isoformat()
        profile["interaction_count"] = profile.get("interaction_count", 0) + 1

        self._profile_cache[user_id] = profile
        self._persist_profile(profile)

        return profile

    def get_personalized_context(
        self,
        user_id: int,
        current_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        current_context = current_context or {}
        profile = self.get_profile(user_id)

        frequent_intents = profile.get("frequent_intents", [])
        preferred_style = profile.get("preferred_style", "brief")

        skill_interests = profile.get("skill_interests", [])
        if not skill_interests and frequent_intents:
            skill_interests = self._infer_skill_interests(frequent_intents)

        personalized = {
            "user_preference": {
                "preferred_style": preferred_style,
                "frequent_intents": frequent_intents[-3:] if frequent_intents else [],
                "skill_interests": skill_interests,
            },
            "personalization_hints": self._generate_hints(profile, current_context),
        }

        return personalized

    def _load_from_history(self, profile: dict[str, Any], user_id: int):
        try:
            from app.models.career import AssistantMessage, AssistantSession

            sessions = (
                self.db.query(AssistantSession)
                .filter(
                    AssistantSession.user_id == user_id,
                    AssistantSession.deleted.is_(False),
                )
                .order_by(AssistantSession.updated_at.desc())
                .limit(50)
                .all()
            )

            if sessions:
                profile["last_active"] = sessions[0].updated_at.isoformat() if sessions[0].updated_at else None
                profile["interaction_count"] = len(sessions)

            session_ids = [s.id for s in sessions]
            if session_ids:
                messages = (
                    self.db.query(AssistantMessage)
                    .filter(
                        AssistantMessage.session_id.in_(session_ids),
                        AssistantMessage.deleted.is_(False),
                        AssistantMessage.role == "assistant",
                    )
                    .order_by(AssistantMessage.created_at.desc())
                    .limit(100)
                    .all()
                )

                intents = []
                for msg in messages:
                    if msg.skill:
                        intents.append(msg.skill)
                profile["frequent_intents"] = list(dict.fromkeys(intents))[-10:]

        except Exception:
            pass

    def _persist_profile(self, profile: dict[str, Any]):
        pass

    def _infer_skill_interests(self, intents: list[str]) -> list[str]:
        skill_mapping = {
            "resume-workbench": ["简历撰写", "简历优化"],
            "profile-insight": ["能力评估", "技能分析"],
            "match-center": ["岗位推荐", "人岗匹配"],
            "gap-analysis": ["技能差距", "能力短板"],
            "growth-planner": ["职业发展", "成长规划"],
            "report-builder": ["职业报告", "规划报告"],
            "interview-training": ["面试准备", "面试技巧"],
        }

        interests = []
        for intent in intents[-5:]:
            mapped = skill_mapping.get(intent, [])
            interests.extend(mapped)

        return list(dict.fromkeys(interests))[:5]

    def _generate_hints(
        self,
        profile: dict[str, Any],
        current_context: dict[str, Any],
    ) -> list[str]:
        hints = []
        interaction_count = profile.get("interaction_count", 0)

        if interaction_count < 3:
            hints.append("新用户引导：可以询问用户的职业目标")

        frequent_intents = profile.get("frequent_intents", [])
        if frequent_intents:
            last_intent = frequent_intents[-1]
            if last_intent == "match-center":
                hints.append("用户关注岗位匹配，可以主动提供差距分析")
            elif last_intent == "growth-planner":
                hints.append("用户关注成长路径，可以追踪执行进度")

        preferred_style = profile.get("preferred_style", "brief")
        if preferred_style == "brief":
            hints.append("用户偏好简洁回答，应控制回复长度")

        return hints

    def clear_cache(self, user_id: int | None = None):
        if user_id:
            self._profile_cache.pop(user_id, None)
        else:
            self._profile_cache.clear()


def get_user_profiler(db: Session) -> UserProfiler:
    return UserProfiler(db)
