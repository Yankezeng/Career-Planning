from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import TimestampSchema


class StudentBaseUpdate(BaseModel):
    name: str
    gender: Optional[str] = None
    student_no: str
    grade: Optional[str] = None
    major: Optional[str] = None
    college: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    interests: List[str] = Field(default_factory=list)
    target_industry: Optional[str] = None
    target_city: Optional[str] = None
    education_experience: Optional[str] = None
    bio: Optional[str] = None


class SkillPayload(BaseModel):
    name: str
    level: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None


class CertificatePayload(BaseModel):
    name: str
    issuer: Optional[str] = None
    issued_date: Optional[str] = None
    score: Optional[str] = None
    description: Optional[str] = None


class ProjectPayload(BaseModel):
    name: str
    role: Optional[str] = None
    description: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)
    outcome: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    relevance_score: float = 75


class InternshipPayload(BaseModel):
    company: str
    position: str
    description: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    relevance_score: float = 75


class CompetitionPayload(BaseModel):
    name: str
    award: Optional[str] = None
    level: Optional[str] = None
    description: Optional[str] = None


class CampusExperiencePayload(BaseModel):
    title: str
    role: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[str] = None


class GrowthRecordPayload(BaseModel):
    stage_label: str
    completed_courses: List[str] = Field(default_factory=list)
    new_skills: List[str] = Field(default_factory=list)
    new_certificates: List[str] = Field(default_factory=list)
    new_projects: List[str] = Field(default_factory=list)
    new_internships: List[str] = Field(default_factory=list)
    weekly_summary: Optional[str] = None
    completion_rate: float = 0


class StudentResumeCreatePayload(BaseModel):
    title: str
    target_job: Optional[str] = None
    target_industry: Optional[str] = None
    target_city: Optional[str] = None
    scene_type: Optional[str] = None
    is_default: bool = False
    status: Optional[str] = "active"
    source_attachment_id: Optional[int] = None
    summary: Optional[str] = None


class StudentResumeUpdatePayload(BaseModel):
    title: Optional[str] = None
    target_job: Optional[str] = None
    target_industry: Optional[str] = None
    target_city: Optional[str] = None
    scene_type: Optional[str] = None
    is_default: Optional[bool] = None
    status: Optional[str] = None
    current_version_id: Optional[int] = None
    summary: Optional[str] = None


class StudentResumeVersionCreatePayload(BaseModel):
    attachment_id: Optional[int] = None
    parsed_json: dict = Field(default_factory=dict)
    optimized_json: dict = Field(default_factory=dict)
    score_snapshot: dict = Field(default_factory=dict)
    change_summary: Optional[str] = None
    resume_status: Optional[str] = None


class StudentResumeClonePayload(BaseModel):
    title: Optional[str] = None


class StudentResumeFromAttachmentPayload(BaseModel):
    title: Optional[str] = None
    target_job: Optional[str] = None
    target_industry: Optional[str] = None
    target_city: Optional[str] = None
    scene_type: Optional[str] = None
    summary: Optional[str] = None


class StudentResumeOptimizePayload(BaseModel):
    resume_version_id: Optional[int] = None
    change_summary: Optional[str] = None
    target_role: Optional[str] = None
    target_job_id: Optional[int] = None
    job_description: Optional[str] = None


class StudentResumeDeliverPayload(BaseModel):
    resume_version_id: Optional[int] = None
    target_job_id: Optional[int] = None
    knowledge_doc_id: Optional[str] = None
    company_name: Optional[str] = None
    target_job_name: Optional[str] = None
    target_job_category: Optional[str] = None
    delivery_note: Optional[str] = None


class StudentSchema(TimestampSchema):
    name: str
    gender: Optional[str] = None
    student_no: str
    grade: Optional[str] = None
    major: Optional[str] = None
    college: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    interests: List[str]
    target_industry: Optional[str] = None
    target_city: Optional[str] = None
    education_experience: Optional[str] = None
    bio: Optional[str] = None
