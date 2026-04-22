from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Student(Base, TimestampMixin):
    __tablename__ = "students"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    student_no: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    grade: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    major: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    college: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    interests: Mapped[list] = mapped_column(JSON, default=list)
    target_industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    target_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    education_experience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="student")
    skills: Mapped[List["StudentSkill"]] = relationship("StudentSkill", back_populates="student", cascade="all, delete-orphan")
    certificates: Mapped[List["StudentCertificate"]] = relationship("StudentCertificate", back_populates="student", cascade="all, delete-orphan")
    projects: Mapped[List["StudentProject"]] = relationship("StudentProject", back_populates="student", cascade="all, delete-orphan")
    internships: Mapped[List["StudentInternship"]] = relationship("StudentInternship", back_populates="student", cascade="all, delete-orphan")
    competitions: Mapped[List["StudentCompetition"]] = relationship("StudentCompetition", back_populates="student", cascade="all, delete-orphan")
    campus_experiences: Mapped[List["StudentCampusExperience"]] = relationship("StudentCampusExperience", back_populates="student", cascade="all, delete-orphan")
    attachments: Mapped[List["StudentAttachment"]] = relationship("StudentAttachment", back_populates="student", cascade="all, delete-orphan")
    resumes: Mapped[List["StudentResume"]] = relationship("StudentResume", back_populates="student", cascade="all, delete-orphan")
    profiles: Mapped[List["StudentProfile"]] = relationship("StudentProfile", back_populates="student", cascade="all, delete-orphan")
    match_results: Mapped[List["JobMatchResult"]] = relationship("JobMatchResult", back_populates="student", cascade="all, delete-orphan")
    growth_records: Mapped[List["GrowthRecord"]] = relationship("GrowthRecord", back_populates="student", cascade="all, delete-orphan")
    resume_deliveries: Mapped[List["ResumeDelivery"]] = relationship("ResumeDelivery", back_populates="student", cascade="all, delete-orphan")


