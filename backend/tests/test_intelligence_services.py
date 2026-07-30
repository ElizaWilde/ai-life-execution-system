from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.models import (
    AutomationAudit,
    DailyTask,
    ForecastHistory,
    ProcrastinationEvent,
)
from app.services.forecast_service import forecast_service
from app.services.procrastination_detection_service import (
    procrastination_detection_service,
)
from conftest import TestingSessionLocal


def test_procrastination_events_are_stored_once_with_audit():
    now = datetime.now(timezone.utc)
    with TestingSessionLocal() as db:
        db.add_all(
            [
                DailyTask(
                    user_id=1,
                    title="Avoided report",
                    task_date=now.date() - timedelta(days=2),
                    due_at=now - timedelta(days=1),
                    estimated_minutes=60,
                    priority="high",
                    status="pending",
                    source="manual",
                ),
                DailyTask(
                    user_id=1,
                    title="Avoided review",
                    task_date=now.date() - timedelta(days=2),
                    due_at=now - timedelta(hours=3),
                    estimated_minutes=30,
                    priority="medium",
                    status="pending",
                    source="manual",
                ),
            ]
        )
        db.commit()

        first = procrastination_detection_service.detect(db, 1, now)
        second = procrastination_detection_service.detect(db, 1, now)

        events = list(db.scalars(select(ProcrastinationEvent)))
        audits = list(
            db.scalars(
                select(AutomationAudit).where(
                    AutomationAudit.trigger_source == "procrastination_detector"
                )
            )
        )

    assert {item.detection_type for item in first} == {
        "planning_overload",
        "deadline_avoidance",
    }
    assert [item.id for item in second] == [item.id for item in first]
    assert len(events) == 2
    assert len(audits) == 2
    assert all(audit.execution_status == "completed" for audit in audits)


def test_forecast_history_is_idempotent_per_goal_and_day(client, user_headers):
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    goal = client.post(
        "/weekly-goals",
        headers=user_headers,
        json={
            "title": "Stored forecast goal",
            "week_start": week_start.isoformat(),
            "week_end": (week_start + timedelta(days=6)).isoformat(),
            "target_minutes": 300,
            "priority": "high",
        },
    ).json()
    client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Forecast task",
            "task_date": today.isoformat(),
            "weekly_goal_id": goal["id"],
            "estimated_minutes": 120,
            "priority": "high",
        },
    )

    now = datetime.now(timezone.utc)
    with TestingSessionLocal() as db:
        first = forecast_service.generate_for_user(db, 1, now)
        second = forecast_service.generate_for_user(db, 1, now)
        stored = list(db.scalars(select(ForecastHistory)))

    assert len(first) == 1
    assert first[0].id == second[0].id
    assert len(stored) == 1
    assert stored[0].risk_level in {"low", "medium", "high"}
    assert 0 <= stored[0].completion_probability <= 1


def test_forecast_and_procrastination_apis_return_stored_records(client, user_headers):
    now = datetime.now(timezone.utc)
    with TestingSessionLocal() as db:
        db.add_all(
            [
                DailyTask(
                    user_id=1,
                    title=f"Overdue {index}",
                    task_date=now.date() - timedelta(days=1),
                    due_at=now - timedelta(hours=index + 1),
                    estimated_minutes=30,
                    priority="medium",
                    status="pending",
                    source="manual",
                )
                for index in range(2)
            ]
        )
        db.commit()

    detected = client.post(
        "/automation/procrastination-events/detect",
        headers=user_headers,
    )
    listed = client.get(
        "/automation/procrastination-events",
        headers=user_headers,
    )
    audits = client.get("/automation/audits", headers=user_headers)

    assert detected.status_code == 200
    assert listed.status_code == 200
    assert len(listed.json()) >= 1
    assert audits.status_code == 200
    assert any(item["automation_type"] == "planning_overload" for item in audits.json())
