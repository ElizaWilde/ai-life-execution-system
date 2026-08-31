"""Persist configurable weekly-plan start-hour choices."""

from alembic import op
import sqlalchemy as sa

revision = "021_add_working_hours"
down_revision = "020_add_automation_enabled"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("automation_preferences", sa.Column("working_start_hour", sa.Integer(), nullable=False, server_default="7"))
    op.add_column("automation_preferences", sa.Column("working_end_hour", sa.Integer(), nullable=False, server_default="22"))


def downgrade() -> None:
    op.drop_column("automation_preferences", "working_end_hour")
    op.drop_column("automation_preferences", "working_start_hour")
