from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.services.job_capability_decomposer_service import get_job_capability_decomposer_service


router = APIRouter()


@router.get("/jobs/{job_id}/capabilities")
def get_job_capabilities(job_id: int, db: Session = Depends(get_db)):
    service = get_job_capability_decomposer_service(db)
    return service.decompose(job_id)


@router.get("/jobs/{job_id}/skill-priority")
def get_skill_priority(
    job_id: int,
    skills: Optional[str] = None,
    db: Session = Depends(get_db)
):
    service = get_job_capability_decomposer_service(db)
    student_skills = skills.split(",") if skills else []
    return service.get_skill_learning_priority(job_id, student_skills)


@router.get("/jobs/{job_id}/learning-path")
def get_learning_path(job_id: int, db: Session = Depends(get_db)):
    service = get_job_capability_decomposer_service(db)
    capabilities = service.decompose(job_id)
    return {
        "job_id": job_id,
        "job_name": capabilities.get("job_name"),
        "hard_skills": capabilities.get("hard_skills", {}),
        "learning_suggestions": capabilities.get("learning_suggestions", []),
    }


@router.get("/jobs/{job_id}/capability-gap/{student_id}")
def get_capability_gap(
    job_id: int,
    student_id: int,
    skills: Optional[str] = None,
    db: Session = Depends(get_db)
):
    service = get_job_capability_decomposer_service(db)
    student_skills = skills.split(",") if skills else []

    try:
        from app.models.student import StudentProfile
        profile = db.query(StudentProfile).filter(
            StudentProfile.student_id == student_id
        ).first()

        if profile and profile.skills:
            if isinstance(profile.skills, str):
                profile_skills = [s.strip() for s in profile.skills.split(",") if s.strip()]
            elif isinstance(profile.skills, list):
                profile_skills = profile.skills
            else:
                profile_skills = []
            student_skills = profile_skills + student_skills
    except Exception:
        pass

    return service.calculate_capability_gap(job_id, student_skills)
