from app.models import User
from conftest import TestingSessionLocal


def test_get_creates_safe_default_preferences(client, user_headers):
    response = client.get("/automation-preferences", headers=user_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["timezone"] == "Asia/Singapore"
    assert data["morning_reminder_time"] == "08:00:00"
    assert data["evening_review_time"] == "21:00:00"
    assert data["notification_channel"] == "email"
    assert data["telegram_chat_id"] is None
    assert data["automatic_rescheduling_enabled"] is False
    assert data["confirmation_required"] is True
    assert data["max_reminders_per_day"] == 3
    assert data["working_days"] == [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
    ]


def test_patch_persists_all_automation_constraints(client, user_headers):
    payload = {
        "timezone": "Europe/London",
        "morning_reminder_time": "07:30",
        "evening_review_time": "20:45",
        "notification_channel": "telegram",
        "telegram_chat_id": "-1001234567890",
        "automatic_rescheduling_enabled": True,
        "confirmation_required": False,
        "max_reminders_per_day": 5,
        "quiet_hours_start": "23:00",
        "quiet_hours_end": "06:30",
        "working_days": ["monday", "wednesday", "saturday"],
        "preferred_study_periods": [
            {"start": "07:00", "end": "09:00"},
            {"start": "19:00", "end": "21:00"},
        ],
    }

    updated = client.patch(
        "/automation-preferences",
        headers=user_headers,
        json=payload,
    )
    fetched = client.get("/automation-preferences", headers=user_headers)

    assert updated.status_code == 200
    assert fetched.status_code == 200
    data = fetched.json()
    assert data["timezone"] == "Europe/London"
    assert data["notification_channel"] == "telegram"
    assert data["telegram_chat_id"] == "-1001234567890"
    assert data["automatic_rescheduling_enabled"] is True
    assert data["confirmation_required"] is False
    assert data["working_days"] == ["monday", "wednesday", "saturday"]
    assert data["preferred_study_periods"] == [
        {"start": "07:00:00", "end": "09:00:00"},
        {"start": "19:00:00", "end": "21:00:00"},
    ]


def test_invalid_timezone_and_reminder_limit_are_rejected(client, user_headers):
    timezone_response = client.patch(
        "/automation-preferences",
        headers=user_headers,
        json={"timezone": "Mars/Olympus"},
    )
    reminder_response = client.patch(
        "/automation-preferences",
        headers=user_headers,
        json={"max_reminders_per_day": 21},
    )

    assert timezone_response.status_code == 422
    assert reminder_response.status_code == 422


def test_preferences_are_scoped_to_current_user(client, user_headers):
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

    client.patch(
        "/automation-preferences",
        headers=user_headers,
        json={"max_reminders_per_day": 8},
    )
    second = client.get("/automation-preferences", headers={"X-User-ID": "2"})

    assert second.status_code == 200
    assert second.json()["max_reminders_per_day"] == 3
