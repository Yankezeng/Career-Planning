from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import AuthService
from app.utils.response import success_response


router = APIRouter()


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    return success_response(service.login(payload.username, payload.password))


@router.post("/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    return success_response(service.register(payload.model_dump()), "注册成功")


@router.get("/me")
def me(current_user=Depends(get_current_user)):
    return success_response(AuthService.serialize_user(current_user))
