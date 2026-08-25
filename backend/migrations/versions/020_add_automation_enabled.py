"""Add a master automation and notifications switch.

Revision ID: 020_add_automation_enabled
Revises: 019_task_schedule_time
"""

from alembic import op
import sqlalchemy as sa


revision = "020_add_automation_enabled"
down_revision = "019_task_schedule_time"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "automation_preferences",
        sa.Column(
            "automation_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("automation_preferences", "automation_enabled")
