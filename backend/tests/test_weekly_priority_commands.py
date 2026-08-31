from copy import deepcopy
from datetime import date, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.models import AutomationCommand, DailyTask, User, WeeklyGoal
from app.schemas.command import CommandInterpretation
from app.services.coordinator_service import coordinator_service
from app.services.llm_service import llm_service
from app.services.planning_service import planning_service
from conftest import TestingSessionLocal


MESSAGE = (
    "add weekly priority:1.update ai coach,10h,high priority;"
    "2.update cambridge reader,10h,high priority;3,update podman project,10h,priority"
)
PAYLOAD = {
    "intent": "create_weekly_priorities",
    "week_start": "2030-07-29",
    "weekly_priorities": [
        {"title": "update ai coach", "target_minutes": 600, "priority": "high"},
        {"title": "update cambridge reader", "target_minutes": 600, "priority": "high"},
        {"title": "update podman project", "target_minutes": 600},
    ],
}


@pytest.fixture
def semantic_payload(monkeypatch):
    payload = deepcopy(PAYLOAD)

    async def interpret(**kwargs):
        assert kwargs["response_model"] is CommandInterpretation
        assert kwargs["tool_name"] == "interpret_command"
        assert "create_weekly_priorities" in kwargs["system_prompt"]
        assert "current_week_start" in kwargs["system_prompt"]
        assert kwargs["user_prompt"] == MESSAGE
        return kwargs["response_model"].model_validate(payload)

    monkeypatch.setattr(llm_service, "call_structured_tool", interpret)
    return payload


def propose(client, headers):
    response = client.post("/coordinator/commands", headers=headers, json={"message": MESSAGE})
    assert response.status_code == 200, response.text
    return response.json()


def goal_count():
    with TestingSessionLocal() as db:
        return db.scalar(select(func.count()).select_from(WeeklyGoal))


def add_existing(*, title="UPDATE   AI COACH", user_id=1, status="active", start=date(2030, 7, 29)):
    with TestingSessionLocal() as db:
        if user_id != 1:
            db.add(User(id=user_id, email=f"user{user_id}@example.com", password_hash="unused", display_name="Other"))
            db.flush()
        db.add(WeeklyGoal(user_id=user_id, title=title, week_start=start,
                          week_end=start + timedelta(days=6), target_minutes=60, status=status))
        db.commit()


def test_batch_preview_then_planning_agent_creates_only_weekly_goals(client, user_headers, semantic_payload, monkeypatch):
    calls = []
    original = planning_service.create_weekly_priorities

    def tracked(db, user_id, plan):
        calls.append(plan)
        return original(db, user_id, plan)

    monkeypatch.setattr(planning_service, "create_weekly_priorities", tracked)
    command = propose(client, {**user_headers, "Idempotency-Key": "weekly-batch"})
    assert command["intent"] == "create_weekly_priorities"
    assert command["status"] == "pending_confirmation"
    assert command["requires_confirmation"] is True
    assert goal_count() == 0
    assert calls == []
    assert [i["target_minutes"] for i in command["parameters_json"]["weekly_priorities"]] == [600] * 3
    assert [i["priority"] for i in command["parameters_json"]["weekly_priorities"]] == ["high", "high", "medium"]
    assert "update podman project" in command["response_message"]
    assert "medium priority" in command["response_message"]
    assert command["parameters_json"]["week_end"] == "2030-08-04"
    repeated = propose(client, {**user_headers, "Idempotency-Key": "weekly-batch"})
    assert repeated["id"] == command["id"]

    response = client.post(f"/coordinator/commands/{command['id']}/confirm", headers=user_headers)
    assert response.status_code == 200, response.text
    confirmed = response.json()
    assert confirmed["status"] == "completed"
    assert confirmed["result_json"]["agent"] == "planning"
    assert len(confirmed["result_json"]["weekly_goal_ids"]) == 3
    assert len(calls) == 1
    with TestingSessionLocal() as db:
        goals = db.scalars(select(WeeklyGoal).order_by(WeeklyGoal.id)).all()
        assert [g.title for g in goals] == [i["title"] for i in PAYLOAD["weekly_priorities"]]
        assert [g.priority for g in goals] == ["high", "high", "medium"]
        assert all(g.target_minutes == 600 and g.status == "active" and g.due_at for g in goals)
        assert db.scalar(select(func.count()).select_from(DailyTask)) == 0
    assert len(client.get("/weekly-goals?date=2030-07-29", headers=user_headers).json()) == 3
    assert client.post(f"/coordinator/commands/{command['id']}/confirm", headers=user_headers).status_code == 200
    assert goal_count() == 3
    assert len(calls) == 1


