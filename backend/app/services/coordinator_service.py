from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AutomationAudit,
    AutomationCommand,
    AutomationPreference,
    DailyTask,
    Milestone,
    Phase,
    User,
    WeeklyGoal,
)
from app.schemas.notification import NotificationSend
from app.services.automation_audit_service import automation_audit_service
from app.services.automation_policy_service import (
    AutomationAction,
    automation_policy_service,
)
from app.services.forecast_service import forecast_service
from app.services.llm_service import llm_service
from app.services.notification_service import notification_service
from app.services.plan_preview_service import plan_preview_service
from app.services.rescheduling_proposal_service import rescheduling_proposal_service
from app.services.task_deadline_service import task_deadline_service


COORDINATOR_SYSTEM_PROMPT = """You are the Coordinator Agent for an AI Life Execution System.
Answer the user's questions clearly and practically. The application separately routes supported
plan-editing commands through a confirmation workflow, so never claim that ordinary chat changed
or saved data. If an action is unavailable, explain what would be needed. Keep answers concise
unless the user asks for detail."""


class CoordinatorService:
    async def answer(self, message: str, history: list[dict[str, str]]) -> str:
        return await llm_service.chat(
            system_prompt=COORDINATOR_SYSTEM_PROMPT,
            user_prompt=message,
            history=history,
        )

    def process_command(
        self,
        db: Session,
        user: User,
        message: str,
        *,
        idempotency_key: str | None = None,
    ) -> AutomationCommand:
        normalized = " ".join(message.strip().split())
        key = (
            idempotency_key.strip()
            if idempotency_key and idempotency_key.strip()
            else self.default_idempotency_key(user.id, normalized)
        )[:180]
        existing = db.scalar(
            select(AutomationCommand).where(
                AutomationCommand.idempotency_key == key,
                AutomationCommand.user_id == user.id,
            )
        )
        if existing is not None:
            return existing

        intent, parameters = self.classify(db, user.id, normalized)
        requires_confirmation = intent in {
            "create_task",
            "reschedule_task",
            "reduce_workload",
            "complete_task",
            "change_task_duration",
            "update_content",
        }
        command = AutomationCommand(
            user_id=user.id,
            idempotency_key=key,
            command_text=normalized,
            intent=intent,
            parameters_json=parameters,
            status="pending_confirmation" if requires_confirmation else "completed",
            requires_confirmation=requires_confirmation,
            response_message="",
            result_json={},
            expires_at=(
                datetime.now(timezone.utc) + timedelta(hours=24)
                if requires_confirmation
                else None
            ),
        )
        db.add(command)
        db.commit()
        db.refresh(command)

        action_key = f"command:{key}"[:180]
        audit, _ = automation_audit_service.claim(
            db,
            user_id=user.id,
            action_key=action_key,
            trigger_source="user_command",
            automation_type=intent,
            service_name="coordinator_service",
            input_json={"message": normalized, "parameters": parameters},
            confirmation_status="pending" if requires_confirmation else "not_required",
        )

        try:
            if requires_confirmation:
                command.response_message = self._pending_message(
                    db,
                    user,
                    command,
                )
                if command.status == "completed":
                    automation_audit_service.complete(
                        db,
                        audit,
                        decision_json={
                            "intent": intent,
                            "requires_confirmation": False,
                            "no_action_needed": True,
                        },
                    )
                else:
                    audit.execution_status = "pending"
                    audit.confirmation_status = "pending"
                    audit.decision_json = {
                        "intent": intent,
                        "requires_confirmation": True,
                    }
                    db.commit()
            else:
                self._execute_read_or_safe(db, user, command)
                automation_audit_service.complete(
                    db,
                    audit,
                    decision_json={
                        "intent": intent,
                        "requires_confirmation": False,
                    },
                    records_changed=command.result_json.get("records_changed", []),
                )
            db.refresh(command)
            return command
        except Exception as exc:
            db.rollback()
            command = db.get(AutomationCommand, command.id)
            if command is not None:
                command.status = "failed"
                command.response_message = str(exc)
                db.commit()
            automation_audit_service.fail(db, audit, exc)
            raise

    def confirm(
        self,
        db: Session,
        user: User,
        command_id: int,
    ) -> AutomationCommand:
        command = self._get_command(db, user.id, command_id)
        if command.status == "completed":
            return command
        if command.status != "pending_confirmation":
            raise ValueError(f"Command cannot be confirmed from status {command.status}.")
        if command.expires_at and self._as_utc(command.expires_at) <= datetime.now(timezone.utc):
            command.status = "failed"
            command.response_message = "This command expired. Submit it again for a fresh preview."
            db.commit()
            return command

        audit = db.scalar(
            select(AutomationAudit).where(
                AutomationAudit.action_key
                == f"command:{command.idempotency_key}"[:180]
            )
        )
        try:
            result, message = self._execute_confirmed(db, user, command)
            command.status = "completed"
            command.confirmed_at = datetime.now(timezone.utc)
            command.executed_at = command.confirmed_at
            command.result_json = result
            command.response_message = message
            db.commit()
            db.refresh(command)
            if audit is not None:
                automation_audit_service.complete(
                    db,
                    audit,
                    decision_json={"intent": command.intent, "confirmed": True},
                    records_changed=result.get("records_changed", []),
                    confirmation_status="confirmed",
                )
            return command
        except Exception as exc:
            db.rollback()
            if audit is not None:
                automation_audit_service.fail(db, audit, exc)
            raise

    def reject(
        self,
        db: Session,
        user_id: int,
        command_id: int,
    ) -> AutomationCommand:
        command = self._get_command(db, user_id, command_id)
        if command.status == "rejected":
            return command
        if command.status != "pending_confirmation":
            raise ValueError(f"Command cannot be rejected from status {command.status}.")
        if command.intent == "reschedule_task" and command.parameters_json.get("proposal_id"):
            rescheduling_proposal_service.reject(
                db,
                user_id,
                int(command.parameters_json["proposal_id"]),
            )
        command.status = "rejected"
        command.rejected_at = datetime.now(timezone.utc)
        command.response_message = "Command rejected. No records were changed."
        db.commit()
        db.refresh(command)
        audit = db.scalar(
            select(AutomationAudit).where(
                AutomationAudit.action_key
                == f"command:{command.idempotency_key}"[:180]
            )
        )
        if audit is not None:
            automation_audit_service.cancel(db, audit)
        return command

    def classify(
        self,
        db: Session,
        user_id: int,
        message: str,
    ) -> tuple[str, dict]:
        lowered = message.casefold()
        task_create = self._task_create_parameters(db, user_id, message)
        if task_create is not None:
            return "create_task", task_create
        if "remind me" in lowered or lowered.startswith("remind "):
            return "create_reminder", self._reminder_parameters(message)
        if any(phrase in lowered for phrase in ("move ", "reschedule", "roll over", "rollover")):
            return "reschedule_task", {"scope": "overdue", "horizon_days": 14}
        if any(phrase in lowered for phrase in ("reduce workload", "lighter week", "reduce this week")):
            return "reduce_workload", {"reduction_percent": 20}
        duration_match = re.search(
            r"(?:change|set|update)\s+(?:the\s+)?(?:daily\s+)?task\s+(.+?)\s+"
            r"(?:(?:duration|planned\s+time)\s+)?(?:to|for)\s+"
            r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m)\b",
            message,
            flags=re.IGNORECASE,
        )
        if duration_match:
            query = duration_match.group(1).strip(" .")
            amount = float(duration_match.group(2))
            unit = duration_match.group(3).casefold()
            proposed_minutes = round(amount * 60) if unit.startswith("h") else round(amount)
            task = self._match_task(db, user_id, query)
            return "change_task_duration", {
                "query": query,
                "daily_task_id": task.id if task else None,
                "title": task.title if task else None,
                "current_minutes": task.estimated_minutes if task else None,
                "proposed_minutes": proposed_minutes,
            }
        content_update = self._content_update_parameters(db, user_id, message)
        if content_update is not None:
            return "update_content", content_update
        complete_match = re.search(
            r"(?:complete|mark)\s+(?:task\s+)?(.+?)(?:\s+(?:as\s+)?done)?$",
            message,
            flags=re.IGNORECASE,
        )
        if complete_match:
            query = complete_match.group(1).strip(" .")
            task = self._match_task(db, user_id, query)
            return "complete_task", {
                "query": query,
                "daily_task_id": task.id if task else None,
                "title": task.title if task else None,
            }
        if "forecast" in lowered or "behind this week" in lowered or "finish this week" in lowered:
            return "get_forecast", {}
        if "progress" in lowered or "how am i doing" in lowered:
            return "get_progress", {}
        if any(phrase in lowered for phrase in ("what should i focus", "what should i do", "coach me")):
            return "get_coaching", {}
        return "unknown", {}

    def _pending_message(
        self,
        db: Session,
        user: User,
        command: AutomationCommand,
    ) -> str:
        if command.intent == "create_task":
            parameters = command.parameters_json
            details = [
                self._format_minutes(int(parameters["estimated_minutes"])),
                parameters["priority"],
            ]
            if parameters.get("channel"):
                details.append(parameters["channel"])
            return (
                f"Add task \u201c{parameters['title']}\u201d to {parameters['task_date']} "
                f"({', '.join(details)}). Confirm?"
            )
        if command.intent == "reschedule_task":
            proposal = rescheduling_proposal_service.create_for_user(
                db,
                user.id,
                datetime.now(timezone.utc),
                horizon_days=command.parameters_json.get("horizon_days", 14),
            )
            if proposal is None:
                command.status = "completed"
                command.requires_confirmation = False
                command.response_message = "No overdue tasks need rescheduling."
                command.result_json = {}
                command.executed_at = datetime.now(timezone.utc)
                db.commit()
                return command.response_message
            command.parameters_json = {
                **command.parameters_json,
                "proposal_id": proposal.id,
            }
            db.commit()
            return (
                f"Proposal #{proposal.id} will move {len(proposal.items)} task(s) "
                f"covering {proposal.expected_minutes} estimated minutes. Confirm?"
            )
        if command.intent == "reduce_workload":
            goals = list(
                db.scalars(
                    select(WeeklyGoal).where(
                        WeeklyGoal.user_id == user.id,
                        WeeklyGoal.status == "active",
                        WeeklyGoal.week_start <= date.today(),
                        WeeklyGoal.week_end >= date.today(),
                    )
                )
            )
            current = sum(goal.target_minutes or 0 for goal in goals)
            proposed = round(current * 0.8)
            command.parameters_json = {
                **command.parameters_json,
                "current_minutes": current,
                "proposed_minutes": proposed,
            }
            db.commit()
            return (
                f"Reduce this week's planned focus from {current} to "
                f"{proposed} minutes across {len(goals)} goal(s). Confirm?"
            )
        if command.intent == "change_task_duration":
            task_id = command.parameters_json.get("daily_task_id")
            if task_id is None:
                command.status = "failed"
                command.response_message = (
                    f"I could not find an unfinished task matching "
                    f"“{command.parameters_json.get('query', '')}”."
                )
                db.commit()
                return command.response_message
            proposed_minutes = int(command.parameters_json.get("proposed_minutes") or 0)
            if not 1 <= proposed_minutes <= 1_440:
                command.status = "failed"
                command.response_message = "Task duration must be between 1 minute and 24 hours."
                db.commit()
                return command.response_message
            return (
                f"Change “{command.parameters_json['title']}” planned time from "
                f"{self._format_minutes(command.parameters_json.get('current_minutes'))} to "
                f"{self._format_minutes(proposed_minutes)}. Confirm?"
            )
        if command.intent == "update_content":
            if command.parameters_json.get("resource_id") is None:
                command.status = "failed"
                command.response_message = (
                    f"I could not find {command.parameters_json.get('resource_label', 'content')} "
                    f"matching “{command.parameters_json.get('query', '')}”."
                )
                db.commit()
                return command.response_message
            return (
                f"Update {command.parameters_json['resource_label']} "
                f"“{command.parameters_json['title']}”: "
                f"{command.parameters_json['field_label']} from "
                f"{self._display_value(command.parameters_json.get('current_value'))} to "
                f"{self._display_value(command.parameters_json.get('new_value'))}. Confirm?"
            )
        task_id = command.parameters_json.get("daily_task_id")
        if task_id is None:
            command.status = "failed"
            command.response_message = (
                f"I could not find an unfinished task matching "
                f"“{command.parameters_json.get('query', '')}”."
            )
            db.commit()
            return command.response_message
        return f"Mark “{command.parameters_json['title']}” complete. Confirm?"

    def _execute_read_or_safe(
        self,
        db: Session,
        user: User,
        command: AutomationCommand,
    ) -> None:
        now = datetime.now(timezone.utc)
        if command.intent == "get_forecast":
            forecasts = forecast_service.generate_for_user(db, user.id, now)
            if forecasts:
                highest = sorted(
                    forecasts,
                    key=lambda item: {"high": 0, "medium": 1, "low": 2}[item.risk_level],
                )[0]
                command.response_message = (
                    f"Your highest-risk goal has a "
                    f"{round(highest.completion_probability * 100)}% completion "
                    f"forecast ({highest.risk_level} risk). "
                    f"{highest.recommended_adjustment}"
                )
                command.result_json = {
                    "forecast_ids": [item.id for item in forecasts],
                    "risk_level": highest.risk_level,
                    "completion_probability": highest.completion_probability,
                }
            else:
                command.response_message = "No active weekly goal is available to forecast."
        elif command.intent == "get_progress":
            week_start = date.today() - timedelta(days=date.today().weekday())
            tasks = list(
                db.scalars(
                    select(DailyTask).where(
                        DailyTask.user_id == user.id,
                        DailyTask.task_date >= week_start,
                        DailyTask.task_date <= week_start + timedelta(days=6),
                        DailyTask.status != "cancelled",
                    )
                )
            )
            completed = sum(task.status == "completed" for task in tasks)
            rate = round((completed / len(tasks)) * 100) if tasks else 0
            command.response_message = (
                f"You completed {completed} of {len(tasks)} planned task(s) "
                f"this week ({rate}%)."
            )
            command.result_json = {"completed": completed, "planned": len(tasks), "rate": rate}
        elif command.intent == "get_coaching":
            tasks = list(
                db.scalars(
                    select(DailyTask)
                    .where(
                        DailyTask.user_id == user.id,
                        DailyTask.task_date <= date.today(),
                        DailyTask.status.in_(("pending", "in_progress")),
                    )
                    .order_by(DailyTask.priority.desc(), DailyTask.due_at, DailyTask.id)
                    .limit(3)
                )
            )
            if tasks:
                command.response_message = (
                    f"Focus first on “{tasks[0].title}”. Keep the first step small, "
                    f"then continue with {len(tasks) - 1} remaining priority task(s)."
                )
                command.result_json = {"task_ids": [task.id for task in tasks]}
            else:
                command.response_message = "Your current plan is clear; choose one weekly goal to advance."
        elif command.intent == "create_reminder":
            scheduled_at = self._scheduled_reminder_time(db, user.id, command.parameters_json)
            subject = command.parameters_json.get("subject") or "Task reminder"
            notification = notification_service.create(
                db,
                user,
                NotificationSend(
                    notification_type="upcoming_task",
                    subject=subject,
                    message=f"Reminder: {subject}",
                    scheduled_at=scheduled_at,
                ),
                deduplication_key=f"command-reminder:{command.idempotency_key}"[:180],
            )
            command.response_message = (
                f"Reminder scheduled for {scheduled_at.isoformat()} "
                f"through {notification.channel}."
            )
            command.result_json = {
                "notification_id": notification.id,
                "records_changed": [{"model": "Notification", "id": notification.id}],
            }
        else:
            command.status = "unknown"
            command.response_message = (
                "I can show progress or forecasts, suggest focus, schedule a reminder, "
                "reschedule overdue tasks, reduce weekly workload, or complete a task."
            )
        command.executed_at = now
        db.commit()
        db.refresh(command)

    def _execute_confirmed(
        self,
        db: Session,
        user: User,
        command: AutomationCommand,
    ) -> tuple[dict, str]:
        if command.intent == "create_task":
            decision = automation_policy_service.evaluate(
                AutomationAction.CREATE_TASK,
                confirmed=True,
            )
            if not decision.allowed:
                raise ValueError(decision.reason)
            parameters = command.parameters_json
            weekly_goal_id = parameters.get("weekly_goal_id")
            if weekly_goal_id is not None:
                goal = db.scalar(
                    select(WeeklyGoal).where(
                        WeeklyGoal.id == int(weekly_goal_id),
                        WeeklyGoal.user_id == user.id,
                        WeeklyGoal.status == "active",
                    )
                )
                if goal is None:
                    raise ValueError("The selected weekly priority no longer exists.")
            task_date = date.fromisoformat(parameters["task_date"])
            task = DailyTask(
                user_id=user.id,
                weekly_goal_id=weekly_goal_id,
                title=parameters["title"],
                description=parameters.get("description"),
                task_date=task_date,
                planning_scope="daily",
                due_at=task_deadline_service.calculate(db, user.id, task_date, "daily"),
                estimated_minutes=int(parameters["estimated_minutes"]),
                channel=parameters.get("channel"),
                priority=parameters["priority"],
                status="pending",
                source="ai",
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            return (
                {
                    "daily_task_id": task.id,
                    "task_date": task.task_date.isoformat(),
                    "records_changed": [{"model": "DailyTask", "id": task.id}],
                },
                f"Added \u201c{task.title}\u201d to {task.task_date.isoformat()}.",
            )

        if command.intent == "reschedule_task":
            decision = automation_policy_service.evaluate(
                AutomationAction.MOVE_TASK_TO_ANOTHER_DAY,
                confirmed=True,
            )
            if not decision.allowed:
                raise ValueError(decision.reason)
            proposal = rescheduling_proposal_service.confirm(
                db,
                user.id,
                int(command.parameters_json["proposal_id"]),
            )
            return (
                {
                    "proposal_id": proposal.id,
                    "records_changed": [
                        {"model": "DailyTask", "id": item.daily_task_id}
                        for item in proposal.items
                    ],
                },
                f"Confirmed and moved {len(proposal.items)} task(s).",
            )
        if command.intent == "reduce_workload":
            decision = automation_policy_service.evaluate(
                AutomationAction.REDUCE_WEEKLY_GOAL,
                confirmed=True,
            )
            if not decision.allowed:
                raise ValueError(decision.reason)
            week_start = date.today() - timedelta(days=date.today().weekday())
            preview = plan_preview_service.create_weekly(
                db,
                user.id,
                week_start,
                int(command.parameters_json["proposed_minutes"]),
            )
            confirmed = plan_preview_service.confirm(db, user.id, preview.id)
            return (
                {
                    "weekly_preview_id": confirmed.id,
                    "records_changed": [
                        {
                            "model": "WeeklyGoal",
                            "id": allocation["weekly_goal_id"],
                        }
                        for allocation in confirmed.payload_json["goal_allocations"]
                    ],
                },
                f"Weekly workload reduced to {confirmed.recommended_minutes} minutes.",
            )

        if command.intent == "change_task_duration":
            decision = automation_policy_service.evaluate(
                AutomationAction.CHANGE_TASK_DURATION,
                confirmed=True,
            )
            if not decision.allowed:
                raise ValueError(decision.reason)
            task = db.scalar(
                select(DailyTask).where(
                    DailyTask.id == command.parameters_json["daily_task_id"],
                    DailyTask.user_id == user.id,
                )
            )
            if task is None:
                raise ValueError("The matched task no longer exists.")
            previous_minutes = task.estimated_minutes
            proposed_minutes = int(command.parameters_json["proposed_minutes"])
            task.estimated_minutes = proposed_minutes
            db.commit()
            return (
                {
                    "daily_task_id": task.id,
                    "previous_minutes": previous_minutes,
                    "estimated_minutes": proposed_minutes,
                    "records_changed": [{"model": "DailyTask", "id": task.id}],
                },
                f"Changed “{task.title}” planned time to {self._format_minutes(proposed_minutes)}.",
            )

        if command.intent == "update_content":
            return self._execute_content_update(db, user, command)

        decision = automation_policy_service.evaluate(
            AutomationAction.COMPLETE_TASK,
            confirmed=True,
        )
        if not decision.allowed:
            raise ValueError(decision.reason)
        task = db.scalar(
            select(DailyTask).where(
                DailyTask.id == command.parameters_json["daily_task_id"],
                DailyTask.user_id == user.id,
            )
        )
        if task is None:
            raise ValueError("The matched task no longer exists.")
        task.status = "completed"
        task.completed_at = datetime.now(timezone.utc)
        db.commit()
        return (
            {
                "daily_task_id": task.id,
                "records_changed": [{"model": "DailyTask", "id": task.id}],
            },
            f"Marked “{task.title}” complete.",
        )

    @staticmethod
    def _get_command(
        db: Session,
        user_id: int,
        command_id: int,
    ) -> AutomationCommand:
        command = db.scalar(
            select(AutomationCommand).where(
                AutomationCommand.id == command_id,
                AutomationCommand.user_id == user_id,
            )
        )
        if command is None:
            raise LookupError("Command not found")
        return command

    def _task_create_parameters(
        self,
        db: Session,
        user_id: int,
        message: str,
    ) -> dict | None:
        if not re.search(r"(?:^/add_task\b|\b(?:add|create)\s+(?:a\s+)?(?:daily\s+)?task\b)", message, re.IGNORECASE):
            return None

        keyed = message.lstrip().casefold().startswith("/add_task")
        local_today = self._user_local_date(db, user_id)
        date_match = re.search(
            r"\bdate\s*=\s*(today|tomorrow|\d{4}-\d{2}-\d{2})\b" if keyed
            else r"\b(today|tomorrow|\d{4}-\d{2}-\d{2})\b",
            message,
            re.IGNORECASE,
        )
        raw_date = date_match.group(1).casefold() if date_match else "today"
        if raw_date == "today":
            task_date = local_today
        elif raw_date == "tomorrow":
            task_date = local_today + timedelta(days=1)
        else:
            task_date = date.fromisoformat(raw_date)

        duration_match = re.search(
            r"\bduration\s*=\s*(\d+(?:\.\d+)?\s*(?:hours?|hrs?|h|minutes?|mins?|m))\b" if keyed
            else r"\b(\d+(?:\.\d+)?\s*(?:hours?|hrs?|h|minutes?|mins?|m))\b",
            message,
            re.IGNORECASE,
        )
        if duration_match is None:
            raise ValueError("Include a planned time such as 1h or 30 minutes.")
        estimated_minutes = self._parse_duration(duration_match.group(1))

        priority_match = re.search(
            r"\bpriority\s*=\s*(urgent|high|medium|normal|low)\b" if keyed
            else r"\b(urgent|high|medium|normal|low)(?:\s+priority)?\b",
            message,
            re.IGNORECASE,
        )
        priority = self._priority_value(priority_match.group(1), allow_urgent=True) if priority_match else "medium"

        channel_match = re.search(
            r"\b(?:tags?|channel)\s*(?:=|:)\s*(work|assignments|networking|projects|study|personal)\b",
            message,
            re.IGNORECASE,
        )
        channel = channel_match.group(1).casefold() if channel_match else None

        goal_match = re.search(r"\bobjective\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|([^\s]+))", message, re.IGNORECASE)
        weekly_goal_id = None
        if goal_match:
            goal_query = next(value for value in goal_match.groups() if value)
            goal = db.scalar(
                select(WeeklyGoal).where(
                    WeeklyGoal.user_id == user_id,
                    WeeklyGoal.status == "active",
                    func.lower(WeeklyGoal.title).contains(goal_query.casefold()),
                )
            )
            if goal is None:
                raise ValueError(f"No active weekly priority matches \u201c{goal_query}\u201d.")
            weekly_goal_id = goal.id

        if keyed:
            title_match = re.search(r"\btitle\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|(.+?)(?=\s+\w+\s*=|$))", message, re.IGNORECASE)
            if title_match is None:
                raise ValueError("Include title=\"Task name\" in the add-task command.")
            title = next(value for value in title_match.groups() if value).strip()
        else:
            title = re.sub(r"^.*?\b(?:add|create)\s+(?:a\s+)?(?:daily\s+)?task\b", "", message, count=1, flags=re.IGNORECASE)
            title = re.sub(
                r"\b(?:in|for|on)?\s*(?:today|tomorrow|\d{4}-\d{2}-\d{2})\b\s*:?",
                " ",
                title,
                flags=re.IGNORECASE,
            )
            title = title.replace(duration_match.group(1), " ")
            title = re.sub(r"\b(?:urgent|high|medium|normal|low)(?:\s+priority)?\b", " ", title, flags=re.IGNORECASE)
            title = re.sub(r"\b(?:tags?|channel)\s*(?:=|:)\s*\w+\b", " ", title, flags=re.IGNORECASE)
            title = re.sub(r"\bobjective\s*=\s*(?:\"[^\"]+\"|'[^']+'|\S+)", " ", title, flags=re.IGNORECASE)
            title = " ".join(title.strip(" :-.,").split())
        if not title:
            raise ValueError("Include a task title.")
        if len(title) > 255:
            raise ValueError("Task title must be 255 characters or fewer.")

        return {
            "title": title,
            "description": None,
            "task_date": task_date.isoformat(),
            "estimated_minutes": estimated_minutes,
            "channel": channel,
            "priority": priority,
            "weekly_goal_id": weekly_goal_id,
        }

    @staticmethod
    def _user_local_date(db: Session, user_id: int) -> date:
        timezone_name = db.scalar(
            select(AutomationPreference.timezone).where(AutomationPreference.user_id == user_id)
        ) or "UTC"
        try:
            zone = ZoneInfo(timezone_name)
        except Exception:
            zone = ZoneInfo("UTC")
        return datetime.now(timezone.utc).astimezone(zone).date()

    def _content_update_parameters(
        self,
        db: Session,
        user_id: int,
        message: str,
    ) -> dict | None:
        status_match = re.search(
            r"(?:mark|set)\s+(?:the\s+)?(?:daily\s+)?task\s+(.+?)\s+"
            r"(?:(?:status\s+)?(?:to|as)\s+)?(pending|in[ _-]?progress|done|completed)$",
            message,
            flags=re.IGNORECASE,
        )
        if status_match:
            resource_name, query, field_name, raw_value = (
                "task",
                status_match.group(1).strip(" ."),
                "status",
                status_match.group(2),
            )
        else:
            rename_match = re.search(
                r"rename\s+(?:the\s+)?(daily\s+task|task|weekly\s+priority|weekly\s+goal|phase|milestone)\s+(.+?)\s+to\s+(.+)$",
                message,
                flags=re.IGNORECASE,
            )
            if rename_match:
                resource_name, query, field_name, raw_value = (
                    rename_match.group(1),
                    rename_match.group(2).strip(" ."),
                    "title",
                    rename_match.group(3).strip(),
                )
            else:
                update_match = re.search(
                    r"(?:change|set|update)\s+(?:the\s+)?"
                    r"(daily\s+task|task|weekly\s+priority|weekly\s+goal|phase|milestone)\s+"
                    r"(.+?)\s+(planned\s+time|target\s+time|focus\s+time|due\s+date|start\s+date|end\s+date|"
                    r"title|name|description|priority|channel|objective|status|progress|notes|date|time)\s+"
                    r"(?:to|as)\s+(.+)$",
                    message,
                    flags=re.IGNORECASE,
                )
                if not update_match:
                    return None
                resource_name, query, field_name, raw_value = (
                    update_match.group(1),
                    update_match.group(2).strip(" ."),
                    update_match.group(3),
                    update_match.group(4).strip(),
                )

        resource_key = re.sub(r"\s+", "_", resource_name.casefold())
        if resource_key in {"daily_task", "task"}:
            resource_key = "daily_task"
            resource = self._match_task(db, user_id, query, include_completed=True)
        elif resource_key in {"weekly_priority", "weekly_goal"}:
            resource_key = "weekly_goal"
            resource = db.scalar(
                select(WeeklyGoal)
                .where(
                    WeeklyGoal.user_id == user_id,
                    WeeklyGoal.status != "cancelled",
                    func.lower(WeeklyGoal.title).contains(query.casefold()),
                )
                .order_by(WeeklyGoal.week_start != self._current_week_start(), WeeklyGoal.id)
            )
        elif resource_key == "phase":
            resource = db.scalar(
                select(Phase)
                .where(
                    Phase.user_id == user_id,
                    func.lower(Phase.title).contains(query.casefold()),
                )
                .order_by(Phase.status != "active", Phase.id)
            )
        else:
            resource_key = "milestone"
            resource = db.scalar(
                select(Milestone)
                .join(Phase, Phase.id == Milestone.phase_id)
                .where(
                    Phase.user_id == user_id,
                    func.lower(Milestone.title).contains(query.casefold()),
                )
                .order_by(Phase.status != "active", Milestone.position, Milestone.id)
            )

        parameters = {
            "resource_type": resource_key,
            "resource_label": {
                "daily_task": "task",
                "weekly_goal": "weekly priority",
                "phase": "phase",
                "milestone": "milestone",
            }[resource_key],
            "resource_id": resource.id if resource else None,
            "query": query,
            "title": resource.title if resource else query,
            "field_label": field_name.casefold(),
            "changes": {},
            "current_value": None,
            "new_value": raw_value,
        }
        if resource is None:
            return parameters

        field, value, display_value = self._normalize_content_change(
            db,
            user_id,
            resource_key,
            field_name,
            raw_value,
        )
        parameters["field_label"] = field_name.casefold()
        parameters["changes"] = {field: value}
        current = getattr(resource, field)
        if field == "weekly_goal_id":
            current_goal = db.get(WeeklyGoal, current) if current else None
            parameters["current_value"] = current_goal.title if current_goal else "unassigned"
        else:
            parameters["current_value"] = self._json_value(current)
        parameters["new_value"] = display_value
        return parameters

    def _normalize_content_change(
        self,
        db: Session,
        user_id: int,
        resource_type: str,
        field_name: str,
        raw_value: str,
    ) -> tuple[str, object, object]:
        field_key = re.sub(r"\s+", "_", field_name.casefold())
        clean_value = raw_value.strip().strip('"')
        if field_key == "name":
            field_key = "title"

        if resource_type == "daily_task":
            if field_key in {"planned_time", "time"}:
                minutes = self._parse_duration(clean_value)
                return "estimated_minutes", minutes, self._format_minutes(minutes)
            if field_key == "date":
                parsed = self._parse_date(clean_value)
                return "task_date", parsed.isoformat(), parsed.isoformat()
            if field_key == "priority":
                mapped = self._priority_value(clean_value, allow_urgent=True)
                return "priority", mapped, mapped
            if field_key == "channel":
                channel = clean_value.casefold().replace(" ", "_")
                if channel in {"unassigned", "none", "clear"}:
                    return "channel", None, "unassigned"
                if channel not in {"work", "assignments", "networking", "projects", "study", "personal"}:
                    raise ValueError("Channel must be work, assignments, networking, projects, study, personal, or unassigned.")
                return "channel", channel, channel
            if field_key == "objective":
                if clean_value.casefold() in {"unassigned", "none", "clear"}:
                    return "weekly_goal_id", None, "unassigned"
                goal = db.scalar(
                    select(WeeklyGoal).where(
                        WeeklyGoal.user_id == user_id,
                        WeeklyGoal.status == "active",
                        func.lower(WeeklyGoal.title).contains(clean_value.casefold()),
                    )
                )
                if goal is None:
                    raise ValueError(f"No active weekly priority matches “{clean_value}”.")
                return "weekly_goal_id", goal.id, goal.title
            if field_key == "status":
                status = self._task_status_value(clean_value)
                return "status", status, status
            if field_key in {"title", "description"}:
                value = None if field_key == "description" and clean_value.casefold() in {"none", "clear"} else clean_value
                return field_key, value, value or "empty"
            raise ValueError(f"{field_name} is not editable for a daily task.")

        if resource_type == "weekly_goal":
            if field_key in {"planned_time", "target_time", "time"}:
                minutes = self._parse_duration(clean_value)
                return "target_minutes", minutes, self._format_minutes(minutes)
            if field_key == "priority":
                mapped = self._priority_value(clean_value, allow_urgent=False)
                return "priority", mapped, mapped
            if field_key == "status":
                status = clean_value.casefold().replace(" ", "_")
                if status not in {"active", "completed", "cancelled"}:
                    raise ValueError("Weekly priority status must be active, completed, or cancelled.")
                return "status", status, status
            if field_key in {"title", "description"}:
                value = None if field_key == "description" and clean_value.casefold() in {"none", "clear"} else clean_value
                return field_key, value, value or "empty"
            raise ValueError(f"{field_name} is not editable for a weekly priority.")

        if resource_type == "phase":
            mapping = {"focus_time": "estimated_focus_minutes"}
            field_key = mapping.get(field_key, field_key)
            if field_key == "estimated_focus_minutes":
                minutes = self._parse_duration(clean_value)
                return field_key, minutes, self._format_minutes(minutes)
            if field_key == "progress":
                progress = self._parse_progress(clean_value)
                return field_key, progress, f"{progress}%"
            if field_key in {"start_date", "end_date"}:
                parsed = self._parse_date(clean_value)
                return field_key, parsed.isoformat(), parsed.isoformat()
            if field_key == "status":
                status = clean_value.casefold().replace(" ", "_")
                if status not in {"planning", "active", "completed", "archived"}:
                    raise ValueError("Phase status must be planning, active, completed, or archived.")
                return field_key, status, status
            if field_key in {"title", "description", "notes"}:
                value = None if field_key in {"description", "notes"} and clean_value.casefold() in {"none", "clear"} else clean_value
                return field_key, value, value or "empty"
            raise ValueError(f"{field_name} is not editable for a phase.")

        if field_key == "progress":
            progress = self._parse_progress(clean_value)
            return field_key, progress, f"{progress}%"
        if field_key == "due_date":
            parsed = self._parse_date(clean_value)
            return field_key, parsed.isoformat(), parsed.isoformat()
        if field_key == "status":
            status = clean_value.casefold().replace(" ", "_").replace("done", "completed")
            if status not in {"not_started", "in_progress", "completed"}:
                raise ValueError("Milestone status must be not started, in progress, or completed.")
            return field_key, status, status
        if field_key in {"title", "description"}:
            value = None if field_key == "description" and clean_value.casefold() in {"none", "clear"} else clean_value
            return field_key, value, value or "empty"
        raise ValueError(f"{field_name} is not editable for a milestone.")

    def _execute_content_update(
        self,
        db: Session,
        user: User,
        command: AutomationCommand,
    ) -> tuple[dict, str]:
        parameters = command.parameters_json
        resource_type = parameters["resource_type"]
        resource_id = int(parameters["resource_id"])
        changes = dict(parameters["changes"])
        if resource_type == "daily_task":
            resource = db.scalar(select(DailyTask).where(DailyTask.id == resource_id, DailyTask.user_id == user.id))
            action = AutomationAction.UPDATE_TASK_DETAILS
            if changes.get("status") == "cancelled":
                action = AutomationAction.DELETE_TASKS
        elif resource_type == "weekly_goal":
            resource = db.scalar(select(WeeklyGoal).where(WeeklyGoal.id == resource_id, WeeklyGoal.user_id == user.id))
            action = AutomationAction.CANCEL_GOALS if changes.get("status") == "cancelled" else AutomationAction.UPDATE_WEEKLY_GOAL_DETAILS
        elif resource_type == "phase":
            resource = db.scalar(select(Phase).where(Phase.id == resource_id, Phase.user_id == user.id))
            action = AutomationAction.UPDATE_PHASE_DETAILS
        else:
            resource = db.scalar(select(Milestone).join(Phase).where(Milestone.id == resource_id, Phase.user_id == user.id))
            action = AutomationAction.UPDATE_PHASE_DETAILS
        if resource is None:
            raise ValueError("The matched content no longer exists.")
        decision = automation_policy_service.evaluate(
            action,
            confirmed=True,
            explicitly_requested_by_user=True,
        )
        if not decision.allowed:
            raise ValueError(decision.reason)

        for field, value in changes.items():
            if field in {"task_date", "start_date", "end_date", "due_date"} and value is not None:
                value = date.fromisoformat(value)
            setattr(resource, field, value)
        if isinstance(resource, DailyTask):
            if "task_date" in changes:
                resource.due_at = task_deadline_service.calculate(db, user.id, resource.task_date, resource.planning_scope)
            if "status" in changes:
                resource.completed_at = datetime.now(timezone.utc) if resource.status == "completed" else None
        if isinstance(resource, Phase) and resource.end_date < resource.start_date:
            raise ValueError("Phase end date must be on or after its start date.")
        db.commit()
        return (
            {
                "resource_type": resource_type,
                "resource_id": resource.id,
                "changes": changes,
                "records_changed": [{"model": type(resource).__name__, "id": resource.id}],
            },
            f"Updated {parameters['resource_label']} “{resource.title}”: {parameters['field_label']} is now {self._display_value(parameters['new_value'])}.",
        )

    @staticmethod
    def _priority_value(value: str, *, allow_urgent: bool) -> str:
        mapped = {
            "urgent": "urgent" if allow_urgent else "high",
            "priority": "high",
            "high": "high",
            "normal": "medium",
            "medium": "medium",
            "low priority": "low",
            "low": "low",
        }.get(value.casefold())
        if mapped is None:
            raise ValueError("Priority must be urgent, high, normal, or low.")
        return mapped

    @staticmethod
    def _task_status_value(value: str) -> str:
        normalized = value.casefold().replace("-", "_").replace(" ", "_")
        normalized = {"done": "completed"}.get(normalized, normalized)
        if normalized not in {"pending", "in_progress", "completed", "cancelled"}:
            raise ValueError("Task status must be pending, in progress, completed, or cancelled.")
        return normalized

    @staticmethod
    def _parse_duration(value: str) -> int:
        match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m)", value, flags=re.IGNORECASE)
        if not match:
            raise ValueError("Use a duration such as 2h, 1.5 hours, or 45 minutes.")
        amount = float(match.group(1))
        minutes = round(amount * 60) if match.group(2).casefold().startswith("h") else round(amount)
        if not 1 <= minutes <= 1_440:
            raise ValueError("Duration must be between 1 minute and 24 hours.")
        return minutes

    @staticmethod
    def _parse_progress(value: str) -> int:
        match = re.fullmatch(r"(\d{1,3})\s*%?", value)
        if not match or not 0 <= int(match.group(1)) <= 100:
            raise ValueError("Progress must be between 0% and 100%.")
        return int(match.group(1))

    @staticmethod
    def _parse_date(value: str) -> date:
        lowered = value.casefold()
        if lowered == "today":
            return date.today()
        if lowered == "tomorrow":
            return date.today() + timedelta(days=1)
        if lowered == "yesterday":
            return date.today() - timedelta(days=1)
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Use today, tomorrow, yesterday, or a YYYY-MM-DD date.") from exc

    @staticmethod
    def _json_value(value: object) -> object:
        return value.isoformat() if isinstance(value, (date, datetime)) else value

    @staticmethod
    def _display_value(value: object) -> str:
        if value is None:
            return "empty"
        if isinstance(value, bool):
            return "yes" if value else "no"
        return str(value)

    @staticmethod
    def _current_week_start() -> date:
        today = date.today()
        return today - timedelta(days=today.weekday())

    @staticmethod
    def _match_task(db: Session, user_id: int, query: str, *, include_completed: bool = False) -> DailyTask | None:
        statuses = ("pending", "in_progress", "completed") if include_completed else ("pending", "in_progress")
        return db.scalar(
            select(DailyTask)
            .where(
                DailyTask.user_id == user_id,
                DailyTask.status.in_(statuses),
                func.lower(DailyTask.title).contains(query.casefold()),
            )
            .order_by(DailyTask.task_date != date.today(), DailyTask.task_date, DailyTask.id)
        )

    @staticmethod
    def _format_minutes(value: int | None) -> str:
        if value is None:
            return "flexible"
        hours, minutes = divmod(int(value), 60)
        if hours and minutes:
            return f"{hours}h {minutes}m"
        if hours:
            return f"{hours}h"
        return f"{minutes}m"

    @staticmethod
    def _reminder_parameters(message: str) -> dict:
        time_match = re.search(
            r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b",
            message,
            flags=re.IGNORECASE,
        )
        hour = int(time_match.group(1)) if time_match else 9
        minute = int(time_match.group(2) or 0) if time_match else 0
        suffix = (time_match.group(3) or "").lower() if time_match else ""
        if suffix == "pm" and hour < 12:
            hour += 12
        if suffix == "am" and hour == 12:
            hour = 0
        subject = re.sub(
            r"^(?:please\s+)?remind\s+me\s+(?:about|to)\s+",
            "",
            message,
            flags=re.IGNORECASE,
        )
        subject = re.sub(
            r"\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*$",
            "",
            subject,
            flags=re.IGNORECASE,
        ).strip(" .")
        return {"subject": subject or "Your task", "hour": min(hour, 23), "minute": min(minute, 59)}

    @staticmethod
    def _scheduled_reminder_time(
        db: Session,
        user_id: int,
        parameters: dict,
    ) -> datetime:
        preference = db.scalar(
            select(AutomationPreference).where(
                AutomationPreference.user_id == user_id
            )
        )
        zone = ZoneInfo(preference.timezone if preference else "UTC")
        local_now = datetime.now(zone)
        scheduled = datetime.combine(
            local_now.date(),
            time(parameters["hour"], parameters["minute"]),
            tzinfo=zone,
        )
        if scheduled <= local_now:
            scheduled += timedelta(days=1)
        return scheduled.astimezone(timezone.utc)

    @staticmethod
    def default_idempotency_key(user_id: int, message: str) -> str:
        digest = sha256(message.casefold().encode("utf-8")).hexdigest()[:24]
        return f"command:{user_id}:{date.today().isoformat()}:{digest}"

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


coordinator_service = CoordinatorService()
