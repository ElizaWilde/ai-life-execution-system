from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AutomationPreference, DailyTask, PlanPreview, StudySession, WeeklyGoal
from app.services.estimation_calibration_service import estimation_calibration_service
from app.services.planning_service import MissingActiveWeeklyGoalError, planning_service
from app.services.task_deadline_service import task_deadline_service


class PlanPreviewNotFoundError(LookupError):
    pass


class InvalidPlanPreviewStateError(ValueError):
    pass


PRIORITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}
WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


class PlanPreviewService:
    async def create_daily(
        self,
        db: Session,
        user_id: int,
        target_date: date,
        available_minutes: int,
        user_instruction: str | None = None,
        base_preview_id: int | None = None,
    ) -> PlanPreview:
        current_preview: list[dict] | None = None
        if base_preview_id is not None:
            base_preview = self.get(db, user_id, base_preview_id)
            if base_preview.preview_type != "daily":
                raise InvalidPlanPreviewStateError(
                    "Only a daily preview can be refined."
                )
            if base_preview.target_date != target_date:
                raise InvalidPlanPreviewStateError(
                    "The preview being refined belongs to a different date."
                )
            current_preview = list(base_preview.payload_json.get("tasks", []))

        generated = await planning_service.build_daily_preview(
            db=db,
            user_id=user_id,
            available_minutes=available_minutes,
            task_date=target_date,
            user_instruction=user_instruction,
            current_preview=current_preview,
        )
        calibration = generated["calibration"]
        tasks = [
            {
                key: value
                for key, value in item.items()
                if key
                in {
                    "title",
                    "description",
                    "estimated_minutes",
                    "original_estimated_minutes",
                    "priority",
                    "weekly_goal_id",
                }
            }
            for item in generated["tasks"]
        ]
        self._expire_matching(db, user_id, "daily", target_date)
        preview = PlanPreview(
            user_id=user_id,
            preview_type="daily",
            status="pending",
            target_date=target_date,
            input_minutes=available_minutes,
            recommended_minutes=sum(item["estimated_minutes"] for item in tasks),
            calibration_factor=calibration.factor,
            payload_json={
                "tasks": tasks,
                "calibration": calibration.as_dict(),
                "workload_level": generated["workload_level"],
                "readiness_score": generated["readiness_score"],
            },
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db.add(preview)
        db.commit()
        db.refresh(preview)
        return preview

    def create_weekly(
        self,
        db: Session,
        user_id: int,
        week_start: date,
        intended_minutes: int,
    ) -> PlanPreview:
        week_start = week_start - timedelta(days=week_start.weekday())
        week_end = week_start + timedelta(days=6)
        goals = list(
            db.scalars(
                select(WeeklyGoal)
                .where(
                    WeeklyGoal.user_id == user_id,
                    WeeklyGoal.week_start <= week_end,
                    WeeklyGoal.week_end >= week_start,
                    WeeklyGoal.status == "active",
                )
                .order_by(WeeklyGoal.priority.desc(), WeeklyGoal.id)
            )
        )
        if not goals:
            raise MissingActiveWeeklyGoalError(
                "Create at least one active weekly priority before generating an adaptive plan."
            )

        history_start = week_start - timedelta(weeks=6)
        historical_focus = int(
            db.scalar(
                select(func.coalesce(func.sum(StudySession.duration_minutes), 0)).where(
                    StudySession.user_id == user_id,
                    StudySession.status == "completed",
                    StudySession.started_at
                    >= datetime.combine(history_start, time.min, tzinfo=timezone.utc),
                    StudySession.started_at
                    < datetime.combine(week_start, time.min, tzinfo=timezone.utc),
                )
            )
            or 0
        )
        historical_weekly_focus = round(historical_focus / 6)

        historical_tasks = list(
            db.scalars(
                select(DailyTask).where(
                    DailyTask.user_id == user_id,
                    DailyTask.task_date >= history_start,
                    DailyTask.task_date < week_start,
                    DailyTask.status != "cancelled",
                )
            )
        )
        completed = sum(task.status == "completed" for task in historical_tasks)
        completion_rate = completed / len(historical_tasks) if historical_tasks else 1.0
        calibration = estimation_calibration_service.calculate(db, user_id)

        if historical_weekly_focus > 0:
            sustainable = round(
                historical_weekly_focus * max(0.65, min(1.1, completion_rate + 0.15))
            )
            lower_bound = round(intended_minutes * 0.6)
            recommended = min(intended_minutes, max(lower_bound, sustainable))
        else:
            recommended = intended_minutes
        recommended = max(30, round(recommended / 15) * 15)

        weights = [
            (goal.target_minutes or 60) * PRIORITY_WEIGHT.get(goal.priority, 2)
            for goal in goals
        ]
        total_weight = sum(weights) or len(goals)
        allocations: list[dict] = []
        allocated = 0
        for index, (goal, weight) in enumerate(zip(goals, weights, strict=True)):
            minutes = (
                recommended - allocated
                if index == len(goals) - 1
                else round((recommended * weight / total_weight) / 15) * 15
            )
            minutes = max(0, minutes)
            allocated += minutes
            allocations.append(
                {
                    "weekly_goal_id": goal.id,
                    "title": goal.title,
                    "priority": goal.priority,
                    "current_minutes": goal.target_minutes or 0,
                    "recommended_minutes": minutes,
                }
            )

        working_days = self._working_day_indexes(db, user_id)
        dates = [
            week_start + timedelta(days=offset)
            for offset in range(7)
            if (week_start + timedelta(days=offset)).weekday() in working_days
        ] or [week_start + timedelta(days=offset) for offset in range(5)]
        daily_base, remainder = divmod(recommended, len(dates))
        daily_allocations = [
            {
                "date": value.isoformat(),
                "minutes": daily_base + (1 if index < remainder else 0),
            }
            for index, value in enumerate(dates)
        ]

        rationale = []
        if historical_weekly_focus:
            rationale.append(
                f"Recent focus history averages {historical_weekly_focus} minutes per week."
            )
        else:
            rationale.append("No six-week focus baseline yet; the intended time is used.")
        rationale.append(f"Recent task completion rate is {round(completion_rate * 100)}%.")
        if calibration.sample_count:
            rationale.append(
                f"Linked sessions calibrate estimates by {calibration.factor:.2f}×."
            )

        self._expire_matching(db, user_id, "weekly", week_start)
        preview = PlanPreview(
            user_id=user_id,
            preview_type="weekly",
            status="pending",
            target_date=week_start,
            input_minutes=intended_minutes,
            recommended_minutes=recommended,
            calibration_factor=calibration.factor,
            payload_json={
                "week_end": week_end.isoformat(),
                "historical_weekly_focus_minutes": historical_weekly_focus,
                "historical_completion_rate": completion_rate,
                "calibration": calibration.as_dict(),
                "rationale": rationale,
                "goal_allocations": allocations,
                "daily_allocations": daily_allocations,
            },
            expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
        )
        db.add(preview)
        db.commit()
        db.refresh(preview)
        return preview

    def get(self, db: Session, user_id: int, preview_id: int) -> PlanPreview:
        preview = db.scalar(
            select(PlanPreview).where(
                PlanPreview.id == preview_id,
                PlanPreview.user_id == user_id,
            )
        )
        if preview is None:
            raise PlanPreviewNotFoundError("Plan preview not found")
        self._expire_if_needed(db, preview)
        return preview

    def latest(
        self,
        db: Session,
        user_id: int,
        preview_type: str,
        target_date: date,
    ) -> PlanPreview | None:
        preview = db.scalar(
            select(PlanPreview)
            .where(
                PlanPreview.user_id == user_id,
                PlanPreview.preview_type == preview_type,
                PlanPreview.target_date == target_date,
            )
            .order_by(PlanPreview.created_at.desc(), PlanPreview.id.desc())
        )
        if preview is not None:
            self._expire_if_needed(db, preview)
        return preview

    def confirm(
        self,
        db: Session,
        user_id: int,
        preview_id: int,
    ) -> PlanPreview:
        preview = self.get(db, user_id, preview_id)
        if preview.status == "confirmed":
            return preview
        if preview.status != "pending":
            raise InvalidPlanPreviewStateError(
                f"Only pending previews can be confirmed; current status is {preview.status}."
            )

        if preview.preview_type == "daily":
            self._confirm_daily(db, user_id, preview)
        else:
            self._confirm_weekly(db, user_id, preview)
        preview.status = "confirmed"
        preview.confirmed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(preview)
        return preview

    def _confirm_daily(
        self,
        db: Session,
        user_id: int,
        preview: PlanPreview,
    ) -> None:
        existing_titles = {
            title.casefold()
            for title in db.scalars(
                select(DailyTask.title).where(
                    DailyTask.user_id == user_id,
                    DailyTask.task_date == preview.target_date,
                    DailyTask.status != "cancelled",
                )
            )
        }
        for item in preview.payload_json.get("tasks", []):
            if item["title"].casefold() in existing_titles:
                continue
            db.add(
                DailyTask(
                    user_id=user_id,
                    title=item["title"],
                    description=item.get("description"),
                    task_date=preview.target_date,
                    planning_scope="daily",
                    due_at=task_deadline_service.calculate(
                        db,
                        user_id,
                        preview.target_date,
                        "daily",
                    ),
                    estimated_minutes=item["estimated_minutes"],
                    priority=item["priority"],
                    weekly_goal_id=item["weekly_goal_id"],
                    status="pending",
                    source="ai",
                )
            )
            existing_titles.add(item["title"].casefold())

    @staticmethod
    def _confirm_weekly(
        db: Session,
        user_id: int,
        preview: PlanPreview,
    ) -> None:
        allocations = {
            int(item["weekly_goal_id"]): int(item["recommended_minutes"])
            for item in preview.payload_json.get("goal_allocations", [])
        }
        goals = db.scalars(
            select(WeeklyGoal).where(
                WeeklyGoal.user_id == user_id,
                WeeklyGoal.id.in_(allocations),
                WeeklyGoal.status == "active",
            )
        )
        for goal in goals:
            goal.target_minutes = allocations[goal.id]

    def _expire_matching(
        self,
        db: Session,
        user_id: int,
        preview_type: str,
        target_date: date,
    ) -> None:
        previews = db.scalars(
            select(PlanPreview).where(
                PlanPreview.user_id == user_id,
                PlanPreview.preview_type == preview_type,
                PlanPreview.target_date == target_date,
                PlanPreview.status == "pending",
            )
        )
        for preview in previews:
            preview.status = "expired"

    @staticmethod
    def _expire_if_needed(db: Session, preview: PlanPreview) -> None:
        expires_at = preview.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if preview.status == "pending" and expires_at <= datetime.now(timezone.utc):
            preview.status = "expired"
            db.commit()
            db.refresh(preview)

    @staticmethod
    def _working_day_indexes(db: Session, user_id: int) -> set[int]:
        preference = db.scalar(
            select(AutomationPreference).where(
                AutomationPreference.user_id == user_id
            )
        )
        if preference is None or not preference.working_days_json:
            return {0, 1, 2, 3, 4}
        return {
            WEEKDAY_INDEX[str(day).lower()]
            for day in preference.working_days_json
            if str(day).lower() in WEEKDAY_INDEX
        }


plan_preview_service = PlanPreviewService()
