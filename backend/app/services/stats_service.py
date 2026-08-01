from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CoachingRecommendation,
    DailyCheckIn,
    DailyTask,
    StudySession,
    WeeklyGoal,
)
from app.services.study_session_duration import focused_seconds, total_focused_minutes
from app.schemas.coaching import (
    CoachingRecommendationRead,
    CoachingRecommendationResponse,
)
from app.schemas.dashboard import (
    DailyFocusPoint,
    TimeAllocationPoint,
    TodayDashboardResponse,
    WeekDashboardResponse,
)

# defines a class named StatsService. A class is a blueprint.
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
        sessions = self._sessions_between(db, user_id, day_start, day_end)
        check_in = db.scalar(
            select(DailyCheckIn).where(
                DailyCheckIn.user_id == user_id,
                DailyCheckIn.check_in_date == dashboard_date,
            )
        )
        coaching_record = db.scalar(
            select(CoachingRecommendation).where(
                CoachingRecommendation.user_id == user_id,
                CoachingRecommendation.recommendation_date == dashboard_date,
            )
        )
        coaching = self._coaching_response(coaching_record)

        return TodayDashboardResponse(
            date=dashboard_date,
            focus_minutes=focus_minutes,
            planned_tasks=planned_tasks,
            completed_tasks=completed_tasks,
            completion_rate=self._completion_rate(completed_tasks, planned_tasks),
            weighted_progress_rate=self._weighted_daily_progress(tasks, sessions),
            tasks=tasks,
            unfinished_tasks=unfinished_tasks,
            time_allocation=self._time_allocation(tasks, sessions),
            check_in=check_in,
            coaching=coaching,
            readiness_score=(
                coaching_record.readiness_score if coaching_record else None
            ),
            workload_multiplier=(
                coaching_record.workload_multiplier if coaching_record else None
            ),
            workload_level=(
                coaching_record.workload_level if coaching_record else None
            ),
            adjustment_reasons=(
                coaching_record.adjustment_reasons_json
                if coaching_record
                else []
            ),
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
        sessions = self._sessions_between(
            db, user_id, week_start_dt, week_end_exclusive_dt
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
                planned_minutes=sum(
                    task.estimated_minutes or 0
                    for task in tasks
                    if task.task_date == week_start + timedelta(days=offset)
                    and task.status != "cancelled"
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
            time_allocation=self._time_allocation(tasks, sessions),
        )

    def _sessions_between(
        self,
        db: Session,
        user_id: int,
        start: datetime,
        end: datetime,
    ) -> list[StudySession]:
        return list(
            db.scalars(
                select(StudySession).where(
                    StudySession.user_id == user_id,
                    StudySession.status == "completed",
                    StudySession.started_at >= start,
                    StudySession.started_at < end,
                )
            )
        )

    @staticmethod
    def _time_allocation(
        tasks: list[DailyTask],
        sessions: list[StudySession],
    ) -> list[TimeAllocationPoint]:
        buckets: dict[str, dict[str, int]] = {}
        task_titles = {task.id: task.title for task in tasks}

        for task in tasks:
            if task.status == "cancelled":
                continue
            bucket = buckets.setdefault(
                task.title,
                {"planned_minutes": 0, "focus_seconds": 0},
            )
            bucket["planned_minutes"] += task.estimated_minutes or 0

        for session in sessions:
            label = task_titles.get(session.daily_task_id) or session.subject or "Other"
            bucket = buckets.setdefault(
                label,
                {"planned_minutes": 0, "focus_seconds": 0},
            )
            bucket["focus_seconds"] += focused_seconds(session)

        return [
            TimeAllocationPoint(
                label=label,
                planned_minutes=minutes["planned_minutes"],
                focus_minutes=minutes["focus_seconds"] // 60,
            )
            for label, minutes in sorted(
                buckets.items(),
                key=lambda item: max(
                    item[1]["planned_minutes"], item[1]["focus_seconds"] // 60
                ),
                reverse=True,
            )
        ]

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
        return total_focused_minutes(sessions)

    @staticmethod
    def _weighted_daily_progress(
        tasks: list[DailyTask],
        sessions: list[StudySession],
    ) -> float:
        """Score execution using task importance and linked focused time."""
        active_tasks = [task for task in tasks if task.status != "cancelled"]
        if not active_tasks:
            return 0.0

        focused_by_task: dict[int, int] = {}
        for session in sessions:
            if session.daily_task_id is None:
                continue
            focused_by_task[session.daily_task_id] = (
                focused_by_task.get(session.daily_task_id, 0)
                + focused_seconds(session)
            )

        priority_weights = {"urgent": 1.8, "high": 1.5, "medium": 1.0, "low": 0.75}
        earned_weight = 0.0
        total_weight = 0.0
        for task in active_tasks:
            estimated_minutes = max(task.estimated_minutes or 30, 1)
            task_weight = estimated_minutes * priority_weights.get(task.priority, 1.0)
            if task.status == "completed":
                progress = 1.0
            else:
                progress = min(
                    focused_by_task.get(task.id, 0) / (estimated_minutes * 60),
                    1.0,
                )
            total_weight += task_weight
            earned_weight += task_weight * progress

        return earned_weight / total_weight if total_weight else 0.0

    @staticmethod
    def _coaching_response(
        recommendation: CoachingRecommendation | None,
    ) -> CoachingRecommendationResponse | None:
        if recommendation is None:
            return None
        read_model = CoachingRecommendationRead.model_validate(recommendation)
        return CoachingRecommendationResponse.from_recommendation(read_model)

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

# creates an object (instance) from that class.
stats_service = StatsService()
'''
    StatsService                class / blueprint
     ↓ creates
    stats_service               object / instance
     ↓ becomes
    self                        name for that object inside its methods
'''
