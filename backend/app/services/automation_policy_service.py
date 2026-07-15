from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AutomationAction(str, Enum):
    """Every action that Phase 3 automation may propose or execute."""

    SEND_REMINDER = "send_reminder"
    GENERATE_FORECAST = "generate_forecast"
    DETECT_OVERDUE_TASKS = "detect_overdue_tasks"
    SUGGEST_SCHEDULE_CHANGES = "suggest_schedule_changes"

    MOVE_TASK_TO_ANOTHER_DAY = "move_task_to_another_day"
    CHANGE_TASK_DURATION = "change_task_duration"
    REDUCE_WEEKLY_GOAL = "reduce_weekly_goal"
    UPDATE_NOTION_TASKS = "update_notion_tasks"

    DELETE_TASKS = "delete_tasks"
    CANCEL_GOALS = "cancel_goals"
    MODIFY_IMPORTANT_DEADLINES = "modify_important_deadlines"
    REPLACE_USER_CREATED_PLANS = "replace_user_created_plans"


class AutomationLevel(str, Enum):
    SAFE_AUTOMATIC = "safe_automatic"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    NEVER_SILENT = "never_silent"

'''
    @dataclass automatically creates methods such as __init__, __repr__, and __eq__
        __init__ runs when you create an object.
        __repr__ controls how the object is displayed.
        __eq__ controls how two objects are compared using ==.
    frozen=True makes instances immutable. After creating the object, its attributes cannot be changed.
'''
@dataclass(frozen=True)
class AutomationRule:
    action: AutomationAction
    level: AutomationLevel
    description: str

    # @property lets you access a method like an attribute. Without @property:rule.requires_confirmation(), but With @property:rule.requires_confirmation
    @property
    def requires_confirmation(self) -> bool:
        return self.level is not AutomationLevel.SAFE_AUTOMATIC

    @property
    def requires_explicit_user_request(self) -> bool:
        return self.level is AutomationLevel.NEVER_SILENT


@dataclass(frozen=True)
class AutomationDecision:
    action: AutomationAction
    level: AutomationLevel
    allowed: bool
    requires_confirmation: bool
    requires_explicit_user_request: bool
    reason: str


AUTOMATION_RULES: dict[AutomationAction, AutomationRule] = {
    AutomationAction.SEND_REMINDER: AutomationRule(
        AutomationAction.SEND_REMINDER,
        AutomationLevel.SAFE_AUTOMATIC,
        "Send a reminder without changing the user's plan.",
    ),
    AutomationAction.GENERATE_FORECAST: AutomationRule(
        AutomationAction.GENERATE_FORECAST,
        AutomationLevel.SAFE_AUTOMATIC,
        "Generate a read-only completion forecast.",
    ),
    AutomationAction.DETECT_OVERDUE_TASKS: AutomationRule(
        AutomationAction.DETECT_OVERDUE_TASKS,
        AutomationLevel.SAFE_AUTOMATIC,
        "Detect overdue tasks without modifying them.",
    ),
    AutomationAction.SUGGEST_SCHEDULE_CHANGES: AutomationRule(
        AutomationAction.SUGGEST_SCHEDULE_CHANGES,
        AutomationLevel.SAFE_AUTOMATIC,
        "Suggest schedule changes without applying them.",
    ),
    AutomationAction.MOVE_TASK_TO_ANOTHER_DAY: AutomationRule(
        AutomationAction.MOVE_TASK_TO_ANOTHER_DAY,
        AutomationLevel.REQUIRES_CONFIRMATION,
        "Move a task only after the user confirms the proposed date.",
    ),
    AutomationAction.CHANGE_TASK_DURATION: AutomationRule(
        AutomationAction.CHANGE_TASK_DURATION,
        AutomationLevel.REQUIRES_CONFIRMATION,
        "Change a task duration only after user confirmation.",
    ),
    AutomationAction.REDUCE_WEEKLY_GOAL: AutomationRule(
        AutomationAction.REDUCE_WEEKLY_GOAL,
        AutomationLevel.REQUIRES_CONFIRMATION,
        "Reduce a weekly goal only after user confirmation.",
    ),
    AutomationAction.UPDATE_NOTION_TASKS: AutomationRule(
        AutomationAction.UPDATE_NOTION_TASKS,
        AutomationLevel.REQUIRES_CONFIRMATION,
        "Update Notion tasks only after user confirmation.",
    ),
    AutomationAction.DELETE_TASKS: AutomationRule(
        AutomationAction.DELETE_TASKS,
        AutomationLevel.NEVER_SILENT,
        "Delete tasks only when explicitly requested and confirmed by the user.",
    ),
    AutomationAction.CANCEL_GOALS: AutomationRule(
        AutomationAction.CANCEL_GOALS,
        AutomationLevel.NEVER_SILENT,
        "Cancel goals only when explicitly requested and confirmed by the user.",
    ),
    AutomationAction.MODIFY_IMPORTANT_DEADLINES: AutomationRule(
        AutomationAction.MODIFY_IMPORTANT_DEADLINES,
        AutomationLevel.NEVER_SILENT,
        "Modify important deadlines only when explicitly requested and confirmed.",
    ),
    AutomationAction.REPLACE_USER_CREATED_PLANS: AutomationRule(
        AutomationAction.REPLACE_USER_CREATED_PLANS,
        AutomationLevel.NEVER_SILENT,
        "Replace a user-created plan only when explicitly requested and confirmed.",
    ),
}


class AutomationPolicyService:
    """Apply the same permission rules to schedulers, APIs, and commands."""

    def get_rule(self, action: AutomationAction) -> AutomationRule:
        return AUTOMATION_RULES[action]

    def evaluate(
        self,
        action: AutomationAction,
        *,
        confirmed: bool = False,
        explicitly_requested_by_user: bool = False,
    ) -> AutomationDecision:
        rule = self.get_rule(action)

        if rule.requires_explicit_user_request and not explicitly_requested_by_user:
            return AutomationDecision(
                action=action,
                level=rule.level,
                allowed=False,
                requires_confirmation=True,
                requires_explicit_user_request=True,
                reason="This action must be explicitly requested by the user.",
            )

        if rule.requires_confirmation and not confirmed:
            return AutomationDecision(
                action=action,
                level=rule.level,
                allowed=False,
                requires_confirmation=True,
                requires_explicit_user_request=rule.requires_explicit_user_request,
                reason="User confirmation is required before this action can run.",
            )

        return AutomationDecision(
            action=action,
            level=rule.level,
            allowed=True,
            requires_confirmation=rule.requires_confirmation,
            requires_explicit_user_request=rule.requires_explicit_user_request,
            reason="The automation policy allows this action.",
        )


automation_policy_service = AutomationPolicyService()
