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
