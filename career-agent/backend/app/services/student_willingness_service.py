from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.student import Student, StudentProfile, StudentResume
from app.services.llm_service import get_llm_service


class StudentWillingnessService:
    def __init__(self, db: Session):
        self.db = db
        self.llm_service = get_llm_service()

    def analyze(self, student_id: int) -> dict[str, Any]:
        student = self.db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return {"error": "Student not found"}

        intent_score = self._analyze_job_search_intent(student_id)
        target_clarity = self._analyze_target_clarity(student_id)
        action_readiness = self._analyze_action_readiness(student_id)
        competitiveness = self._analyze_competitiveness(student_id)

        overall_score = (
            intent_score * 0.3 +
            target_clarity * 0.3 +
            action_readiness * 0.2 +
            competitiveness * 0.2
        )

        level = self._get_level(overall_score)

        suggestions = self._generate_suggestions(
            intent_score, target_clarity, action_readiness, competitiveness
        )

        return {
            "student_id": student_id,
            "overall_score": round(overall_score, 1),
            "level": level,
            "dimensions": {
                "intent_score": round(intent_score, 1),
                "intent_label": self._get_intent_label(intent_score),
                "target_clarity": round(target_clarity, 1),
                "target_clarity_label": self._get_clarity_label(target_clarity),
                "action_readiness": round(action_readiness, 1),
                "action_readiness_label": self._get_action_label(action_readiness),
                "competitiveness": round(competitiveness, 1),
                "competitiveness_label": self._get_competitiveness_label(competitiveness),
            },
            "suggestions": suggestions,
            "analyzed_at": datetime.now().isoformat(),
        }

    def _analyze_job_search_intent(self, student_id: int) -> float:
        score = 50.0

        profile = self.db.query(StudentProfile).filter(
            StudentProfile.student_id == student_id
        ).first()

        if profile:
            if profile.career_objective:
                score += 15.0
            if profile.self_evaluation:
                score += 10.0

        resume_count = self.db.query(Resume).filter(
            Resume.student_id == student_id,
            Resume.deleted.is_(False)
        ).count()
        if resume_count > 0:
            score += 10.0
        if resume_count >= 2:
            score += 5.0

        try:
            from app.models.career import AssistantSession
            sessions = self.db.query(AssistantSession).filter(
                AssistantSession.user_id == student_id,
                AssistantSession.deleted.is_(False)
            ).count()
            if sessions > 5:
                score += 10.0
            elif sessions > 0:
                score += 5.0
        except Exception:
            pass

        return min(100.0, max(0.0, score))

    def _analyze_target_clarity(self, student_id: int) -> float:
        score = 30.0

        profile = self.db.query(StudentProfile).filter(
            StudentProfile.student_id == student_id
        ).first()

        if profile and profile.career_objective:
            objective = profile.career_objective.lower()
            if any(kw in objective for kw in ["工程师", "开发", "产品", "运营", "数据"]):
                score += 25.0
            if len(objective) > 20:
                score += 15.0
            else:
                score += 10.0
        else:
            resumes = self.db.query(Resume).filter(
                Resume.student_id == student_id,
                Resume.deleted.is_(False)
            ).all()

            for resume in resumes:
                if resume.target_position:
                    score += 20.0
                    break

        resumes = self.db.query(Resume).filter(
            Resume.student_id == student_id,
            Resume.deleted.is_(False)
        ).count()
        if resumes > 0:
            score += 10.0

        return min(100.0, max(0.0, score))

    def _analyze_action_readiness(self, student_id: int) -> float:
        score = 40.0

        profile = self.db.query(StudentProfile).filter(
            StudentProfile.student_id == student_id
        ).first()

        if profile:
            if profile.education:
                score += 10.0

            skills = []
            if profile.skills:
                if isinstance(profile.skills, str):
                    skills = [s.strip() for s in profile.skills.split(",") if s.strip()]
                elif isinstance(profile.skills, list):
                    skills = profile.skills

            if len(skills) >= 3:
                score += 15.0
            elif len(skills) >= 1:
                score += 10.0

        try:
            from app.models.student import StudentResume
            resumes = self.db.query(StudentResume).filter(
                StudentResume.student_id == student_id,
                StudentResume.deleted.is_(False)
            ).all()

            project_count = 0
            internship_count = 0

            for resume in resumes:
                parsed = resume.current_version.parsed_json if resume.current_version else {}
                projects = parsed.get("projects", []) or []
                internships = parsed.get("internships", []) or []
                if projects and len(projects) > 0:
                    project_count += 1
                if internships and len(internships) > 0:
                    internship_count += 1

            if project_count >= 2:
                score += 15.0
            elif project_count >= 1:
                score += 10.0

            if internship_count >= 1:
                score += 10.0
        except Exception:
            pass

        return min(100.0, max(0.0, score))

    def _analyze_competitiveness(self, student_id: int) -> float:
        score = 50.0

        try:
            from app.models.career import StudentAbilityScore
            ability_scores = self.db.query(StudentAbilityScore).filter(
                StudentAbilityScore.student_id == student_id
            ).all()

            if ability_scores:
                total = sum(s.total_score for s in ability_scores) / len(ability_scores)
                score = min(100.0, max(0.0, total))
            else:
                profile = self.db.query(StudentProfile).filter(
                    StudentProfile.student_id == student_id
                ).first()

                if profile and profile.self_evaluation:
                    score = 60.0
        except Exception:
            pass

        return min(100.0, max(0.0, score))

    def _get_level(self, score: float) -> str:
        if score >= 80:
            return "高"
        elif score >= 60:
            return "中"
        else:
            return "低"

    def _get_intent_label(self, score: float) -> str:
        if score >= 80:
            return "强烈"
        elif score >= 60:
            return "较强"
        elif score >= 40:
            return "一般"
        else:
            return "较弱"

    def _get_clarity_label(self, score: float) -> str:
        if score >= 80:
            return "清晰"
        elif score >= 60:
            return "较清晰"
        elif score >= 40:
            return "一般"
        else:
            return "模糊"

    def _get_action_label(self, score: float) -> str:
        if score >= 80:
            return "充分"
        elif score >= 60:
            return "较充分"
        elif score >= 40:
            return "一般"
        else:
            return "不足"

    def _get_competitiveness_label(self, score: float) -> str:
        if score >= 80:
            return "强"
        elif score >= 60:
            return "较强"
        elif score >= 40:
            return "一般"
        else:
            return "较弱"

    def _generate_suggestions(
        self,
        intent_score: float,
        target_clarity: float,
        action_readiness: float,
        competitiveness: float,
    ) -> list[str]:
        suggestions = []

        if intent_score < 60:
            suggestions.append("建议明确自己的求职意向，积极参与校园招聘会和宣讲会")
        if target_clarity < 60:
            suggestions.append("建议深入了解目标岗位的具体要求，完善职业规划")
        if action_readiness < 60:
            suggestions.append("建议积极寻找实习机会，积累实际工作经验")
        if competitiveness < 60:
            suggestions.append("建议提升专业技能，参加相关培训或认证考试")

        if len(suggestions) == 0:
            suggestions.append("继续保持当前状态，关注行业动态和招聘信息的更新")

        return suggestions

    def submit_survey(
        self,
        student_id: int,
        answers: dict[str, Any],
    ) -> dict[str, Any]:
        student = self.db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return {"error": "Student not found"}

        questionnaire_answers = {
            "submitted_at": datetime.now().isoformat(),
            "answers": answers,
        }

        try:
            from app.models.career import StudentWillingness
            willingness = self.db.query(StudentWillingness).filter(
                StudentWillingness.student_id == student_id
            ).first()

            if willingness:
                willingness.questionnaire_answers = questionnaire_answers
                willingness.updated_at = datetime.now()
            else:
                willingness = StudentWillingness(
                    student_id=student_id,
                    questionnaire_answers=questionnaire_answers,
                )
                self.db.add(willingness)

            self.db.commit()

            result = self.analyze(student_id)
            return result

        except Exception as e:
            self.db.rollback()
            return {"error": str(e)}

    def get_details(self, student_id: int) -> dict[str, Any]:
        try:
            from app.models.career import StudentWillingness
            willingness = self.db.query(StudentWillingness).filter(
                StudentWillingness.student_id == student_id
            ).first()

            if not willingness:
                return self.analyze(student_id)

            return {
                "student_id": student_id,
                "questionnaire_answers": willingness.questionnaire_answers,
                "created_at": willingness.created_at.isoformat() if willingness.created_at else None,
                "updated_at": willingness.updated_at.isoformat() if willingness.updated_at else None,
            }

        except Exception:
            return self.analyze(student_id)


def get_student_willingness_service(db: Session) -> StudentWillingnessService:
    return StudentWillingnessService(db)
