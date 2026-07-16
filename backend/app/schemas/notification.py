from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.automation_preference import NotificationChannel


NotificationType = Literal[
    "morning_plan",
    "upcoming_task",
    "missed_task",
    "deadline_warning",
    "evening_check_in",
    "weekly_review",
    "rescheduling_proposal",
]
NotificationStatus = Literal["pending", "delivered", "failed"]


class NotificationSend(BaseModel):
    notification_type: NotificationType
    message: str = Field(min_length=1, max_length=4000)
    channel: NotificationChannel | None = None
    scheduled_at: datetime | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Notification message must not be blank")
        return value

    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_at(cls, value: datetime | None) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise ValueError("scheduled_at must include a timezone offset")
        return value


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    notification_type: NotificationType
    channel: NotificationChannel
    message: str
    scheduled_at: datetime
    delivered_at: datetime | None
    status: NotificationStatus
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime
