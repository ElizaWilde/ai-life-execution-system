from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SessionStatus = Literal["running", "paused", "completed", "cancelled"]


class StudySessionStart(BaseModel):
    daily_task_id: int | None = Field(default=None, gt=0)
    subject: str = Field(min_length=1, max_length=255)
    started_at: datetime | None = None


class StudySessionFinish(BaseModel):
    session_id: int = Field(gt=0)
    ended_at: datetime | None = None
    notes: str | None = None


class StudySessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    daily_task_id: int | None
    subject: str
    started_at: datetime
    ended_at: datetime | None
    duration_minutes: int | None = Field(ge=0)
    status: SessionStatus
    notes: str | None
    created_at: datetime

    # This code validates the relationship between started_at and ended_at.
    '''
        This is a decorator, it tells Pydantic after all fields in StudySessionRead have been created and validated, run the following method.
        Pydantic supports model validators because sometimes validation depends on multiple fields, not just one field. An after validator receives the completed model instance.
            e.g. Here, you need to compare two fields: self.started_at & self.ended_at .A simple field constraint such as Field(ge=0) cannot compare these two values. 
    '''
    @model_validator(mode="after")
    # self represents the current StudySessionRead object.
    # The quotation marks make "StudySessionRead" a forward reference because the method appears while the StudySessionRead class is still being defined.
    def validate_time_range(self) -> "StudySessionRead":
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at must be on or after started_at")
        return self
