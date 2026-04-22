from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class CareerGoal(Base, TimestampMixin):
    __tablename__ = "career_goals"

    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("students.id"), nullable=False)
    target_job_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("jobs.id"), nullable=True)
    target_company_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    short_term_goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    medium_term_goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mid_long_term_goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    long_term_goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class CareerPath(Base, TimestampMixin):
    __tablename__ = "career_paths"

    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("students.id"), nullable=False)
    target_job_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("jobs.id"), nullable=True)
    based_on_match_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("job_match_results.id"), nullable=True)
    overview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active")

    tasks: Mapped[List["CareerPathTask"]] = relationship(
        "CareerPathTask", back_populates="career_path", cascade="all, delete-orphan"
    )


class CareerPathTask(Base, TimestampMixin):
    __tablename__ = "career_path_tasks"

    career_path_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("career_paths.id"), nullable=False)
    stage_label: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    due_hint: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    priority: Mapped[int] = mapped_column(default=3)
    weekly_tasks: Mapped[list] = mapped_column(JSON, default=list)
    related_skills: Mapped[list] = mapped_column(JSON, default=list)
    difficulty_level: Mapped[str] = mapped_column(String(20), default="中", nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    career_path: Mapped["CareerPath"] = relationship("CareerPath", back_populates="tasks")


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("students.id"), nullable=False)
    career_path_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("career_paths.id"), nullable=True)
    match_result_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("job_match_results.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_json: Mapped[dict] = mapped_column(JSON, default=dict)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class ReportVersion(Base, TimestampMixin):
    __tablename__ = "report_versions"

    report_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("reports.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    action: Mapped[str] = mapped_column(String(50), nullable=False, default="save")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_json: Mapped[dict] = mapped_column(JSON, default=dict)
    check_result: Mapped[dict] = mapped_column(JSON, default=dict)


class OptimizationRecord(Base, TimestampMixin):
    __tablename__ = "optimization_records"

    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("students.id"), nullable=False)
    based_on_growth_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("growth_records.id"), nullable=True)
    based_on_review_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("review_records.id"), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggestions: Mapped[list] = mapped_column(JSON, default=list)
    new_profile_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    new_match_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)


class SystemConfig(Base, TimestampMixin):
    __tablename__ = "system_configs"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    config_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ResumeDelivery(Base, TimestampMixin):
    __tablename__ = "resume_deliveries"

    student_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("students.id"), nullable=False)
    attachment_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("student_attachments.id"), nullable=False)
    resume_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("student_resumes.id"), nullable=True)
    resume_version_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("student_resume_versions.id"), nullable=True)
    target_job_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("jobs.id"), nullable=True)
    enterprise_profile_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("enterprise_profiles.id"), nullable=False)
    knowledge_doc_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    target_job_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    target_job_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    match_score: Mapped[float] = mapped_column(Float, default=0)
    delivery_status: Mapped[str] = mapped_column(String(30), default="delivered")
    delivery_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enterprise_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)

    student: Mapped["Student"] = relationship("Student", back_populates="resume_deliveries")
    attachment: Mapped["StudentAttachment"] = relationship("StudentAttachment", back_populates="deliveries")
    resume: Mapped[Optional["StudentResume"]] = relationship("StudentResume", back_populates="deliveries")
    resume_version: Mapped[Optional["StudentResumeVersion"]] = relationship("StudentResumeVersion", back_populates="deliveries")
    job: Mapped[Optional["Job"]] = relationship("Job")
    enterprise_profile: Mapped["EnterpriseProfile"] = relationship("EnterpriseProfile", back_populates="deliveries")


class AssistantSession(Base, TimestampMixin):
    __tablename__ = "assistant_sessions"
    __table_args__ = (
        Index("ix_assistant_sessions_user_deleted_updated_id", "user_id", "deleted", "updated_at", "id"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), default="新任务", nullable=False)
    last_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    state_json: Mapped[dict] = mapped_column(JSON, default=dict)

    messages: Mapped[List["AssistantMessage"]] = relationship(
        "AssistantMessage",
        back_populates="session",
        cascade="all, delete-orphan",
    )


class AssistantMessage(Base, TimestampMixin):
    __tablename__ = "assistant_messages"
    __table_args__ = (
        Index("ix_assistant_messages_session_deleted_created_id", "session_id", "deleted", "created_at", "id"),
    )

    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("assistant_sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    skill: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    knowledge_hits_json: Mapped[list] = mapped_column(JSON, default=list)
    tool_steps_json: Mapped[list] = mapped_column(JSON, default=list)
    result_cards_json: Mapped[list] = mapped_column(JSON, default=list)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict)

    session: Mapped["AssistantSession"] = relationship("AssistantSession", back_populates="messages")


class LLMRequestLog(Base, TimestampMixin):
    __tablename__ = "llm_request_logs"

    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="mock")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, default="mock")
    scene: Mapped[str] = mapped_column(String(100), nullable=False, default="assistant_chat")
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    session_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    input_chars: Mapped[int] = mapped_column(Integer, default=0)
    output_chars: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_usage_json: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_meta_json: Mapped[dict] = mapped_column(JSON, default=dict)
