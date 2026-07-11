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


class CoachingRecommendation(Base):
    __tablename__ = "coaching_recommendations"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "recommendation_date",
            name="uq_coaching_recommendations_user_date",
        ),
        CheckConstraint(
            "readiness_score >= 0 AND readiness_score <= 100",
            name="ck_coaching_recommendations_readiness_score",
        ),
        CheckConstraint(
            "workload_multiplier >= 0",
            name="ck_coaching_recommendations_workload_multiplier",
        ),
        CheckConstraint(
            "workload_level IN ('light', 'reduced', 'normal')",
            name="ck_coaching_recommendations_workload_level",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    recommendation_date: Mapped[date] = mapped_column(Date, index=True)

    readiness_score: Mapped[float]
    workload_multiplier: Mapped[float]
    workload_level: Mapped[str] = mapped_column(String(20))
    adjustment_reasons_json: Mapped[list[str]] = mapped_column(JSON, default=list)

    summary: Mapped[str] = mapped_column(Text)
    recommendations_json: Mapped[dict[str, Any]] = mapped_column(JSON)

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

    user: Mapped["User"] = relationship(back_populates="coaching_recommendations")
