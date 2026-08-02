"""Add floating coach roaming preferences.

Revision ID: 017_add_coach_roaming_preferences
Revises: 016_session_seconds
"""

from alembic import op
import sqlalchemy as sa


revision = "017_add_coach_roaming_preferences"
down_revision = "016_session_seconds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_app_settings",
        sa.Column("coach_roaming_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "user_app_settings",
        sa.Column("coach_move_interval_seconds", sa.Integer(), nullable=False, server_default="30"),
    )
    op.create_check_constraint(
        "ck_user_app_settings_coach_move_interval",
        "user_app_settings",
        "coach_move_interval_seconds IN (15, 30, 60, 120)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_user_app_settings_coach_move_interval",
        "user_app_settings",
        type_="check",
    )
    op.drop_column("user_app_settings", "coach_move_interval_seconds")
    op.drop_column("user_app_settings", "coach_roaming_enabled")
