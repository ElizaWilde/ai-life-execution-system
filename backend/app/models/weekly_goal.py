from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, Text, event, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WeeklyGoal(Base):
    __tablename__ = "weekly_goals"
    __table_args__ = (
        CheckConstraint("week_end >= week_start", name="ck_weekly_goals_date_range"),
        CheckConstraint(
            "target_minutes IS NULL OR target_minutes >= 0",
            name="ck_weekly_goals_target_minutes",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    week_start: Mapped[date] = mapped_column(Date, index=True)
    week_end: Mapped[date] = mapped_column(Date)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    target_minutes: Mapped[int | None]
    notion_page_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="weekly_goals")
    daily_tasks: Mapped[list["DailyTask"]] = relationship(back_populates="weekly_goal")

    @property
    def is_overdue(self) -> bool:
        if self.status in {"completed", "cancelled"} or self.due_at is None:
            return False
        due_at = self.due_at
        if due_at.tzinfo is None or due_at.utcoffset() is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        return due_at <= datetime.now(timezone.utc)


@event.listens_for(WeeklyGoal, "before_insert")
def set_default_weekly_due_at(
    _mapper: object,
    _connection: object,
    goal: WeeklyGoal,
) -> None:
    if goal.due_at is None:
        goal.due_at = datetime.combine(
            goal.week_end + timedelta(days=1),
            time.min,
            tzinfo=timezone.utc,
        )
