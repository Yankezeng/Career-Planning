from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_roles
from app.schemas.job import JobPayload
from app.services.graph.job_graph_neo4j import JobGraphNeo4jService
from app.services.job_profile_service_clean import JobProfileService
from app.services.job_service import JobService
from app.utils.response import success_response
from app.utils.serializers import to_dict


router = APIRouter()


@router.get("")
def list_jobs(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return success_response(JobService(db).list_jobs(current_user))


@router.get("/knowledge-postings")
def list_knowledge_postings(
    page: int = 1,
    page_size: int = 40,
    keyword: str = "",
    category: str = "",
    company: str = "",
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return success_response(
        JobService(db).list_knowledge_postings(
            current_user=current_user,
            page=page,
            page_size=page_size,
            keyword=keyword,
            category=category,
            company=company,
        )
    )


@router.get("/relations/transfer/{source_job_id}/{target_job_id}")
def get_transfer_advice(source_job_id: int, target_job_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    service = JobGraphNeo4jService()
    paths = service.get_transfer_paths(source_job_id, target_job_id)
    return success_response(paths)


@router.post("")
def create_job(payload: JobPayload, db: Session = Depends(get_db), current_user=Depends(require_roles("admin"))):
    job = JobService(db).create_job(payload.model_dump(), current_user.id)
    return success_response(to_dict(job, include=["skills", "certificates"]), "岗位创建成功")


@router.get("/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    job = JobService(db).get_job(job_id, current_user)
    return success_response(to_dict(job, include=["skills", "certificates"]))


@router.put("/{job_id}")
def update_job(job_id: int, payload: JobPayload, db: Session = Depends(get_db), current_user=Depends(require_roles("admin"))):
    job = JobService(db).update_job(job_id, payload.model_dump(), current_user.id)
    return success_response(to_dict(job, include=["skills", "certificates"]), "岗位更新成功")


@router.delete("/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db), _=Depends(require_roles("admin"))):
    JobService(db).delete_job(job_id)
    return success_response(message="岗位删除成功")


@router.post("/{job_id}/generate-profile")
def generate_profile(job_id: int, db: Session = Depends(get_db), _=Depends(require_roles("admin"))):
    job = JobProfileService(db).generate_profile(job_id)
    return success_response(to_dict(job, include=["skills", "certificates"]), "岗位画像生成成功")


@router.get("/{job_id}/relations")
def get_relations(job_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return success_response(JobGraphService(db).get_relations_for_user(job_id, current_user))
