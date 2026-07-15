from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyTask, WeeklyGoal
from app.schemas.daily_task import DailyPlanResponse
from app.services.coaching_context_service import coaching_context_service
from app.services.llm_service import llm_service
from app.services.workload_adjustment_service import workload_adjustment_service


VALID_PRIORITIES = {"low", "medium", "high"}
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
UNFINISHED_STATUSES = {"pending", "in_progress"}


class MissingActiveWeeklyGoalError(ValueError):
    """Raised when daily planning has no active weekly goal for direction."""


class PlanningService:
    """Generate and persist AI daily plans from weekly goals and unfinished tasks."""

    async def generate_daily_plan(
        self,
        db: Session,
        user_id: int,
        available_minutes: int,
        task_date: date | None = None,
    ) -> DailyPlanResponse:
        plan_date = task_date or date.today()
        context = coaching_context_service.build_daily_context(
            db=db,
            user_id=user_id,
            target_date=plan_date,
            available_minutes=available_minutes,
        )
        adjustment = workload_adjustment_service.calculate(context)
        adjusted_minutes = int(
            available_minutes * adjustment.workload_multiplier
        )

        weekly_goals = self._get_active_weekly_goals(db, user_id, plan_date)
        unfinished_tasks = self._get_unfinished_tasks(db, user_id, plan_date)

        if not weekly_goals:
            raise MissingActiveWeeklyGoalError(
                "No active weekly goal was found for this date. "
                "Create an active weekly goal before generating an AI plan."
            )

        generated_items = await llm_service.generate_daily_plan(
            weekly_goals=[self._weekly_goal_to_prompt(goal) for goal in weekly_goals],
            unfinished_tasks=[self._task_to_prompt(task) for task in unfinished_tasks],
            available_minutes=adjusted_minutes,
        )

        allowed_goal_ids = {goal.id for goal in weekly_goals}
        created_tasks = self._create_tasks_from_plan(
            db=db,
            user_id=user_id,
            plan_date=plan_date,
            generated_items=generated_items,
            allowed_goal_ids=allowed_goal_ids,
            available_minutes=adjusted_minutes,
        )

        db.commit()
        for task in created_tasks:
            db.refresh(task)

        return DailyPlanResponse(
            task_date=plan_date,
            original_available_minutes=available_minutes,
            adjusted_available_minutes=adjusted_minutes,
            workload_level=adjustment.workload_level,
            readiness_score=adjustment.readiness_score,
            tasks=created_tasks,
            total_estimated_minutes=sum(
                task.estimated_minutes or 0 for task in created_tasks
            ),
        )

    def _get_active_weekly_goals(
        self,
        db: Session,
        user_id: int,
        plan_date: date,
    ) -> list[WeeklyGoal]:
        return list(
            db.scalars(
                select(WeeklyGoal)
                .where(
                    WeeklyGoal.user_id == user_id,
                    WeeklyGoal.status == "active",
                    WeeklyGoal.week_start <= plan_date,
                    WeeklyGoal.week_end >= plan_date,
                )
                .order_by(WeeklyGoal.priority.desc(), WeeklyGoal.id)
            )
        )

    def _get_unfinished_tasks(
        self,
        db: Session,
        user_id: int,
        plan_date: date,
    ) -> list[DailyTask]:
        return list(
            db.scalars(
                select(DailyTask)
                .where(
                    DailyTask.user_id == user_id,
                    DailyTask.status.in_(UNFINISHED_STATUSES),
                    DailyTask.task_date <= plan_date,
                )
                .order_by(DailyTask.task_date, DailyTask.priority.desc(), DailyTask.id)
            )
        )

    def _create_tasks_from_plan(
        self,
        db: Session,
        user_id: int,
        plan_date: date,
        generated_items: list[dict[str, Any]],
        allowed_goal_ids: set[int],
        available_minutes: int,
    ) -> list[DailyTask]:
        created_tasks: list[DailyTask] = []
        remaining_minutes = available_minutes

        normalized_items = [
            normalized
            for item in generated_items
            if (normalized := self._normalize_plan_item(item, allowed_goal_ids))
            is not None
        ]
        normalized_items.sort(key=lambda item: PRIORITY_ORDER[item["priority"]])

        for normalized in normalized_items:
            if remaining_minutes <= 0:
                break

            estimated_minutes = normalized["estimated_minutes"]
            if estimated_minutes is not None and estimated_minutes > remaining_minutes:
                if not created_tasks:
                    normalized["estimated_minutes"] = remaining_minutes
                else:
                    continue

            task = DailyTask(
                user_id=user_id,
                task_date=plan_date,
                source="ai",
                status="pending",
                **normalized,
            )
            db.add(task)
            created_tasks.append(task)
            if task.estimated_minutes is not None:
                remaining_minutes -= task.estimated_minutes

            if remaining_minutes <= 0:
                break

        return created_tasks

    def _normalize_plan_item(
        self,
        item: dict[str, Any],
        allowed_goal_ids: set[int],
    ) -> dict[str, Any] | None:
        title = str(item.get("title") or "").strip()
        if not title:
            return None

        estimated_minutes = item.get("estimated_minutes")
        if estimated_minutes is not None:
            try:
                estimated_minutes = int(estimated_minutes)
            except (TypeError, ValueError):
                estimated_minutes = 30
            estimated_minutes = max(0, estimated_minutes)

        priority = str(item.get("priority") or "medium").lower()
        if priority not in VALID_PRIORITIES:
            priority = "medium"

        weekly_goal_id = item.get("weekly_goal_id")
        if weekly_goal_id is not None:
            try:
                weekly_goal_id = int(weekly_goal_id)
            except (TypeError, ValueError):
                weekly_goal_id = None
            if weekly_goal_id not in allowed_goal_ids:
                weekly_goal_id = None

        description = item.get("description")
        if description is not None:
            description = str(description)

        raw_model_output = item.get("raw_model_output")
        if raw_model_output is not None:
            raw_model_output = str(raw_model_output)

        return {
            "title": title[:255],
            "description": description,
            "estimated_minutes": estimated_minutes,
            "priority": priority,
            "weekly_goal_id": weekly_goal_id,
            "raw_model_output": raw_model_output,
        }

    @staticmethod
    def _weekly_goal_to_prompt(goal: WeeklyGoal) -> dict[str, Any]:
        return {
            "id": goal.id,
            "title": goal.title,
            "description": goal.description,
            "week_start": goal.week_start.isoformat(),
            "week_end": goal.week_end.isoformat(),
            "priority": goal.priority,
            "target_minutes": goal.target_minutes,
        }

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
            "weekly_goal_id": task.weekly_goal_id,
        }


planning_service = PlanningService()
