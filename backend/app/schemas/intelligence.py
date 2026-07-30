from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AutomationAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    action_key: str
    trigger_source: str
    automation_type: str
    service_name: str
    input_json: dict
    decision_json: dict
    records_changed_json: list
    confirmation_status: Literal["not_required", "pending", "confirmed", "rejected"]
    execution_status: Literal["pending", "running", "completed", "failed", "cancelled"]
    failure_reason: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProcrastinationEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    detection_key: str
    detection_type: str
    severity: Literal["low", "medium", "high"]
    evidence_json: list[str]
    related_task_ids_json: list[int]
    confidence: float = Field(ge=0, le=1)
    recommended_intervention: str
    status: Literal["active", "resolved", "dismissed"]
    detected_at: datetime
    resolved_at: datetime | None
    created_at: datetime


class ForecastHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    weekly_goal_id: int
    forecast_key: str
    forecast_date: date
    completion_probability: float = Field(ge=0, le=1)
    risk_level: Literal["low", "medium", "high"]
    remaining_minutes: int = Field(ge=0)
    remaining_days: int = Field(ge=1)
    required_daily_minutes: int = Field(ge=0)
    current_daily_minutes: int = Field(ge=0)
    risk_factors_json: list[str]
    data_json: dict
    recommended_adjustment: str
    actual_outcome: str | None
    predicted_at: datetime
    created_at: datetime
