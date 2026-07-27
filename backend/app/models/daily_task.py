from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, Text, event, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DailyTask(Base):
    __tablename__ = "daily_tasks"
    __table_args__ = (
        CheckConstraint(
            "estimated_minutes IS NULL OR estimated_minutes >= 0",
            name="ck_daily_tasks_estimated_minutes",
        ),
        CheckConstraint(
            "planning_scope IN ('daily', 'weekly')",
            name="ck_daily_tasks_planning_scope",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    weekly_goal_id: Mapped[int | None] = mapped_column(
        ForeignKey("weekly_goals.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    task_date: Mapped[date] = mapped_column(Date, index=True)
    planning_scope: Mapped[str] = mapped_column(String(20), default="daily", index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    estimated_minutes: Mapped[int | None]
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    source: Mapped[str] = mapped_column(String(20), default="manual")
    raw_model_output: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="daily_tasks")
    weekly_goal: Mapped["WeeklyGoal | None"] = relationship(back_populates="daily_tasks")
    study_sessions: Mapped[list["StudySession"]] = relationship(
        back_populates="daily_task"
    )
    proposal_items: Mapped[list["ReschedulingProposalItem"]] = relationship(
        back_populates="daily_task"
    )

    @property
    def is_overdue(self) -> bool:
        if self.status in {"completed", "cancelled"} or self.due_at is None:
            return False
        due_at = self.due_at
        if due_at.tzinfo is None or due_at.utcoffset() is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        return due_at <= datetime.now(timezone.utc)


@event.listens_for(DailyTask, "before_insert")
def set_default_due_at(_mapper: object, _connection: object, task: DailyTask) -> None:
    """Backstop for internal/test inserts; API services apply the user's timezone."""
    if task.due_at is None:
        task.due_at = datetime.combine(
            task.task_date + timedelta(days=1),
            time.min,
            tzinfo=timezone.utc,
        )
