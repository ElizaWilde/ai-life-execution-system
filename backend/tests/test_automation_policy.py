import pytest

from app.services.automation_policy_service import (
    AUTOMATION_RULES,
    AutomationAction,
    AutomationLevel,
    automation_policy_service,
)


SAFE_ACTIONS = {
    AutomationAction.SEND_REMINDER,
    AutomationAction.GENERATE_FORECAST,
    AutomationAction.DETECT_OVERDUE_TASKS,
    AutomationAction.SUGGEST_SCHEDULE_CHANGES,
}

CONFIRMATION_ACTIONS = {
    AutomationAction.MOVE_TASK_TO_ANOTHER_DAY,
    AutomationAction.CHANGE_TASK_DURATION,
    AutomationAction.REDUCE_WEEKLY_GOAL,
    AutomationAction.UPDATE_NOTION_TASKS,
}

NEVER_SILENT_ACTIONS = {
    AutomationAction.DELETE_TASKS,
    AutomationAction.CANCEL_GOALS,
    AutomationAction.MODIFY_IMPORTANT_DEADLINES,
    AutomationAction.REPLACE_USER_CREATED_PLANS,
}


def test_every_known_action_has_exactly_one_rule():
    assert set(AUTOMATION_RULES) == set(AutomationAction)
    assert len(AUTOMATION_RULES) == len(AutomationAction)


@pytest.mark.parametrize("action", SAFE_ACTIONS)
def test_safe_actions_can_run_automatically(action):
    decision = automation_policy_service.evaluate(action)

    assert decision.level is AutomationLevel.SAFE_AUTOMATIC
    assert decision.allowed is True
    assert decision.requires_confirmation is False
    assert decision.requires_explicit_user_request is False


@pytest.mark.parametrize("action", CONFIRMATION_ACTIONS)
def test_confirmation_actions_are_blocked_until_confirmed(action):
    blocked = automation_policy_service.evaluate(action)
    allowed = automation_policy_service.evaluate(action, confirmed=True)

    assert blocked.level is AutomationLevel.REQUIRES_CONFIRMATION
    assert blocked.allowed is False
    assert blocked.requires_confirmation is True
    assert allowed.allowed is True


@pytest.mark.parametrize("action", NEVER_SILENT_ACTIONS)
def test_never_silent_actions_require_request_and_confirmation(action):
    silent = automation_policy_service.evaluate(action, confirmed=True)
    unconfirmed = automation_policy_service.evaluate(
        action,
        explicitly_requested_by_user=True,
    )
    allowed = automation_policy_service.evaluate(
        action,
        explicitly_requested_by_user=True,
        confirmed=True,
    )

    assert silent.level is AutomationLevel.NEVER_SILENT
    assert silent.allowed is False
    assert silent.requires_explicit_user_request is True
    assert unconfirmed.allowed is False
    assert unconfirmed.requires_confirmation is True
    assert allowed.allowed is True


def test_replacing_a_user_plan_is_never_a_safe_automatic_action():
    rule = automation_policy_service.get_rule(
        AutomationAction.REPLACE_USER_CREATED_PLANS
    )

    assert rule.level is AutomationLevel.NEVER_SILENT
    assert rule.requires_confirmation is True
    assert rule.requires_explicit_user_request is True
