from datetime import date, datetime, timedelta, timezone


def test_generate_ai_daily_review(client, user_headers, monkeypatch):
    monkeypatch.setattr("app.api.reviews.settings.ollama_api_key", "test-key")
    today = date.today()

    task = client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Finish review service",
            "task_date": today.isoformat(),
            "estimated_minutes": 45,
            "priority": "high",
        },
    ).json()
    client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Polish review endpoint",
            "task_date": today.isoformat(),
            "estimated_minutes": 30,
            "priority": "medium",
        },
    )
    client.patch(
        f"/daily-tasks/{task['id']}",
        headers=user_headers,
        json={"status": "completed"},
    )

    started_at = datetime.now(timezone.utc) - timedelta(minutes=40)
    session = client.post(
        "/study-sessions/start",
        headers=user_headers,
        json={
            "daily_task_id": task["id"],
            "subject": "Daily review backend",
            "started_at": started_at.isoformat(),
        },
    ).json()
    client.post(
        "/study-sessions/finish",
        headers=user_headers,
        json={
            "session_id": session["id"],
            "ended_at": (started_at + timedelta(minutes=40)).isoformat(),
            "notes": "Review service completed",
        },
    )

    async def fake_generate_daily_review(
        planned_tasks,
        completed_tasks,
        study_sessions,
    ):
        assert len(planned_tasks) == 2
        assert len(completed_tasks) == 1
        assert study_sessions[0]["duration_minutes"] == 40
        return "Good execution day. One task finished; carry the endpoint polish forward."

    monkeypatch.setattr(
        "app.services.review_service.llm_service.generate_daily_review",
        fake_generate_daily_review,
    )

    response = client.post(
        "/reviews/generate",
        headers=user_headers,
        json={"review_date": today.isoformat()},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["review_date"] == today.isoformat()
    assert body["summary"] == (
        "Good execution day. One task finished; carry the endpoint polish forward."
    )
    assert body["tomorrow_adjustment"] == (
        "Carry forward unfinished work: Polish review endpoint"
    )
    assert body["planned_tasks"] == 2
    assert body["completed_tasks"] == 1
    assert body["focus_minutes"] == 40
    assert body["source"] == "ai"

    fetched = client.get(
        f"/reviews/daily?date={today.isoformat()}",
        headers=user_headers,
    )
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


def test_generate_ai_daily_review_updates_existing_review(
    client,
    user_headers,
    monkeypatch,
):
    monkeypatch.setattr("app.api.reviews.settings.ollama_api_key", "test-key")
    today = date.today()

    async def first_review(planned_tasks, completed_tasks, study_sessions):
        return "First review"

    async def second_review(planned_tasks, completed_tasks, study_sessions):
        return "Second review"

    monkeypatch.setattr(
        "app.services.review_service.llm_service.generate_daily_review",
        first_review,
    )
    first = client.post(
        "/reviews/generate",
        headers=user_headers,
        json={"review_date": today.isoformat()},
    )

    monkeypatch.setattr(
        "app.services.review_service.llm_service.generate_daily_review",
        second_review,
    )
    second = client.post(
        "/reviews/generate",
        headers=user_headers,
        json={"review_date": today.isoformat()},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["summary"] == "Second review"
