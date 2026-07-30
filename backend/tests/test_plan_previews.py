from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.models import DailyTask, StudySession, WeeklyGoal
from app.services.estimation_calibration_service import estimation_calibration_service
from conftest import TestingSessionLocal


def _goal(client, user_headers, start: date, end: date, minutes: int = 300) -> dict:
    return client.post(
        "/weekly-goals",
        headers=user_headers,
        json={
            "title": "Adaptive planning",
            "week_start": start.isoformat(),
            "week_end": end.isoformat(),
            "priority": "high",
            "target_minutes": minutes,
        },
    ).json()


def test_calibration_uses_completed_sessions_linked_to_tasks():
    today = date.today()
    with TestingSessionLocal() as db:
        task = DailyTask(
            user_id=1,
            title="Calibrate this task",
            task_date=today,
            estimated_minutes=50,
            priority="high",
            status="completed",
            source="manual",
        )
        db.add(task)
        db.flush()
        db.add(
            StudySession(
                user_id=1,
                daily_task_id=task.id,
                subject=task.title,
                started_at=datetime.now(timezone.utc) - timedelta(minutes=100),
                ended_at=datetime.now(timezone.utc),
                duration_minutes=100,
                status="completed",
            )
        )
        db.commit()

        calibration = estimation_calibration_service.calculate(db, 1)

    assert calibration.sample_count == 1
    assert calibration.planned_minutes == 50
    assert calibration.actual_minutes == 100
    assert calibration.factor == 1.2


def test_daily_preview_is_inert_until_confirmed(
    client,
    user_headers,
    monkeypatch,
):
    monkeypatch.setattr("app.api.planning.settings.ollama_api_key", "test-key")
    today = date.today()
    goal = _goal(client, user_headers, today, today + timedelta(days=1))

    async def fake_generate_daily_plan(
        weekly_goals,
        unfinished_tasks,
        available_minutes,
        user_instruction=None,
        current_preview=None,
    ):
        if user_instruction:
            assert current_preview[0]["title"] == "Preview-only task"
            return [
                {
                    **current_preview[0],
                    "title": "Refined preview task",
                    "estimated_minutes": 30,
                }
            ]
        return [
            {
                "title": "Preview-only task",
                "estimated_minutes": 45,
                "priority": "high",
                "weekly_goal_id": goal["id"],
            }
        ]

    monkeypatch.setattr(
        "app.services.planning_service.llm_service.generate_daily_plan",
        fake_generate_daily_plan,
    )

    preview_response = client.post(
        "/planning/daily-previews",
        headers=user_headers,
        json={
            "target_date": today.isoformat(),
            "available_minutes": 120,
        },
    )

    assert preview_response.status_code == 201
    preview = preview_response.json()
    assert preview["status"] == "pending"
    assert preview["tasks"][0]["title"] == "Preview-only task"
    assert client.get("/daily-tasks/today", headers=user_headers).json() == []

    refined_response = client.post(
        "/planning/daily-previews",
        headers=user_headers,
        json={
            "target_date": today.isoformat(),
            "available_minutes": 120,
            "user_instruction": "Make the current preview shorter",
            "base_preview_id": preview["id"],
        },
    )
    assert refined_response.status_code == 201
    refined = refined_response.json()
    assert refined["tasks"][0]["title"] == "Refined preview task"
    assert refined["recommended_minutes"] == 30

    confirmed = client.post(
        f"/planning/daily-previews/{refined['id']}/confirm",
        headers=user_headers,
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"
    tasks = client.get("/daily-tasks/today", headers=user_headers).json()
    assert [task["title"] for task in tasks] == ["Refined preview task"]
    assert client.post(
        f"/planning/daily-previews/{refined['id']}/confirm",
        headers=user_headers,
    ).status_code == 200
    assert len(client.get("/daily-tasks/today", headers=user_headers).json()) == 1


def test_weekly_preview_adapts_and_requires_confirmation(client, user_headers):
    selected = date.today() - timedelta(days=date.today().weekday())
    goal = _goal(client, user_headers, selected, selected + timedelta(days=6), 600)
    history_start = selected - timedelta(weeks=2)
    with TestingSessionLocal() as db:
        db.add_all(
            [
                StudySession(
                    user_id=1,
                    subject="Historical focus",
                    started_at=datetime.combine(
                        history_start + timedelta(days=index),
                        datetime.min.time(),
                        tzinfo=timezone.utc,
                    ),
                    ended_at=datetime.combine(
                        history_start + timedelta(days=index),
                        datetime.min.time(),
                        tzinfo=timezone.utc,
                    )
                    + timedelta(minutes=120),
                    duration_minutes=120,
                    status="completed",
                )
                for index in range(5)
            ]
        )
        db.commit()

    preview_response = client.post(
        "/planning/weekly-previews",
        headers=user_headers,
        json={
            "week_start": selected.isoformat(),
            "intended_minutes": 900,
        },
    )

    assert preview_response.status_code == 201
    preview = preview_response.json()
    assert preview["status"] == "pending"
    assert 0 < preview["recommended_minutes"] <= 900
    with TestingSessionLocal() as db:
        unchanged = db.get(WeeklyGoal, goal["id"])
        assert unchanged is not None
        assert unchanged.target_minutes == 600

    confirmed = client.post(
        f"/planning/weekly-previews/{preview['id']}/confirm",
        headers=user_headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"
    with TestingSessionLocal() as db:
        updated = db.scalar(select(WeeklyGoal).where(WeeklyGoal.id == goal["id"]))
        assert updated is not None
        assert updated.target_minutes == preview["goal_allocations"][0]["recommended_minutes"]
