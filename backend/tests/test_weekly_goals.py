from datetime import date, timedelta


def test_create_and_get_current_weekly_goal(client, user_headers):
    today = date.today()
    payload = {
        "title": "Ship the MVP",
        "description": "Complete the manual execution loop",
        "week_start": (today - timedelta(days=1)).isoformat(),
        "week_end": (today + timedelta(days=5)).isoformat(),
        "priority": "high",
        "target_minutes": 300,
    }

    created = client.post("/weekly-goals", json=payload, headers=user_headers)

    assert created.status_code == 201
    assert created.json()["title"] == "Ship the MVP"
    assert created.json()["status"] == "active"

    current = client.get("/weekly-goals/current", headers=user_headers)

    assert current.status_code == 200
    assert [goal["id"] for goal in current.json()] == [created.json()["id"]]
