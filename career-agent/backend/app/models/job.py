from typing import List, Optional

from sqlalchemy import BigInteger, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    degree_requirement: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    major_requirement: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    internship_requirement: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    work_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    development_direction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    salary_range: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    skill_weight: Mapped[float] = mapped_column(Float, default=0.4)
    certificate_weight: Mapped[float] = mapped_column(Float, default=0.1)
    project_weight: Mapped[float] = mapped_column(Float, default=0.2)
    soft_skill_weight: Mapped[float] = mapped_column(Float, default=0.1)
    core_skill_tags: Mapped[list] = mapped_column(JSON, default=list)
    common_skill_tags: Mapped[list] = mapped_column(JSON, default=list)
    certificate_tags: Mapped[list] = mapped_column(JSON, default=list)
    job_profile: Mapped[dict] = mapped_column(JSON, default=dict)
    generated_by_ai: Mapped[bool] = mapped_column(default=False)

    skills: Mapped[List["JobSkill"]] = relationship("JobSkill", back_populates="job", cascade="all, delete-orphan")
    certificates: Mapped[List["JobCertificate"]] = relationship(
        "JobCertificate", back_populates="job", cascade="all, delete-orphan"
    )


class JobSkill(Base, TimestampMixin):
    __tablename__ = "job_skills"

    job_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("jobs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    importance: Mapped[int] = mapped_column(default=3)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    job: Mapped["Job"] = relationship("Job", back_populates="skills")


class JobCertificate(Base, TimestampMixin):
    __tablename__ = "job_certificates"

    job_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("jobs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    importance: Mapped[int] = mapped_column(default=3)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    job: Mapped["Job"] = relationship("Job", back_populates="certificates")


class JobMatchResult(Base, TimestampMixin):
    __tablename__ = "job_match_results"

    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("students.id"), nullable=False)
    job_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("jobs.id"), nullable=False)
    total_score: Mapped[float] = mapped_column(Float, default=0)
    major_match: Mapped[float] = mapped_column(Float, default=0)
    skill_match: Mapped[float] = mapped_column(Float, default=0)
    certificate_match: Mapped[float] = mapped_column(Float, default=0)
    project_match: Mapped[float] = mapped_column(Float, default=0)
    internship_match: Mapped[float] = mapped_column(Float, default=0)
    soft_skill_match: Mapped[float] = mapped_column(Float, default=0)
    interest_match: Mapped[float] = mapped_column(Float, default=0)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    student: Mapped["Student"] = relationship("Student", back_populates="match_results")
    job: Mapped["Job"] = relationship("Job")
    gaps: Mapped[List["JobMatchGap"]] = relationship(
        "JobMatchGap", back_populates="match_result", cascade="all, delete-orphan"
    )


class JobMatchGap(Base, TimestampMixin):
    __tablename__ = "job_match_gaps"

    match_result_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("job_match_results.id"), nullable=False)
    gap_type: Mapped[str] = mapped_column(String(50), nullable=False)
    gap_item: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(default=3)

    match_result: Mapped["JobMatchResult"] = relationship("JobMatchResult", back_populates="gaps")
