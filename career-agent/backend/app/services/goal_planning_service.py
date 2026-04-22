from sqlalchemy.orm import Session

from app.models.career import CareerGoal
from app.utils.serializers import to_dict


class GoalPlanningService:
    def __init__(self, db: Session):
        self.db = db

    def save_goal(self, student_id: int, payload: dict):
        goal = (
            self.db.query(CareerGoal)
            .filter(CareerGoal.student_id == student_id, CareerGoal.deleted.is_(False))
            .order_by(CareerGoal.id.desc())
            .first()
        )
        if goal:
            for key, value in payload.items():
                setattr(goal, key, value)
        else:
            goal = CareerGoal(student_id=student_id, **payload)
            self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)
        return to_dict(goal)

    def get_goal(self, student_id: int):
        goal = (
            self.db.query(CareerGoal)
            .filter(CareerGoal.student_id == student_id, CareerGoal.deleted.is_(False))
            .order_by(CareerGoal.id.desc())
            .first()
        )
        return to_dict(goal) if goal else None
