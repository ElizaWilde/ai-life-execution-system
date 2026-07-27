from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select

from app.models import AutomationPreference, DailyTask, UserAppSetting
from app.services.overdue_detection_service import overdue_detection_service
from conftest import TestingSessionLocal


def add_automation_settings(*, timezone_name: str = "UTC") -> None:
    with TestingSessionLocal() as db:
        db.add(
            AutomationPreference(
                user_id=1,
                timezone=timezone_name,
                morning_reminder_time=time(8, 0),
                evening_review_time=time(21, 0),
                notification_channel="email",
                automatic_rescheduling_enabled=True,
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
        db.add(UserAppSetting(user_id=1, week_start="Monday"))
        db.commit()


def test_daily_and_weekly_default_due_times_use_user_timezone(client, user_headers):
    add_automation_settings(timezone_name="Asia/Singapore")

    daily = client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Daily deadline",
            "task_date": "2030-07-29",
            "planning_scope": "daily",
        },
    )
    weekly = client.post(
        "/weekly-goals",
        headers=user_headers,
        json={
            "title": "Weekly deadline",
            "week_start": "2030-07-29",
            "week_end": "2030-08-04",
            "priority": "high",
        },
    )

    assert daily.status_code == 201
    assert daily.json()["due_at"].startswith("2030-07-29T16:00:00")
    assert daily.json()["planning_scope"] == "daily"
    assert daily.json()["is_overdue"] is False
    assert weekly.status_code == 201
    assert weekly.json()["due_at"].startswith("2030-08-04T16:00:00")
    assert weekly.json()["is_overdue"] is False


def test_overdue_detection_is_derived_and_classified():
    now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
    with TestingSessionLocal() as db:
        db.add(
            DailyTask(
                user_id=1,
                title="Urgent overdue task",
                task_date=date(2026, 7, 26),
                planning_scope="daily",
                due_at=now - timedelta(hours=2),
                estimated_minutes=45,
                priority="high",
                status="in_progress",
                source="manual",
            )
        )
        db.commit()

        findings = overdue_detection_service.find(db, 1, now)

    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].overdue_minutes == 120
    assert "Task priority is high" in findings[0].evidence


def test_proposal_requires_approval_and_applies_once(client, user_headers):
    add_automation_settings()
    now = datetime.now(timezone.utc)
    original_date = now.date() - timedelta(days=1)
    created = client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Carry this task",
            "task_date": original_date.isoformat(),
            "planning_scope": "daily",
            "due_at": (now - timedelta(hours=1)).isoformat(),
            "estimated_minutes": 60,
            "priority": "high",
        },
    ).json()

    generated = client.post(
        "/automation/rescheduling-proposals",
        headers=user_headers,
        json={"horizon_days": 7},
    )
    assert generated.status_code == 201
    proposal = generated.json()
    assert proposal["status"] == "pending"
    assert proposal["expected_minutes"] == 60
    assert proposal["items"][0]["daily_task_id"] == created["id"]
    assert proposal["items"][0]["original_date"] == original_date.isoformat()

    not_approved = client.post(
        f"/automation/proposals/{proposal['id']}/apply",
        headers=user_headers,
    )
    assert not_approved.status_code == 409

    approved = client.post(
        f"/automation/proposals/{proposal['id']}/approve",
        headers=user_headers,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    applied = client.post(
        f"/automation/proposals/{proposal['id']}/apply",
        headers=user_headers,
    )
    repeated = client.post(
        f"/automation/proposals/{proposal['id']}/apply",
        headers=user_headers,
    )
    assert applied.status_code == 200
    assert applied.json()["status"] == "applied"
    assert repeated.status_code == 200
    assert repeated.json()["status"] == "applied"

    with TestingSessionLocal() as db:
        task = db.scalar(select(DailyTask).where(DailyTask.id == created["id"]))
        assert task is not None
        assert task.task_date.isoformat() == proposal["items"][0]["proposed_date"]
        assert task.due_at is not None


def test_rejected_proposal_cannot_be_applied(client, user_headers):
    add_automation_settings()
    now = datetime.now(timezone.utc)
    client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Do not move",
            "task_date": (now.date() - timedelta(days=1)).isoformat(),
            "due_at": (now - timedelta(hours=1)).isoformat(),
        },
    )
    proposal = client.post(
        "/automation/rescheduling-proposals",
        headers=user_headers,
        json={},
    ).json()

    rejected = client.post(
        f"/automation/proposals/{proposal['id']}/reject",
        headers=user_headers,
    )
    apply_result = client.post(
        f"/automation/proposals/{proposal['id']}/apply",
        headers=user_headers,
    )

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert apply_result.status_code == 409
