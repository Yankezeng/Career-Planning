import json
from datetime import datetime, timedelta
from random import choice, randint, uniform
from sqlalchemy.orm import Session

from app.core.database import engine, SessionLocal
from app.models import *  # noqa: F401, F403
from app.models.auth import Classroom, Department, EnterpriseProfile, Role, User
from app.models.career import ResumeDelivery, SystemConfig
from app.models.job import Job, JobCertificate, JobMatchResult, JobSkill
from app.models.student import (
    GrowthRecord,
    ReviewRecord,
    Student,
    StudentAttachment,
    StudentCampusExperience,
    StudentCertificate,
    StudentCompetition,
    StudentInternship,
    StudentProfile,
    StudentProject,
    StudentSkill,
)

JOB_RELATIONS = [
    ("软件开发", "高级开发", "promotion"),
    ("前端开发", "前端专家", "promotion"),
]


def seed_all(db: Session) -> None:
    print("[Seed] Starting database seeding...")
    _ensure_roles(db)
    _ensure_departments(db)
    _ensure_classrooms(db)
    _ensure_admin_user(db)
    _ensure_students(db)
    _ensure_jobs(db)
    _ensure_job_relations_disabled(db, {})
    _ensure_enterprises(db)
    print("[Seed] Done!")


def _ensure_roles(db: Session) -> None:
    Role.get_or_40X(db, name="student", description="学生")
    Role.get_or_40X(db, name="enterprise", description="企业")
    Role.get_or_40X(db, name="admin", description="管理员")


def _ensure_departments(db: Session) -> None:
    Department.get_or_40X(db, name="计算机学院", code="CS")
    Department.get_or_40X(db, name="软件学院", code="SE")


def _ensure_classrooms(db: Session) -> None:
    cs = db.query(Department).filter(Department.code == "CS").first()
    Classroom.get_or_40X(db, name="计科1班", code="CS001", department_id=cs.id)
    Classroom.get_or_40X(db, name="计科2班", code="CS002", department_id=cs.id)


def _ensure_admin_user(db: Session) -> None:
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        admin = User(
            username="admin",
            email="admin@example.com",
            password_hash="hashed_not_available",
            role_name="admin",
            is_active=True,
        )
        db.add(admin)
        db.flush()


def _ensure_students(db: Session) -> None:
    for i in range(1, 21):
        username = f"student{i}"
        if db.query(Student).filter(Student.username == username).first():
            continue
        student = Student(
            username=username,
            email=f"student{i}@example.com",
            password_hash="hashed_not_available",
            role_name="student",
            name=f"学生{i}",
            gender=choice(["male", "female", "other"]),
            phone=f"1380000{i:04d}",
            department_id=1,
            major=f"计算机科学与技术",
            class_id=i % 2 + 1,
            graduation_year=2025 + (i % 3),
            is_active=True,
        )
        db.add(student)
        db.flush()
        _add_student_profile(db, student)


def _add_student_profile(db: Session, student: Student) -> None:
    profile = StudentProfile(
        student_id=student.id,
        summary=f"{student.name}是一名应届毕业生，对职业发展充满热情。",
        target_industry="互联网",
        target_city="北京",
        target_position="软件开发工程师",
        maturity_level="intermediate",
        ability_tags=["Python", "Java", "SQL"],
        strengths=["学习能力强", "技术热情高"],
        weaknesses=["经验不足"],
    )
    db.add(profile)
    db.flush()


def _ensure_jobs(db: Session) -> None:
    JOBS = [
        ("软件开发", "互联网", "15-25K", ["Python", "Java", "SQL", "Git"], ["计算机专业"]),
        ("Java开发工程师", "互联网", "18-30K", ["Java", "Spring", "MySQL", "Redis", "微服务"], ["Java相关"]),
        ("前端开发", "互联网", "15-28K", ["JavaScript", "Vue", "React", "CSS"], ["前端相关"]),
        ("UI设计师", "互联网", "12-22K", ["Figma", "Sketch", "Photoshop", "UI设计", "交互设计"], ["设计相关"]),
        ("高级开发", "互联网", "25-45K", ["系统设计", "架构", "Java", "Python"], ["计算机专业"]),
        ("前端专家", "互联网", "30-50K", ["TypeScript", "React", "性能优化"], ["前端相关"]),
    ]
    for name, industry, salary, skills, certificates in JOBS:
        if not db.query(Job).filter(Job.name == name).first():
            job = Job(name=name, industry=industry, salary_range=salary, description=f"{name}岗位")
            for skill in skills:
                job.skills.append(JobSkill(name=skill, importance=3))
            for cert in certificates:
                job.certificates.append(JobCertificate(name=cert, importance=4))
            db.add(job)
    db.flush()


# _ensure_job_relations 已迁移到 Neo4j，暂时禁用
def _ensure_job_relations_disabled(db: Session, jobs: dict) -> None:
    pass


def _ensure_enterprises(db: Session) -> None:
    for i in range(1, 6):
        name = f"企业{i}"
        if db.query(EnterpriseProfile).filter(EnterpriseProfile.name == name).first():
            continue
        ep = EnterpriseProfile(
            username=f"enterprise{i}",
            email=f"hr{i}@company.com",
            password_hash="hashed_not_available",
            name=name,
            industry="互联网",
            city="北京",
            description=f"{name}是一家知名互联网公司",
            verified=True,
        )
        db.add(ep)
    db.flush()


if __name__ == "__main__":
    with SessionLocal() as db:
        seed_all(db)
    print("Seeding completed!")
