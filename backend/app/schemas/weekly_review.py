from datetime import date, datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)


ReviewText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class WeeklyReviewGenerateRequest(BaseModel):
    week_start: date | None = None

    @field_validator("week_start")
    @classmethod
    def validate_week_start(cls, value: date | None) -> date | None:
        if value is not None and value.weekday() != 0:
            raise ValueError("week_start must be a Monday")
        return value


class WeeklyReviewContext(BaseModel):
    week_start: date
    week_end: date
    planned_tasks: int = Field(ge=0)
    completed_tasks: int = Field(ge=0)
    unfinished_tasks: int = Field(ge=0)
    completion_rate: float = Field(ge=0, le=1)
    focus_minutes: int = Field(ge=0)
    check_in_days: int = Field(ge=0, le=7)
    average_sleep_hours: float | None = Field(default=None, ge=0, le=24)
    energy_distribution: dict[str, int]
    mood_distribution: dict[str, int]
    completed_task_titles: list[str]
    unfinished_task_titles: list[str]
    study_subjects: list[str]
    check_in_notes: list[str]


class WeeklyReviewAdvice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: ReviewText
    achievements: list[ReviewText]
    obstacles: list[ReviewText]
    next_week_actions: list[ReviewText]


class WeeklyReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    week_start: date
    week_end: date
    planned_tasks: int = Field(ge=0)
    completed_tasks: int = Field(ge=0)
    completion_rate: float = Field(ge=0, le=1)
    focus_minutes: int = Field(ge=0)
    check_in_days: int = Field(ge=0, le=7)
    average_sleep_hours: float | None = Field(default=None, ge=0, le=24)
    energy_distribution_json: dict[str, int]
    mood_distribution_json: dict[str, int]
    summary: str
    achievements_json: list[str]
    obstacles_json: list[str]
    next_week_actions_json: list[str]
    context_json: dict
    model_name: str | None
    prompt_version: str | None
    created_at: datetime
    updated_at: datetime
