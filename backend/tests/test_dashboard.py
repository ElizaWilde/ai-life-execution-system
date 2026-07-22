from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock

from app.models import CoachingRecommendation, DailyCheckIn, User
from app.services.llm_service import llm_service
from conftest import TestingSessionLocal


def test_today_dashboard_stats(client, user_headers):
    today = date.today()

    first_task = client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Finish dashboard service",
            "task_date": today.isoformat(),
            "estimated_minutes": 45,
            "priority": "high",
        },
    ).json()
    client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Write dashboard API tests",
            "task_date": today.isoformat(),
            "estimated_minutes": 30,
            "priority": "medium",
        },
    )
    client.patch(
        f"/daily-tasks/{first_task['id']}",
        headers=user_headers,
        json={"status": "completed"},
    )

    started_at = datetime.now(timezone.utc) - timedelta(minutes=35)
    session = client.post(
        "/study-sessions/start",
        headers=user_headers,
        json={
            "daily_task_id": first_task["id"],
            "subject": "Dashboard statistics",
            "started_at": started_at.isoformat(),
        },
    ).json()
    client.post(
        "/study-sessions/finish",
        headers=user_headers,
        json={
            "session_id": session["id"],
            "ended_at": (started_at + timedelta(minutes=35)).isoformat(),
        },
    )

    response = client.get("/dashboard/today", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == today.isoformat()
    assert body["focus_minutes"] == 35
    assert body["planned_tasks"] == 2
    assert body["completed_tasks"] == 1
    assert body["completion_rate"] == 0.5
    assert [task["title"] for task in body["tasks"]] == [
        "Finish dashboard service",
        "Write dashboard API tests",
    ]
    assert [task["title"] for task in body["unfinished_tasks"]] == [
        "Write dashboard API tests"
    ]
    assert body["time_allocation"] == [
        {
            "label": "Finish dashboard service",
            "planned_minutes": 45,
            "focus_minutes": 35,
        },
        {
            "label": "Write dashboard API tests",
            "planned_minutes": 30,
            "focus_minutes": 0,
        },
    ]
    assert body["check_in"] is None
    assert body["coaching"] is None
    assert body["readiness_score"] is None
    assert body["workload_multiplier"] is None
    assert body["workload_level"] is None
    assert body["adjustment_reasons"] == []


def test_today_dashboard_reads_stored_check_in_and_coaching_without_calling_llm(
    client,
    user_headers,
    monkeypatch,
):
    today = date.today()
    with TestingSessionLocal() as db:
        db.add(
            DailyCheckIn(
                user_id=1,
                check_in_date=today,
                energy_level="steady",
                mood_level="good",
                sleep_hours=6.5,
                stress_level=3,
                notes="Keep the day focused.",
            )
        )
        db.add(
            CoachingRecommendation(
                user_id=1,
                recommendation_date=today,
                readiness_score=70,
                workload_multiplier=0.8,
                workload_level="reduced",
                adjustment_reasons_json=[
                    "Insufficient sleep",
                    "Steady but limited energy",
                ],
                summary="Use a reduced workload today.",
                recommendations_json={
                    "summary": "Use a reduced workload today.",
                    "suggestions": ["Complete one high-priority task."],
                    "risk_factors": ["Insufficient sleep."],
                    "planning_changes": ["Move optional work to tomorrow."],
                },
                model_name="test-model",
                prompt_version="phase2-v1",
            )
        )
        db.commit()

    generate_json = AsyncMock()
    monkeypatch.setattr(llm_service, "generate_json", generate_json)

    response = client.get("/dashboard/today", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["check_in"]["energy_level"] == "steady"
    assert body["check_in"]["mood_level"] == "good"
    assert body["check_in"]["sleep_hours"] == 6.5
    assert body["coaching"] == {
        "recommendation_date": today.isoformat(),
        "readiness_score": 70.0,
        "workload_multiplier": 0.8,
        "workload_level": "reduced",
        "summary": "Use a reduced workload today.",
        "suggestions": ["Complete one high-priority task."],
        "risk_factors": ["Insufficient sleep."],
        "planning_changes": ["Move optional work to tomorrow."],
    }
    assert body["readiness_score"] == 70.0
    assert body["workload_multiplier"] == 0.8
    assert body["workload_level"] == "reduced"
    assert body["adjustment_reasons"] == [
        "Insufficient sleep",
        "Steady but limited energy",
    ]
    generate_json.assert_not_awaited()


def test_today_dashboard_does_not_read_another_users_phase2_data(client):
    today = date.today()
    with TestingSessionLocal() as db:
        db.add(
            User(
                id=2,
                email="dashboard-other@example.com",
                password_hash="not-used",
                display_name="Other User",
            )
        )
        db.add(
            DailyCheckIn(
                user_id=2,
                check_in_date=today,
                energy_level="energized",
                mood_level="great",
                sleep_hours=8,
                stress_level=1,
                notes=None,
            )
        )
        db.add(
            CoachingRecommendation(
                user_id=2,
                recommendation_date=today,
                readiness_score=100,
                workload_multiplier=1,
                workload_level="normal",
                adjustment_reasons_json=[],
                summary="Other user's private coaching.",
                recommendations_json={
                    "summary": "Other user's private coaching.",
                    "suggestions": [],
                    "risk_factors": [],
                    "planning_changes": [],
                },
                model_name="test-model",
                prompt_version="phase2-v1",
            )
        )
        db.commit()

    response = client.get(
        "/dashboard/today",
        headers={"X-User-ID": "1"},
    )

    assert response.status_code == 200
    assert response.json()["check_in"] is None
    assert response.json()["coaching"] is None


def test_week_dashboard_stats(client, user_headers):
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    active_goal = client.post(
        "/weekly-goals",
        headers=user_headers,
        json={
            "title": "Ship dashboard",
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "priority": "high",
        },
    ).json()
    completed_goal = client.post(
        "/weekly-goals",
        headers=user_headers,
        json={
            "title": "Finish migrations",
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "priority": "medium",
        },
    ).json()
    client.patch(
        f"/weekly-goals/{completed_goal['id']}",
        headers=user_headers,
        json={"status": "completed"},
    )

    completed_task = client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Complete dashboard endpoint",
            "task_date": today.isoformat(),
            "priority": "high",
            "weekly_goal_id": active_goal["id"],
        },
    ).json()
    client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Review dashboard UI",
            "task_date": today.isoformat(),
            "priority": "medium",
            "weekly_goal_id": active_goal["id"],
        },
    )
    client.patch(
        f"/daily-tasks/{completed_task['id']}",
        headers=user_headers,
        json={"status": "completed"},
    )

    started_at = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    session = client.post(
        "/study-sessions/start",
        headers=user_headers,
        json={
            "daily_task_id": completed_task["id"],
            "subject": "Weekly dashboard",
            "started_at": started_at.isoformat(),
        },
    ).json()
    client.post(
        "/study-sessions/finish",
        headers=user_headers,
        json={
            "session_id": session["id"],
            "ended_at": (started_at + timedelta(minutes=50)).isoformat(),
        },
    )

    response = client.get("/dashboard/week", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["week_start"] == week_start.isoformat()
    assert body["week_end"] == week_end.isoformat()
    assert body["focus_minutes"] == 50
    assert body["planned_tasks"] == 2
    assert body["completed_tasks"] == 1
    assert body["completion_rate"] == 0.5
    assert body["active_goals"] == 1
    assert body["completed_goals"] == 1
    assert len(body["daily_focus"]) == 7
    assert sum(point["focus_minutes"] for point in body["daily_focus"]) == 50
    assert all("planned_minutes" in point for point in body["daily_focus"])
    assert body["time_allocation"][0]["label"] == "Complete dashboard endpoint"
    assert body["time_allocation"][0]["focus_minutes"] == 50
