from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


PhaseStatus = Literal["planning", "active", "completed", "archived"]
MilestoneStatus = Literal["not_started", "in_progress", "completed"]


class MilestoneBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    due_date: date | None = None
    status: MilestoneStatus = "not_started"
    progress: int = Field(default=0, ge=0, le=100)
    position: int = Field(default=0, ge=0)


class MilestoneCreate(MilestoneBase):
    pass


class MilestoneUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    due_date: date | None = None
    status: MilestoneStatus | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    position: int | None = Field(default=None, ge=0)


class MilestoneRead(MilestoneBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phase_id: int
    created_at: datetime
    updated_at: datetime


class PhaseBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    start_date: date
    end_date: date
    status: PhaseStatus = "planning"
    progress: int = Field(default=0, ge=0, le=100)
    estimated_focus_minutes: int = Field(default=0, ge=0)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "PhaseBase":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class PhaseCreate(PhaseBase):
    pass


class PhaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: PhaseStatus | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    estimated_focus_minutes: int | None = Field(default=None, ge=0)
    notes: str | None = None


class PhaseRead(PhaseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    milestones: list[MilestoneRead]
    created_at: datetime
    updated_at: datetime
