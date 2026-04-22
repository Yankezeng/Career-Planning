from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.student_willingness_service import get_student_willingness_service


router = APIRouter()


@router.get("/willingness/{student_id}")
def get_willingness_analysis(student_id: int, db: Session = Depends(get_db)):
    service = get_student_willingness_service(db)
    return service.analyze(student_id)


@router.post("/willingness/{student_id}/survey")
def submit_willingness_survey(
    student_id: int,
    answers: dict,
    db: Session = Depends(get_db)
):
    service = get_student_willingness_service(db)
    return service.submit_survey(student_id, answers)


@router.get("/willingness/{student_id}/details")
def get_willingness_details(student_id: int, db: Session = Depends(get_db)):
    service = get_student_willingness_service(db)
    return service.get_details(student_id)
