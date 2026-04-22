from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.models.auth import EnterpriseProfile, User
from app.models.career import ResumeDelivery
from app.models.student import Student
from app.schemas.career import ReviewPayload
from app.services.graph.career_path_neo4j import CareerPathService
from app.services.growth_tracking_service import GrowthTrackingService
from app.services.job_match_service_clean import JobMatchService
from app.services.optimization_service_clean import OptimizationService
from app.services.report_service_v2_clean import ReportService
from app.services.resume_delivery_service import ResumeDeliveryService
from app.services.review_service import ReviewService
from app.services.student_profile_service_clean import StudentProfileService
from app.utils.response import success_response


router = APIRouter()


def enterprise_student_query(db: Session, current_user: User):
    query = db.query(Student).filter(Student.deleted.is_(False))
    if current_user.role and current_user.role.code == "admin":
        return query

    enterprise_profile = (
        db.query(EnterpriseProfile)
        .filter(EnterpriseProfile.user_id == current_user.id, EnterpriseProfile.deleted.is_(False))
        .first()
    )
    if not enterprise_profile:
        raise HTTPException(status_code=404, detail="当前企业账号尚未绑定企业档案")

    return (
        query.join(ResumeDelivery, ResumeDelivery.student_id == Student.id)
        .filter(
            ResumeDelivery.enterprise_profile_id == enterprise_profile.id,
            ResumeDelivery.deleted.is_(False),
        )
        .distinct()
    )


def ensure_enterprise_can_view_student(db: Session, current_user: User, student_id: int) -> Student:
    student = enterprise_student_query(db, current_user).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="当前企业无法查看该学生")
    return student


@router.get("/students")
def list_students(db: Session = Depends(get_db), current_user=Depends(require_roles("enterprise", "admin"))):
    students = enterprise_student_query(db, current_user).all()
    return success_response(
        [
            {
                "id": student.id,
                "name": student.name,
                "student_no": student.student_no,
                "major": student.major,
                "grade": student.grade,
                "college": student.college,
            }
            for student in students
        ]
    )


@router.get("/students/{student_id}/profile")
def student_profile(student_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles("enterprise", "admin"))):
    ensure_enterprise_can_view_student(db, current_user, student_id)
    return success_response(StudentProfileService(db).get_latest_profile(student_id))


@router.get("/students/{student_id}/report")
def student_report(student_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles("enterprise", "admin"))):
    ensure_enterprise_can_view_student(db, current_user, student_id)
    return success_response(ReportService(db).get_latest_report(student_id))


@router.get("/students/{student_id}/matches")
def student_matches(student_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles("enterprise", "admin"))):
    ensure_enterprise_can_view_student(db, current_user, student_id)
    return success_response(JobMatchService(db).get_matches(student_id))


@router.get("/students/{student_id}/matches/{job_id}")
def student_match_detail(
    student_id: int,
    job_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("enterprise", "admin")),
):
    ensure_enterprise_can_view_student(db, current_user, student_id)
    return success_response(JobMatchService(db).get_match(student_id, job_id))


@router.get("/students/{student_id}/career-path")
def student_career_path(student_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles("enterprise", "admin"))):
    ensure_enterprise_can_view_student(db, current_user, student_id)
    return success_response(CareerPathService(db).get_latest_path(student_id))


@router.get("/students/{student_id}/growth-records")
def student_growth_records(student_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles("enterprise", "admin"))):
    ensure_enterprise_can_view_student(db, current_user, student_id)
    service = GrowthTrackingService(db)
    return success_response({"records": service.list_records(student_id), "trend": service.get_trend(student_id)})


@router.get("/students/{student_id}/optimization/latest")
def student_latest_optimization(student_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles("enterprise", "admin"))):
    ensure_enterprise_can_view_student(db, current_user, student_id)
    return success_response(OptimizationService(db).get_latest_optimization(student_id))


@router.post("/students/{student_id}/review")
def create_review(
    student_id: int,
    payload: ReviewPayload,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("enterprise", "admin")),
):
    ensure_enterprise_can_view_student(db, current_user, student_id)
    review = ReviewService(db).create_review(student_id, current_user.id, payload.model_dump())
    return success_response(review, "企业复评已提交")


@router.get("/deliveries")
def enterprise_deliveries(db: Session = Depends(get_db), current_user=Depends(require_roles("enterprise", "admin"))):
    return success_response(ResumeDeliveryService(db).list_enterprise_deliveries(current_user.id))


@router.get("/dashboard")
def enterprise_dashboard(db: Session = Depends(get_db), current_user=Depends(require_roles("enterprise", "admin"))):
    return success_response(ResumeDeliveryService(db).get_enterprise_board(current_user.id))


@router.get("/deliveries/{delivery_id}")
def enterprise_delivery_detail(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("enterprise", "admin")),
):
    return success_response(ResumeDeliveryService(db).get_enterprise_delivery(current_user.id, delivery_id))


@router.get("/deliveries/{delivery_id}/resume-analysis")
def enterprise_delivery_resume_analysis(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("enterprise", "admin")),
):
    data = ResumeDeliveryService(db).get_enterprise_resume_analysis(current_user.id, delivery_id)
    return success_response(data)
