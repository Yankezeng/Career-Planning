from typing import Optional

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserCreateRequest(BaseModel):
    username: str
    password: str
    real_name: str
    role_code: str
    email: Optional[str] = None
    phone: Optional[str] = None
    department_id: Optional[int] = None
    class_id: Optional[int] = None


class RegisterRequest(BaseModel):
    username: str
    password: str
    real_name: str
    role_code: str
    email: Optional[str] = None
    phone: Optional[str] = None
    student_no: Optional[str] = None
    grade: Optional[str] = None
    major: Optional[str] = None
    college: Optional[str] = None
    company_name: Optional[str] = None
    company_type: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    address: Optional[str] = None
