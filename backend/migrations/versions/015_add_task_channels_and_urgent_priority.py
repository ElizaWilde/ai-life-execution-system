"""Add task channels and support urgent daily priorities.

Revision ID: 015_task_channels
Revises: 014_intelligence_commands
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa


revision = "015_task_channels"
down_revision = "014_intelligence_commands"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("daily_tasks", sa.Column("channel", sa.String(length=40), nullable=True))
    op.create_index("ix_daily_tasks_channel", "daily_tasks", ["channel"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_daily_tasks_channel", table_name="daily_tasks")
    op.drop_column("daily_tasks", "channel")
