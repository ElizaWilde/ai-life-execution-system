from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class WeeklyPriorityDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2_000)
    target_minutes: int = Field(strict=True, ge=1, le=10_080)
    priority: Literal["low", "medium", "high"] | None = None

    @field_validator("title")
    @classmethod
    def nonblank_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A weekly priority needs a title")
        return value

    @model_validator(mode="after")
    def default_priority(self) -> "WeeklyPriorityDraft":
        if self.priority is None:
            self.priority = "medium"
        return self


class WeeklyPriorityPlan(BaseModel):
    """Validated, bounded batch for the planning service; not daily calendar tasks."""

    model_config = ConfigDict(extra="forbid")

    week_start: date
    week_end: date
    weekly_priorities: list[WeeklyPriorityDraft] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def full_week(self) -> "WeeklyPriorityPlan":
        if self.week_end != self.week_start + timedelta(days=6):
            raise ValueError("Weekly priorities must cover exactly seven days")
        return self
