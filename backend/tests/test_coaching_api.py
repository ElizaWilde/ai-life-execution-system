from datetime import date
from unittest.mock import AsyncMock

from app.config import settings
from app.models import CoachingRecommendation, User
from app.schemas.coaching import CoachingRecommendationRead
from app.services.coaching_service import coaching_service
from conftest import TestingSessionLocal


TARGET_DATE = date(2026, 7, 13)


def _advice(summary: str = "Focus on one important task.") -> dict:
    return {
        "summary": summary,
        "suggestions": ["Complete the coaching API first."],
        "risk_factors": ["Insufficient sleep."],
        "planning_changes": ["Move optional work to tomorrow."],
    }


def _add_recommendation(user_id: int, target_date: date, summary: str):
    with TestingSessionLocal() as db:
        recommendation = CoachingRecommendation(
            user_id=user_id,
            recommendation_date=target_date,
            readiness_score=70,
            workload_multiplier=0.8,
            workload_level="reduced",
            adjustment_reasons_json=["Insufficient sleep"],
            summary=summary,
            recommendations_json=_advice(summary),
            model_name="test-model",
            prompt_version="phase2-v1",
        )
        db.add(recommendation)
        db.commit()
        db.refresh(recommendation)
        return CoachingRecommendationRead.model_validate(recommendation)


def test_generate_daily_recommendation_uses_authenticated_user(
    client,
    user_headers,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ollama_api_key", "test-key")
    generated = _add_recommendation(1, TARGET_DATE, "Use a reduced workload.")
    generate = AsyncMock(return_value=generated)
    monkeypatch.setattr(
        coaching_service,
        "generate_daily_recommendation",
        generate,
    )

    with TestingSessionLocal() as db:
        saved = db.get(CoachingRecommendation, generated.id)
        db.delete(saved)
        db.commit()

    response = client.post(
        "/coaching/daily/generate",
        headers=user_headers,
        json={"target_date": TARGET_DATE.isoformat()},
    )

    assert response.status_code == 201
    assert response.json() == {
        "recommendation_date": TARGET_DATE.isoformat(),
        "readiness_score": 70.0,
        "workload_multiplier": 0.8,
        "workload_level": "reduced",
        "summary": "Use a reduced workload.",
        "suggestions": ["Complete the coaching API first."],
        "risk_factors": ["Insufficient sleep."],
        "planning_changes": ["Move optional work to tomorrow."],
    }
    generate.assert_awaited_once_with(
        db=generate.await_args.kwargs["db"],
        user_id=1,
        target_date=TARGET_DATE,
    )


def test_get_daily_recommendation_never_returns_another_users_record(client):
    with TestingSessionLocal() as db:
        db.add(
            User(
                id=2,
                email="other@example.com",
                password_hash="not-used",
                display_name="Other User",
            )
        )
        db.commit()

    _add_recommendation(1, TARGET_DATE, "Private recommendation")

    response = client.get(
        f"/coaching/daily?date={TARGET_DATE.isoformat()}",
        headers={"X-User-ID": "2"},
    )

    assert response.status_code == 404


def test_get_daily_recommendation_returns_authenticated_users_record(
    client,
    user_headers,
):
    _add_recommendation(1, TARGET_DATE, "My recommendation")

    response = client.get(
        f"/coaching/daily?date={TARGET_DATE.isoformat()}",
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["summary"] == "My recommendation"
    assert response.json()["suggestions"] == [
        "Complete the coaching API first."
    ]


def test_history_is_scoped_to_authenticated_user_and_newest_first(
    client,
    user_headers,
):
    with TestingSessionLocal() as db:
        db.add(
            User(
                id=2,
                email="other@example.com",
                password_hash="not-used",
                display_name="Other User",
            )
        )
        db.commit()

    _add_recommendation(1, date(2026, 7, 12), "Older own recommendation")
    _add_recommendation(2, date(2026, 7, 13), "Other user's recommendation")
    _add_recommendation(1, date(2026, 7, 13), "Newest own recommendation")

    response = client.get("/coaching/history", headers=user_headers)

    assert response.status_code == 200
    assert [item["summary"] for item in response.json()] == [
        "Newest own recommendation",
        "Older own recommendation",
    ]


def test_generate_rejects_duplicate_without_calling_ollama(
    client,
    user_headers,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ollama_api_key", "test-key")
    _add_recommendation(1, TARGET_DATE, "Already generated")
    generate = AsyncMock()
    monkeypatch.setattr(
        coaching_service,
        "generate_daily_recommendation",
        generate,
    )

    response = client.post(
        "/coaching/daily/generate",
        headers=user_headers,
        json={"target_date": TARGET_DATE.isoformat()},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Coaching recommendation already exists"
    generate.assert_not_awaited()


def test_generate_requires_configured_ollama_key(
    client,
    user_headers,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ollama_api_key", None)

    response = client.post(
        "/coaching/daily/generate",
        headers=user_headers,
        json={"target_date": TARGET_DATE.isoformat()},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "OLLAMA_API_KEY is not configured"
