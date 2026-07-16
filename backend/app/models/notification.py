from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "notification_type IN ("
            "'morning_plan', 'upcoming_task', 'missed_task', 'deadline_warning', "
            "'evening_check_in', 'weekly_review', 'rescheduling_proposal'"
            ")",
            name="ck_notifications_type",
        ),
        CheckConstraint(
            "channel IN ('in_app', 'email', 'telegram')",
            name="ck_notifications_channel",
        ),
        CheckConstraint(
            "status IN ('pending', 'delivered', 'failed')",
            name="ck_notifications_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    notification_type: Mapped[str] = mapped_column(String(40), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="notifications")
