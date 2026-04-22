from typing import List, Optional

from pydantic import BaseModel, Field


class CareerGoalPayload(BaseModel):
    target_job_id: Optional[int] = None
    target_company_type: Optional[str] = None
    short_term_goal: Optional[str] = None
    medium_term_goal: Optional[str] = None
    mid_long_term_goal: Optional[str] = None
    long_term_goal: Optional[str] = None
    notes: Optional[str] = None


class GenerateCareerPathPayload(BaseModel):
    target_job_id: Optional[int] = None


class ReviewPayload(BaseModel):
    growth_record_id: Optional[int] = None
    comment: Optional[str] = None
    score: float = 80
    suggestions: List[str] = Field(default_factory=list)
