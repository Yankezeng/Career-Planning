from typing import Optional

from pydantic import BaseModel


class ResumeDeliveryCreatePayload(BaseModel):
    attachment_id: int
    resume_id: Optional[int] = None
    resume_version_id: Optional[int] = None
    target_job_id: Optional[int] = None
    knowledge_doc_id: Optional[str] = None
    company_name: Optional[str] = None
    target_job_name: Optional[str] = None
    target_job_category: Optional[str] = None
    delivery_note: Optional[str] = None
