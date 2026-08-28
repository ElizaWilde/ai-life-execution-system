from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


CommandIntent = Literal[
    "create_task",
    "create_reminder",
    "reschedule_task",
    "reduce_workload",
    "get_progress",
    "get_forecast",
    "get_coaching",
    "complete_task",
    "change_task_duration",
    "update_content",
    "unknown",
]


class CommandRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2_000)


class CommandInterpretation(BaseModel):
    """Strict semantic result produced by the LLM; it is never executed directly."""

    model_config = ConfigDict(extra="forbid")

    intent: CommandIntent
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2_000)
    task_date: date | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=1_440)
    scheduled_start_minutes: int | None = Field(default=None, ge=0, le=1_439)
    priority: Literal["low", "medium", "high", "urgent"] | None = None
    channel: Literal["work", "assignments", "networking", "projects", "study", "personal"] | None = None
    weekly_goal_query: str | None = Field(default=None, min_length=1, max_length=255)
    query: str | None = Field(default=None, min_length=1, max_length=255)
    proposed_minutes: int | None = Field(default=None, ge=1, le=1_440)
    resource_type: Literal["daily_task", "weekly_goal", "phase", "milestone"] | None = None
    field_name: str | None = Field(default=None, min_length=1, max_length=80)
    new_value: str | None = Field(default=None, max_length=2_000)
    reminder_subject: str | None = Field(default=None, min_length=1, max_length=255)
    reminder_hour: int | None = Field(default=None, ge=0, le=23)
    reminder_minute: int | None = Field(default=None, ge=0, le=59)
    horizon_days: int | None = Field(default=None, ge=1, le=90)
    reduction_percent: int | None = Field(default=None, ge=1, le=90)
    clarification_needed: bool = False
    clarification_question: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_intent_fields(self) -> "CommandInterpretation":
        required: dict[str, tuple[str, ...]] = {
            "create_task": ("title", "task_date", "estimated_minutes"),
            "create_reminder": ("reminder_subject", "reminder_hour", "reminder_minute"),
            "complete_task": ("query",),
            "change_task_duration": ("query", "proposed_minutes"),
            "update_content": ("resource_type", "query", "field_name", "new_value"),
        }
        if not self.clarification_needed:
            missing = [name for name in required.get(self.intent, ()) if getattr(self, name) is None]
            if missing:
                raise ValueError(f"{self.intent} is missing required fields: {', '.join(missing)}")
        if self.clarification_needed and not self.clarification_question:
            raise ValueError("clarification_question is required when clarification_needed is true")
        return self


class CommandDecision(BaseModel):
    """Deterministic application decision made after semantic interpretation."""

    model_config = ConfigDict(extra="forbid")

    allowed: bool
    code: Literal["allowed", "duplicate_task_name", "schedule_conflict", "task_conflict"]
    message: str
    conflicts: list[dict] = Field(default_factory=list)


class CommandRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    idempotency_key: str
    command_text: str
    intent: CommandIntent
    parameters_json: dict
    status: Literal[
        "pending_confirmation",
        "completed",
        "rejected",
        "failed",
        "unknown",
    ]
    requires_confirmation: bool
    response_message: str
    result_json: dict
    expires_at: datetime | None
    confirmed_at: datetime | None
    rejected_at: datetime | None
    executed_at: datetime | None
    created_at: datetime
    updated_at: datetime
