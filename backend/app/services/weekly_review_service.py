from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta, timezone

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import DailyCheckIn, DailyTask, StudySession, WeeklyReview
from app.prompts.weekly_review_prompt import (
    WEEKLY_REVIEW_PROMPT_VERSION,
    WEEKLY_REVIEW_SYSTEM_PROMPT,
    build_weekly_review_user_prompt,
)
from app.schemas.weekly_review import (
    WeeklyReviewAdvice,
    WeeklyReviewContext,
    WeeklyReviewRead,
)
from app.services.llm_service import llm_service


class InvalidWeeklyReviewResponseError(ValueError):
    """Raised when the LLM response violates the weekly review contract."""


class PendingWeeklyReviewChangesError(RuntimeError):
    """Raised rather than rolling back unrelated caller changes."""


class WeeklyReviewService:
    async def generate_weekly_review(
        self,
        db: Session,
        user_id: int,
        week_start: date | None = None,
    ) -> WeeklyReviewRead:
        self._ensure_no_pending_changes(db)
        start = week_start or self.current_week_start()
        end = start + timedelta(days=6)
        context = self.build_context(db, user_id, start, end)
        existing_id = db.scalar(
            select(WeeklyReview.id).where(
                WeeklyReview.user_id == user_id,
                WeeklyReview.week_start == start,
            )
        )

        self._close_read_transaction(db)

        llm_result = await llm_service.generate_json(
            system_prompt=WEEKLY_REVIEW_SYSTEM_PROMPT,
            user_prompt=build_weekly_review_user_prompt(context),
        )
        advice = self._validate_advice(llm_result)

        with db.begin():
            review = db.get(WeeklyReview, existing_id) if existing_id else None
            if review is None:
                review = WeeklyReview(user_id=user_id, week_start=start)
                db.add(review)

            review.week_end = end
            review.planned_tasks = context.planned_tasks
            review.completed_tasks = context.completed_tasks
            review.completion_rate = context.completion_rate
            review.focus_minutes = context.focus_minutes
            review.check_in_days = context.check_in_days
            review.average_sleep_hours = context.average_sleep_hours
            review.energy_distribution_json = context.energy_distribution
            review.mood_distribution_json = context.mood_distribution
            review.summary = advice.summary
            review.achievements_json = advice.achievements
            review.obstacles_json = advice.obstacles
            review.next_week_actions_json = advice.next_week_actions
            review.context_json = context.model_dump(mode="json")
            review.model_name = settings.ollama_model
            review.prompt_version = WEEKLY_REVIEW_PROMPT_VERSION

            db.flush()
            db.refresh(review)
            result = WeeklyReviewRead.model_validate(review)

        return result

    def build_context(
        self,
        db: Session,
        user_id: int,
        week_start: date,
        week_end: date,
    ) -> WeeklyReviewContext:
        tasks = list(
            db.scalars(
                select(DailyTask).where(
                    DailyTask.user_id == user_id,
                    DailyTask.task_date >= week_start,
                    DailyTask.task_date <= week_end,
                )
            )
        )
        completed_tasks = [task for task in tasks if task.status == "completed"]
        unfinished_tasks = [
            task for task in tasks if task.status in {"pending", "in_progress"}
        ]

        period_start = datetime.combine(week_start, time.min, tzinfo=timezone.utc)
        period_end = datetime.combine(
            week_end + timedelta(days=1),
            time.min,
            tzinfo=timezone.utc,
        )
        sessions = list(
            db.scalars(
                select(StudySession).where(
                    StudySession.user_id == user_id,
                    StudySession.status == "completed",
                    StudySession.started_at >= period_start,
                    StudySession.started_at < period_end,
                )
            )
        )
        check_ins = list(
            db.scalars(
                select(DailyCheckIn).where(
                    DailyCheckIn.user_id == user_id,
                    DailyCheckIn.check_in_date >= week_start,
                    DailyCheckIn.check_in_date <= week_end,
                )
            )
        )

        sleep_values = [item.sleep_hours for item in check_ins]
        average_sleep = (
            round(sum(sleep_values) / len(sleep_values), 2)
            if sleep_values
            else None
        )

        return WeeklyReviewContext(
            week_start=week_start,
            week_end=week_end,
            planned_tasks=len(tasks),
            completed_tasks=len(completed_tasks),
            unfinished_tasks=len(unfinished_tasks),
            completion_rate=(len(completed_tasks) / len(tasks) if tasks else 0.0),
            focus_minutes=sum(session.duration_minutes or 0 for session in sessions),
            check_in_days=len(check_ins),
            average_sleep_hours=average_sleep,
            energy_distribution=dict(
                Counter(item.energy_level for item in check_ins)
            ),
            mood_distribution=dict(Counter(item.mood_level for item in check_ins)),
            completed_task_titles=[task.title for task in completed_tasks],
            unfinished_task_titles=[task.title for task in unfinished_tasks],
            study_subjects=[session.subject for session in sessions],
            check_in_notes=[item.notes for item in check_ins if item.notes],
        )

    @staticmethod
    def current_week_start(reference_date: date | None = None) -> date:
        value = reference_date or date.today()
        return value - timedelta(days=value.weekday())

    @staticmethod
    def _ensure_no_pending_changes(db: Session) -> None:
        if db.new or db.dirty or db.deleted:
            raise PendingWeeklyReviewChangesError(
                "Cannot generate a weekly review with pending database changes"
            )

    @classmethod
    def _close_read_transaction(cls, db: Session) -> None:
        cls._ensure_no_pending_changes(db)
        if db.in_transaction():
            db.rollback()

    @staticmethod
    def _validate_advice(llm_result: dict) -> WeeklyReviewAdvice:
        try:
            return WeeklyReviewAdvice.model_validate(llm_result)
        except ValidationError as exc:
            raise InvalidWeeklyReviewResponseError(
                "Ollama returned an invalid weekly review"
            ) from exc


weekly_review_service = WeeklyReviewService()
