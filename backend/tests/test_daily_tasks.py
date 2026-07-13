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


def test_generate_ai_daily_plan(client, user_headers, monkeypatch):
    monkeypatch.setattr("app.api.daily_tasks.settings.ollama_api_key", "test-key")
    today = date.today()
    goal = client.post(
        "/weekly-goals",
        headers=user_headers,
        json={
            "title": "Ship planning service",
            "week_start": today.isoformat(),
            "week_end": today.isoformat(),
            "priority": "high",
            "target_minutes": 120,
        },
    ).json()

    async def fake_generate_daily_plan(
        weekly_goals,
        unfinished_tasks,
        available_minutes,
    ):
        assert weekly_goals[0]["id"] == goal["id"]
        assert unfinished_tasks == []
        assert available_minutes == 90
        return [
            {
                "title": "Implement AI daily plan",
                "description": "Use weekly goals to create focused tasks",
                "estimated_minutes": 45,
                "priority": "high",
                "weekly_goal_id": goal["id"],
            },
            {
                "title": "Review generated tasks",
                "estimated_minutes": 30,
                "priority": "medium",
                "weekly_goal_id": 999,
            },
        ]

    monkeypatch.setattr(
        "app.services.planning_service.llm_service.generate_daily_plan",
        fake_generate_daily_plan,
    )

    response = client.post(
        "/daily-tasks/generate",
        headers=user_headers,
        json={
            "available_minutes": 90,
            "task_date": today.isoformat(),
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["task_date"] == today.isoformat()
    assert body["original_available_minutes"] == 90
    assert body["adjusted_available_minutes"] == 90
    assert body["workload_level"] == "normal"
    assert body["readiness_score"] == 90.0
    assert body["total_estimated_minutes"] == 75
    assert [task["title"] for task in body["tasks"]] == [
        "Implement AI daily plan",
        "Review generated tasks",
    ]
    assert body["tasks"][0]["source"] == "ai"
    assert body["tasks"][0]["weekly_goal_id"] == goal["id"]
    assert body["tasks"][1]["weekly_goal_id"] is None

    today_tasks = client.get("/daily-tasks/today", headers=user_headers)
    assert today_tasks.status_code == 200
    assert [task["source"] for task in today_tasks.json()] == ["ai", "ai"]


def test_coaching_condition_reduces_plan_and_prioritizes_important_work(
    client,
    user_headers,
    monkeypatch,
):
    monkeypatch.setattr("app.api.daily_tasks.settings.ollama_api_key", "test-key")
    today = date.today()

    check_in = client.post(
        "/check-ins",
        headers=user_headers,
        json={
            "check_in_date": today.isoformat(),
            "energy_level": "depleted",
            "mood_level": "struggling",
            "sleep_hours": 4,
            "stress_level": 5,
        },
    )
    assert check_in.status_code == 201

    async def fake_generate_daily_plan(
        weekly_goals,
        unfinished_tasks,
        available_minutes,
    ):
        assert available_minutes == 54
        return [
            {
                "title": "Optional cleanup",
                "estimated_minutes": 30,
                "priority": "low",
            },
            {
                "title": "Critical implementation",
                "estimated_minutes": 45,
                "priority": "high",
            },
        ]

    monkeypatch.setattr(
        "app.services.planning_service.llm_service.generate_daily_plan",
        fake_generate_daily_plan,
    )

    response = client.post(
        "/daily-tasks/generate",
        headers=user_headers,
        json={
            "available_minutes": 90,
            "task_date": today.isoformat(),
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["original_available_minutes"] == 90
    assert body["adjusted_available_minutes"] == 54
    assert body["workload_level"] == "light"
    assert body["readiness_score"] == 0.0
    assert body["total_estimated_minutes"] == 45
    assert [task["title"] for task in body["tasks"]] == [
        "Critical implementation"
    ]
