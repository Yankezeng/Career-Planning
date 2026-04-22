from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, get_db, require_roles
from app.models.student import Student, StudentAttachment, StudentResume, StudentResumeVersion
from app.schemas.career import CareerGoalPayload, GenerateCareerPathPayload
from app.schemas.delivery import ResumeDeliveryCreatePayload
from app.schemas.report import ReportGeneratePayload, ReportRestorePayload, ReportUpdatePayload
from app.schemas.student import (
    CampusExperiencePayload,
    CertificatePayload,
    CompetitionPayload,
    GrowthRecordPayload,
    InternshipPayload,
    ProjectPayload,
    SkillPayload,
    StudentResumeClonePayload,
    StudentResumeCreatePayload,
    StudentResumeDeliverPayload,
    StudentResumeFromAttachmentPayload,
    StudentResumeOptimizePayload,
    StudentResumeUpdatePayload,
    StudentResumeVersionCreatePayload,
    StudentBaseUpdate,
)
from app.services.career_goal_recommendation_service import CareerGoalRecommendationService
from app.services.graph.career_path_neo4j import CareerPathService
from app.services.goal_planning_service import GoalPlanningService
from app.services.growth_tracking_service import GrowthTrackingService
from app.services.agent_tool_registry import AgentToolRegistry
from app.services.job_match_service_clean import JobMatchService
from app.services.optimization_service_clean import OptimizationService
from app.services.persona_image_asset_service import PersonaImageAssetService
from app.services.report_service_v2_clean import ReportService
from app.services.resume_delivery_service import ResumeDeliveryService
from app.services.resume_optimizer_service import ResumeOptimizerService
from app.services.resume_profile_pipeline_service import ResumeProfilePipelineService
from app.services.review_service import ReviewService
from app.services.student_profile_service_clean import StudentProfileService
from app.services.student_service import StudentService
from app.utils.response import success_response


router = APIRouter()


