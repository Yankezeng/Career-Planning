from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TimestampSchema(ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class ConfigItem(BaseModel):
    key: str
    value: Any
    description: Optional[str] = None
