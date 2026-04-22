from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.auth import Classroom, Department, EnterpriseProfile, Role, User
from app.models.student import Student, StudentCertificate, StudentInternship, StudentProject, StudentSkill


def _upsert_role(db: Session, code: str, name: str, description: str) -> Role:
    role = db.query(Role).filter(Role.code == code).first()
    if not role:
        role = Role(code=code, name=name, description=description)
        db.add(role)
        db.flush()
    role.name = name
    role.description = description
    role.deleted = False
    return role


def _upsert_department(db: Session, name: str, description: str) -> Department:
    department = db.query(Department).filter(Department.name == name).first()
    if not department:
        department = Department(name=name, description=description)
        db.add(department)
        db.flush()
    department.description = description
    department.deleted = False
    return department


def _upsert_classroom(db: Session, name: str, grade: str, department: Department) -> Classroom:
    classroom = db.query(Classroom).filter(Classroom.name == name).first()
    if not classroom:
        classroom = Classroom(name=name, grade=grade, department_id=department.id)
        db.add(classroom)
        db.flush()
    classroom.grade = grade
    classroom.department_id = department.id
    classroom.deleted = False
    return classroom


def _upsert_user(
    db: Session,
    *,
    username: str,
    password: str,
    real_name: str,
    role: Role,
    email: str | None = None,
    phone: str | None = None,
    department: Department | None = None,
    classroom: Classroom | None = None,
) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(username=username, password_hash=get_password_hash(password), real_name=real_name)
        db.add(user)
        db.flush()
    user.password_hash = get_password_hash(password)
    user.real_name = real_name
    user.email = email
    user.phone = phone
    user.role_id = role.id
    user.department_id = department.id if department else None
    user.class_id = classroom.id if classroom else None
    user.is_active = True
    user.deleted = False
    return user


def _upsert_enterprise_profile(db: Session, user: User) -> EnterpriseProfile:
    profile = db.query(EnterpriseProfile).filter(EnterpriseProfile.user_id == user.id).first()
    if not profile:
        profile = db.query(EnterpriseProfile).filter(EnterpriseProfile.company_name == "星联科技有限公司").first()
    if not profile:
        profile = EnterpriseProfile(user_id=user.id, company_name="星联科技有限公司")
        db.add(profile)
        db.flush()
    profile.user_id = user.id
    profile.company_name = "星联科技有限公司"
    profile.company_code = "ENT-001"
    profile.industry = "互联网"
    profile.address = "上海市浦东新区"
    profile.company_type = "成长型企业"
    profile.company_size = "100-499人"
    profile.description = "聚焦校企协同招聘与人才培养。"
    profile.source_doc_ids = profile.source_doc_ids or []
    profile.deleted = False
    return profile


def _upsert_student(db: Session, user: User) -> Student:
    student = db.query(Student).filter(Student.user_id == user.id).first()
    if not student:
        student = Student(user_id=user.id, student_no="2022001", name="张晨")
        db.add(student)
        db.flush()
    student.name = "张晨"
    student.gender = "男"
    student.student_no = "2022001"
    student.grade = "2022"
    student.major = "软件工程"
    student.college = "计算机学院"
    student.phone = "13800000000"
    student.email = "student01@example.com"
    student.interests = ["前端开发", "数据分析", "Java开发"]
    student.target_industry = "互联网"
    student.target_city = "上海"
    student.education_experience = "软件工程本科在读"
    student.bio = "具备基础项目经验，正在围绕目标岗位持续完善能力证据。"
    student.deleted = False
    return student


def _ensure_student_resources(db: Session, student: Student) -> None:
    if not db.query(StudentSkill).filter(StudentSkill.student_id == student.id, StudentSkill.deleted.is_(False)).count():
        db.add_all(
            [
                StudentSkill(student_id=student.id, name="Vue 3", level="熟练", category="前端"),
                StudentSkill(student_id=student.id, name="TypeScript", level="熟练", category="前端"),
                StudentSkill(student_id=student.id, name="Java", level="良好", category="后端"),
                StudentSkill(student_id=student.id, name="SQL", level="良好", category="数据"),
            ]
        )

    if not db.query(StudentCertificate).filter(StudentCertificate.student_id == student.id, StudentCertificate.deleted.is_(False)).count():
        db.add(StudentCertificate(student_id=student.id, name="英语四级", issuer="教育部考试中心"))

    if not db.query(StudentProject).filter(StudentProject.student_id == student.id, StudentProject.deleted.is_(False)).count():
        db.add(
            StudentProject(
                student_id=student.id,
                name="校园可视化平台",
                role="前端负责人",
                technologies=["Vue 3", "TypeScript", "ECharts"],
                outcome="完成核心页面与图表模块交付",
            )
        )

    if not db.query(StudentInternship).filter(StudentInternship.student_id == student.id, StudentInternship.deleted.is_(False)).count():
        db.add(
            StudentInternship(
                student_id=student.id,
                company="星联科技有限公司",
                position="前端实习生",
                skills=["Vue 3", "接口联调", "问题排查"],
                description="参与招聘业务页面重构与交互优化。",
            )
        )


def seed_demo_data() -> None:
    db = SessionLocal()
    try:
        admin_role = _upsert_role(db, "admin", "管理员", "系统管理员")
        student_role = _upsert_role(db, "student", "学生", "学生端用户")
        enterprise_role = _upsert_role(db, "enterprise", "企业", "企业端用户")

        department = _upsert_department(db, "计算机学院", "计算机相关专业院系")
        classroom = _upsert_classroom(db, "软工2201", "2022", department)

        _upsert_user(
            db,
            username="admin",
            password="admin123",
            real_name="系统管理员",
            role=admin_role,
            email="admin@example.com",
        )
        student_user = _upsert_user(
            db,
            username="student01",
            password="student123",
            real_name="张晨",
            role=student_role,
            email="student01@example.com",
            department=department,
            classroom=classroom,
        )
        enterprise_user = _upsert_user(
            db,
            username="enterprise01",
            password="enterprise123",
            real_name="星联HR",
            role=enterprise_role,
            email="enterprise01@example.com",
        )

        _upsert_enterprise_profile(db, enterprise_user)
        student = _upsert_student(db, student_user)
        _ensure_student_resources(db, student)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

