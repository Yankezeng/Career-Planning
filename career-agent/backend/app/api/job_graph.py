from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.job_graph_api_service import get_job_graph_api_service


router = APIRouter()
service = get_job_graph_api_service()


class JobGraphQuery(BaseModel):
    enterprise_id: int | None = None
    category: str | None = None
    limit: int = 100


class JobDetailQuery(BaseModel):
    job_id: int


@router.get("/job-graph")
async def get_job_graph(enterprise_id: int | None = None, category: str | None = None, limit: int = 100):
    try:
        data = service.get_job_graph_data(
            enterprise_id=enterprise_id,
            category=category,
            limit=limit
        )
        return {"code": 0, "data": data, "message": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/job-graph/check")
async def check_job_graph():
    try:
        has_data = service.check_has_data()
        return {"code": 0, "data": {"has_neo4j_data": has_data}, "message": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/job-graph/detail/{job_id}")
async def get_job_detail(job_id: int):
    try:
        detail = service.get_job_detail(job_id)
        if not detail:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"code": 0, "data": detail, "message": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