def test_default_week_and_rejection_do_not_change_plan(client, user_headers, semantic_payload):
    semantic_payload.pop("week_start")
    with TestingSessionLocal() as db:
        today = coordinator_service._user_local_date(db, 1)
    command = propose(client, user_headers)
    assert command["parameters_json"]["week_start"] == (today - timedelta(days=today.weekday())).isoformat()
    response = client.post(f"/coordinator/commands/{command['id']}/reject", headers=user_headers)
    assert response.json()["status"] == "rejected"
    assert goal_count() == 0


@pytest.mark.parametrize("when", ["before_preview", "before_confirmation"])
def test_duplicate_in_same_week_blocks_entire_batch(client, user_headers, semantic_payload, when):
    if when == "before_preview":
        add_existing()
    command = propose(client, user_headers)
    if when == "before_confirmation":
        add_existing()
        command = client.post(f"/coordinator/commands/{command['id']}/confirm", headers=user_headers).json()
    assert command["status"] == "failed"
    assert command["requires_confirmation"] is False
    assert command["result_json"]["decision"]["code"] == "duplicate_weekly_priority"
    assert goal_count() == 1


def test_duplicate_inside_batch_blocks_without_silently_dropping_items(client, user_headers, semantic_payload):
    semantic_payload["weekly_priorities"][1]["title"] = " UPDATE   AI COACH "
    command = propose(client, user_headers)
    assert command["status"] == "failed"
    assert command["result_json"]["decision"]["conflicts"][0]["type"] == "duplicate_in_batch"
    assert goal_count() == 0


@pytest.mark.parametrize("existing", [{"user_id": 2}, {"status": "cancelled"}, {"start": date(2030, 8, 5)}])
def test_other_user_cancelled_and_other_week_priorities_do_not_conflict(client, user_headers, semantic_payload, existing):
    add_existing(**existing)
    command = propose(client, user_headers)
    assert command["status"] == "pending_confirmation"


def test_missing_required_facts_can_request_clarification(client, user_headers, semantic_payload):
    semantic_payload.clear()
    semantic_payload.update(intent="create_weekly_priorities", clarification_needed=True,
                            clarification_question="What are the priority titles and time estimates?")
    command = propose(client, user_headers)
    assert command["intent"] == "unknown"
    assert command["parameters_json"]["clarification_question"]
    assert goal_count() == 0


@pytest.mark.parametrize("items", [[], [{"title": "x", "target_minutes": -1}],
                                  [{"title": " ", "target_minutes": 60}],
                                  [{"title": "x", "target_minutes": "10h"}],
                                  [{"title": "x", "target_minutes": 60, "daily_task_id": 1}]])
def test_schema_rejects_invalid_weekly_batches(items):
    with pytest.raises(ValidationError):
        CommandInterpretation.model_validate({"intent": "create_weekly_priorities", "weekly_priorities": items})


def test_planning_batch_rolls_back_if_execution_fails(client, user_headers, semantic_payload, monkeypatch):
    command = propose(client, user_headers)
    original = planning_service.create_weekly_priorities

    def fail_after_flush(db, user_id, plan):
        original(db, user_id, plan)
        raise ValueError("Simulated failure after staging the batch")

    monkeypatch.setattr(planning_service, "create_weekly_priorities", fail_after_flush)
    response = client.post(f"/coordinator/commands/{command['id']}/confirm", headers=user_headers)
    assert response.status_code == 409
    assert goal_count() == 0
    with TestingSessionLocal() as db:
        assert db.get(AutomationCommand, command["id"]).status == "pending_confirmation"
