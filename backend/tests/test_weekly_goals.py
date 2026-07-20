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


def test_get_goals_for_selected_week(client, user_headers):
    selected = date.today() + timedelta(days=21)
    week_start = selected - timedelta(days=selected.weekday())
    created = client.post(
        "/weekly-goals",
        headers=user_headers,
        json={
            "title": "Future weekly goal",
            "week_start": week_start.isoformat(),
            "week_end": (week_start + timedelta(days=6)).isoformat(),
            "priority": "medium",
            "target_minutes": 240,
        },
    )

    response = client.get(
        f"/weekly-goals?date={selected.isoformat()}",
        headers=user_headers,
    )

    assert created.status_code == 201
    assert response.status_code == 200
    assert [goal["title"] for goal in response.json()] == ["Future weekly goal"]