@router.get("/profile/persona-images/{code}")
def get_persona_image(code: str, db: Session = Depends(get_db)):
    asset = PersonaImageAssetService(db).get_asset(code)
    return Response(
        content=asset.image_data,
        media_type=asset.mime_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


def _current_student_id(db: Session, user_id: int) -> int:
    student = db.query(Student).filter(Student.user_id == user_id, Student.deleted.is_(False)).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    return student.id


def _resolve_export_attachment_id(
    *,
    db: Session,
    student_id: int,
    attachment_id: int,
    resume_id: int | None = None,
    resume_version_id: int | None = None,
) -> int:
    """Resolve export target attachment with resume/version priority."""
    if resume_version_id:
        version = (
            db.query(StudentResumeVersion)
            .join(StudentResume, StudentResume.id == StudentResumeVersion.resume_id)
            .filter(
                StudentResumeVersion.id == int(resume_version_id),
                StudentResumeVersion.deleted.is_(False),
                StudentResume.id == StudentResumeVersion.resume_id,
                StudentResume.student_id == student_id,
                StudentResume.deleted.is_(False),
            )
            .first()
        )
        if not version:
            raise HTTPException(status_code=404, detail="resume version not found")
        if not version.attachment_id:
            raise HTTPException(status_code=400, detail="resume version has no attachment")
        return int(version.attachment_id)

    if resume_id:
        resume = (
            db.query(StudentResume)
            .options(joinedload(StudentResume.current_version))
            .filter(
                StudentResume.id == int(resume_id),
                StudentResume.student_id == student_id,
                StudentResume.deleted.is_(False),
            )
            .first()
        )
        if not resume:
            raise HTTPException(status_code=404, detail="resume not found")
        current_attachment_id = getattr(getattr(resume, "current_version", None), "attachment_id", None)
        if current_attachment_id:
            return int(current_attachment_id)
        if resume.source_attachment_id:
            return int(resume.source_attachment_id)

    attachment = (
        db.query(StudentAttachment)
        .filter(
            StudentAttachment.id == int(attachment_id),
            StudentAttachment.student_id == student_id,
            StudentAttachment.deleted.is_(False),
        )
        .first()
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="attachment not found")
    return int(attachment.id)


def _register_resource_routes(resource: str, schema_cls):
    @router.get(f"/me/{resource}")
    def list_items(db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
        student_id = _current_student_id(db, current_user.id)
        return success_response(StudentService(db).list_resource(student_id, resource))

    @router.post(f"/me/{resource}")
    def create_item(payload: schema_cls, db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
        student_id = _current_student_id(db, current_user.id)
        return success_response(StudentService(db).create_resource(student_id, resource, payload.model_dump()), "创建成功")

    @router.put(f"/me/{resource}" + "/{item_id}")
    def update_item(item_id: int, payload: schema_cls, db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
        student_id = _current_student_id(db, current_user.id)
        return success_response(StudentService(db).update_resource(student_id, resource, item_id, payload.model_dump()), "更新成功")

    @router.delete(f"/me/{resource}" + "/{item_id}")
    def delete_item(item_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
        student_id = _current_student_id(db, current_user.id)
        StudentService(db).delete_resource(student_id, resource, item_id)
        return success_response(message="删除成功")


_register_resource_routes("projects", ProjectPayload)
_register_resource_routes("skills", SkillPayload)
_register_resource_routes("certificates", CertificatePayload)
_register_resource_routes("internships", InternshipPayload)
_register_resource_routes("competitions", CompetitionPayload)
_register_resource_routes("campus-experiences", CampusExperiencePayload)


@router.get("/me")
def get_me(db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    return success_response(StudentService(db).get_me(current_user.id))


@router.put("/me")
def update_me(payload: StudentBaseUpdate, db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    return success_response(StudentService(db).update_me(current_user.id, payload.model_dump()), "个人信息已更新")


@router.get("/me/attachments")
def list_attachments(db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(StudentService(db).list_resource(student_id, "attachments"))


@router.post("/me/attachments")
def upload_attachment(
    file: UploadFile = File(...),
    description: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("student")),
):
    student_id = _current_student_id(db, current_user.id)
    return success_response(StudentService(db).upload_attachment(student_id, file, description), "附件上传成功")


@router.delete("/me/attachments/{item_id}")
def delete_attachment(item_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    StudentService(db).delete_resource(student_id, "attachments", item_id)
    return success_response(message="附件删除成功")


@router.get("/me/resumes")
def list_resumes(db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(StudentService(db).list_resumes(student_id))


@router.post("/me/resumes")
def create_resume(
    payload: StudentResumeCreatePayload,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("student")),
):
    student_id = _current_student_id(db, current_user.id)
    return success_response(StudentService(db).create_resume(student_id, payload.model_dump()), "created")


@router.put("/me/resumes/{resume_id}")
def update_resume(
    resume_id: int,
    payload: StudentResumeUpdatePayload,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("student")),
):
    student_id = _current_student_id(db, current_user.id)
    return success_response(
        StudentService(db).update_resume(student_id, resume_id, payload.model_dump(exclude_none=True)),
        "updated",
    )


@router.delete("/me/resumes/{resume_id}")
def delete_resume(resume_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    StudentService(db).delete_resume(student_id, resume_id)
    return success_response(message="简历删除成功")


@router.get("/me/resumes/{resume_id}/versions")
def list_resume_versions(resume_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(StudentService(db).list_resume_versions(student_id, resume_id))


@router.post("/me/resumes/{resume_id}/versions")
def create_resume_version(
    resume_id: int,
    payload: StudentResumeVersionCreatePayload,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("student")),
):
    student_id = _current_student_id(db, current_user.id)
    return success_response(StudentService(db).create_resume_version(student_id, resume_id, payload.model_dump()), "created")


@router.post("/me/resumes/{resume_id}/clone")
def clone_resume(
    resume_id: int,
    payload: StudentResumeClonePayload,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("student")),
):
    student_id = _current_student_id(db, current_user.id)
    return success_response(StudentService(db).clone_resume(student_id, resume_id, payload.model_dump(exclude_none=True)), "cloned")


@router.post("/me/resumes/{resume_id}/set-default")
def set_default_resume(resume_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(StudentService(db).set_default_resume(student_id, resume_id), "updated")


@router.post("/me/resumes/from-attachment/{attachment_id}")
def create_resume_from_attachment(
    attachment_id: int,
    payload: StudentResumeFromAttachmentPayload,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("student")),
):
    student_id = _current_student_id(db, current_user.id)
    return success_response(
        StudentService(db).create_resume_from_attachment(student_id, attachment_id, payload.model_dump(exclude_none=True)),
        "created",
    )


@router.post("/me/resumes/{resume_id}/optimize")
def optimize_resume_by_resume(
    resume_id: int,
    payload: StudentResumeOptimizePayload,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("student")),
):
    student_id = _current_student_id(db, current_user.id)
    return success_response(
        StudentService(db).optimize_resume_by_resume(student_id, resume_id, payload.model_dump(exclude_none=True)),
        "optimized",
    )


@router.post("/me/resumes/{resume_id}/deliver")
def deliver_resume_by_resume(
    resume_id: int,
    payload: StudentResumeDeliverPayload,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("student")),
):
    student_id = _current_student_id(db, current_user.id)
    return success_response(
        StudentService(db).deliver_resume_by_resume(student_id, resume_id, payload.model_dump(exclude_none=True)),
        "delivered",
    )


@router.post("/me/resume/parse/{attachment_id}")
def parse_resume(attachment_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(StudentService(db).parse_resume(attachment_id, student_id), "简历解析完成")


@router.post("/me/resume/ingest/{attachment_id}")
def ingest_resume_to_profile(attachment_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    result = ResumeProfilePipelineService(db).ingest_resume(student_id, attachment_id)
    return success_response(result, "简历内容已同步到画像")


@router.get("/me/resume-delivery/targets")
def resume_delivery_targets(db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(ResumeDeliveryService(db).list_targets(student_id))


@router.get("/me/resume-deliveries")
def my_resume_deliveries(db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(ResumeDeliveryService(db).list_student_deliveries(student_id))


@router.post("/me/resume-deliveries")
def create_resume_delivery(
    payload: ResumeDeliveryCreatePayload,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("student")),
):
    student_id = _current_student_id(db, current_user.id)
    return success_response(ResumeDeliveryService(db).create_delivery(student_id, payload.model_dump()), "简历投递成功")


@router.post("/me/resume/optimize/{attachment_id}")
def optimize_resume(
    attachment_id: int,
    target_role: str | None = None,
    target_job_id: int | None = None,
    job_description: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("student")),
):
    student_id = _current_student_id(db, current_user.id)
    options = {
        "target_role": target_role,
        "target_job_id": target_job_id,
        "job_description": job_description,
    }
    return success_response(ResumeOptimizerService(db).optimize_resume(student_id, attachment_id, options=options), "简历优化完成")


@router.get("/me/resume/preview/{attachment_id}")
def preview_resume_pdf(attachment_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(ResumeOptimizerService(db).get_pdf_preview_images(student_id, attachment_id))


@router.get("/me/resume/export/word/{attachment_id}")
def export_resume_word(
    attachment_id: int,
    resume_id: int | None = None,
    resume_version_id: int | None = None,
    target_role: str | None = None,
    target_job_id: int | None = None,
    job_description: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("student")),
):
    student_id = _current_student_id(db, current_user.id)
    resolved_attachment_id = _resolve_export_attachment_id(
        db=db,
        student_id=student_id,
        attachment_id=attachment_id,
        resume_id=resume_id,
        resume_version_id=resume_version_id,
    )
    options = {
        "resume_id": resume_id,
        "resume_version_id": resume_version_id,
        "target_role": target_role,
        "target_job_id": target_job_id,
        "job_description": job_description,
    }
    output_path = ResumeOptimizerService(db).export_editable_word(student_id, resolved_attachment_id, options=options)
    return FileResponse(
        path=output_path,
        filename=output_path.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get("/me/resume/export/pdf/{attachment_id}")
def export_resume_pdf(
    attachment_id: int,
    resume_id: int | None = None,
    resume_version_id: int | None = None,
    target_role: str | None = None,
    target_job_id: int | None = None,
    job_description: str | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("student")),
):
    student_id = _current_student_id(db, current_user.id)
    resolved_attachment_id = _resolve_export_attachment_id(
        db=db,
        student_id=student_id,
        attachment_id=attachment_id,
        resume_id=resume_id,
        resume_version_id=resume_version_id,
    )
    options = {
        "resume_id": resume_id,
        "resume_version_id": resume_version_id,
        "target_role": target_role,
        "target_job_id": target_job_id,
        "job_description": job_description,
    }
    output_path = ResumeOptimizerService(db).export_pdf(student_id, resolved_attachment_id, options=options)
    return FileResponse(path=output_path, filename=output_path.name, media_type="application/pdf")


@router.post("/me/profile/generate")
def generate_profile(db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    profile = StudentProfileService(db).generate_profile(student_id)
    AgentToolRegistry(db).image_generator_agent.generate_for_student(student_id=student_id, profile=profile)
    return success_response(StudentProfileService(db).get_latest_profile(student_id), "画像生成成功")


@router.get("/me/profile")
def get_profile(db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(StudentProfileService(db).get_latest_profile(student_id))


@router.post("/me/profile/image/generate")
def generate_profile_image(db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    data = AgentToolRegistry(db).image_generator_agent.generate_for_student(student_id=student_id)
    return success_response(data, "画像图生成成功")


@router.get("/me/profile/image")
def get_profile_image(db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    data = AgentToolRegistry(db).image_generator_agent.get_latest_profile_image(student_id)
    return success_response(data)


@router.post("/me/matches/generate")
def generate_matches(db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(JobMatchService(db).generate_matches(student_id), "岗位匹配已生成")


@router.get("/me/matches")
def get_matches(db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(JobMatchService(db).get_matches(student_id))


@router.get("/me/matches/{job_id}")
def get_match(job_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(JobMatchService(db).get_match(student_id, job_id))


@router.post("/me/career-goals")
def save_goal(payload: CareerGoalPayload, db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(GoalPlanningService(db).save_goal(student_id, payload.model_dump()), "职业目标已保存")


@router.get("/me/career-goals")
def get_goal(db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(GoalPlanningService(db).get_goal(student_id))


@router.get("/me/career-goals/recommendations")
def get_goal_recommendations(top_k: int = 5, db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(CareerGoalRecommendationService(db).get_recommendations(student_id, top_k=top_k))


@router.post("/me/career-path/generate")
def generate_path(payload: GenerateCareerPathPayload, db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(CareerPathService(db).generate_path(student_id, payload.target_job_id), "成长路径已生成")


@router.get("/me/career-path")
def get_path(db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(CareerPathService(db).get_latest_path(student_id))


@router.post("/me/career-path/progress")
def get_path_progress(db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(CareerPathService(db).get_progress_summary(student_id))


@router.post("/me/career-path/tasks/{task_id}/complete")
def complete_task(task_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(CareerPathService(db).complete_task(student_id, task_id), "任务已标记完成")


@router.post("/me/career-path/re-evaluate")
def re_evaluate_path(db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(CareerPathService(db).re_evaluate_path(student_id), "路径已重新评估")


@router.post("/me/report/generate")
def generate_report(payload: ReportGeneratePayload, db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(ReportService(db).generate_report(student_id, payload.target_job_id), "报告生成成功")


@router.get("/me/report/latest")
def latest_report(db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(ReportService(db).get_latest_report(student_id))


@router.get("/reports/{report_id}/preview")
def preview_report(report_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    report_service = ReportService(db)
    report = report_service.get_report(report_id)
    return success_response(
        {
            "id": report.id,
            "title": report.title,
            "html": report.content_html,
            "summary": report.summary,
            "content_json": report.content_json,
            "check_result": report_service.check_report(report_id),
        }
    )


@router.put("/reports/{report_id}")
def update_report(
    report_id: int,
    payload: ReportUpdatePayload,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("student")),
):
    student_id = _current_student_id(db, current_user.id)
    report_service = ReportService(db)
    report = report_service.get_report(report_id)
    if report.student_id != student_id:
        raise HTTPException(status_code=403, detail="当前学生无权编辑该报告")
    return success_response(report_service.update_report(report_id, payload.model_dump(exclude_none=True)), "报告内容已更新")


@router.post("/reports/{report_id}/polish")
def polish_report(report_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    report_service = ReportService(db)
    report = report_service.get_report(report_id)
    if report.student_id != student_id:
        raise HTTPException(status_code=403, detail="当前学生无权润色该报告")
    return success_response(report_service.polish_report(report_id), "报告内容已润色")


@router.get("/reports/{report_id}/check")
def check_report(report_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    report_service = ReportService(db)
    report = report_service.get_report(report_id)
    if report.student_id != student_id:
        raise HTTPException(status_code=403, detail="当前学生无权检查该报告")
    return success_response(report_service.check_report(report_id))


@router.get("/reports/{report_id}/versions")
def list_report_versions(report_id: int, db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    report_service = ReportService(db)
    report = report_service.get_report(report_id)
    if report.student_id != student_id:
        raise HTTPException(status_code=403, detail="当前学生无权查看该报告版本")
    return success_response(report_service.list_versions(report_id))


@router.post("/reports/{report_id}/restore")
def restore_report_version(
    report_id: int,
    payload: ReportRestorePayload,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("student")),
):
    student_id = _current_student_id(db, current_user.id)
    report_service = ReportService(db)
    report = report_service.get_report(report_id)
    if report.student_id != student_id:
        raise HTTPException(status_code=403, detail="当前学生无权恢复该报告版本")
    return success_response(report_service.restore_version(report_id, payload.version_no), "报告版本已恢复")


@router.get("/reports/{report_id}/export/pdf")
def export_report_pdf(report_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    report_service = ReportService(db)
    report_service.ensure_export_ready(report_id)
    report = report_service.get_report(report_id)
    return FileResponse(path=report.pdf_path, filename=Path(report.pdf_path).name, media_type="application/pdf")


@router.get("/me/growth-records")
def growth_records(db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    growth_service = GrowthTrackingService(db)
    return success_response({"records": growth_service.list_records(student_id), "trend": growth_service.get_trend(student_id)})


@router.post("/me/growth-records")
def create_growth_record(payload: GrowthRecordPayload, db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(GrowthTrackingService(db).create_record(student_id, payload.model_dump()), "成长记录已创建")


@router.get("/me/reviews")
def my_reviews(db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(ReviewService(db).list_reviews(student_id))


@router.get("/me/re-optimization/latest")
def latest_optimization(db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(OptimizationService(db).get_latest_optimization(student_id))


@router.post("/me/re-optimization")
def re_optimize(db: Session = Depends(get_db), current_user=Depends(require_roles("student"))):
    student_id = _current_student_id(db, current_user.id)
    return success_response(OptimizationService(db).re_optimize(student_id), "优化建议已生成")

