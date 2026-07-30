from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.coaching import WorkloadLevel


class EstimationCalibrationRead(BaseModel):
    factor: float = Field(gt=0)
    sample_count: int = Field(ge=0)
    planned_minutes: int = Field(ge=0)
    actual_minutes: int = Field(ge=0)
    confidence: Literal["none", "low", "medium", "high"]


class DailyPreviewTask(BaseModel):
    title: str
    description: str | None = None
    estimated_minutes: int = Field(ge=0)
    original_estimated_minutes: int = Field(ge=0)
    priority: Literal["low", "medium", "high"]
    weekly_goal_id: int


class DailyPlanPreviewCreate(BaseModel):
    target_date: date
    available_minutes: int = Field(gt=0, le=1_440)
    user_instruction: str | None = Field(default=None, max_length=1_000)
    base_preview_id: int | None = Field(default=None, gt=0)


class DailyPlanPreviewRead(BaseModel):
    id: int
    status: Literal["pending", "confirmed", "expired"]
    target_date: date
    input_minutes: int
    recommended_minutes: int
    calibration: EstimationCalibrationRead
    workload_level: WorkloadLevel
    readiness_score: float
    tasks: list[DailyPreviewTask]
    expires_at: datetime
    confirmed_at: datetime | None
    created_at: datetime


class WeeklyGoalAllocation(BaseModel):
    weekly_goal_id: int
    title: str
    priority: Literal["low", "medium", "high"]
    current_minutes: int = Field(ge=0)
    recommended_minutes: int = Field(ge=0)


class DailyCapacityAllocation(BaseModel):
    date: date
    minutes: int = Field(ge=0)


class WeeklyPlanPreviewCreate(BaseModel):
    week_start: date
    intended_minutes: int = Field(gt=0, le=10_080)


class WeeklyPlanPreviewRead(BaseModel):
    id: int
    status: Literal["pending", "confirmed", "expired"]
    week_start: date
    week_end: date
    intended_minutes: int
    recommended_minutes: int
    historical_weekly_focus_minutes: int
    historical_completion_rate: float = Field(ge=0, le=1)
    calibration: EstimationCalibrationRead
    rationale: list[str]
    goal_allocations: list[WeeklyGoalAllocation]
    daily_allocations: list[DailyCapacityAllocation]
    expires_at: datetime
    confirmed_at: datetime | None
    created_at: datetime


class PlanPreviewRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    preview_type: Literal["daily", "weekly"]
    status: Literal["pending", "confirmed", "expired"]
    target_date: date
    input_minutes: int
    recommended_minutes: int
    calibration_factor: float
    payload_json: dict
    expires_at: datetime
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime
