from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock

from sqlalchemy import select

from app.config import settings
from app.models import DailyCheckIn, DailyTask, StudySession, User, WeeklyReview
from app.services.llm_service import llm_service
from app.services.weekly_review_service import weekly_review_service
from conftest import TestingSessionLocal


WEEK_START = date(2026, 7, 6)
WEEK_END = date(2026, 7, 12)


def _llm_result(summary: str = "A grounded weekly review.") -> dict:
    return {
        "summary": summary,
        "achievements": ["Completed the implementation task."],
        "obstacles": ["One planned task remains unfinished."],
        "next_week_actions": ["Start with the unfinished priority task."],
    }


def _seed_behavior(user_id: int = 1) -> None:
    started_at = datetime(2026, 7, 7, 9, 0, tzinfo=timezone.utc)
    with TestingSessionLocal() as db:
        db.add_all(
            [
                DailyTask(
                    user_id=user_id,
                    title="Completed implementation",
                    task_date=date(2026, 7, 7),
                    estimated_minutes=45,
                    priority="high",
                    status="completed",
                    source="manual",
                ),
                DailyTask(
                    user_id=user_id,
                    title="Unfinished documentation",
                    task_date=date(2026, 7, 8),
                    estimated_minutes=30,
                    priority="medium",
                    status="pending",
                    source="manual",
                ),
                DailyTask(
                    user_id=user_id,
                    title="Cancelled optional cleanup",
                    task_date=date(2026, 7, 9),
                    estimated_minutes=20,
                    priority="low",
                    status="cancelled",
                    source="manual",
                ),
                StudySession(
                    user_id=user_id,
                    subject="Phase 2 backend",
                    started_at=started_at,
                    ended_at=started_at + timedelta(minutes=50),
                    duration_minutes=50,
                    status="completed",
                    notes="Implemented weekly statistics",
                ),
                StudySession(
                    user_id=user_id,
                    subject="Running session excluded",
                    started_at=started_at,
                    duration_minutes=None,
                    status="running",
                ),
                DailyCheckIn(
                    user_id=user_id,
                    check_in_date=date(2026, 7, 7),
                    energy_level="steady",
                    mood_level="neutral",
                    sleep_hours=6,
                    stress_level=3,
                    notes="Needed a slower start.",
                ),
                DailyCheckIn(
                    user_id=user_id,
                    check_in_date=date(2026, 7, 9),
                    energy_level="high",
                    mood_level="good",
                    sleep_hours=8,
                    stress_level=2,
                    notes=None,
                ),
            ]
        )
        db.commit()


def test_weekly_context_calculates_statistics_from_stored_behavior():
    _seed_behavior()

    with TestingSessionLocal() as db:
        context = weekly_review_service.build_context(
            db,
            user_id=1,
            week_start=WEEK_START,
            week_end=WEEK_END,
        )

    assert context.planned_tasks == 3
    assert context.completed_tasks == 1
    assert context.unfinished_tasks == 1
    assert context.completion_rate == 1 / 3
    assert context.focus_minutes == 50
    assert context.check_in_days == 2
    assert context.average_sleep_hours == 7.0
    assert context.energy_distribution == {"steady": 1, "high": 1}
    assert context.mood_distribution == {"neutral": 1, "good": 1}
    assert context.completed_task_titles == ["Completed implementation"]
    assert context.unfinished_task_titles == ["Unfinished documentation"]


def test_manual_generation_saves_and_retrieves_grounded_review(
    client,
    user_headers,
    monkeypatch,
):
    _seed_behavior()
    monkeypatch.setattr(settings, "ollama_api_key", "test-key")

    async def generate_json(system_prompt, user_prompt):
        assert '"planned_tasks": 3' in user_prompt
        assert '"completed_tasks": 1' in user_prompt
        assert '"focus_minutes": 50' in user_prompt
        assert '"steady": 1' in user_prompt
        assert "Completed implementation" in user_prompt
        assert "Do not recalculate database statistics" in system_prompt
        return _llm_result()

    monkeypatch.setattr(llm_service, "generate_json", generate_json)

    generated = client.post(
        "/weekly-reviews/generate",
        headers=user_headers,
        json={"week_start": WEEK_START.isoformat()},
    )

    assert generated.status_code == 201
    body = generated.json()
    assert body["week_start"] == WEEK_START.isoformat()
    assert body["week_end"] == WEEK_END.isoformat()
    assert body["planned_tasks"] == 3
    assert body["completed_tasks"] == 1
    assert body["focus_minutes"] == 50
    assert body["energy_distribution_json"] == {"steady": 1, "high": 1}
    assert body["mood_distribution_json"] == {"neutral": 1, "good": 1}
    assert body["summary"] == "A grounded weekly review."

    fetched = client.get(
        f"/weekly-reviews/{WEEK_START.isoformat()}",
        headers=user_headers,
    )
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


