from pydantic import BaseModel, Field


class ReportGeneratePayload(BaseModel):
    target_job_id: int | None = None


class ReportSectionPayload(BaseModel):
    key: str
    title: str
    content: str
    highlights: list[str] = Field(default_factory=list)


class ReportUpdatePayload(BaseModel):
    title: str | None = None
    summary: str | None = None
    sections: list[ReportSectionPayload] | None = None


class ReportRestorePayload(BaseModel):
    version_no: int
