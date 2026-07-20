from __future__ import annotations

import logging
import signal
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.database import SessionLocal
from app.models import AutomationPreference, DailyTask, Notification, User
from app.schemas.notification import NotificationSend
from app.services.automation_policy_service import (
    AutomationAction,
    automation_policy_service,
)
from app.services.automation_preference_service import automation_preference_service
from app.services.notification_service import NotificationService, notification_service


logger = logging.getLogger("automation_scheduler")
SCHEDULER_LOCK_ID = 1_901_202_603
INCOMPLETE_STATUSES = ("pending", "in_progress")


class AutomationScheduler:
    """Runs safe, read-only automation and creates confirmation-only proposals."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker = SessionLocal,
        notifications: NotificationService = notification_service,
        poll_seconds: float | None = None,
        notification_grace_minutes: int | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.notifications = notifications
        self.poll_seconds = max(
            1.0,
            poll_seconds or settings.scheduler_poll_seconds,
        )
        self.notification_grace = timedelta(
            minutes=(
                notification_grace_minutes
                if notification_grace_minutes is not None
                else settings.scheduler_notification_grace_minutes
            )
        )
        self.apscheduler: BlockingScheduler | None = None

    def run_forever(self) -> None:
        self.apscheduler = self.build_apscheduler()
        logger.info(
            "APScheduler started with %d jobs (base interval: %.1fs)",
            len(self.apscheduler.get_jobs()),
            self.poll_seconds,
        )
        self.apscheduler.start()

    def stop(self, *_: object) -> None:
        if self.apscheduler is not None and self.apscheduler.running:
            logger.info("Stopping APScheduler")
            self.apscheduler.shutdown(wait=False)

    def build_apscheduler(
        self,
        *,
        first_run_time: datetime | None = None,
    ) -> BlockingScheduler:
        scheduler = BlockingScheduler(
            timezone=timezone.utc,
            executors={"default": ThreadPoolExecutor(max_workers=1)},
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": max(1, round(self.poll_seconds * 2)),
            },
        )
        scheduler.add_listener(
            self._log_job_event,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR,
        )
        first_run_time = first_run_time or datetime.now(timezone.utc)
        for name in self._job_functions():
            scheduler.add_job(
                self.run_job,
                trigger="interval",
                seconds=self.poll_seconds,
                args=[name],
                id=name,
                name=name.replace("_", " ").title(),
                next_run_time=first_run_time,
                replace_existing=True,
            )
        return scheduler

    def run_job(self, name: str, now: datetime | None = None) -> int:
        jobs = self._job_functions()
        if name not in jobs:
            raise KeyError(f"Unknown scheduler job: {name}")
        now = now or datetime.now(timezone.utc)
        with self.session_factory() as db:
            if not self._acquire_lock(db):
                logger.info("Job %s skipped because another scheduler owns the lock", name)
                return 0
            try:
                result = jobs[name](db, now)
                logger.info("Scheduler job complete: %s=%d", name, result)
                return result
            except Exception:
                db.rollback()
                logger.exception("Scheduler job failed: %s", name)
                raise
            finally:
                self._release_lock(db)

    def run_once(self, now: datetime | None = None) -> dict[str, int]:
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Scheduler time must include a timezone")

        results: dict[str, int] = {}
        with self.session_factory() as db:
            if not self._acquire_lock(db):
                logger.info("Another scheduler owns the database lock; cycle skipped")
                return {"skipped_locked": 1}
            try:
                for name, job in self._job_functions().items():
                    try:
                        results[name] = job(db, now)
                    except Exception:
                        db.rollback()
                        results[name] = -1
                        logger.exception("Scheduler job failed: %s", name)
                logger.info("Scheduler cycle complete: %s", results)
                return results
            finally:
                self._release_lock(db)

    def _job_functions(
        self,
    ) -> dict[str, Callable[[Session, datetime], int]]:
        return {
            "due_reminders": self.dispatch_due_notifications,
            "morning_evening": self.send_time_based_notifications,
            "overdue_tasks": self.detect_overdue_tasks,
            "procrastination": self.detect_procrastination_signals,
            "completion_forecasts": self.recalculate_completion_forecasts,
            "rescheduling_proposals": self.generate_rescheduling_proposals,
        }

    @staticmethod
    def _log_job_event(event: JobExecutionEvent) -> None:
        if event.exception is not None:
            logger.error("APScheduler job %s failed: %s", event.job_id, event.exception)
        else:
            logger.info("APScheduler job %s executed", event.job_id)

    def dispatch_due_notifications(self, db: Session, now: datetime) -> int:
        stale_before = now - timedelta(minutes=settings.scheduler_stale_sending_minutes)
        stale = list(
            db.scalars(
                select(Notification).where(
                    Notification.status == "sending",
                    Notification.last_attempt_at < stale_before,
                )
            )
        )
        for notification in stale:
            notification.status = "failed"
            notification.failure_reason = (
                "Delivery was interrupted while the scheduler was unavailable"
            )
        exhausted = list(
            db.scalars(
                select(Notification).where(
                    Notification.status == "pending",
                    Notification.attempt_count >= Notification.max_attempts,
                )
            )
        )
        for notification in exhausted:
            notification.status = "failed"
            notification.failure_reason = "Maximum delivery attempts reached"
        if stale or exhausted:
            db.commit()

        query = (
            select(Notification)
            .where(
                Notification.status == "pending",
                Notification.scheduled_at <= now,
                Notification.attempt_count < Notification.max_attempts,
            )
            .order_by(Notification.scheduled_at, Notification.id)
            .limit(100)
        )
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        due = list(db.scalars(query))
        for notification in due:
            self.notifications.deliver(db, notification)
        return len(due)

    def send_time_based_notifications(self, db: Session, now: datetime) -> int:
        self._require_safe(AutomationAction.SEND_REMINDER)
        created = 0
        for user, preference in self._users_with_preferences(db):
            local_now = self._local_now(now, preference.timezone)
            if not self._is_working_day(local_now.date(), preference):
                continue
            if self._is_quiet(local_now.time(), preference):
                continue

            today_tasks = self._tasks_for_date(db, user.id, local_now.date())
            if self._time_is_due(local_now, preference.morning_reminder_time):
                completed = sum(task.status == "completed" for task in today_tasks)
                pending = len(today_tasks) - completed
                message = (
                    f"Good morning. You have {pending} task(s) remaining today"
                    f" and {completed} already completed."
                )
                created += self._send_once(
                    db,
                    user,
                    preference,
                    now,
                    notification_type="morning_plan",
                    subject="Your plan for today",
                    message=message,
                    key=f"morning:{user.id}:{local_now.date().isoformat()}",
                    counts_toward_reminder_limit=True,
                )

            if self._time_is_due(local_now, preference.evening_review_time):
                completed = sum(task.status == "completed" for task in today_tasks)
                message = (
                    f"Evening check-in: you completed {completed} of "
                    f"{len(today_tasks)} planned task(s). Review the day when ready."
                )
                created += self._send_once(
                    db,
                    user,
                    preference,
                    now,
                    notification_type="evening_check_in",
                    subject="Evening check-in",
                    message=message,
                    key=f"evening:{user.id}:{local_now.date().isoformat()}",
                    counts_toward_reminder_limit=True,
                )
        return created

    def detect_overdue_tasks(self, db: Session, now: datetime) -> int:
        self._require_safe(AutomationAction.DETECT_OVERDUE_TASKS)
        created = 0
        for user, preference in self._users_with_preferences(db):
            local_now = self._local_now(now, preference.timezone)
            overdue = self._overdue_tasks(db, user.id, local_now.date())
            if not overdue or self._is_quiet(local_now.time(), preference):
                continue
            titles = ", ".join(task.title for task in overdue[:5])
            if len(overdue) > 5:
                titles += f", and {len(overdue) - 5} more"
            created += self._send_once(
                db,
                user,
                preference,
                now,
                notification_type="missed_task",
                subject="Overdue tasks detected",
                message=f"You have {len(overdue)} overdue task(s): {titles}.",
                key=f"overdue:{user.id}:{local_now.date().isoformat()}",
                counts_toward_reminder_limit=True,
            )
        return created

    def detect_procrastination_signals(self, db: Session, now: datetime) -> int:
        self._require_safe(AutomationAction.DETECT_OVERDUE_TASKS)
        created = 0
        for user, preference in self._users_with_preferences(db):
            local_now = self._local_now(now, preference.timezone)
            overdue = self._overdue_tasks(db, user.id, local_now.date())
            if len(overdue) < 2 or self._is_quiet(local_now.time(), preference):
                continue
            oldest_days = max((local_now.date() - task.task_date).days for task in overdue)
            created += self._send_once(
                db,
                user,
                preference,
                now,
                notification_type="procrastination_alert",
                subject="A procrastination pattern may be forming",
                message=(
                    f"{len(overdue)} tasks are overdue; the oldest is {oldest_days} "
                    "day(s) late. Consider choosing one small next action."
                ),
                key=f"procrastination:{user.id}:{local_now.date().isoformat()}",
                counts_toward_reminder_limit=True,
            )
        return created

    def recalculate_completion_forecasts(self, db: Session, now: datetime) -> int:
        self._require_safe(AutomationAction.GENERATE_FORECAST)
        created = 0
        for user, preference in self._users_with_preferences(db):
            local_now = self._local_now(now, preference.timezone)
            if self._is_quiet(local_now.time(), preference):
                continue
            week_start = local_now.date() - timedelta(days=local_now.weekday())
            week_end = week_start + timedelta(days=6)
            tasks = list(
                db.scalars(
                    select(DailyTask).where(
                        DailyTask.user_id == user.id,
                        DailyTask.task_date >= week_start,
                        DailyTask.task_date <= week_end,
                        DailyTask.status != "cancelled",
                    )
                )
            )
            if not tasks:
                continue
            completed = sum(task.status == "completed" for task in tasks)
            elapsed_days = max(1, min(7, (local_now.date() - week_start).days + 1))
            projected = min(len(tasks), round((completed / elapsed_days) * 7))
            percent = round((projected / len(tasks)) * 100)
            created += self._send_once(
                db,
                user,
                preference,
                now,
                notification_type="completion_forecast",
                subject="Weekly completion forecast",
                message=(
                    f"You have completed {completed} of {len(tasks)} task(s) this "
                    f"week. At the current pace, about {projected} ({percent}%) "
                    "may be completed by week end."
                ),
                key=f"forecast:{user.id}:{local_now.date().isoformat()}",
                counts_toward_reminder_limit=False,
            )
        return created

    def generate_rescheduling_proposals(self, db: Session, now: datetime) -> int:
        self._require_safe(AutomationAction.SUGGEST_SCHEDULE_CHANGES)
        created = 0
        for user, preference in self._users_with_preferences(db):
            if not preference.automatic_rescheduling_enabled:
                continue
            local_now = self._local_now(now, preference.timezone)
            overdue = self._overdue_tasks(db, user.id, local_now.date())
            if not overdue or self._is_quiet(local_now.time(), preference):
                continue
            total_minutes = sum(task.estimated_minutes or 0 for task in overdue)
            created += self._send_once(
                db,
                user,
                preference,
                now,
                notification_type="rescheduling_proposal",
                subject="Schedule change proposal",
                message=(
                    f"Proposal: review {len(overdue)} overdue task(s)"
                    + (f" ({total_minutes} estimated minutes)" if total_minutes else "")
                    + " and choose new dates. No task was moved; confirmation is required."
                ),
                key=f"reschedule-proposal:{user.id}:{local_now.date().isoformat()}",
                counts_toward_reminder_limit=False,
            )
        return created

    def _send_once(
        self,
        db: Session,
        user: User,
        preference: AutomationPreference,
        now: datetime,
        *,
        notification_type: str,
        subject: str,
        message: str,
        key: str,
        counts_toward_reminder_limit: bool,
    ) -> int:
        if db.scalar(
            select(Notification.id).where(Notification.deduplication_key == key)
        ) is not None:
            return 0
        if counts_toward_reminder_limit and not self._has_reminder_capacity(
            db, user.id, preference, now
        ):
            return 0
        self.notifications.create(
            db,
            user,
            NotificationSend(
                notification_type=notification_type,
                subject=subject,
                message=message,
                scheduled_at=now,
            ),
            deduplication_key=key,
        )
        return 1

    def _has_reminder_capacity(
        self,
        db: Session,
        user_id: int,
        preference: AutomationPreference,
        now: datetime,
    ) -> bool:
        if preference.max_reminders_per_day <= 0:
            return False
        local_now = self._local_now(now, preference.timezone)
        local_start = datetime.combine(local_now.date(), time.min, local_now.tzinfo)
        utc_start = local_start.astimezone(timezone.utc)
        utc_end = (local_start + timedelta(days=1)).astimezone(timezone.utc)
        count = db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.created_at >= utc_start,
                Notification.created_at < utc_end,
                Notification.notification_type.in_(
                    (
                        "morning_plan",
                        "upcoming_task",
                        "missed_task",
                        "deadline_warning",
                        "evening_check_in",
                        "procrastination_alert",
                    )
                ),
            )
        )
        return int(count or 0) < preference.max_reminders_per_day

    def _users_with_preferences(
        self, db: Session
    ) -> list[tuple[User, AutomationPreference]]:
        users = list(db.scalars(select(User).order_by(User.id)))
        return [
            (user, automation_preference_service.get_or_create(db, user.id))
            for user in users
        ]

    @staticmethod
    def _tasks_for_date(db: Session, user_id: int, task_date: date) -> list[DailyTask]:
        return list(
            db.scalars(
                select(DailyTask).where(
                    DailyTask.user_id == user_id,
                    DailyTask.task_date == task_date,
                    DailyTask.status != "cancelled",
                )
            )
        )

    @staticmethod
    def _overdue_tasks(db: Session, user_id: int, today: date) -> list[DailyTask]:
        return list(
            db.scalars(
                select(DailyTask)
                .where(
                    DailyTask.user_id == user_id,
                    DailyTask.task_date < today,
                    DailyTask.status.in_(INCOMPLETE_STATUSES),
                )
                .order_by(DailyTask.task_date, DailyTask.id)
            )
        )

    def _time_is_due(self, local_now: datetime, configured: time) -> bool:
        scheduled = datetime.combine(local_now.date(), configured, local_now.tzinfo)
        return scheduled <= local_now < scheduled + self.notification_grace

    @staticmethod
    def _local_now(now: datetime, timezone_name: str) -> datetime:
        try:
            zone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            logger.warning("Invalid timezone %s; using UTC", timezone_name)
            zone = timezone.utc
        return now.astimezone(zone)

    @staticmethod
    def _is_working_day(day: date, preference: AutomationPreference) -> bool:
        return day.strftime("%A").lower() in preference.working_days_json

    @staticmethod
    def _is_quiet(current: time, preference: AutomationPreference) -> bool:
        start = preference.quiet_hours_start
        end = preference.quiet_hours_end
        if start == end:
            return False
        if start < end:
            return start <= current < end
        return current >= start or current < end

    @staticmethod
    def _require_safe(action: AutomationAction) -> None:
        decision = automation_policy_service.evaluate(action)
        if not decision.allowed:
            raise PermissionError(decision.reason)

    @staticmethod
    def _acquire_lock(db: Session) -> bool:
        if db.bind is None or db.bind.dialect.name != "postgresql":
            return True
        return bool(
            db.scalar(
                text("SELECT pg_try_advisory_lock(:lock_id)"),
                {"lock_id": SCHEDULER_LOCK_ID},
            )
        )

    @staticmethod
    def _release_lock(db: Session) -> None:
        if db.bind is None or db.bind.dialect.name != "postgresql":
            return
        try:
            db.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": SCHEDULER_LOCK_ID},
            )
        except Exception:
            logger.exception("Could not release scheduler advisory lock")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    scheduler = AutomationScheduler()
    signal.signal(signal.SIGTERM, scheduler.stop)
    signal.signal(signal.SIGINT, scheduler.stop)
    scheduler.run_forever()


if __name__ == "__main__":
    main()
