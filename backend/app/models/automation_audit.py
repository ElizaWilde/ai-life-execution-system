from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AutomationAudit(Base):
    __tablename__ = "automation_audits"
    __table_args__ = (
        CheckConstraint(
            "execution_status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_automation_audits_execution_status",
        ),
        CheckConstraint(
            "confirmation_status IN ('not_required', 'pending', 'confirmed', 'rejected')",
            name="ck_automation_audits_confirmation_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    action_key: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    trigger_source: Mapped[str] = mapped_column(String(40), index=True)
    automation_type: Mapped[str] = mapped_column(String(60), index=True)
    service_name: Mapped[str] = mapped_column(String(100))
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    decision_json: Mapped[dict] = mapped_column(JSON, default=dict)
    records_changed_json: Mapped[list] = mapped_column(JSON, default=list)
    confirmation_status: Mapped[str] = mapped_column(
        String(20),
        default="not_required",
    )
    execution_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        index=True,
    )
    failure_reason: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="automation_audits")
