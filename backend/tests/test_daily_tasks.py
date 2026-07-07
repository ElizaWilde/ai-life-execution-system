from datetime import date


def test_manually_create_daily_task(client, user_headers):
    response = client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Implement the timer endpoint",
            "task_date": date.today().isoformat(),
            "estimated_minutes": 45,
            "priority": "high",
        },
    )

    assert response.status_code == 201
    assert response.json()["source"] == "manual"
    assert response.json()["status"] == "pending"

    today = client.get("/daily-tasks/today", headers=user_headers)

    assert today.status_code == 200
    assert [task["id"] for task in today.json()] == [response.json()["id"]]
