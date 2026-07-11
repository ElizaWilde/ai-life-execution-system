from datetime import date, timedelta


def test_create_check_in_uses_authenticated_user_defaults_today_and_returns_saved_record(
    client,
    user_headers,
):
    response = client.post(
        "/check-ins",
        headers=user_headers,
        json={
            "energy_level": "steady",
            "mood_level": "neutral",
            "sleep_hours": 7.5,
            "stress_level": 2,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["user_id"] == 1
    assert body["check_in_date"] == date.today().isoformat()
    assert body["energy_level"] == "steady"
    assert body["mood_level"] == "neutral"
    assert body["sleep_hours"] == 7.5
    assert body["created_at"] is not None
    assert body["updated_at"] is not None

    saved = client.get("/check-ins/today", headers=user_headers)

    assert saved.status_code == 200
    assert saved.json()["id"] == body["id"]


def test_create_check_in_uses_payload_date_and_rejects_duplicate(
    client,
    user_headers,
):
    check_in_date = date.today() - timedelta(days=1)
    payload = {
        "check_in_date": check_in_date.isoformat(),
        "energy_level": "high",
        "mood_level": "good",
        "sleep_hours": 8,
    }

    response = client.post("/check-ins", headers=user_headers, json=payload)

    assert response.status_code == 201
    assert response.json()["check_in_date"] == check_in_date.isoformat()

    duplicate = client.post("/check-ins", headers=user_headers, json=payload)

    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Daily check-in already exists"
