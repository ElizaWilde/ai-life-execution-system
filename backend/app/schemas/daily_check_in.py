from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


EnergyLevel = Literal["depleted", "low", "steady", "high", "energized"]
MoodLevel = Literal["struggling", "low", "neutral", "good", "great"]
FocusMode = Literal["Deep work", "Meetings", "Study", "Recovery"]


class DailyCheckInBase(BaseModel):
    energy_level: EnergyLevel
    mood_level: MoodLevel
    sleep_hours: float = Field(ge=0, le=24)

    stress_level: int | None = Field(default=None, ge=1, le=5)
    available_minutes: int | None = Field(default=None, ge=0, le=1440)
    focus_mode: FocusMode | None = None
    notes: str | None = Field(default=None, max_length=2000)

    cycle_day: int | None = Field(default=None, ge=1, le=100)
    cycle_notes: str | None = Field(default=None, max_length=1000)


class DailyCheckInCreate(DailyCheckInBase):
    check_in_date: date | None = None


class DailyCheckInUpdate(BaseModel):
    energy_level: EnergyLevel | None = None
    mood_level: MoodLevel | None = None
    sleep_hours: float | None = Field(default=None, ge=0, le=24)

    stress_level: int | None = Field(default=None, ge=1, le=5)
    available_minutes: int | None = Field(default=None, ge=0, le=1440)
    focus_mode: FocusMode | None = None
    notes: str | None = Field(default=None, max_length=2000)

    cycle_day: int | None = Field(default=None, ge=1, le=100)
    cycle_notes: str | None = Field(default=None, max_length=1000)


class DailyCheckInRead(DailyCheckInBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    check_in_date: date
    created_at: datetime
    updated_at: datetime
