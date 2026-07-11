from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyCheckIn, DailyTask, StudySession
from app.schemas.coaching import CoachingContext


UNFINISHED_TASK_STATUSES = {"pending", "in_progress"}


class CoachingContextService:
    """Collect deterministic context for coaching without invoking an LLM."""

    def build_daily_context(
        self,
        db: Session,
        user_id: int,
        target_date: date,
        available_minutes: int | None = None,
    ) -> CoachingContext:
        check_in = self._get_check_in(db, user_id, target_date)
        today_tasks = self._get_tasks_for_date(db, user_id, target_date)
        recent_start_date = target_date - timedelta(days=6)
        recent_tasks = self._get_tasks_between(
            db,
            user_id,
            recent_start_date,
            target_date,
        )

        completed_tasks = sum(1 for task in today_tasks if task.status == "completed")
        unfinished_tasks = sum(
            1 for task in today_tasks if task.status in UNFINISHED_TASK_STATUSES
        )
        recent_completed_tasks = sum(
            1 for task in recent_tasks if task.status == "completed"
        )

        return CoachingContext(
            target_date=target_date,
            energy_level=check_in.energy_level if check_in else None,
            mood_level=check_in.mood_level if check_in else None,
            sleep_hours=check_in.sleep_hours if check_in else None,
            stress_level=check_in.stress_level if check_in else None,
            planned_tasks=len(today_tasks),
            completed_tasks=completed_tasks,
            unfinished_tasks=unfinished_tasks,
            recent_focus_minutes=self._recent_focus_minutes(
                db,
                user_id,
                recent_start_date,
                target_date,
            ),
            recent_completion_rate=self._completion_rate(
                recent_completed_tasks,
                len(recent_tasks),
            ),
            available_minutes=available_minutes,
            high_priority_tasks=[
                task.title
                for task in today_tasks
                if task.priority == "high" and task.status in UNFINISHED_TASK_STATUSES
            ],
            user_notes=check_in.notes if check_in else None,
        )

    def _get_check_in(
        self,
        db: Session,
        user_id: int,
        target_date: date,
    ) -> DailyCheckIn | None:
        return db.scalar(
            select(DailyCheckIn).where(
                DailyCheckIn.user_id == user_id,
                DailyCheckIn.check_in_date == target_date,
            )
        )

    def _get_tasks_for_date(
        self,
        db: Session,
        user_id: int,
        target_date: date,
    ) -> list[DailyTask]:
        return list(
            db.scalars(
                select(DailyTask)
                .where(
                    DailyTask.user_id == user_id,
                    DailyTask.task_date == target_date,
                )
                .order_by(DailyTask.priority.desc(), DailyTask.id)
            )
        )

    def _get_tasks_between(
        self,
        db: Session,
        user_id: int,
        start_date: date,
        end_date: date,
    ) -> list[DailyTask]:
        return list(
            db.scalars(
                select(DailyTask).where(
                    DailyTask.user_id == user_id,
                    DailyTask.task_date >= start_date,
                    DailyTask.task_date <= end_date,
                )
            )
        )

    def _recent_focus_minutes(
        self,
        db: Session,
        user_id: int,
        start_date: date,
        end_date: date,
    ) -> int:
        start = self._day_start(start_date)
        end = self._day_start(end_date + timedelta(days=1))
        sessions = db.scalars(
            select(StudySession).where(
                StudySession.user_id == user_id,
                StudySession.status == "completed",
                StudySession.started_at >= start,
                StudySession.started_at < end,
            )
        )
        return sum(session.duration_minutes or 0 for session in sessions)

    @staticmethod
    def _completion_rate(completed_tasks: int, planned_tasks: int) -> float:
        if planned_tasks == 0:
            return 0.0
        return completed_tasks / planned_tasks

    @staticmethod
    def _day_start(value: date) -> datetime:
        return datetime.combine(value, time.min, tzinfo=timezone.utc)


coaching_context_service = CoachingContextService()
