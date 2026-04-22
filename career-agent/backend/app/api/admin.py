import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.schemas.auth import UserCreateRequest
from app.schemas.common import ConfigItem
from app.services.system_monitor_service import SystemMonitorService
from app.services.user_service import UserService
from app.utils.response import success_response


router = APIRouter()


@router.get("/users")
def list_users(db: Session = Depends(get_db), _=Depends(require_roles("admin"))):
    return success_response(UserService(db).list_users())


@router.post("/users")
def create_user(payload: UserCreateRequest, db: Session = Depends(get_db), _=Depends(require_roles("admin"))):
    user = UserService(db).create_user(payload.model_dump())
    return success_response({"id": user.id, "username": user.username}, "用户创建成功")


@router.get("/stats/dashboard")
def dashboard_stats(db: Session = Depends(get_db), _=Depends(require_roles("admin"))):
    return success_response(UserService(db).get_dashboard_stats())


@router.get("/stats/control-center")
def control_center_stats(db: Session = Depends(get_db), _=Depends(require_roles("admin"))):
    return success_response(SystemMonitorService(db).get_control_center())


@router.get("/llm/overview")
def llm_overview(db: Session = Depends(get_db), _=Depends(require_roles("admin"))):
    return success_response(SystemMonitorService(db).get_llm_overview())


@router.get("/llm/usage/trend")
def llm_usage_trend(
    mode: str = "24h",
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
):
    return success_response(SystemMonitorService(db).get_llm_usage_trend(mode=mode))


@router.get("/llm/logs")
def llm_logs(
    page: int = 1,
    page_size: int = 20,
    limit: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
):
    return success_response(SystemMonitorService(db).get_llm_logs(page=page, page_size=page_size, limit=limit))


@router.post("/llm/ping")
def llm_ping(db: Session = Depends(get_db), _=Depends(require_roles("admin"))):
    return success_response(SystemMonitorService(db).ping_llm())


@router.get("/configs")
def list_configs(db: Session = Depends(get_db), _=Depends(require_roles("admin"))):
    configs = UserService(db).get_configs()
    parsed = []
    for item in configs:
        value = item.value
        try:
            if isinstance(value, str) and value.startswith(("[", "{")):
                value = json.loads(value)
        except json.JSONDecodeError:
            value = item.value
        parsed.append({"key": item.key, "value": value, "description": item.description})
    return success_response(
        parsed
    )


@router.put("/configs")
def update_configs(payload: list[ConfigItem], db: Session = Depends(get_db), _=Depends(require_roles("admin"))):
    configs = UserService(db).update_configs([item.model_dump() for item in payload])
    return success_response([{"key": item.key, "value": item.value, "description": item.description} for item in configs], "配置更新成功")


@router.get("/departments")
def list_departments(db: Session = Depends(get_db), _=Depends(require_roles("admin"))):
    departments = UserService(db).get_departments()
    return success_response([{"id": item.id, "name": item.name, "description": item.description} for item in departments])


@router.get("/classes")
def list_classes(db: Session = Depends(get_db), _=Depends(require_roles("admin"))):
    classes = UserService(db).get_classes()
    return success_response(
        [{"id": item.id, "name": item.name, "grade": item.grade, "department_id": item.department_id} for item in classes]
    )
