from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


DIMENSION_KEY_ORDER = (
    "professional_skill",
    "certificate",
    "innovation",
    "learning",
    "stress_resistance",
    "communication",
    "internship",
)
DIMENSION_KEYS = set(DIMENSION_KEY_ORDER)

MATCH_DIMENSION_KEY_ORDER = (
    "basic_requirement",
    "professional_skill",
    "professional_literacy",
    "development_potential",
)
MATCH_DIMENSION_KEYS = set(MATCH_DIMENSION_KEY_ORDER)


class PortraitDimension(BaseModel):
    key: str
    label: str
    score: float = Field(ge=0, le=100)
    description: str = ""

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        if value not in DIMENSION_KEYS:
            raise ValueError(f"unsupported portrait dimension key: {value}")
        return value


class VerticalPathNode(BaseModel):
    level: str
    job_name: str
    description: str
    requirements: list[str] = Field(default_factory=list)
    promotion_condition: str = ""
    path_note: str = ""


class TransferPath(BaseModel):
    target_job_name: str
    relation_type: str
    path_note: str
    required_skills: list[str] = Field(default_factory=list)


class JobPortraitSchema(BaseModel):
    summary: str
    core_skills: list[str] = Field(default_factory=list)
    common_skills: list[str] = Field(default_factory=list)
    certificates: list[str] = Field(default_factory=list)
    degree_requirement: str = ""
    major_requirement: str = ""
    internship_requirement: str = ""
    work_content: str = ""
    development_direction: str = ""
    recommended_courses: list[str] = Field(default_factory=list)
    portrait_dimensions: list[PortraitDimension] = Field(default_factory=list)
    vertical_path: list[VerticalPathNode] = Field(default_factory=list)
    transfer_paths: list[TransferPath] = Field(default_factory=list)
    match_weights: dict[str, float] = Field(default_factory=dict)
    source_companies: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dimensions_and_weights(self) -> "JobPortraitSchema":
        dimension_keys = {item.key for item in self.portrait_dimensions}
        missing_dimensions = DIMENSION_KEYS - dimension_keys
        if missing_dimensions:
            raise ValueError(f"missing portrait dimensions: {sorted(missing_dimensions)}")

        if set(self.match_weights) != MATCH_DIMENSION_KEYS:
            raise ValueError("match_weights must include four match dimensions")
        total = round(sum(float(value) for value in self.match_weights.values()), 6)
        if abs(total - 1.0) > 1e-4:
            raise ValueError("match_weights must sum to 1.0")
        return self


class StudentPortraitSchema(BaseModel):
    dimensions: list[PortraitDimension] = Field(default_factory=list)
    completeness_score: float = Field(ge=0, le=100)
    competitiveness_score: float = Field(ge=0, le=100)
    maturity_level: Literal["起步积累型", "基础提升型", "稳定成长型", "高成熟冲刺型"]
    ability_tags: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    summary: str

    @model_validator(mode="after")
    def validate_dimensions(self) -> "StudentPortraitSchema":
        dimension_keys = {item.key for item in self.dimensions}
        missing_dimensions = DIMENSION_KEYS - dimension_keys
        if missing_dimensions:
            raise ValueError(f"missing student portrait dimensions: {sorted(missing_dimensions)}")
        return self


class MatchDimensionSchema(BaseModel):
    key: str
    label: str
    score: float = Field(ge=0, le=100)
    description: str

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        if value not in MATCH_DIMENSION_KEYS:
            raise ValueError(f"unsupported match dimension key: {value}")
        return value


class MatchSchema(BaseModel):
    total_score: float = Field(ge=0, le=100)
    weights: dict[str, float]
    dimensions: list[MatchDimensionSchema] = Field(default_factory=list)
    key_skill_hit_rate: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_payload(self) -> "MatchSchema":
        if set(self.weights) != MATCH_DIMENSION_KEYS:
            raise ValueError("weights must include four match dimensions")
        total = round(sum(float(value) for value in self.weights.values()), 6)
        if abs(total - 1.0) > 1e-4:
            raise ValueError("weights must sum to 1.0")
        if len(self.dimensions) != len(MATCH_DIMENSION_KEY_ORDER):
            raise ValueError("dimensions must contain four match dimensions")
        return self
