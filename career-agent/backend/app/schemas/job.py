from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import TimestampSchema


class JobSkillPayload(BaseModel):
    name: str
    importance: int = 3
    category: Optional[str] = None
    description: Optional[str] = None


class JobCertificatePayload(BaseModel):
    name: str
    importance: int = 3
    description: Optional[str] = None


class JobPayload(BaseModel):
    name: str
    category: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    degree_requirement: Optional[str] = None
    major_requirement: Optional[str] = None
    internship_requirement: Optional[str] = None
    work_content: Optional[str] = None
    development_direction: Optional[str] = None
    salary_range: Optional[str] = None
    skill_weight: float = 0.4
    certificate_weight: float = 0.1
    project_weight: float = 0.2
    soft_skill_weight: float = 0.1
    core_skill_tags: List[str] = Field(default_factory=list)
    common_skill_tags: List[str] = Field(default_factory=list)
    certificate_tags: List[str] = Field(default_factory=list)
    job_profile: dict = Field(default_factory=dict)
    skills: List[JobSkillPayload] = Field(default_factory=list)
    certificates: List[JobCertificatePayload] = Field(default_factory=list)


class JobRelationPayload(BaseModel):
    target_job_id: int
    relation_type: str
    reason: Optional[str] = None
    related_skills: List[str] = Field(default_factory=list)
    recommended_courses: List[str] = Field(default_factory=list)
    recommended_certificates: List[str] = Field(default_factory=list)


class JobSkillSchema(TimestampSchema):
    name: str
    importance: int
    category: Optional[str] = None
    description: Optional[str] = None


class JobCertificateSchema(TimestampSchema):
    name: str
    importance: int
    description: Optional[str] = None


class JobSchema(TimestampSchema):
    name: str
    category: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    degree_requirement: Optional[str] = None
    major_requirement: Optional[str] = None
    internship_requirement: Optional[str] = None
    work_content: Optional[str] = None
    development_direction: Optional[str] = None
    salary_range: Optional[str] = None
    skill_weight: float
    certificate_weight: float
    project_weight: float
    soft_skill_weight: float
    core_skill_tags: List[str]
    common_skill_tags: List[str]
    certificate_tags: List[str]
    job_profile: dict
    generated_by_ai: bool
    skills: List[JobSkillSchema] = []
    certificates: List[JobCertificateSchema] = []
