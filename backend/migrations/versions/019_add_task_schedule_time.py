"""Add a schedulable start time to daily tasks.

Revision ID: 019_task_schedule_time
Revises: 018_allow_15_minute_focus
"""

from alembic import op
import sqlalchemy as sa


revision = "019_task_schedule_time"
down_revision = "018_allow_15_minute_focus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "daily_tasks",
        sa.Column("scheduled_start_minutes", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_daily_tasks_scheduled_start_minutes",
        "daily_tasks",
        "scheduled_start_minutes IS NULL OR (scheduled_start_minutes >= 0 AND scheduled_start_minutes <= 1439)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_daily_tasks_scheduled_start_minutes",
        "daily_tasks",
        type_="check",
    )
    op.drop_column("daily_tasks", "scheduled_start_minutes")
