from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Priority = Literal["low", "medium", "high"]
GoalStatus = Literal["active", "completed", "cancelled"]


class WeeklyGoalBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    week_start: date
    week_end: date
    priority: Priority = "medium"
    target_minutes: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_date_range(self) -> "WeeklyGoalBase":
        if self.week_end < self.week_start:
            raise ValueError("week_end must be on or after week_start")
        return self


class WeeklyGoalCreate(WeeklyGoalBase):
    notion_page_id: str | None = Field(default=None, max_length=100)


class WeeklyGoalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    priority: Priority | None = None
    status: GoalStatus | None = None
    target_minutes: int | None = Field(default=None, ge=0)


class WeeklyGoalRead(WeeklyGoalBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    status: GoalStatus
    notion_page_id: str | None
    created_at: datetime
    updated_at: datetime
