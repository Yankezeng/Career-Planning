from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.services.action_plan_service import get_action_plan_service


router = APIRouter()


@router.post("/action-plans/generate")
def generate_action_plan(
    student_id: int,
    target_job_id: int,
    timeline: str = "3 months",
    db: Session = Depends(get_db)
):
    service = get_action_plan_service(db)
    return service.generate_plan(student_id, target_job_id, timeline)


@router.get("/action-plans/{student_id}")
def get_action_plan(student_id: int, db: Session = Depends(get_db)):
    service = get_action_plan_service(db)
    try:
        from app.models.career import ActionPlan
        plan = db.query(ActionPlan).filter(
            ActionPlan.student_id == student_id
        ).order_by(ActionPlan.created_at.desc()).first()

        if plan:
            return {
                "id": plan.id,
                "student_id": plan.student_id,
                "target_job_id": plan.target_job_id,
                "timeline": plan.timeline,
                "daily_plans": plan.daily_plans,
                "weekly_plans": plan.weekly_plans,
                "monthly_plans": plan.monthly_plans,
                "resources": plan.resources,
                "milestones": plan.milestones,
                "created_at": plan.created_at.isoformat() if plan.created_at else None,
            }
    except Exception:
        pass

    return {"error": "No action plan found", "student_id": student_id}


@router.put("/action-plans/{plan_id}/progress")
def update_progress(
    plan_id: int,
    task_id: str,
    completed: bool,
    notes: Optional[str] = None,
    db: Session = Depends(get_db)
):
    service = get_action_plan_service(db)
    return service.update_progress(plan_id, task_id, completed, notes)


@router.get("/action-plans/{plan_id}/resources")
def get_plan_resources(plan_id: int, db: Session = Depends(get_db)):
    service = get_action_plan_service(db)
    stats = service.get_progress_stats(plan_id)

    try:
        from app.models.career import ActionPlan
        plan = db.query(ActionPlan).filter(ActionPlan.id == plan_id).first()
        if plan and plan.resources:
            return {"resources": plan.resources, "progress": stats}
    except Exception:
        pass

    return {"resources": {}, "progress": stats}


@router.get("/action-plans/{plan_id}/milestones")
def get_plan_milestones(plan_id: int, db: Session = Depends(get_db)):
    service = get_action_plan_service(db)
    stats = service.get_progress_stats(plan_id)

    try:
        from app.models.career import ActionPlan
        plan = db.query(ActionPlan).filter(ActionPlan.id == plan_id).first()
        if plan and plan.milestones:
            return {"milestones": plan.milestones, "progress": stats}
    except Exception:
        pass

    return {"milestones": [], "progress": stats}


@router.get("/action-plans/{plan_id}/stats")
def get_plan_stats(plan_id: int, db: Session = Depends(get_db)):
    service = get_action_plan_service(db)
    return service.get_progress_stats(plan_id)
