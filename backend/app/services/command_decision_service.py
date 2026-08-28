from __future__ import annotations

from collections.abc import Callable
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyTask
from app.schemas.command import CommandDecision


DecisionPolicy = Callable[[Session, int, dict], CommandDecision]


class CommandDecisionService:
    """Deterministic policy layer between model interpretation and execution."""

    def __init__(self) -> None:
        self._policies: dict[str, DecisionPolicy] = {
            "create_task": self._decide_create_task,
            "change_task_duration": self._decide_change_task_duration,
            "update_content": self._decide_update_content,
        }

    def evaluate(self, db: Session, user_id: int, intent: str, parameters: dict) -> CommandDecision:
        policy = self._policies.get(intent)
        return policy(db, user_id, parameters) if policy else self._allowed()

    def _decide_create_task(self, db: Session, user_id: int, parameters: dict) -> CommandDecision:
        return self._task_state_conflicts(
            db,
            user_id,
            title=str(parameters["title"]),
            task_date=date.fromisoformat(parameters["task_date"]),
            estimated_minutes=int(parameters["estimated_minutes"]),
            scheduled_start_minutes=parameters.get("scheduled_start_minutes"),
        )

    def _decide_change_task_duration(self, db: Session, user_id: int, parameters: dict) -> CommandDecision:
        task = self._task(db, user_id, parameters.get("daily_task_id"))
        if task is None:
            return self._allowed()
        return self._task_state_conflicts(
            db,
            user_id,
            title=task.title,
            task_date=task.task_date,
            estimated_minutes=int(parameters["proposed_minutes"]),
            scheduled_start_minutes=task.scheduled_start_minutes,
            exclude_task_id=task.id,
            check_name=False,
        )

    def _decide_update_content(self, db: Session, user_id: int, parameters: dict) -> CommandDecision:
        if parameters.get("resource_type") != "daily_task":
            return self._allowed()
        task = self._task(db, user_id, parameters.get("resource_id"))
        if task is None:
            return self._allowed()
        changes = dict(parameters.get("changes") or {})
        task_date = changes.get("task_date", task.task_date)
        if isinstance(task_date, str):
            task_date = date.fromisoformat(task_date)
        estimated_minutes = changes.get("estimated_minutes", task.estimated_minutes)
        return self._task_state_conflicts(
            db,
            user_id,
            title=str(changes.get("title", task.title)),
            task_date=task_date,
            estimated_minutes=int(estimated_minutes or 0),
            scheduled_start_minutes=changes.get("scheduled_start_minutes", task.scheduled_start_minutes),
            exclude_task_id=task.id,
        )

    def _task_state_conflicts(
        self,
        db: Session,
        user_id: int,
        *,
        title: str,
        task_date: date,
        estimated_minutes: int,
        scheduled_start_minutes: int | None,
        exclude_task_id: int | None = None,
        check_name: bool = True,
    ) -> CommandDecision:
        query = select(DailyTask).where(
            DailyTask.user_id == user_id,
            DailyTask.task_date == task_date,
            DailyTask.status != "cancelled",
        )
        if exclude_task_id is not None:
            query = query.where(DailyTask.id != exclude_task_id)
        existing_tasks = list(db.scalars(query))
        conflicts: list[dict] = []

        if check_name:
            normalized_title = self._normalize_title(title)
            for task in existing_tasks:
                if self._normalize_title(task.title) == normalized_title:
                    conflicts.append({
                        "type": "duplicate_task_name",
                        "daily_task_id": task.id,
                        "title": task.title,
                        "task_date": task.task_date.isoformat(),
                    })

        if scheduled_start_minutes is not None:
            proposed_start = int(scheduled_start_minutes)
            proposed_end = proposed_start + max(1, estimated_minutes)
            for task in existing_tasks:
                if task.scheduled_start_minutes is None:
                    continue
                existing_start = int(task.scheduled_start_minutes)
                existing_end = existing_start + max(1, int(task.estimated_minutes or 0))
                if proposed_start < existing_end and existing_start < proposed_end:
                    conflicts.append({
                        "type": "schedule_conflict",
                        "daily_task_id": task.id,
                        "title": task.title,
                        "start_minutes": existing_start,
                        "end_minutes": existing_end,
                    })

        return self._conflict_decision(title, task_date, conflicts)

    def _conflict_decision(self, title: str, task_date: date, conflicts: list[dict]) -> CommandDecision:
        if not conflicts:
            return self._allowed()
        name_conflicts = [item for item in conflicts if item["type"] == "duplicate_task_name"]
        time_conflicts = [item for item in conflicts if item["type"] == "schedule_conflict"]
        reasons: list[str] = []
        if name_conflicts:
            reasons.append(f"A task named “{title}” already exists on {task_date.isoformat()}.")
        if time_conflicts:
            windows = ", ".join(
                f"“{item['title']}” ({self._format_clock(item['start_minutes'])}–{self._format_clock(item['end_minutes'])})"
                for item in time_conflicts
            )
            reasons.append(f"The proposed time overlaps with {windows}.")
        code = "task_conflict" if name_conflicts and time_conflicts else (
            "duplicate_task_name" if name_conflicts else "schedule_conflict"
        )
        return CommandDecision(
            allowed=False,
            code=code,
            message=" ".join(reasons) + " No change was made; choose a different name or time.",
            conflicts=conflicts,
        )

    @staticmethod
    def _task(db: Session, user_id: int, task_id: object) -> DailyTask | None:
        if task_id is None:
            return None
        return db.scalar(
            select(DailyTask).where(DailyTask.id == int(task_id), DailyTask.user_id == user_id)
        )

    @staticmethod
    def _normalize_title(title: str) -> str:
        return " ".join(title.casefold().split())

    @staticmethod
    def _format_clock(minutes_after_midnight: int) -> str:
        hours, minutes = divmod(int(minutes_after_midnight), 60)
        return f"{hours:02d}:{minutes:02d}"

    @staticmethod
    def _allowed() -> CommandDecision:
        return CommandDecision(allowed=True, code="allowed", message="Command is allowed.")


command_decision_service = CommandDecisionService()
