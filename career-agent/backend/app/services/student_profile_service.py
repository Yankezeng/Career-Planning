from sqlalchemy.orm import Session, joinedload

from app.models.student import Student, StudentProfile
from app.services.ability_scoring_service import AbilityScoringService
from app.services.structured_llm_service import get_structured_llm_service
from app.utils.serializers import to_dict


class StudentProfileService:
    def __init__(self, db: Session):
        self.db = db
        self.scoring_service = AbilityScoringService()

    def generate_profile(self, student_id: int):
        student = (
            self.db.query(Student)
            .options(
                joinedload(Student.skills),
                joinedload(Student.certificates),
                joinedload(Student.projects),
                joinedload(Student.internships),
                joinedload(Student.competitions),
                joinedload(Student.campus_experiences),
                joinedload(Student.growth_records),
            )
            .filter(Student.id == student_id, Student.deleted.is_(False))
            .first()
        )
        if not student:
            raise ValueError("学生不存在")
        result = self.scoring_service.calculate(student)
        profile = StudentProfile(student_id=student_id, **result)
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return to_dict(profile)

    def get_latest_profile(self, student_id: int):
        profile = (
            self.db.query(StudentProfile)
            .filter(StudentProfile.student_id == student_id, StudentProfile.deleted.is_(False))
            .order_by(StudentProfile.id.desc())
            .first()
        )
        return to_dict(profile) if profile else None

    def __init__(self, db: Session):
        self.db = db
        self.scoring_service = AbilityScoringService()
        self.structured_llm = get_structured_llm_service()

    def generate_profile(self, student_id: int):
        student = (
            self.db.query(Student)
            .options(
                joinedload(Student.skills),
                joinedload(Student.certificates),
                joinedload(Student.projects),
                joinedload(Student.internships),
                joinedload(Student.competitions),
                joinedload(Student.campus_experiences),
                joinedload(Student.growth_records),
            )
            .filter(Student.id == student_id, Student.deleted.is_(False))
            .first()
        )
        if not student:
            raise ValueError("学生不存在")

        portrait = self.structured_llm.generate_student_profile(self._build_student_payload(student))
        dimension_scores = {item["key"]: float(item["score"]) for item in portrait["dimensions"]}
        profile = StudentProfile(
            student_id=student_id,
            professional_score=dimension_scores["professional_skill"],
            practice_score=dimension_scores["internship"],
            communication_score=dimension_scores["communication"],
            learning_score=dimension_scores["learning"],
            innovation_score=dimension_scores["innovation"],
            professionalism_score=dimension_scores["stress_resistance"],
            ability_tags=portrait["ability_tags"],
            strengths=portrait["strengths"],
            weaknesses=portrait["weaknesses"],
            maturity_level=portrait["maturity_level"],
            summary=portrait["summary"],
            raw_metrics={
                "completeness_score": portrait["completeness_score"],
                "competitiveness_score": portrait["competitiveness_score"],
                "dimension_scores": portrait["dimensions"],
                "certificate_score": dimension_scores["certificate"],
                "stress_score": dimension_scores["stress_resistance"],
            },
        )
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return to_dict(profile)

    @staticmethod
    def _build_student_payload(student: Student) -> dict[str, object]:
        return {
            "student_id": student.id,
            "name": student.name,
            "major": student.major,
            "college": student.college,
            "target_industry": student.target_industry,
            "target_city": student.target_city,
            "skills": [item.name for item in student.skills if not item.deleted],
            "certificates": [item.name for item in student.certificates if not item.deleted],
            "projects": [
                {
                    "name": item.name,
                    "role": item.role,
                    "technologies": item.technologies or [],
                    "outcome": item.outcome,
                }
                for item in student.projects
                if not item.deleted
            ],
            "internships": [
                {
                    "company": item.company,
                    "position": item.position,
                    "skills": item.skills or [],
                }
                for item in student.internships
                if not item.deleted
            ],
            "competitions": [
                {
                    "name": item.name,
                    "award": item.award,
                    "level": item.level,
                }
                for item in student.competitions
                if not item.deleted
            ],
            "campus_experiences": [
                {"title": item.title, "role": item.role, "duration": item.duration}
                for item in student.campus_experiences
                if not item.deleted
            ],
        }


from app.services.student_profile_service_clean import StudentProfileService  # noqa: E402,F401
