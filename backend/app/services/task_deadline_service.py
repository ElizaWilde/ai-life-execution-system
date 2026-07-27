from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AutomationPreference, UserAppSetting


class TaskDeadlineService:
    """Calculate task due times from plan scope and user-local settings."""

    def calculate(
        self,
        db: Session,
        user_id: int,
        task_date: date,
        planning_scope: str,
        *,
        explicit_due_at: datetime | None = None,
    ) -> datetime:
        timezone_name = (
            db.scalar(
                select(AutomationPreference.timezone).where(
                    AutomationPreference.user_id == user_id
                )
            )
            or "Asia/Singapore"
        )
        timezone_info = self._timezone(timezone_name)

        if explicit_due_at is not None:
            if explicit_due_at.tzinfo is None or explicit_due_at.utcoffset() is None:
                explicit_due_at = explicit_due_at.replace(tzinfo=timezone_info)
            return explicit_due_at.astimezone(timezone.utc)

        if planning_scope == "weekly":
            week_start_name = (
                db.scalar(
                    select(UserAppSetting.week_start).where(
                        UserAppSetting.user_id == user_id
                    )
                )
                or "Monday"
            )
            start_weekday = 6 if week_start_name == "Sunday" else 0
            current_week_start = task_date - timedelta(
                days=(task_date.weekday() - start_weekday) % 7
            )
            due_date = current_week_start + timedelta(days=7)
        else:
            due_date = task_date + timedelta(days=1)

        return datetime.combine(due_date, time.min, tzinfo=timezone_info).astimezone(
            timezone.utc
        )

    def calculate_weekly_goal(
        self,
        db: Session,
        user_id: int,
        week_end: date,
        *,
        explicit_due_at: datetime | None = None,
    ) -> datetime:
        """Weekly goals expire exactly at local midnight after their recorded week."""
        timezone_name = (
            db.scalar(
                select(AutomationPreference.timezone).where(
                    AutomationPreference.user_id == user_id
                )
            )
            or "Asia/Singapore"
        )
        timezone_info = self._timezone(timezone_name)
        if explicit_due_at is not None:
            if explicit_due_at.tzinfo is None or explicit_due_at.utcoffset() is None:
                explicit_due_at = explicit_due_at.replace(tzinfo=timezone_info)
            return explicit_due_at.astimezone(timezone.utc)
        return datetime.combine(
            week_end + timedelta(days=1),
            time.min,
            tzinfo=timezone_info,
        ).astimezone(timezone.utc)

    @staticmethod
    def _timezone(timezone_name: str) -> ZoneInfo:
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")


task_deadline_service = TaskDeadlineService()
