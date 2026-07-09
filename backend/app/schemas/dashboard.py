from datetime import date

from pydantic import BaseModel, Field

from app.schemas.daily_task import DailyTaskRead


class TimeAllocationPoint(BaseModel):
    label: str
    planned_minutes: int = Field(ge=0)
    focus_minutes: int = Field(ge=0)


class TodayDashboardResponse(BaseModel):
    date: date
    focus_minutes: int = Field(ge=0)
    planned_tasks: int = Field(ge=0)
    completed_tasks: int = Field(ge=0)
    completion_rate: float = Field(ge=0, le=1)
    unfinished_tasks: list[DailyTaskRead]
    time_allocation: list[TimeAllocationPoint]


class DailyFocusPoint(BaseModel):
    date: date
    focus_minutes: int = Field(ge=0)
    planned_minutes: int = Field(ge=0)


class WeekDashboardResponse(BaseModel):
    week_start: date
    week_end: date
    focus_minutes: int = Field(ge=0)
    planned_tasks: int = Field(ge=0)
    completed_tasks: int = Field(ge=0)
    completion_rate: float = Field(ge=0, le=1)
    active_goals: int = Field(ge=0)
    completed_goals: int = Field(ge=0)
    daily_focus: list[DailyFocusPoint]
    time_allocation: list[TimeAllocationPoint]
