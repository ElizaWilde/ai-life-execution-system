from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


NotificationType = Literal[
    "morning_plan",
    "upcoming_task",
    "missed_task",
    "deadline_warning",
    "evening_check_in",
    "weekly_review",
    "rescheduling_proposal",
    "procrastination_alert",
    "completion_forecast",
]
NotificationStatus = Literal["pending", "sending", "delivered", "failed"]


class NotificationSend(BaseModel):
    notification_type: NotificationType
    subject: str | None = Field(default=None, min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=10_000)
    channel: Literal["email", "telegram"] | None = None
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
    def require_aware_scheduled_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise ValueError("scheduled_at must include a timezone")
        return value


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    notification_type: NotificationType
    channel: Literal["email", "telegram"]
    recipient: str
    subject: str
    message: str
    scheduled_at: datetime
    delivered_at: datetime | None
    last_attempt_at: datetime | None
    status: NotificationStatus
    failure_reason: str | None
    attempt_count: int
    max_attempts: int
    deduplication_key: str | None
    created_at: datetime
    updated_at: datetime