class StudentSkill(Base, TimestampMixin):
    __tablename__ = "student_skills"

    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("students.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    student: Mapped["Student"] = relationship("Student", back_populates="skills")


class StudentCertificate(Base, TimestampMixin):
    __tablename__ = "student_certificates"

    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("students.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    issuer: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    issued_date: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    score: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    student: Mapped["Student"] = relationship("Student", back_populates="certificates")


class StudentProject(Base, TimestampMixin):
    __tablename__ = "student_projects"

    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("students.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    technologies: Mapped[list] = mapped_column(JSON, default=list)
    outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_date: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    end_date: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    relevance_score: Mapped[float] = mapped_column(Float, default=75)

    student: Mapped["Student"] = relationship("Student", back_populates="projects")


class StudentInternship(Base, TimestampMixin):
    __tablename__ = "student_internships"

    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("students.id"), nullable=False)
    company: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    start_date: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    end_date: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    relevance_score: Mapped[float] = mapped_column(Float, default=75)

    student: Mapped["Student"] = relationship("Student", back_populates="internships")


class StudentCompetition(Base, TimestampMixin):
    __tablename__ = "student_competitions"

    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("students.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    award: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    student: Mapped["Student"] = relationship("Student", back_populates="competitions")


class StudentCampusExperience(Base, TimestampMixin):
    __tablename__ = "student_campus_experiences"

    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("students.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    student: Mapped["Student"] = relationship("Student", back_populates="campus_experiences")


class StudentAttachment(Base, TimestampMixin):
    __tablename__ = "student_attachments"

    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("students.id"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    student: Mapped["Student"] = relationship("Student", back_populates="attachments")
    deliveries: Mapped[List["ResumeDelivery"]] = relationship("ResumeDelivery", back_populates="attachment")
    source_resumes: Mapped[List["StudentResume"]] = relationship("StudentResume", back_populates="source_attachment")
    resume_versions: Mapped[List["StudentResumeVersion"]] = relationship("StudentResumeVersion", back_populates="attachment")


class StudentResume(Base, TimestampMixin):
    __tablename__ = "student_resumes"

    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("students.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    target_job: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    target_industry: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    target_city: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    scene_type: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    source_attachment_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("student_attachments.id"), nullable=True)
    current_version_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("student_resume_versions.id"), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    student: Mapped["Student"] = relationship("Student", back_populates="resumes")
    source_attachment: Mapped[Optional["StudentAttachment"]] = relationship(
        "StudentAttachment",
        back_populates="source_resumes",
        foreign_keys=[source_attachment_id],
    )
    versions: Mapped[List["StudentResumeVersion"]] = relationship(
        "StudentResumeVersion",
        back_populates="resume",
        cascade="all, delete-orphan",
        foreign_keys="StudentResumeVersion.resume_id",
    )
    current_version: Mapped[Optional["StudentResumeVersion"]] = relationship(
        "StudentResumeVersion",
        foreign_keys=[current_version_id],
        post_update=True,
    )
    deliveries: Mapped[List["ResumeDelivery"]] = relationship("ResumeDelivery", back_populates="resume")


class StudentResumeVersion(Base, TimestampMixin):
    __tablename__ = "student_resume_versions"

    resume_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("student_resumes.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    attachment_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("student_attachments.id"), nullable=True)
    parsed_json: Mapped[dict] = mapped_column(JSON, default=dict)
    optimized_json: Mapped[dict] = mapped_column(JSON, default=dict)
    score_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    resume: Mapped["StudentResume"] = relationship(
        "StudentResume",
        back_populates="versions",
        foreign_keys=[resume_id],
    )
    attachment: Mapped[Optional["StudentAttachment"]] = relationship(
        "StudentAttachment",
        back_populates="resume_versions",
        foreign_keys=[attachment_id],
    )
    deliveries: Mapped[List["ResumeDelivery"]] = relationship("ResumeDelivery", back_populates="resume_version")


class StudentProfile(Base, TimestampMixin):
    __tablename__ = "student_profiles"

    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("students.id"), nullable=False)
    professional_score: Mapped[float] = mapped_column(Float, default=0)
    practice_score: Mapped[float] = mapped_column(Float, default=0)
    communication_score: Mapped[float] = mapped_column(Float, default=0)
    learning_score: Mapped[float] = mapped_column(Float, default=0)
    innovation_score: Mapped[float] = mapped_column(Float, default=0)
    professionalism_score: Mapped[float] = mapped_column(Float, default=0)
    ability_tags: Mapped[list] = mapped_column(JSON, default=list)
    strengths: Mapped[list] = mapped_column(JSON, default=list)
    weaknesses: Mapped[list] = mapped_column(JSON, default=list)
    maturity_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_metrics: Mapped[dict] = mapped_column(JSON, default=dict)

    student: Mapped["Student"] = relationship("Student", back_populates="profiles")


class GrowthRecord(Base, TimestampMixin):
    __tablename__ = "growth_records"

    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("students.id"), nullable=False)
    stage_label: Mapped[str] = mapped_column(String(50), nullable=False)
    completed_courses: Mapped[list] = mapped_column(JSON, default=list)
    new_skills: Mapped[list] = mapped_column(JSON, default=list)
    new_certificates: Mapped[list] = mapped_column(JSON, default=list)
    new_projects: Mapped[list] = mapped_column(JSON, default=list)
    new_internships: Mapped[list] = mapped_column(JSON, default=list)
    weekly_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completion_rate: Mapped[float] = mapped_column(Float, default=0)

    student: Mapped["Student"] = relationship("Student", back_populates="growth_records")
    reviews: Mapped[List["ReviewRecord"]] = relationship("ReviewRecord", back_populates="growth_record", cascade="all, delete-orphan")


class ReviewRecord(Base, TimestampMixin):
    __tablename__ = "review_records"

    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("students.id"), nullable=False)
    growth_record_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("growth_records.id"), nullable=True)
    enterprise_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0)
    suggestions: Mapped[list] = mapped_column(JSON, default=list)

    growth_record: Mapped[Optional["GrowthRecord"]] = relationship("GrowthRecord", back_populates="reviews")
