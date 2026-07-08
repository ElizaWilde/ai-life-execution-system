from datetime import date, datetime, timedelta, timezone


def test_today_dashboard_stats(client, user_headers):
    today = date.today()

    first_task = client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Finish dashboard service",
            "task_date": today.isoformat(),
            "estimated_minutes": 45,
            "priority": "high",
        },
    ).json()
    client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Write dashboard API tests",
            "task_date": today.isoformat(),
            "estimated_minutes": 30,
            "priority": "medium",
        },
    )
    client.patch(
        f"/daily-tasks/{first_task['id']}",
        headers=user_headers,
        json={"status": "completed"},
    )

    started_at = datetime.now(timezone.utc) - timedelta(minutes=35)
    session = client.post(
        "/study-sessions/start",
        headers=user_headers,
        json={
            "daily_task_id": first_task["id"],
            "subject": "Dashboard statistics",
            "started_at": started_at.isoformat(),
        },
    ).json()
    client.post(
        "/study-sessions/finish",
        headers=user_headers,
        json={
            "session_id": session["id"],
            "ended_at": (started_at + timedelta(minutes=35)).isoformat(),
        },
    )

    response = client.get("/dashboard/today", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == today.isoformat()
    assert body["focus_minutes"] == 35
    assert body["planned_tasks"] == 2
    assert body["completed_tasks"] == 1
    assert body["completion_rate"] == 0.5
    assert [task["title"] for task in body["unfinished_tasks"]] == [
        "Write dashboard API tests"
    ]


def test_week_dashboard_stats(client, user_headers):
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    active_goal = client.post(
        "/weekly-goals",
        headers=user_headers,
        json={
            "title": "Ship dashboard",
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "priority": "high",
        },
    ).json()
    completed_goal = client.post(
        "/weekly-goals",
        headers=user_headers,
        json={
            "title": "Finish migrations",
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "priority": "medium",
        },
    ).json()
    client.patch(
        f"/weekly-goals/{completed_goal['id']}",
        headers=user_headers,
        json={"status": "completed"},
    )

    completed_task = client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Complete dashboard endpoint",
            "task_date": today.isoformat(),
            "priority": "high",
            "weekly_goal_id": active_goal["id"],
        },
    ).json()
    client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Review dashboard UI",
            "task_date": today.isoformat(),
            "priority": "medium",
            "weekly_goal_id": active_goal["id"],
        },
    )
    client.patch(
        f"/daily-tasks/{completed_task['id']}",
        headers=user_headers,
        json={"status": "completed"},
    )

    started_at = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    session = client.post(
        "/study-sessions/start",
        headers=user_headers,
        json={
            "daily_task_id": completed_task["id"],
            "subject": "Weekly dashboard",
            "started_at": started_at.isoformat(),
        },
    ).json()
    client.post(
        "/study-sessions/finish",
        headers=user_headers,
        json={
            "session_id": session["id"],
            "ended_at": (started_at + timedelta(minutes=50)).isoformat(),
        },
    )

    response = client.get("/dashboard/week", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["week_start"] == week_start.isoformat()
    assert body["week_end"] == week_end.isoformat()
    assert body["focus_minutes"] == 50
    assert body["planned_tasks"] == 2
    assert body["completed_tasks"] == 1
    assert body["completion_rate"] == 0.5
    assert body["active_goals"] == 1
    assert body["completed_goals"] == 1
    assert len(body["daily_focus"]) == 7
    assert sum(point["focus_minutes"] for point in body["daily_focus"]) == 50
