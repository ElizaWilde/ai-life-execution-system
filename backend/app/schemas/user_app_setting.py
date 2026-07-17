from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Integration = Literal["Google Calendar", "Notion", "Telegram", "Gmail"]


class UserAppSettingFields(BaseModel):
    week_start: Literal["Monday", "Sunday"] = "Monday"
    focus_minutes: Literal[25, 45, 60] = 25
    short_break_minutes: Literal[5, 10] = 5
    long_break_minutes: Literal[15, 30] = 15
    workload: Literal["light", "medium", "high"] = "medium"
    theme: Literal["light", "dark", "auto"] = "light"
    tone: Literal["supportive", "direct", "reflective"] = "supportive"
    strictness: Literal["flexible", "balanced", "strict"] = "balanced"
    adjustment: Literal["gentle", "moderate", "strong"] = "moderate"
    proactive: bool = True
    focus_matters: bool = True
    protect_deep_work: bool = True
    learn_from_feedback: bool = True
    integrations: list[Integration] = Field(default_factory=list, max_length=4)
    avatar_data_url: str | None = Field(default=None, max_length=2_000_000)

    @field_validator("integrations")
    @classmethod
    def validate_unique_integrations(cls, value: list[Integration]) -> list[Integration]:
        if len(value) != len(set(value)):
            raise ValueError("Integrations must not contain duplicates")
        return value


class UserAppSettingUpdate(UserAppSettingFields):
    pass


class UserAppSettingRead(UserAppSettingFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
