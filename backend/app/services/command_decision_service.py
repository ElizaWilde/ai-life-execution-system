from __future__ import annotations

from collections.abc import Callable
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.models import DailyTask, WeeklyGoal
from app.schemas.command import CommandDecision
from app.schemas.weekly_priority_plan import WeeklyPriorityPlan


DecisionPolicy = Callable[[Session, int, dict], CommandDecision]


class CommandDecisionService:
    """Deterministic policy layer between model interpretation and execution."""

    def __init__(self) -> None:
        self._policies: dict[str, DecisionPolicy] = {
            "create_task": self._decide_create_task,
            "create_weekly_priorities": self._decide_create_weekly_priorities,
            "reschedule_task": self._decide_move_task,
            "change_task_duration": self._decide_change_task_duration,
            "update_content": self._decide_update_content,
        }

    def evaluate(self, db: Session, user_id: int, intent: str, parameters: dict) -> CommandDecision:
        policy = self._policies.get(intent)
        return policy(db, user_id, parameters) if policy else self._allowed()

    def _decide_create_weekly_priorities(self, db: Session, user_id: int, parameters: dict) -> CommandDecision:
        try:
            plan = WeeklyPriorityPlan.model_validate(parameters)
        except ValidationError:
            return self._blocked("invalid_weekly_priority_plan", "The weekly priority plan is invalid. No priorities were added; submit a complete list with titles and time estimates.")
        existing = list(db.scalars(select(WeeklyGoal).where(
            WeeklyGoal.user_id == user_id,
            WeeklyGoal.status != "cancelled",
            WeeklyGoal.week_start <= plan.week_end,
            WeeklyGoal.week_end >= plan.week_start,
        )))
        seen: set[str] = set()
        conflicts = []
        for item in plan.weekly_priorities:
            name = self._normalize_title(item.title)
            if name in seen:
                conflicts.append({"type": "duplicate_in_batch", "title": item.title})
            seen.add(name)
            for goal in existing:
                if name == self._normalize_title(goal.title):
                    conflicts.append({"type": "duplicate_weekly_priority", "title": item.title, "weekly_goal_id": goal.id})
        if conflicts:
            titles = ", ".join(dict.fromkeys(f"“{item['title']}”" for item in conflicts))
            return self._blocked(
                "duplicate_weekly_priority",
                f"Duplicate weekly priorities in this list or the selected week: {titles}. No priorities were added. Choose different names or update the existing priorities.",
                conflicts=conflicts,
            )
        return self._allowed()

    def _decide_create_task(self, db: Session, user_id: int, parameters: dict) -> CommandDecision:
        return self._task_state_conflicts(
            db,
            user_id,
            title=str(parameters["title"]),
            task_date=date.fromisoformat(parameters["task_date"]),
            estimated_minutes=int(parameters["estimated_minutes"]),
            scheduled_start_minutes=parameters.get("scheduled_start_minutes"),
        )

    def _decide_move_task(self, db: Session, user_id: int, parameters: dict) -> CommandDecision:
        if parameters.get("scope") == "overdue":
            return self._allowed()

        task_id = parameters.get("daily_task_id")
        if task_id is not None:
            task = self._task(db, user_id, task_id)
            if task is None or task.status not in {"pending", "in_progress"}:
                return self._blocked(
                    "task_not_available",
                    "The selected task no longer exists or cannot be moved.",
                )
            original_date = parameters.get("original_date")
            if original_date and task.task_date != date.fromisoformat(original_date):
                return self._blocked(
                    "task_changed",
                    "The selected task has changed since the proposal was created. No change was made.",
                )
        else:
            candidates = self._move_candidates(db, user_id, parameters)
            if not candidates:
                return self._blocked(
                    "no_task_match",
                    f"I could not find a movable task matching “{parameters.get('query', '')}”.",
                )
            if len(candidates) > 1:
                details = ", ".join(
                    f"#{task.id} “{task.title}” on {task.task_date.isoformat()}"
                    + (
                        f" at {self._format_clock(task.scheduled_start_minutes)}"
                        if task.scheduled_start_minutes is not None
                        else ""
                    )
                    for task in candidates[:8]
                )
                return self._blocked(
                    "ambiguous_task_match",
                    f"More than one task matches. Choose one of: {details}.",
                    conflicts=[{
                        "type": "task_candidate",
                        "daily_task_id": task.id,
                        "title": task.title,
                        "task_date": task.task_date.isoformat(),
                        "scheduled_start_minutes": task.scheduled_start_minutes,
                    } for task in candidates[:8]],
                )
            task = candidates[0]

        destination_date = date.fromisoformat(parameters["destination_date"])
        destination_start = parameters.get("destination_start_minutes")
        if destination_start is None and parameters.get("preserve_start_time", True):
            destination_start = task.scheduled_start_minutes
        if (
            destination_start is not None
            and int(destination_start) + max(1, int(task.estimated_minutes or 0)) > 1_440
        ):
            return self._blocked(
                "invalid_destination",
                "The moved task would finish after the end of the destination day.",
            )
        if destination_date == task.task_date and destination_start == task.scheduled_start_minutes:
            return self._blocked("no_change", "The task is already scheduled at that date and time.")

        conflict = self._task_state_conflicts(
            db,
            user_id,
            title=task.title,
            task_date=destination_date,
            estimated_minutes=int(task.estimated_minutes or 0),
            scheduled_start_minutes=destination_start,
            exclude_task_id=task.id,
        )
        if not conflict.allowed:
            return conflict
        return CommandDecision(
            allowed=True,
            code="allowed",
            message="Move is allowed.",
            parameters_patch={
                "daily_task_id": task.id,
                "title": task.title,
                "original_date": task.task_date.isoformat(),
                "destination_date": destination_date.isoformat(),
                "destination_start_minutes": destination_start,
            },
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

    def _move_candidates(self, db: Session, user_id: int, parameters: dict) -> list[DailyTask]:
        query = select(DailyTask).where(
            DailyTask.user_id == user_id,
            DailyTask.status.in_(("pending", "in_progress")),
        )
        source_date = parameters.get("source_task_date")
        if source_date and parameters.get("source_date_was_stated", False):
            query = query.where(DailyTask.task_date == date.fromisoformat(source_date))
        source_start = parameters.get("source_start_minutes")
        if source_start is not None and parameters.get("source_start_was_stated", False):
            query = query.where(DailyTask.scheduled_start_minutes == int(source_start))
        tasks = list(db.scalars(query.order_by(DailyTask.task_date, DailyTask.id)))
        normalized_query = self._normalize_title(str(parameters.get("query") or ""))
        exact = [task for task in tasks if self._normalize_title(task.title) == normalized_query]
        if exact:
            return exact
        return [task for task in tasks if normalized_query in self._normalize_title(task.title)]

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
    def _blocked(
        code: str,
        message: str,
        *,
        conflicts: list[dict] | None = None,
    ) -> CommandDecision:
        return CommandDecision(
            allowed=False,
            code=code,
            message=message,
            conflicts=conflicts or [],
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
