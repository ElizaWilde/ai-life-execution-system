from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyTask, StudySession, WeeklyGoal
from app.schemas.dashboard import (
    DailyFocusPoint,
    TodayDashboardResponse,
    WeekDashboardResponse,
)


class StatsService:
    """Build dashboard statistics from tasks, study sessions, and goals."""

    def get_today_dashboard(
        self,
        db: Session,
        user_id: int,
        target_date: date | None = None,
    ) -> TodayDashboardResponse:
        dashboard_date = target_date or date.today()
        # self means the current object (instance) of the class
        day_start = self._day_start(dashboard_date)
        day_end = day_start + timedelta(days=1)

        tasks = list(
            db.scalars(
                select(DailyTask)
                .where(
                    DailyTask.user_id == user_id,
                    DailyTask.task_date == dashboard_date,
                )
                .order_by(DailyTask.status, DailyTask.priority.desc(), DailyTask.id)
            )
        )
        planned_tasks = len(tasks)
        completed_tasks = sum(1 for task in tasks if task.status == "completed")
        unfinished_tasks = [
            task for task in tasks if task.status not in {"completed", "cancelled"}
        ]

        focus_minutes = self._focus_minutes_between(db, user_id, day_start, day_end)

        return TodayDashboardResponse(
            date=dashboard_date,
            focus_minutes=focus_minutes,
            planned_tasks=planned_tasks,
            completed_tasks=completed_tasks,
            completion_rate=self._completion_rate(completed_tasks, planned_tasks),
            unfinished_tasks=unfinished_tasks,
        )

    def get_week_dashboard(
        self,
        db: Session,
        user_id: int,
        target_date: date | None = None,
    ) -> WeekDashboardResponse:
        week_start = self._week_start(target_date or date.today())
        week_end = week_start + timedelta(days=6)
        week_start_dt = self._day_start(week_start)
        week_end_exclusive_dt = self._day_start(week_end + timedelta(days=1))

        tasks = list(
            db.scalars(
                select(DailyTask).where(
                    DailyTask.user_id == user_id,
                    DailyTask.task_date >= week_start,
                    DailyTask.task_date <= week_end,
                )
            )
        )
        planned_tasks = len(tasks)
        completed_tasks = sum(1 for task in tasks if task.status == "completed")

        goals = list(
            db.scalars(
                select(WeeklyGoal).where(
                    WeeklyGoal.user_id == user_id,
                    WeeklyGoal.week_start <= week_end,
                    WeeklyGoal.week_end >= week_start,
                )
            )
        )

        daily_focus = [
            DailyFocusPoint(
                date=week_start + timedelta(days=offset),
                focus_minutes=self._focus_minutes_between(
                    db,
                    user_id,
                    self._day_start(week_start + timedelta(days=offset)),
                    self._day_start(week_start + timedelta(days=offset + 1)),
                ),
            )
            for offset in range(7)
        ]

        return WeekDashboardResponse(
            week_start=week_start,
            week_end=week_end,
            focus_minutes=self._focus_minutes_between(
                db,
                user_id,
                week_start_dt,
                week_end_exclusive_dt,
            ),
            planned_tasks=planned_tasks,
            completed_tasks=completed_tasks,
            completion_rate=self._completion_rate(completed_tasks, planned_tasks),
            active_goals=sum(1 for goal in goals if goal.status == "active"),
            completed_goals=sum(1 for goal in goals if goal.status == "completed"),
            daily_focus=daily_focus,
        )

    def _focus_minutes_between(
        self,
        db: Session,
        user_id: int,
        start: datetime,
        end: datetime,
    ) -> int:
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

    @staticmethod
    def _week_start(value: date) -> date:
        return value - timedelta(days=value.weekday())


stats_service = StatsService()
