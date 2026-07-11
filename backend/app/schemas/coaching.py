from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.daily_check_in import EnergyLevel, MoodLevel

WorkloadLevel = Literal["light", "reduced", "normal"]


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
