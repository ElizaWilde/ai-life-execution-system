from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
