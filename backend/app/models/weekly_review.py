from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WeeklyReview(Base):
    __tablename__ = "weekly_reviews"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "week_start",
            name="uq_weekly_reviews_user_week_start",
        ),
        CheckConstraint(
            "week_end >= week_start",
            name="ck_weekly_reviews_date_range",
        ),
        CheckConstraint(
            "planned_tasks >= 0 AND completed_tasks >= 0 "
            "AND focus_minutes >= 0 AND check_in_days >= 0",
            name="ck_weekly_reviews_nonnegative_stats",
        ),
        CheckConstraint(
            "completion_rate >= 0 AND completion_rate <= 1",
            name="ck_weekly_reviews_completion_rate",
        ),
        CheckConstraint(
            "average_sleep_hours IS NULL OR "
            "(average_sleep_hours >= 0 AND average_sleep_hours <= 24)",
            name="ck_weekly_reviews_average_sleep",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    week_start: Mapped[date] = mapped_column(Date, index=True)
    week_end: Mapped[date] = mapped_column(Date)

    planned_tasks: Mapped[int]
    completed_tasks: Mapped[int]
    completion_rate: Mapped[float]
    focus_minutes: Mapped[int]
    check_in_days: Mapped[int]
    average_sleep_hours: Mapped[float | None]
    energy_distribution_json: Mapped[dict[str, int]] = mapped_column(
        JSON,
        default=dict,
    )
    mood_distribution_json: Mapped[dict[str, int]] = mapped_column(
        JSON,
        default=dict,
    )

    summary: Mapped[str] = mapped_column(Text)
    achievements_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    obstacles_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    next_week_actions_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    context_json: Mapped[dict[str, Any]] = mapped_column(JSON)

    model_name: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="weekly_reviews")
