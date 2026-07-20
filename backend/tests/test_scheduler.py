from datetime import date, datetime, time, timedelta, timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.models import AutomationPreference, DailyTask, Notification
from app.scheduler import AutomationScheduler
from app.services.notification_service import NotificationService
from conftest import TestingSessionLocal


class RecordingProvider:
    channel = "email"

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    def send(self, *, recipient: str, subject: str, message: str) -> None:
        self.sent.append(
            {"recipient": recipient, "subject": subject, "message": message}
        )


def make_scheduler(provider: RecordingProvider) -> AutomationScheduler:
    notifications = NotificationService(provider, provider)
    return AutomationScheduler(
        session_factory=TestingSessionLocal,
        notifications=notifications,
        notification_grace_minutes=60,
    )


def add_preferences(*, automatic_rescheduling_enabled: bool = False) -> None:
    with TestingSessionLocal() as db:
        db.add(
            AutomationPreference(
                user_id=1,
                timezone="UTC",
                morning_reminder_time=time(8, 0),
                evening_review_time=time(21, 0),
                notification_channel="email",
                automatic_rescheduling_enabled=automatic_rescheduling_enabled,
                confirmation_required=True,
                max_reminders_per_day=10,
                quiet_hours_start=time(22, 0),
                quiet_hours_end=time(7, 0),
                working_days_json=[
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                ],
                preferred_study_periods_json=[],
            )
        )
        db.commit()


def test_apscheduler_registers_each_automation_as_an_interval_job():
    provider = RecordingProvider()
    automation = make_scheduler(provider)
    scheduler = automation.build_apscheduler(
        first_run_time=datetime(2026, 7, 20, tzinfo=timezone.utc)
    )

    jobs = scheduler.get_jobs()

    assert isinstance(scheduler, BlockingScheduler)
    assert {job.id for job in jobs} == {
        "due_reminders",
        "morning_evening",
        "overdue_tasks",
        "procrastination",
        "completion_forecasts",
        "rescheduling_proposals",
    }
    assert all(isinstance(job.trigger, IntervalTrigger) for job in jobs)


def test_morning_notification_is_generated_once_across_repeated_cycles():
    add_preferences()
    provider = RecordingProvider()
    scheduler = make_scheduler(provider)
    now = datetime(2026, 7, 15, 8, 5, tzinfo=timezone.utc)

    first = scheduler.run_once(now)
    second = scheduler.run_once(now + timedelta(minutes=1))

    with TestingSessionLocal() as db:
        morning = list(
            db.scalars(
                select(Notification).where(
                    Notification.notification_type == "morning_plan"
                )
            )
        )
    assert first["morning_evening"] == 1
    assert second["morning_evening"] == 0
    assert len(morning) == 1
    assert morning[0].deduplication_key == "morning:1:2026-07-15"
    assert len(provider.sent) == 1


def test_scheduler_detects_patterns_and_only_proposes_rescheduling():
    add_preferences(automatic_rescheduling_enabled=True)
    provider = RecordingProvider()
    scheduler = make_scheduler(provider)
    original_date = date(2026, 7, 14)
    with TestingSessionLocal() as db:
        db.add_all(
            [
                DailyTask(
                    user_id=1,
                    title="Write report",
                    task_date=original_date,
                    estimated_minutes=60,
                    status="pending",
                    source="manual",
                ),
                DailyTask(
                    user_id=1,
                    title="Review notes",
                    task_date=original_date,
                    estimated_minutes=30,
                    status="in_progress",
                    source="manual",
                ),
            ]
        )
        db.commit()

    result = scheduler.run_once(
        datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    )

    with TestingSessionLocal() as db:
        notification_types = set(
            db.scalars(select(Notification.notification_type))
        )
        tasks = list(db.scalars(select(DailyTask).order_by(DailyTask.id)))
        proposal = db.scalar(
            select(Notification).where(
                Notification.notification_type == "rescheduling_proposal"
            )
        )
    assert result["overdue_tasks"] == 1
    assert result["procrastination"] == 1
    assert result["completion_forecasts"] == 1
    assert result["rescheduling_proposals"] == 1
    assert {
        "missed_task",
        "procrastination_alert",
        "completion_forecast",
        "rescheduling_proposal",
    }.issubset(notification_types)
    assert [task.task_date for task in tasks] == [original_date, original_date]
    assert [task.status for task in tasks] == ["pending", "in_progress"]
    assert proposal is not None
    assert "No task was moved" in proposal.message
    assert "confirmation is required" in proposal.message


def test_due_pending_notifications_are_delivered_without_an_api_request():
    add_preferences()
    provider = RecordingProvider()
    scheduler = make_scheduler(provider)
    now = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    with TestingSessionLocal() as db:
        db.add(
            Notification(
                user_id=1,
                notification_type="upcoming_task",
                channel="email",
                recipient="mvp@example.com",
                subject="Task reminder",
                message="Start the task now.",
                scheduled_at=now - timedelta(minutes=5),
                status="pending",
                attempt_count=0,
                max_attempts=3,
            )
        )
        db.commit()

    result = scheduler.run_once(now)

    with TestingSessionLocal() as db:
        notification = db.scalar(
            select(Notification).where(
                Notification.notification_type == "upcoming_task"
            )
        )
    assert result["due_reminders"] == 1
    assert notification is not None
    assert notification.status == "delivered"
    assert notification.attempt_count == 1
    assert len(provider.sent) == 1
