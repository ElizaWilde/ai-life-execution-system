from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ReviewSource = Literal["manual", "ai"]


class DailyReviewGenerateRequest(BaseModel):
    review_date: date | None = None


class DailyReviewCreate(BaseModel):
    review_date: date
    summary: str = Field(min_length=1)
    tomorrow_adjustment: str | None = None
    source: ReviewSource = "manual"


class DailyReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    review_date: date
    summary: str
    tomorrow_adjustment: str | None
    planned_tasks: int = Field(ge=0)
    completed_tasks: int = Field(ge=0)
    focus_minutes: int = Field(ge=0)
    source: ReviewSource
    created_at: datetime
    updated_at: datetime
