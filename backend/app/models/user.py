from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    ''' 
    A User object has a list of related WeeklyGoal objects, and SQLAlchemy manages the connection between them.
        (1)relationship(...) in SQLAlchemy defines the Python-side connection between ORM models.
            This means user.weekly_goals returns all WeeklyGoal objects belonging to that User.
        (2)Mapped[list["WeeklyGoal"]] is the type annotation. user.weekly_goals is a list of WeeklyGoal objects, This represents a one-to-many relationship.
        (3)back_populates="user" connects the two sides of the relationship.
            On User: weekly_goals = relationship(back_populates="user")
            On WeeklyGoal: user = relationship(back_populates="weekly_goals")
            The names must point to each other:
                User.weekly_goals
                        ↕
                WeeklyGoal.user
        (4)cascade="all, delete-orphan" -> This is ORM-level behavior, it is controlled by SQLAlchemy in Python.
        means: If the User is deleted, delete the WeeklyGoals too. If a WeeklyGoal is removed from the User, delete that WeeklyGoal too.
    '''
    weekly_goals: Mapped[list["WeeklyGoal"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    daily_tasks: Mapped[list["DailyTask"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    study_sessions: Mapped[list["StudySession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    daily_reviews: Mapped[list["DailyReview"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    daily_check_ins: Mapped[list["DailyCheckIn"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    coaching_recommendations: Mapped[list["CoachingRecommendation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    weekly_reviews: Mapped[list["WeeklyReview"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    automation_preference: Mapped["AutomationPreference | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
