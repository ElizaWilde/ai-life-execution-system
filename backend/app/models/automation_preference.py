from __future__ import annotations

from datetime import datetime, time
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AutomationPreference(Base):
    __tablename__ = "automation_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_automation_preferences_user_id"),
        CheckConstraint(
            "notification_channel IN ('in_app', 'email', 'telegram')",
            name="ck_automation_preferences_notification_channel",
        ),
        CheckConstraint(
            "max_reminders_per_day >= 0 AND max_reminders_per_day <= 20",
            name="ck_automation_preferences_max_reminders",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    timezone: Mapped[str] = mapped_column(String(100), default="Asia/Singapore")
    morning_reminder_time: Mapped[time] = mapped_column(Time, default=time(8, 0))
    evening_review_time: Mapped[time] = mapped_column(Time, default=time(21, 0))
    notification_channel: Mapped[str] = mapped_column(String(20), default="email")
    telegram_chat_id: Mapped[str | None] = mapped_column(String(40))
    automatic_rescheduling_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmation_required: Mapped[bool] = mapped_column(Boolean, default=True)
    max_reminders_per_day: Mapped[int] = mapped_column(Integer, default=3)
    quiet_hours_start: Mapped[time] = mapped_column(Time, default=time(22, 0))
    quiet_hours_end: Mapped[time] = mapped_column(Time, default=time(7, 0))
    working_days_json: Mapped[list[str]] = mapped_column(
        JSON,
        default=lambda: ["monday", "tuesday", "wednesday", "thursday", "friday"],
    )
    preferred_study_periods_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="automation_preference")
