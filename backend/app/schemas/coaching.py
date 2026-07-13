from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.daily_check_in import EnergyLevel, MoodLevel

WorkloadLevel = Literal["light", "reduced", "normal"]
RecommendationText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class CoachingContext(BaseModel):
    target_date: date

    energy_level: EnergyLevel | None = None
    mood_level: MoodLevel | None = None
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    stress_level: int | None = Field(default=None, ge=1, le=5)

    planned_tasks: int = Field(ge=0)
    completed_tasks: int = Field(ge=0)
    unfinished_tasks: int = Field(ge=0)

    recent_focus_minutes: int = Field(ge=0)
    recent_completion_rate: float = Field(ge=0, le=1)

    available_minutes: int | None = Field(default=None, ge=0)
    high_priority_tasks: list[str]
    user_notes: str | None = None


class WorkloadAdjustment(BaseModel):
    readiness_score: float = Field(ge=0, le=100)
    workload_multiplier: float = Field(ge=0)
    workload_level: WorkloadLevel
    reasons: list[str]


class CoachingAdvice(BaseModel):
    """Validated JSON contract returned by the coaching LLM prompt."""

    model_config = ConfigDict(extra="forbid")

    summary: RecommendationText
    suggestions: list[RecommendationText]
    risk_factors: list[RecommendationText]
    planning_changes: list[RecommendationText]


class CoachingRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    recommendation_date: date
    readiness_score: float = Field(ge=0, le=100)
    workload_multiplier: float = Field(ge=0)
    workload_level: WorkloadLevel
    adjustment_reasons_json: list[str]
    summary: str
    recommendations_json: CoachingAdvice
    model_name: str | None
    prompt_version: str | None
    created_at: datetime
    updated_at: datetime
