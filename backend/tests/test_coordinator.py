from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.coordinator_service import coordinator_service


client = TestClient(app)


def test_coordinator_chat(monkeypatch):
    monkeypatch.setattr(settings, "ollama_api_key", "test-key")
    answer = AsyncMock(return_value="Start with one small task.")
    monkeypatch.setattr(coordinator_service, "answer", answer)

    response = client.post(
        "/coordinator/chat",
        headers={"X-User-ID": "1"},
        json={
            "message": "What should I do first?",
            "history": [{"role": "user", "content": "I feel stuck."}],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "reply": "Start with one small task.",
        "model": settings.ollama_model,
        "agent": "coordinator",
    }
    answer.assert_awaited_once_with(
        db=answer.await_args.kwargs["db"],
        user=answer.await_args.kwargs["user"],
        message="What should I do first?",
        history=[{"role": "user", "content": "I feel stuck."}],
    )
    assert answer.await_args.kwargs["user"].id == 1


def test_coordinator_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "ollama_api_key", None)

    response = client.post(
        "/coordinator/chat",
        headers={"X-User-ID": "1"},
        json={"message": "Hello"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "OLLAMA_API_KEY is not configured"


def test_coordinator_chat_receives_today_plan_and_check_in(
    client,
    user_headers,
    monkeypatch,
):
    from datetime import date

    from app.services.llm_service import llm_service

    monkeypatch.setattr(settings, "ollama_api_key", "test-key")
    chat = AsyncMock(return_value="Your plan fits your steady energy.")
    monkeypatch.setattr(llm_service, "chat", chat)

    task = client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Finish the execution context",
            "task_date": date.today().isoformat(),
            "estimated_minutes": 45,
            "priority": "high",
        },
    )
    assert task.status_code == 201
    check_in = client.post(
        "/check-ins",
        headers=user_headers,
        json={
            "check_in_date": date.today().isoformat(),
            "energy_level": "steady",
            "mood_level": "good",
            "sleep_hours": 7.5,
            "stress_level": 2,
            "available_minutes": 120,
            "focus_mode": "Deep work",
            "notes": "Protect the morning block.",
        },
    )
    assert check_in.status_code == 201

    response = client.post(
        "/coordinator/chat",
        headers=user_headers,
        json={"message": "What do you think of my plan today?"},
    )

    assert response.status_code == 200
    assert response.json()["reply"] == "Your plan fits your steady energy."
    prompt = chat.await_args.kwargs["system_prompt"]
    assert '"title":"Finish the execution context"' in prompt
    assert '"energy_level":"steady"' in prompt
    assert '"available_minutes":120' in prompt
    assert "lack the user's schedule" in prompt
