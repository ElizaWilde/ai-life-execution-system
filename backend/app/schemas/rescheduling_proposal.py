from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ProposalStatus = Literal["pending", "approved", "rejected", "applied", "expired"]
ProposalType = Literal["rollover", "reschedule"]


class ReschedulingProposalItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    daily_task_id: int
    original_date: date
    proposed_date: date
    estimated_minutes: int
    reason: str
    created_at: datetime


class ReschedulingProposalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    proposal_type: ProposalType
    status: ProposalStatus
    reason: str
    expected_minutes: int
    expires_at: datetime
    approved_at: datetime | None
    rejected_at: datetime | None
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime
    items: list[ReschedulingProposalItemRead]


class ReschedulingProposalGenerateRequest(BaseModel):
    horizon_days: int = Field(default=14, ge=1, le=30)
