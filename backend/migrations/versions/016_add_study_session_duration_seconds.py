"""Store exact active duration for interrupted and short focus sessions.

Revision ID: 016_session_seconds
Revises: 015_task_channels
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa


revision = "016_session_seconds"
down_revision = "015_task_channels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("study_sessions", sa.Column("duration_seconds", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE study_sessions SET duration_seconds = duration_minutes * 60 "
        "WHERE duration_minutes IS NOT NULL"
    )
    op.create_check_constraint(
        "ck_study_sessions_duration_seconds",
        "study_sessions",
        "duration_seconds IS NULL OR duration_seconds >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_study_sessions_duration_seconds", "study_sessions", type_="check")
    op.drop_column("study_sessions", "duration_seconds")
