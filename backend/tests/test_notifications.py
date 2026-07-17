from datetime import datetime, timedelta, timezone

from app.models import User
from app.services.notification_provider import NotificationProviderError
from app.services.notification_service import notification_service
from conftest import TestingSessionLocal


class FakeEmailProvider:
    channel = "email"

    def __init__(self, failure: str | None = None) -> None:
        self.failure = failure
        self.sent: list[dict[str, str]] = []

    def send(self, *, recipient: str, subject: str, message: str) -> None:
        if self.failure:
            raise NotificationProviderError(self.failure)
        self.sent.append(
            {"recipient": recipient, "subject": subject, "message": message}
        )


class FakeTelegramProvider(FakeEmailProvider):
    channel = "telegram"


def test_email_delivery_is_recorded(client, user_headers, monkeypatch):
    provider = FakeEmailProvider()
    monkeypatch.setattr(notification_service, "provider", provider)

    response = client.post(
        "/notifications",
        headers=user_headers,
        json={
            "notification_type": "morning_plan",
            "subject": "Your plan for today",
            "message": "Start with the database task.",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["channel"] == "email"
    assert data["recipient"] == "mvp@example.com"
    assert data["status"] == "delivered"
    assert data["attempt_count"] == 1
    assert data["delivered_at"] is not None
    assert data["failure_reason"] is None
    assert provider.sent == [
        {
            "recipient": "mvp@example.com",
            "subject": "Your plan for today",
            "message": "Start with the database task.",
        }
    ]


def test_notification_uses_email_saved_in_backend_profile(
    client,
    user_headers,
    monkeypatch,
):
    provider = FakeEmailProvider()
    monkeypatch.setattr(notification_service, "provider", provider)
    profile = client.patch(
        "/users/me",
        headers=user_headers,
        json={"email": "car@example.com", "display_name": "Car"},
    )

    notification = client.post(
        "/notifications",
        headers=user_headers,
        json={
            "notification_type": "upcoming_task",
            "subject": "Upcoming task",
            "message": "Your task starts soon.",
        },
    )

    assert profile.status_code == 200
    assert notification.status_code == 201
    assert notification.json()["recipient"] == "car@example.com"
    assert provider.sent[0]["recipient"] == "car@example.com"


def test_future_notification_stays_pending(client, user_headers, monkeypatch):
    provider = FakeEmailProvider()
    monkeypatch.setattr(notification_service, "provider", provider)
    scheduled_at = datetime.now(timezone.utc) + timedelta(hours=2)

    response = client.post(
        "/notifications",
        headers=user_headers,
        json={
            "notification_type": "upcoming_task",
            "subject": "Task coming up",
            "message": "Your task starts soon.",
            "scheduled_at": scheduled_at.isoformat(),
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    assert response.json()["attempt_count"] == 0
    assert provider.sent == []


def test_telegram_delivery_uses_saved_chat_id(client, user_headers, monkeypatch):
    provider = FakeTelegramProvider()
    monkeypatch.setattr(notification_service, "telegram_provider", provider)
    preferences = client.patch(
        "/automation-preferences",
        headers=user_headers,
        json={
            "notification_channel": "telegram",
            "telegram_chat_id": "123456789",
        },
    )

    response = client.post(
        "/notifications",
        headers=user_headers,
        json={
            "notification_type": "upcoming_task",
            "channel": "telegram",
            "subject": "Upcoming task",
            "message": "Your task starts soon.",
        },
    )

    assert preferences.status_code == 200
    assert response.status_code == 201
    assert response.json()["channel"] == "telegram"
    assert response.json()["recipient"] == "123456789"
    assert response.json()["status"] == "delivered"
    assert provider.sent[0]["recipient"] == "123456789"


def test_telegram_failure_is_recorded_when_chat_id_is_missing(
    client,
    user_headers,
    monkeypatch,
):
    from app.config import settings

    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")

    response = client.post(
        "/notifications",
        headers=user_headers,
        json={
            "notification_type": "upcoming_task",
            "channel": "telegram",
            "subject": "Upcoming task",
            "message": "Your task starts soon.",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert "save a Telegram chat ID" in response.json()["failure_reason"]


def test_failed_delivery_is_visible_and_can_be_retried(
    client,
    user_headers,
    monkeypatch,
):
    failing_provider = FakeEmailProvider("SMTP is unavailable")
    monkeypatch.setattr(notification_service, "provider", failing_provider)
    created = client.post(
        "/notifications",
        headers=user_headers,
        json={
            "notification_type": "deadline_warning",
            "subject": "Deadline warning",
            "message": "A deadline is approaching.",
        },
    )

    assert created.status_code == 201
    assert created.json()["status"] == "failed"
    assert created.json()["failure_reason"] == "SMTP is unavailable"

    failures = client.get(
        "/notifications?status=failed",
        headers=user_headers,
    )
    assert failures.status_code == 200
    assert [item["id"] for item in failures.json()] == [created.json()["id"]]

    working_provider = FakeEmailProvider()
    monkeypatch.setattr(notification_service, "provider", working_provider)
    retried = client.post(
        f"/notifications/{created.json()['id']}/retry",
        headers=user_headers,
    )

    assert retried.status_code == 200
    assert retried.json()["status"] == "delivered"
    assert retried.json()["attempt_count"] == 2
    assert retried.json()["failure_reason"] is None


def test_user_cannot_retry_another_users_notification(
    client,
    user_headers,
    monkeypatch,
):
    monkeypatch.setattr(
        notification_service,
        "provider",
        FakeEmailProvider("SMTP is unavailable"),
    )
    created = client.post(
        "/notifications",
        headers=user_headers,
        json={
            "notification_type": "weekly_review",
            "subject": "Weekly review",
            "message": "Your review is ready.",
        },
    )
    with TestingSessionLocal() as db:
        db.add(
            User(
                id=2,
                email="second@example.com",
                password_hash="not-used",
                display_name="Second User",
            )
        )
        db.commit()

    response = client.post(
        f"/notifications/{created.json()['id']}/retry",
        headers={"X-User-ID": "2"},
    )

    assert response.status_code == 404


def test_delivered_notification_cannot_be_retried(client, user_headers, monkeypatch):
    monkeypatch.setattr(notification_service, "provider", FakeEmailProvider())
    created = client.post(
        "/notifications",
        headers=user_headers,
        json={
            "notification_type": "evening_check_in",
            "subject": "Evening check-in",
            "message": "How did today go?",
        },
    )

    response = client.post(
        f"/notifications/{created.json()['id']}/retry",
        headers=user_headers,
    )

    assert response.status_code == 409
