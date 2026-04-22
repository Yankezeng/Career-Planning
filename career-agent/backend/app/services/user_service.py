import json

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.auth import Classroom, Department, Role, User
from app.models.career import Report, SystemConfig
from app.models.job import Job
from app.models.student import Student, StudentProfile


class UserService:
    def __init__(self, db: Session):
        self.db = db

    def list_users(self):
        users = self.db.query(User).filter(User.deleted.is_(False)).all()
        return [
            {
                "id": user.id,
                "username": user.username,
                "real_name": user.real_name,
                "role": user.role.name if user.role else "",
                "email": user.email,
                "phone": user.phone,
                "department": user.department.name if user.department else "",
                "classroom": user.classroom.name if user.classroom else "",
            }
            for user in users
        ]

    def create_user(self, payload: dict):
        role = self.db.query(Role).filter(Role.code == payload["role_code"]).first()
        if payload["role_code"] == "enterprise":
            if role and (role.name != "\u4f01\u4e1a" or role.description != "\u4f01\u4e1a\u62db\u8058\u65b9\u7528\u6237"):
                role.name = "\u4f01\u4e1a"
                role.description = "\u4f01\u4e1a\u62db\u8058\u65b9\u7528\u6237"
                self.db.flush()
            if not role:
                role = Role(code="enterprise", name="\u4f01\u4e1a", description="\u4f01\u4e1a\u62db\u8058\u65b9\u7528\u6237")
                self.db.add(role)
                self.db.flush()
        user = User(
            username=payload["username"],
            password_hash=get_password_hash(payload["password"]),
            real_name=payload["real_name"],
            role_id=role.id if role else None,
            email=payload.get("email"),
            phone=payload.get("phone"),
            department_id=payload.get("department_id"),
            class_id=payload.get("class_id"),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_dashboard_stats(self):
        return {
            "student_count": self.db.query(func.count(Student.id)).scalar() or 0,
            "job_count": self.db.query(func.count(Job.id)).scalar() or 0,
            "profile_count": self.db.query(func.count(StudentProfile.id)).scalar() or 0,
            "report_count": self.db.query(func.count(Report.id)).scalar() or 0,
        }

    def get_departments(self):
        return self.db.query(Department).filter(Department.deleted.is_(False)).all()

    def get_classes(self):
        return self.db.query(Classroom).filter(Classroom.deleted.is_(False)).all()

    def get_configs(self):
        return self.db.query(SystemConfig).filter(SystemConfig.deleted.is_(False)).all()

    def update_configs(self, configs: list[dict]):
        current = {config.key: config for config in self.get_configs()}
        for item in configs:
            value = json.dumps(item["value"], ensure_ascii=False) if isinstance(item["value"], (list, dict)) else str(item["value"])
            config = current.get(item["key"])
            if config:
                config.value = value
                config.description = item.get("description", config.description)
            else:
                self.db.add(
                    SystemConfig(
                        key=item["key"],
                        value=value,
                        description=item.get("description"),
                        config_type="json" if isinstance(item["value"], (list, dict)) else "text",
                    )
                )
        self.db.commit()
        return self.get_configs()
