from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.auth import EnterpriseProfile, Role, User
from app.models.student import Student


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def login(self, username: str, password: str) -> dict:
        user = self.db.query(User).filter(User.username == username, User.deleted.is_(False)).first()
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=400, detail="用户名或密码错误")
        token = create_access_token(user.id)
        return {"access_token": token, "token_type": "bearer", "user": self.serialize_user(user)}

    def register(self, payload: dict) -> dict:
        role_code = (payload.get("role_code") or "").strip().lower()
        if role_code not in {"student", "enterprise"}:
            raise HTTPException(status_code=400, detail="公开注册仅支持学生和企业账号")

        username = (payload.get("username") or "").strip()
        password = payload.get("password") or ""
        real_name = (payload.get("real_name") or "").strip()
        if not username:
            raise HTTPException(status_code=400, detail="用户名不能为空")
        if len(password) < 6:
            raise HTTPException(status_code=400, detail="密码长度不能少于 6 位")
        if not real_name:
            raise HTTPException(status_code=400, detail="姓名不能为空")

        existing_user = self.db.query(User).filter(User.username == username, User.deleted.is_(False)).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="该用户名已被注册")

        role = self._ensure_role(role_code)
        user = User(
            username=username,
            password_hash=get_password_hash(password),
            real_name=real_name,
            role_id=role.id,
            email=(payload.get("email") or "").strip() or None,
            phone=(payload.get("phone") or "").strip() or None,
            is_active=True,
            deleted=False,
        )
        self.db.add(user)
        self.db.flush()

        if role_code == "student":
            self._create_student_profile(user, payload)
        else:
            self._create_enterprise_profile(user, payload)

        self.db.commit()
        self.db.refresh(user)
        token = create_access_token(user.id)
        return {"access_token": token, "token_type": "bearer", "user": self.serialize_user(user)}

    def _ensure_role(self, role_code: str) -> Role:
        role = self.db.query(Role).filter(Role.code == role_code, Role.deleted.is_(False)).first()
        if role:
            return role
        if role_code == "student":
            role = Role(code="student", name="学生", description="学生用户")
        else:
            role = Role(code="enterprise", name="企业", description="企业招聘方用户")
        self.db.add(role)
        self.db.flush()
        return role

    def _create_student_profile(self, user: User, payload: dict) -> None:
        student_no = (payload.get("student_no") or "").strip()
        if not student_no:
            raise HTTPException(status_code=400, detail="学生注册必须填写学号")
        existing_student = self.db.query(Student).filter(Student.student_no == student_no, Student.deleted.is_(False)).first()
        if existing_student:
            raise HTTPException(status_code=400, detail="该学号已存在")

        student = Student(
            user_id=user.id,
            name=user.real_name,
            student_no=student_no,
            grade=(payload.get("grade") or "").strip() or None,
            major=(payload.get("major") or "").strip() or None,
            college=(payload.get("college") or "").strip() or None,
            phone=user.phone,
            email=user.email,
            interests=[],
        )
        self.db.add(student)

    def _create_enterprise_profile(self, user: User, payload: dict) -> None:
        company_name = (payload.get("company_name") or "").strip()
        if not company_name:
            raise HTTPException(status_code=400, detail="企业注册必须填写企业名称")
        existing_profile = (
            self.db.query(EnterpriseProfile)
            .filter(EnterpriseProfile.company_name == company_name, EnterpriseProfile.deleted.is_(False))
            .first()
        )
        if existing_profile:
            raise HTTPException(status_code=400, detail="该企业名称已存在")

        profile = EnterpriseProfile(
            user_id=user.id,
            company_name=company_name,
            company_type=(payload.get("company_type") or "").strip() or None,
            company_size=(payload.get("company_size") or "").strip() or None,
            industry=(payload.get("industry") or "").strip() or None,
            address=(payload.get("address") or "").strip() or None,
            source_doc_ids=[],
        )
        self.db.add(profile)

    @staticmethod
    def serialize_user(user: User) -> dict:
        return {
            "id": user.id,
            "username": user.username,
            "real_name": user.real_name,
            "role": user.role.code if user.role else None,
            "role_name": user.role.name if user.role else None,
            "department_id": user.department_id,
            "class_id": user.class_id,
        }
