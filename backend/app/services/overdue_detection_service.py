from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models import DailyTask


INCOMPLETE_STATUSES = ("pending", "in_progress")


@dataclass(frozen=True)
class OverdueTaskFinding:
    task: DailyTask
    severity: str
    overdue_minutes: int
    evidence: tuple[str, ...]


class OverdueDetectionService:
    """Read-only, deterministic overdue classification."""

    def find(
        self,
        db: Session,
        user_id: int,
        now: datetime,
        *,
        local_date: date | None = None,
    ) -> list[OverdueTaskFinding]:
        now = self._as_utc(now)
        fallback_date = local_date or now.date()
        tasks = list(
            db.scalars(
                select(DailyTask)
                .where(
                    DailyTask.user_id == user_id,
                    DailyTask.status.in_(INCOMPLETE_STATUSES),
                    or_(
                        DailyTask.due_at <= now,
                        and_(
                            DailyTask.due_at.is_(None),
                            DailyTask.task_date < fallback_date,
                        ),
                    ),
                )
                .order_by(DailyTask.due_at, DailyTask.task_date, DailyTask.id)
            )
        )
        return [self._classify(task, now, fallback_date) for task in tasks]

    def _classify(
        self,
        task: DailyTask,
        now: datetime,
        fallback_date: date,
    ) -> OverdueTaskFinding:
        if task.due_at is not None:
            due_at = self._as_utc(task.due_at)
            overdue_minutes = max(0, int((now - due_at).total_seconds() // 60))
        else:
            overdue_minutes = max(
                0,
                (fallback_date - task.task_date).days * 24 * 60,
            )

        evidence = [f"Due time passed by {overdue_minutes} minute(s)"]
        if task.priority == "high":
            severity = "high"
            evidence.append("Task priority is high")
        elif overdue_minutes >= 3 * 24 * 60:
            severity = "high"
            evidence.append("Task is at least three days overdue")
        elif task.priority == "medium" or overdue_minutes >= 24 * 60:
            severity = "medium"
        else:
            severity = "low"

        return OverdueTaskFinding(
            task=task,
            severity=severity,
            overdue_minutes=overdue_minutes,
            evidence=tuple(evidence),
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


overdue_detection_service = OverdueDetectionService()
