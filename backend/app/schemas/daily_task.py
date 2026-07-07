from datetime import date, datetime
from typing import Literal

'''
    Pydantix is a data validation(验证) and settings management library for Python, based on Python type annotations.
    (SQLAlchemy model describes the database table.)Pydantic model describes the data entering or leaving the API.
    What Pydantic does:
        1. Validate data
        2. Convert data types into the correct Python type
        3. Work with FastAPI
    Why need Pydantic:
        Pydantic is like a gatekeeper(守门人).
        In a backend project, data moves like this:

Frontend JSON
    ↓
FastAPI endpoint
    ↓
Pydantic validation
    ↓
Python service logic
    ↓
SQLAlchemy database model
    ↓
Database

        For response:
        
Database
    ↓
SQLAlchemy object
    ↓
Pydantic response schema
    ↓
JSON response to frontend
'''
from pydantic import BaseModel, ConfigDict, Field

# Literal means the value must be one of the exact values you list.
Priority = Literal["low", "medium", "high"]
TaskStatus = Literal["pending", "in_progress", "completed", "cancelled"]
TaskSource = Literal["manual", "ai", "notion"]


class DailyTaskBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    # = None means this gives it a default value
    description: str | None = None
    task_date: date
    # ge=0 and gt=0 are validation constraints(验证约束) in Pydantic Field.
    # ge means greater than or equal to. gt means greater than.
    estimated_minutes: int | None = Field(default=None, ge=0)
    priority: Priority = "medium"
    weekly_goal_id: int | None = Field(default=None, gt=0)


class DailyTaskCreate(DailyTaskBase):
    source: TaskSource = "manual"


class DailyPlanGenerateRequest(BaseModel):
    available_minutes: int = Field(gt=0, le=1_440)
    task_date: date | None = None


class DailyTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    estimated_minutes: int | None = Field(default=None, ge=0)
    priority: Priority | None = None
    status: TaskStatus | None = None
    weekly_goal_id: int | None = Field(default=None, gt=0)


class DailyTaskRead(DailyTaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    status: TaskStatus
    source: TaskSource
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DailyPlanResponse(BaseModel):
    task_date: date
    # tasks must be a list, and every item in the list must be a DailyTaskRead object.
    tasks: list[DailyTaskRead]
    total_estimated_minutes: int = Field(ge=0)
