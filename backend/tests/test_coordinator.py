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
        message="What should I do first?",
        history=[{"role": "user", "content": "I feel stuck."}],
    )


def test_coordinator_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "ollama_api_key", None)

    response = client.post("/coordinator/chat", json={"message": "Hello"})

    assert response.status_code == 503
    assert response.json()["detail"] == "OLLAMA_API_KEY is not configured"