def test_empty_week_and_missing_check_ins_are_allowed(
    client,
    user_headers,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ollama_api_key", "test-key")
    monkeypatch.setattr(
        llm_service,
        "generate_json",
        AsyncMock(return_value=_llm_result("No stored activity this week.")),
    )

    response = client.post(
        "/weekly-reviews/generate",
        headers=user_headers,
        json={"week_start": WEEK_START.isoformat()},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["planned_tasks"] == 0
    assert body["completed_tasks"] == 0
    assert body["completion_rate"] == 0.0
    assert body["focus_minutes"] == 0
    assert body["check_in_days"] == 0
    assert body["average_sleep_hours"] is None
    assert body["energy_distribution_json"] == {}
    assert body["mood_distribution_json"] == {}


def test_generate_defaults_to_current_week_and_current_endpoint_retrieves_it(
    client,
    user_headers,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ollama_api_key", "test-key")
    monkeypatch.setattr(
        llm_service,
        "generate_json",
        AsyncMock(return_value=_llm_result("Current weekly review.")),
    )

    generated = client.post(
        "/weekly-reviews/generate",
        headers=user_headers,
        json={},
    )
    current = client.get("/weekly-reviews/current", headers=user_headers)

    assert generated.status_code == 201
    assert current.status_code == 200
    assert generated.json()["week_start"] == (
        weekly_review_service.current_week_start().isoformat()
    )
    assert current.json()["id"] == generated.json()["id"]


def test_regeneration_updates_the_same_weekly_review(
    client,
    user_headers,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ollama_api_key", "test-key")
    generate = AsyncMock(return_value=_llm_result("First weekly review."))
    monkeypatch.setattr(llm_service, "generate_json", generate)

    first = client.post(
        "/weekly-reviews/generate",
        headers=user_headers,
        json={"week_start": WEEK_START.isoformat()},
    )
    generate.return_value = _llm_result("Updated weekly review.")
    second = client.post(
        "/weekly-reviews/generate",
        headers=user_headers,
        json={"week_start": WEEK_START.isoformat()},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["summary"] == "Updated weekly review."


def test_weekly_review_queries_never_return_another_users_data(
    client,
    monkeypatch,
):
    with TestingSessionLocal() as db:
        db.add(
            User(
                id=2,
                email="weekly-other@example.com",
                password_hash="not-used",
                display_name="Other User",
            )
        )
        db.commit()

    monkeypatch.setattr(settings, "ollama_api_key", "test-key")
    monkeypatch.setattr(
        llm_service,
        "generate_json",
        AsyncMock(return_value=_llm_result()),
    )
    generated = client.post(
        "/weekly-reviews/generate",
        headers={"X-User-ID": "1"},
        json={"week_start": WEEK_START.isoformat()},
    )
    assert generated.status_code == 201

    other_headers = {"X-User-ID": "2"}
    fetched = client.get(
        f"/weekly-reviews/{WEEK_START.isoformat()}",
        headers=other_headers,
    )
    history = client.get("/weekly-reviews", headers=other_headers)

    assert fetched.status_code == 404
    assert history.status_code == 200
    assert history.json() == []


def test_invalid_weekly_review_response_returns_502_without_saving(
    client,
    user_headers,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ollama_api_key", "test-key")
    monkeypatch.setattr(
        llm_service,
        "generate_json",
        AsyncMock(return_value={"summary": "Missing required fields"}),
    )

    response = client.post(
        "/weekly-reviews/generate",
        headers=user_headers,
        json={"week_start": WEEK_START.isoformat()},
    )

    assert response.status_code == 502
    with TestingSessionLocal() as db:
        assert db.scalar(select(WeeklyReview)) is None
