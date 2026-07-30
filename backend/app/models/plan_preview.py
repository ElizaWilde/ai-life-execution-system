from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlanPreview(Base):
    """A proposed planning change that is inert until the user confirms it."""

    __tablename__ = "plan_previews"
    __table_args__ = (
        CheckConstraint(
            "preview_type IN ('daily', 'weekly')",
            name="ck_plan_previews_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'expired')",
            name="ck_plan_previews_status",
        ),
        CheckConstraint(
            "input_minutes >= 0 AND recommended_minutes >= 0",
            name="ck_plan_previews_minutes",
        ),
        CheckConstraint(
            "calibration_factor > 0",
            name="ck_plan_previews_calibration_factor",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    preview_type: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    target_date: Mapped[date] = mapped_column(Date, index=True)
    input_minutes: Mapped[int] = mapped_column(Integer, default=0)
    recommended_minutes: Mapped[int] = mapped_column(Integer, default=0)
    calibration_factor: Mapped[float] = mapped_column(Float, default=1.0)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="plan_previews")
