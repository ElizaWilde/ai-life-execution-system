from datetime import datetime, time
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


NotificationChannel = Literal["in_app", "email", "telegram"]
WorkingDay = Literal[
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


class StudyPeriod(BaseModel):
    start: time
    end: time

    @model_validator(mode="after")
    def validate_period(self) -> "StudyPeriod":
        if self.start == self.end:
            raise ValueError("Study period start and end must be different")
        return self


class AutomationPreferenceFields(BaseModel):
    timezone: str = Field(default="Asia/Singapore", min_length=1, max_length=100)
    morning_reminder_time: time = time(8, 0)
    evening_review_time: time = time(21, 0)
    notification_channel: NotificationChannel = "email"
    telegram_chat_id: str | None = Field(default=None, max_length=40)
    automatic_rescheduling_enabled: bool = False
    confirmation_required: bool = True
    max_reminders_per_day: int = Field(default=3, ge=0, le=20)
    quiet_hours_start: time = time(22, 0)
    quiet_hours_end: time = time(7, 0)
    working_days: list[WorkingDay] = Field(
        default_factory=lambda: [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
        ],
        min_length=1,
        max_length=7,
    )
    preferred_study_periods: list[StudyPeriod] = Field(default_factory=list, max_length=5)

    @field_validator("telegram_chat_id")
    @classmethod
    def validate_telegram_chat_id(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        if not normalized.lstrip("-").isdigit():
            raise ValueError("Telegram chat ID must be numeric")
        return normalized

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Timezone must be a valid IANA timezone") from exc
        return value

    @field_validator("working_days")
    @classmethod
    def validate_unique_working_days(cls, value: list[WorkingDay]) -> list[WorkingDay]:
        if len(value) != len(set(value)):
            raise ValueError("Working days must not contain duplicates")
        return value


class AutomationPreferenceUpdate(BaseModel):
    timezone: str | None = Field(default=None, min_length=1, max_length=100)
    morning_reminder_time: time | None = None
    evening_review_time: time | None = None
    notification_channel: NotificationChannel | None = None
    telegram_chat_id: str | None = Field(default=None, max_length=40)
    automatic_rescheduling_enabled: bool | None = None
    confirmation_required: bool | None = None
    max_reminders_per_day: int | None = Field(default=None, ge=0, le=20)
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    working_days: list[WorkingDay] | None = Field(default=None, min_length=1, max_length=7)
    preferred_study_periods: list[StudyPeriod] | None = Field(default=None, max_length=5)

    @field_validator("telegram_chat_id")
    @classmethod
    def validate_telegram_chat_id(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        if not normalized.lstrip("-").isdigit():
            raise ValueError("Telegram chat ID must be numeric")
        return normalized

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Timezone must be a valid IANA timezone") from exc
        return value

    @field_validator("working_days")
    @classmethod
    def validate_unique_working_days(
        cls,
        value: list[WorkingDay] | None,
    ) -> list[WorkingDay] | None:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("Working days must not contain duplicates")
        return value


class AutomationPreferenceRead(AutomationPreferenceFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
