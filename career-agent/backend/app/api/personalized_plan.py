from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.services.personalized_plan_service import get_personalized_plan_service


router = APIRouter()


@router.post("/personalized-plans/generate")
def generate_personalized_plan(
    student_id: int,
    target_job_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    service = get_personalized_plan_service(db)
    return service.generate(student_id, target_job_id)


@router.get("/personalized-plans/{student_id}")
def get_personalized_plan(student_id: int, db: Session = Depends(get_db)):
    service = get_personalized_plan_service(db)
    return service.generate(student_id)


@router.get("/personalized-plans/{student_id}/strengths")
def get_strengths(student_id: int, db: Session = Depends(get_db)):
    service = get_personalized_plan_service(db)
    result = service.generate(student_id)
    return {"strengths": result.get("strengths", [])}


@router.get("/personalized-plans/{student_id}/weaknesses")
def get_weaknesses(
    student_id: int,
    target_job_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    service = get_personalized_plan_service(db)
    result = service.generate(student_id, target_job_id)
    return {"weaknesses": result.get("weaknesses", [])}


@router.get("/personalized-plans/{student_id}/report")
def get_personalized_report(student_id: int, db: Session = Depends(get_db)):
    service = get_personalized_plan_service(db)
    result = service.generate(student_id)
    return result.get("personalized_report", {})
