from fastapi import APIRouter

from app.api import admin, assistant, auth, enterprise, jobs, students_clean as students
from app.api.job_graph import router as job_graph_router


api_router = APIRouter()
api_router.include_router(assistant.router, prefix="/assistant", tags=["AI 助手"])
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["岗位"])
api_router.include_router(students.router, prefix="/students", tags=["学生"])
api_router.include_router(enterprise.router, prefix="/enterprise", tags=["企业"])
api_router.include_router(admin.router, prefix="/admin", tags=["管理端"])
api_router.include_router(job_graph_router, prefix="/graph", tags=["岗位图谱"])

from app.api import willingness, job_capability, action_plan, personalized_plan
api_router.include_router(willingness.router, prefix="/api/v1", tags=["就业意愿"])
api_router.include_router(job_capability.router, prefix="/api/v1", tags=["岗位能力"])
api_router.include_router(action_plan.router, prefix="/api/v1", tags=["行动计划"])
api_router.include_router(personalized_plan.router, prefix="/api/v1", tags=["个性化方案"])
