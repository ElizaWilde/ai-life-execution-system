from datetime import date, datetime, timedelta, timezone

from app.models import ReschedulingProposal
from conftest import TestingSessionLocal


def test_read_only_command_executes_and_is_idempotent(client, user_headers):
    headers = {**user_headers, "Idempotency-Key": "progress-command-1"}
    first = client.post(
        "/coordinator/commands",
        headers=headers,
        json={"message": "How is my progress this week?"},
    )
    second = client.post(
        "/coordinator/commands",
        headers=headers,
        json={"message": "How is my progress this week?"},
    )

    assert first.status_code == 200
    assert first.json()["intent"] == "get_progress"
    assert first.json()["status"] == "completed"
    assert first.json()["id"] == second.json()["id"]


def test_create_today_task_requires_confirmation(client, user_headers):
    command = client.post(
        "/coordinator/commands",
        headers={**user_headers, "Idempotency-Key": "create-task-command-1"},
        json={"message": "add a task in today: 1h learn eg high priority tag:study"},
    )

    assert command.status_code == 200
    assert command.json()["intent"] == "create_task"
    assert command.json()["status"] == "pending_confirmation"
    assert command.json()["parameters_json"] == {
        "title": "learn eg",
        "description": None,
        "task_date": date.today().isoformat(),
        "estimated_minutes": 60,
        "channel": "study",
        "priority": "high",
        "weekly_goal_id": None,
    }
    assert all(item["title"] != "learn eg" for item in client.get("/daily-tasks/today", headers=user_headers).json())

    confirmed = client.post(
        f"/coordinator/commands/{command.json()['id']}/confirm",
        headers=user_headers,
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "completed"
    tasks = client.get("/daily-tasks/today", headers=user_headers).json()
    created = next(item for item in tasks if item["title"] == "learn eg")
    assert created["estimated_minutes"] == 60
    assert created["priority"] == "high"
    assert created["channel"] == "study"
    assert created["source"] == "ai"


def test_slash_create_task_can_be_rejected(client, user_headers):
    command = client.post(
        "/coordinator/commands",
        headers={**user_headers, "Idempotency-Key": "slash-create-task-command-1"},
        json={
            "message": '/add_task date=today duration=1h title="Learn EG slash" priority=high tags=study'
        },
    ).json()

    assert command["intent"] == "create_task"
    assert command["parameters_json"]["title"] == "Learn EG slash"
    assert command["status"] == "pending_confirmation"

    rejected = client.post(
        f"/coordinator/commands/{command['id']}/reject",
        headers=user_headers,
    )

    assert rejected.status_code == 200
    assert all(item["title"] != "Learn EG slash" for item in client.get("/daily-tasks/today", headers=user_headers).json())


def test_complete_task_command_requires_confirmation(client, user_headers):
    task = client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Finish command routing",
            "task_date": date.today().isoformat(),
            "estimated_minutes": 30,
        },
    ).json()
    command = client.post(
        "/coordinator/commands",
        headers={**user_headers, "Idempotency-Key": "complete-command-1"},
        json={"message": "Mark Finish command routing done"},
    )

    assert command.status_code == 200
    assert command.json()["status"] == "pending_confirmation"
    assert command.json()["intent"] == "complete_task"
    before = client.get("/daily-tasks/today", headers=user_headers).json()
    assert next(item for item in before if item["id"] == task["id"])["status"] == "pending"

    confirmed = client.post(
        f"/coordinator/commands/{command.json()['id']}/confirm",
        headers=user_headers,
    )
    repeated = client.post(
        f"/coordinator/commands/{command.json()['id']}/confirm",
        headers=user_headers,
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "completed"
    assert repeated.status_code == 200
    after = client.get("/daily-tasks/today", headers=user_headers).json()
    assert next(item for item in after if item["id"] == task["id"])["status"] == "completed"


def test_change_task_duration_requires_confirmation(client, user_headers):
    task = client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "security and frontend integration",
            "task_date": date.today().isoformat(),
            "estimated_minutes": 60,
        },
    ).json()
    command = client.post(
        "/coordinator/commands",
        headers={**user_headers, "Idempotency-Key": "duration-command-1"},
        json={"message": "I want to change daily task security and frontend integration to 2h"},
    )

    assert command.status_code == 200
    assert command.json()["intent"] == "change_task_duration"
    assert command.json()["status"] == "pending_confirmation"
    assert command.json()["parameters_json"]["proposed_minutes"] == 120
    before = client.get("/daily-tasks/today", headers=user_headers).json()
    assert next(item for item in before if item["id"] == task["id"])["estimated_minutes"] == 60

    confirmed = client.post(
        f"/coordinator/commands/{command.json()['id']}/confirm",
        headers=user_headers,
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "completed"
    assert confirmed.json()["result_json"]["estimated_minutes"] == 120
    after = client.get("/daily-tasks/today", headers=user_headers).json()
    assert next(item for item in after if item["id"] == task["id"])["estimated_minutes"] == 120


def test_update_today_task_content_requires_confirmation(client, user_headers):
    task = client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Prepare launch notes",
            "task_date": date.today().isoformat(),
            "priority": "medium",
            "channel": "work",
        },
    ).json()
    command = client.post(
        "/coordinator/commands",
        headers={**user_headers, "Idempotency-Key": "task-content-command-1"},
        json={"message": "Change task Prepare launch notes priority to urgent"},
    )

    assert command.status_code == 200
    assert command.json()["intent"] == "update_content"
    assert command.json()["status"] == "pending_confirmation"
    before = client.get("/daily-tasks/today", headers=user_headers).json()
    assert next(item for item in before if item["id"] == task["id"])["priority"] == "medium"

    confirmed = client.post(
        f"/coordinator/commands/{command.json()['id']}/confirm",
        headers=user_headers,
    )

    assert confirmed.status_code == 200
    after = client.get("/daily-tasks/today", headers=user_headers).json()
    assert next(item for item in after if item["id"] == task["id"])["priority"] == "urgent"


