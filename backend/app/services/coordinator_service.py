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


COORDINATOR_SYSTEM_PROMPT = """You are the Coordinator Agent for an AI Life Execution System.
Answer the user's questions clearly and practically.
For now, this is a basic conversation test: do not claim to have used tools, changed plans,
or saved memories. If the user asks for an unavailable action, explain what would be needed.
Keep answers concise unless the user asks for detail."""


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
            "reschedule_task",
            "reduce_workload",
            "complete_task",
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
        if "remind me" in lowered or lowered.startswith("remind "):
            return "create_reminder", self._reminder_parameters(message)
        if any(phrase in lowered for phrase in ("move ", "reschedule", "roll over", "rollover")):
            return "reschedule_task", {"scope": "overdue", "horizon_days": 14}
        if any(phrase in lowered for phrase in ("reduce workload", "lighter week", "reduce this week")):
            return "reduce_workload", {"reduction_percent": 20}
        if "forecast" in lowered or "behind this week" in lowered or "finish this week" in lowered:
            return "get_forecast", {}
        if "progress" in lowered or "how am i doing" in lowered:
            return "get_progress", {}
        if any(phrase in lowered for phrase in ("what should i focus", "what should i do", "coach me")):
            return "get_coaching", {}
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
        return "unknown", {}

    def _pending_message(
        self,
        db: Session,
        user: User,
        command: AutomationCommand,
    ) -> str:
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

    @staticmethod
    def _match_task(db: Session, user_id: int, query: str) -> DailyTask | None:
        return db.scalar(
            select(DailyTask)
            .where(
                DailyTask.user_id == user_id,
                DailyTask.status.in_(("pending", "in_progress")),
                func.lower(DailyTask.title).contains(query.casefold()),
            )
            .order_by(DailyTask.task_date, DailyTask.id)
        )

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
