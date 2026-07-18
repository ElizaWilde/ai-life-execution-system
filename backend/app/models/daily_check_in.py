from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DailyCheckIn(Base):
    __tablename__ = "daily_check_ins"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "check_in_date",
            name="uq_daily_check_ins_user_date",
        ),
        CheckConstraint(
            "energy_level IN ('depleted', 'low', 'steady', 'high', 'energized')",
            name="ck_daily_check_ins_energy",
        ),
        CheckConstraint(
            "mood_level IN ('struggling', 'low', 'neutral', 'good', 'great')",
            name="ck_daily_check_ins_mood",
        ),
        CheckConstraint(
            "sleep_hours >= 0 AND sleep_hours <= 24",
            name="ck_daily_check_ins_sleep",
        ),
        CheckConstraint(
            "available_minutes IS NULL OR (available_minutes >= 0 AND available_minutes <= 1440)",
            name="ck_daily_check_ins_available_minutes",
        ),
        CheckConstraint(
            "focus_mode IS NULL OR focus_mode IN ('Deep work', 'Meetings', 'Study', 'Recovery')",
            name="ck_daily_check_ins_focus_mode",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    check_in_date: Mapped[date] = mapped_column(Date, index=True)

    energy_level: Mapped[str] = mapped_column(String(20))
    mood_level: Mapped[str] = mapped_column(String(20))
    sleep_hours: Mapped[float]
    stress_level: Mapped[int | None]
    available_minutes: Mapped[int | None]
    focus_mode: Mapped[str | None] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text)

    cycle_day: Mapped[int | None]
    cycle_notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="daily_check_ins")
