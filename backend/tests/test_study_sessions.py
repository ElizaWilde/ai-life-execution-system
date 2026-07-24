from datetime import date, datetime, timedelta, timezone


def test_start_and_finish_study_session(client, user_headers):
    task = client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Study SQLAlchemy",
            "task_date": date.today().isoformat(),
            "estimated_minutes": 25,
        },
    ).json()
    started_at = datetime.now(timezone.utc) - timedelta(minutes=25)

    started = client.post(
        "/study-sessions/start",
        headers=user_headers,
        json={
            "daily_task_id": task["id"],
            "subject": "Backend development",
            "started_at": started_at.isoformat(),
        },
    )

    assert started.status_code == 201
    assert started.json()["status"] == "running"

    finished = client.post(
        "/study-sessions/finish",
        headers=user_headers,
        json={
            "session_id": started.json()["id"],
            "ended_at": (started_at + timedelta(minutes=25)).isoformat(),
            "notes": "CRUD complete",
        },
    )

    assert finished.status_code == 200
    assert finished.json()["status"] == "completed"
    assert finished.json()["duration_minutes"] == 25

    completed_task = client.get("/daily-tasks/today", headers=user_headers).json()[0]
    assert completed_task["status"] == "completed"
    assert completed_task["completed_at"] is not None


def test_task_completes_when_cumulative_focus_reaches_estimate(client, user_headers):
    task = client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Cumulative focus task",
            "task_date": date.today().isoformat(),
            "estimated_minutes": 40,
        },
    ).json()

    for offset in (25, 15):
        started_at = datetime.now(timezone.utc) - timedelta(minutes=offset)
        started = client.post(
            "/study-sessions/start",
            headers=user_headers,
            json={
                "daily_task_id": task["id"],
                "subject": "Focused work",
                "started_at": started_at.isoformat(),
            },
        ).json()
        client.post(
            "/study-sessions/finish",
            headers=user_headers,
            json={
                "session_id": started["id"],
                "ended_at": (started_at + timedelta(minutes=offset)).isoformat(),
            },
        )

    completed_task = client.get("/daily-tasks/today", headers=user_headers).json()[0]
    assert completed_task["status"] == "completed"