def test_review_task_status_update_can_be_rejected(client, user_headers):
    task = client.post(
        "/daily-tasks",
        headers=user_headers,
        json={"title": "Review status task", "task_date": date.today().isoformat()},
    ).json()
    command = client.post(
        "/coordinator/commands",
        headers={**user_headers, "Idempotency-Key": "review-status-command-1"},
        json={"message": "Set task Review status task status to completed"},
    ).json()

    assert command["intent"] == "update_content"
    assert command["status"] == "pending_confirmation"
    assert command["parameters_json"]["resource_id"] == task["id"]

    rejected = client.post(
        f"/coordinator/commands/{command['id']}/reject",
        headers=user_headers,
    )

    assert rejected.status_code == 200
    tasks = client.get("/daily-tasks/today", headers=user_headers).json()
    assert next(item for item in tasks if item["id"] == task["id"])["status"] == "pending"


def test_update_weekly_priority_content_requires_confirmation(client, user_headers):
    week_start = date.today() - timedelta(days=date.today().weekday())
    goal = client.post(
        "/weekly-goals",
        headers=user_headers,
        json={
            "title": "Launch preparation",
            "week_start": week_start.isoformat(),
            "week_end": (week_start + timedelta(days=6)).isoformat(),
            "priority": "medium",
            "target_minutes": 120,
        },
    ).json()
    command = client.post(
        "/coordinator/commands",
        headers={**user_headers, "Idempotency-Key": "weekly-content-command-1"},
        json={"message": "Update weekly priority Launch preparation target time to 4h"},
    )

    assert command.status_code == 200
    assert command.json()["intent"] == "update_content"
    assert command.json()["status"] == "pending_confirmation"
    before = client.get("/weekly-goals", headers=user_headers).json()
    assert next(item for item in before if item["id"] == goal["id"])["target_minutes"] == 120

    confirmed = client.post(
        f"/coordinator/commands/{command.json()['id']}/confirm",
        headers=user_headers,
    )

    assert confirmed.status_code == 200
    after = client.get("/weekly-goals", headers=user_headers).json()
    assert next(item for item in after if item["id"] == goal["id"])["target_minutes"] == 240


def test_update_phase_and_milestone_content_requires_confirmation(client, user_headers):
    phase = client.post(
        "/phases",
        headers=user_headers,
        json={
            "title": "Automation rollout",
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=14)).isoformat(),
            "status": "active",
        },
    ).json()
    milestone = client.post(
        f"/phases/{phase['id']}/milestones",
        headers=user_headers,
        json={"title": "Forecast engine", "status": "not_started"},
    ).json()

    phase_command = client.post(
        "/coordinator/commands",
        headers={**user_headers, "Idempotency-Key": "phase-content-command-1"},
        json={"message": "Set phase Automation rollout progress to 45%"},
    ).json()
    milestone_command = client.post(
        "/coordinator/commands",
        headers={**user_headers, "Idempotency-Key": "milestone-content-command-1"},
        json={"message": "Set milestone Forecast engine status to in progress"},
    ).json()

    assert phase_command["status"] == "pending_confirmation"
    assert milestone_command["status"] == "pending_confirmation"
    before = client.get("/phases", headers=user_headers).json()
    current_phase = next(item for item in before if item["id"] == phase["id"])
    assert current_phase["progress"] == 0
    assert next(item for item in current_phase["milestones"] if item["id"] == milestone["id"])["status"] == "not_started"

    client.post(f"/coordinator/commands/{phase_command['id']}/confirm", headers=user_headers)
    client.post(f"/coordinator/commands/{milestone_command['id']}/confirm", headers=user_headers)

    after = client.get("/phases", headers=user_headers).json()
    current_phase = next(item for item in after if item["id"] == phase["id"])
    assert current_phase["progress"] == 45
    assert next(item for item in current_phase["milestones"] if item["id"] == milestone["id"])["status"] == "in_progress"


def test_pending_command_can_be_rejected_without_changes(client, user_headers):
    task = client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Keep this task open",
            "task_date": date.today().isoformat(),
        },
    ).json()
    command = client.post(
        "/coordinator/commands",
        headers={**user_headers, "Idempotency-Key": "reject-command-1"},
        json={"message": "Complete Keep this task open"},
    ).json()

    rejected = client.post(
        f"/coordinator/commands/{command['id']}/reject",
        headers=user_headers,
    )

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    tasks = client.get("/daily-tasks/today", headers=user_headers).json()
    assert next(item for item in tasks if item["id"] == task["id"])["status"] == "pending"


def test_rejecting_reschedule_command_rejects_its_proposal(client, user_headers):
    now = datetime.now(timezone.utc)
    client.post(
        "/daily-tasks",
        headers=user_headers,
        json={
            "title": "Overdue command task",
            "task_date": (date.today() - timedelta(days=1)).isoformat(),
            "due_at": (now - timedelta(hours=1)).isoformat(),
            "estimated_minutes": 30,
        },
    )
    command = client.post(
        "/coordinator/commands",
        headers={**user_headers, "Idempotency-Key": "reschedule-command-1"},
        json={"message": "Move overdue tasks"},
    ).json()
    proposal_id = command["parameters_json"]["proposal_id"]

    rejected = client.post(
        f"/coordinator/commands/{command['id']}/reject",
        headers=user_headers,
    )

    assert rejected.status_code == 200
    with TestingSessionLocal() as db:
        proposal = db.get(ReschedulingProposal, proposal_id)
        assert proposal is not None
        assert proposal.status == "rejected"
