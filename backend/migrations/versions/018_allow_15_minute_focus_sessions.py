"""Allow 15-minute default focus sessions.

Revision ID: 018_allow_15_minute_focus
Revises: 017_add_coach_roaming_preferences
"""

from alembic import op


revision = "018_allow_15_minute_focus"
down_revision = "017_add_coach_roaming_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_user_app_settings_focus_minutes",
        "user_app_settings",
        type_="check",
    )
    op.create_check_constraint(
        "ck_user_app_settings_focus_minutes",
        "user_app_settings",
        "focus_minutes IN (15, 25, 45, 60)",
    )


def downgrade() -> None:
    op.execute("UPDATE user_app_settings SET focus_minutes = 25 WHERE focus_minutes = 15")
    op.drop_constraint(
        "ck_user_app_settings_focus_minutes",
        "user_app_settings",
        type_="check",
    )
    op.create_check_constraint(
        "ck_user_app_settings_focus_minutes",
        "user_app_settings",
        "focus_minutes IN (25, 45, 60)",
    )
