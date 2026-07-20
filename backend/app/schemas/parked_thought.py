from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ParkedThoughtCreate(BaseModel):
    content: str = Field(min_length=1, max_length=500)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Thought must not be blank")
        return value


class ParkedThoughtUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=500)
    completed: bool | None = None

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Thought must not be blank")
        return value


class ParkedThoughtRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    content: str
    completed: bool
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
