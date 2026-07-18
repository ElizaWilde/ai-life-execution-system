"""Add planning preferences to daily check-ins.

Revision ID: 009_add_check_in_preferences
Revises: 008_add_focus_cycle_count
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa


revision = "009_add_check_in_preferences"
down_revision = "008_add_focus_cycle_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("daily_check_ins", sa.Column("available_minutes", sa.Integer(), nullable=True))
    op.add_column("daily_check_ins", sa.Column("focus_mode", sa.String(length=20), nullable=True))
    op.create_check_constraint(
        "ck_daily_check_ins_available_minutes",
        "daily_check_ins",
        "available_minutes IS NULL OR (available_minutes >= 0 AND available_minutes <= 1440)",
    )
    op.create_check_constraint(
        "ck_daily_check_ins_focus_mode",
        "daily_check_ins",
        "focus_mode IS NULL OR focus_mode IN ('Deep work', 'Meetings', 'Study', 'Recovery')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_daily_check_ins_focus_mode", "daily_check_ins", type_="check")
    op.drop_constraint("ck_daily_check_ins_available_minutes", "daily_check_ins", type_="check")
    op.drop_column("daily_check_ins", "focus_mode")
    op.drop_column("daily_check_ins", "available_minutes")
