from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from math import ceil

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DailyTask, ForecastHistory, StudySession, WeeklyGoal
from app.services.automation_audit_service import automation_audit_service
from app.services.study_session_duration import counted_focus_session_clause


class ForecastService:
    """Create transparent, stored weekly-goal completion forecasts."""

    def generate_for_user(
        self,
        db: Session,
        user_id: int,
        now: datetime,
    ) -> list[ForecastHistory]:
        forecast_date = now.date()
        self._finalize_outcomes(db, user_id, forecast_date)
        goals = list(
            db.scalars(
                select(WeeklyGoal)
                .where(
                    WeeklyGoal.user_id == user_id,
                    WeeklyGoal.status == "active",
                    WeeklyGoal.week_start <= forecast_date,
                    WeeklyGoal.week_end >= forecast_date,
                )
                .order_by(WeeklyGoal.priority.desc(), WeeklyGoal.id)
            )
        )
        return [self._generate_goal(db, user_id, goal, now) for goal in goals]

    def list_for_user(
        self,
        db: Session,
        user_id: int,
        *,
        latest_only: bool = False,
    ) -> list[ForecastHistory]:
        forecasts = list(
            db.scalars(
                select(ForecastHistory)
                .where(ForecastHistory.user_id == user_id)
                .order_by(
                    ForecastHistory.predicted_at.desc(),
                    ForecastHistory.id.desc(),
                )
            )
        )
        if not latest_only:
            return forecasts
        latest: dict[int, ForecastHistory] = {}
        for forecast in forecasts:
            latest.setdefault(forecast.weekly_goal_id, forecast)
        return list(latest.values())

    def _generate_goal(
        self,
        db: Session,
        user_id: int,
        goal: WeeklyGoal,
        now: datetime,
    ) -> ForecastHistory:
        key = f"forecast:{user_id}:{goal.id}:{now.date().isoformat()}"
        existing = db.scalar(
            select(ForecastHistory).where(ForecastHistory.forecast_key == key)
        )
        if existing is not None:
            return existing

        target = goal.target_minutes or self._planned_minutes(db, user_id, goal)
        target = max(target, 1)
        actual = self._goal_focus_minutes(db, user_id, goal)
        completed_estimates = self._completed_estimated_minutes(db, user_id, goal)
        credited = min(target, max(actual, completed_estimates))
        remaining = max(0, target - credited)
        remaining_days = max(1, (goal.week_end - now.date()).days + 1)
        required_daily = ceil(remaining / remaining_days)
        elapsed_days = max(1, (now.date() - goal.week_start).days + 1)
        current_daily = round(actual / elapsed_days)
        task_completion_rate = self._task_completion_rate(db, user_id, goal)
        overdue_count = self._overdue_count(db, user_id, goal, now)

        progress_ratio = credited / target
        pace_ratio = 1.0 if required_daily == 0 else min(1.2, current_daily / required_daily)
        probability = (
            0.15
            + progress_ratio * 0.45
            + (pace_ratio / 1.2) * 0.25
            + task_completion_rate * 0.15
            - min(0.25, overdue_count * 0.06)
        )
        probability = round(max(0.03, min(0.98, probability)), 3)
        risk = "low" if probability >= 0.7 else "medium" if probability >= 0.4 else "high"
        factors: list[str] = []
        if current_daily < required_daily:
            factors.append(
                f"Current pace is {current_daily} min/day versus {required_daily} required."
            )
        if overdue_count:
            factors.append(f"{overdue_count} linked task(s) are overdue.")
        if task_completion_rate < 0.5:
            factors.append(
                f"Only {round(task_completion_rate * 100)}% of linked tasks are complete."
            )
        if not factors:
            factors.append("Current pace and completion history support the goal.")

        recommendation = (
            "Protect the required daily focus time and move optional work."
            if risk == "high"
            else "Schedule the remaining work across the available days."
            if risk == "medium"
            else "Keep the current pace and preserve a small buffer."
        )
        audit, _ = automation_audit_service.claim(
            db,
            user_id=user_id,
            action_key=f"audit:{key}",
            trigger_source="scheduler",
            automation_type="completion_forecast",
            service_name="forecast_service",
            input_json={"weekly_goal_id": goal.id, "forecast_date": str(now.date())},
        )
        try:
            forecast = ForecastHistory(
                user_id=user_id,
                weekly_goal_id=goal.id,
                forecast_key=key,
                forecast_date=now.date(),
                completion_probability=probability,
                risk_level=risk,
                remaining_minutes=remaining,
                remaining_days=remaining_days,
                required_daily_minutes=required_daily,
                current_daily_minutes=current_daily,
                risk_factors_json=factors,
                data_json={
                    "target_minutes": target,
                    "credited_minutes": credited,
                    "actual_focus_minutes": actual,
                    "task_completion_rate": task_completion_rate,
                    "overdue_tasks": overdue_count,
                },
                recommended_adjustment=recommendation,
                predicted_at=now.astimezone(timezone.utc),
            )
            db.add(forecast)
            db.commit()
            db.refresh(forecast)
            automation_audit_service.complete(
                db,
                audit,
                decision_json={"probability": probability, "risk_level": risk},
                records_changed=[{"model": "ForecastHistory", "id": forecast.id}],
            )
            return forecast
        except Exception as exc:
            db.rollback()
            automation_audit_service.fail(db, audit, exc)
            raise

    @staticmethod
    def _planned_minutes(db: Session, user_id: int, goal: WeeklyGoal) -> int:
        return int(
            db.scalar(
                select(func.coalesce(func.sum(DailyTask.estimated_minutes), 0)).where(
                    DailyTask.user_id == user_id,
                    DailyTask.weekly_goal_id == goal.id,
                    DailyTask.status != "cancelled",
                )
            )
            or 0
        )

    @staticmethod
    def _goal_focus_minutes(db: Session, user_id: int, goal: WeeklyGoal) -> int:
        start = datetime.combine(goal.week_start, time.min, tzinfo=timezone.utc)
        end = datetime.combine(goal.week_end + timedelta(days=1), time.min, tzinfo=timezone.utc)
        return int(
            db.scalar(
                select(func.coalesce(func.sum(StudySession.duration_minutes), 0))
                .join(DailyTask, DailyTask.id == StudySession.daily_task_id)
                .where(
                    StudySession.user_id == user_id,
                    StudySession.status == "completed",
                    StudySession.started_at >= start,
                    StudySession.started_at < end,
                    DailyTask.weekly_goal_id == goal.id,
                    counted_focus_session_clause(),
                )
            )
            or 0
        )

    @staticmethod
    def _completed_estimated_minutes(
        db: Session,
        user_id: int,
        goal: WeeklyGoal,
    ) -> int:
        return int(
            db.scalar(
                select(func.coalesce(func.sum(DailyTask.estimated_minutes), 0)).where(
                    DailyTask.user_id == user_id,
                    DailyTask.weekly_goal_id == goal.id,
                    DailyTask.status == "completed",
                )
            )
            or 0
        )

    @staticmethod
    def _task_completion_rate(db: Session, user_id: int, goal: WeeklyGoal) -> float:
        tasks = list(
            db.scalars(
                select(DailyTask).where(
                    DailyTask.user_id == user_id,
                    DailyTask.weekly_goal_id == goal.id,
                    DailyTask.status != "cancelled",
                )
            )
        )
        if not tasks:
            return 0.0
        return sum(task.status == "completed" for task in tasks) / len(tasks)

    @staticmethod
    def _overdue_count(
        db: Session,
        user_id: int,
        goal: WeeklyGoal,
        now: datetime,
    ) -> int:
        return int(
            db.scalar(
                select(func.count(DailyTask.id)).where(
                    DailyTask.user_id == user_id,
                    DailyTask.weekly_goal_id == goal.id,
                    DailyTask.status.in_(("pending", "in_progress")),
                    DailyTask.due_at <= now,
                )
            )
            or 0
        )

    @staticmethod
    def _finalize_outcomes(db: Session, user_id: int, today: date) -> None:
        forecasts = list(
            db.scalars(
                select(ForecastHistory)
                .join(WeeklyGoal, WeeklyGoal.id == ForecastHistory.weekly_goal_id)
                .where(
                    ForecastHistory.user_id == user_id,
                    ForecastHistory.actual_outcome.is_(None),
                    WeeklyGoal.week_end < today,
                )
            )
        )
        for forecast in forecasts:
            goal = db.get(WeeklyGoal, forecast.weekly_goal_id)
            forecast.actual_outcome = (
                "completed" if goal is not None and goal.status == "completed" else "incomplete"
            )
        if forecasts:
            db.commit()


forecast_service = ForecastService()
