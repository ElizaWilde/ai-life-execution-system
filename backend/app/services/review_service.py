from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyReview, DailyTask, StudySession
from app.schemas.review import DailyReviewRead
from app.services.llm_service import llm_service


class ReviewService:
    """Generate and persist AI daily reviews from tasks and study sessions."""

    async def generate_daily_review(
        self,
        db: Session,
        user_id: int,
        review_date: date | None = None,
    ) -> DailyReviewRead:
        target_date = review_date or date.today()
        planned_tasks = self._get_planned_tasks(db, user_id, target_date)
        completed_tasks = [
            task for task in planned_tasks if task.status == "completed"
        ]
        study_sessions = self._get_study_sessions(db, user_id, target_date)
        focus_minutes = sum(session.duration_minutes or 0 for session in study_sessions)

        summary = await llm_service.generate_daily_review(
            planned_tasks=[self._task_to_prompt(task) for task in planned_tasks],
            completed_tasks=[self._task_to_prompt(task) for task in completed_tasks],
            study_sessions=[
                self._study_session_to_prompt(session) for session in study_sessions
            ],
        )

        review = self._get_existing_review(db, user_id, target_date)
        if review is None:
            review = DailyReview(
                user_id=user_id,
                review_date=target_date,
            )
            db.add(review)

        review.summary = summary.strip() or "No review generated."
        review.tomorrow_adjustment = self._build_tomorrow_adjustment(planned_tasks)
        review.planned_tasks = len(planned_tasks)
        review.completed_tasks = len(completed_tasks)
        review.focus_minutes = focus_minutes
        review.source = "ai"

        db.commit()
        db.refresh(review)
        return DailyReviewRead.model_validate(review)

    def _get_planned_tasks(
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
                .order_by(DailyTask.status, DailyTask.priority.desc(), DailyTask.id)
            )
        )

    def _get_study_sessions(
        self,
        db: Session,
        user_id: int,
        target_date: date,
    ) -> list[StudySession]:
        day_start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)
        return list(
            db.scalars(
                select(StudySession)
                .where(
                    StudySession.user_id == user_id,
                    StudySession.status == "completed",
                    StudySession.started_at >= day_start,
                    StudySession.started_at < day_end,
                )
                .order_by(StudySession.started_at, StudySession.id)
            )
        )

    def _get_existing_review(
        self,
        db: Session,
        user_id: int,
        target_date: date,
    ) -> DailyReview | None:
        return db.scalar(
            select(DailyReview).where(
                DailyReview.user_id == user_id,
                DailyReview.review_date == target_date,
            )
        )

    @staticmethod
    def _build_tomorrow_adjustment(tasks: list[DailyTask]) -> str | None:
        unfinished = [
            task.title
            for task in tasks
            if task.status not in {"completed", "cancelled"}
        ]
        if not unfinished:
            return "Keep tomorrow focused: start with the next highest-priority goal."
        return "Carry forward unfinished work: " + "; ".join(unfinished[:3])

    @staticmethod
    def _task_to_prompt(task: DailyTask) -> dict[str, Any]:
        return {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "task_date": task.task_date.isoformat(),
            "estimated_minutes": task.estimated_minutes,
            "priority": task.priority,
            "status": task.status,
            "source": task.source,
        }

    @staticmethod
    def _study_session_to_prompt(session: StudySession) -> dict[str, Any]:
        return {
            "id": session.id,
            "daily_task_id": session.daily_task_id,
            "subject": session.subject,
            "started_at": session.started_at.isoformat(),
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "duration_minutes": session.duration_minutes,
            "notes": session.notes,
        }


review_service = ReviewService()
