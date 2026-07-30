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
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ForecastHistory(Base):
    __tablename__ = "forecast_history"
    __table_args__ = (
        CheckConstraint(
            "completion_probability >= 0 AND completion_probability <= 1",
            name="ck_forecast_history_probability",
        ),
        CheckConstraint(
            "risk_level IN ('low', 'medium', 'high')",
            name="ck_forecast_history_risk",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    weekly_goal_id: Mapped[int] = mapped_column(
        ForeignKey("weekly_goals.id", ondelete="CASCADE"),
        index=True,
    )
    forecast_key: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    forecast_date: Mapped[date] = mapped_column(Date, index=True)
    completion_probability: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(20), index=True)
    remaining_minutes: Mapped[int] = mapped_column(Integer)
    remaining_days: Mapped[int] = mapped_column(Integer)
    required_daily_minutes: Mapped[int] = mapped_column(Integer)
    current_daily_minutes: Mapped[int] = mapped_column(Integer)
    risk_factors_json: Mapped[list] = mapped_column(JSON, default=list)
    data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    recommended_adjustment: Mapped[str] = mapped_column(Text)
    actual_outcome: Mapped[str | None] = mapped_column(String(30))
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="forecast_history")
    weekly_goal: Mapped["WeeklyGoal"] = relationship()
