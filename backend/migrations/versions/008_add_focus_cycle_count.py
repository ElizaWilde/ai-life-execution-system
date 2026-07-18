"""Add the focus-session cycle count preference.

Revision ID: 008_add_focus_cycle_count
Revises: 007_add_scheduler_notifications
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa


revision = "008_add_focus_cycle_count"
down_revision = "007_add_scheduler_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_app_settings",
        sa.Column("cycle_count", sa.Integer(), nullable=False, server_default="4"),
    )
    op.create_check_constraint(
        "ck_user_app_settings_cycle_count",
        "user_app_settings",
        "cycle_count BETWEEN 1 AND 12",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_user_app_settings_cycle_count",
        "user_app_settings",
        type_="check",
    )
    op.drop_column("user_app_settings", "cycle_count")
