from sqlalchemy.orm import Session

from app.models.student import ReviewRecord
from app.utils.serializers import to_dict


class ReviewService:
    def __init__(self, db: Session):
        self.db = db

    def list_reviews(self, student_id: int):
        reviews = (
            self.db.query(ReviewRecord)
            .filter(ReviewRecord.student_id == student_id, ReviewRecord.deleted.is_(False))
            .order_by(ReviewRecord.id.desc())
            .all()
        )
        return [to_dict(review) for review in reviews]

    def create_review(self, student_id: int, enterprise_id: int, payload: dict):
        review = ReviewRecord(student_id=student_id, enterprise_id=enterprise_id, **payload)
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        return to_dict(review)
