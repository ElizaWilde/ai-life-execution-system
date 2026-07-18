from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserAppSetting(Base):
    __tablename__ = "user_app_settings"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_app_settings_user_id"),
        CheckConstraint("week_start IN ('Monday', 'Sunday')", name="ck_user_app_settings_week_start"),
        CheckConstraint("focus_minutes IN (25, 45, 60)", name="ck_user_app_settings_focus_minutes"),
        CheckConstraint("short_break_minutes IN (5, 10)", name="ck_user_app_settings_short_break"),
        CheckConstraint("long_break_minutes IN (15, 30)", name="ck_user_app_settings_long_break"),
        CheckConstraint("cycle_count BETWEEN 1 AND 12", name="ck_user_app_settings_cycle_count"),
        CheckConstraint("workload IN ('light', 'medium', 'high')", name="ck_user_app_settings_workload"),
        CheckConstraint("theme IN ('light', 'dark', 'auto')", name="ck_user_app_settings_theme"),
        CheckConstraint("tone IN ('supportive', 'direct', 'reflective')", name="ck_user_app_settings_tone"),
        CheckConstraint("strictness IN ('flexible', 'balanced', 'strict')", name="ck_user_app_settings_strictness"),
        CheckConstraint("adjustment IN ('gentle', 'moderate', 'strong')", name="ck_user_app_settings_adjustment"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    week_start: Mapped[str] = mapped_column(String(10), default="Monday")
    focus_minutes: Mapped[int] = mapped_column(Integer, default=25)
    short_break_minutes: Mapped[int] = mapped_column(Integer, default=5)
    long_break_minutes: Mapped[int] = mapped_column(Integer, default=15)
    cycle_count: Mapped[int] = mapped_column(Integer, default=4)
    workload: Mapped[str] = mapped_column(String(10), default="medium")
    theme: Mapped[str] = mapped_column(String(10), default="light")
    tone: Mapped[str] = mapped_column(String(20), default="supportive")
    strictness: Mapped[str] = mapped_column(String(20), default="balanced")
    adjustment: Mapped[str] = mapped_column(String(20), default="moderate")
    proactive: Mapped[bool] = mapped_column(Boolean, default=True)
    focus_matters: Mapped[bool] = mapped_column(Boolean, default=True)
    protect_deep_work: Mapped[bool] = mapped_column(Boolean, default=True)
    learn_from_feedback: Mapped[bool] = mapped_column(Boolean, default=True)
    integrations_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    avatar_data_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="app_setting")
