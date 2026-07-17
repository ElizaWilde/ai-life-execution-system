"""Add scheduler notification types and deduplication.

Revision ID: 007_add_scheduler_notifications
Revises: 006_add_telegram_notifications
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa


revision = "007_add_scheduler_notifications"
down_revision = "006_add_telegram_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("deduplication_key", sa.String(length=180), nullable=True),
    )
    op.create_index(
        op.f("ix_notifications_deduplication_key"),
        "notifications",
        ["deduplication_key"],
        unique=True,
    )
    op.drop_constraint(
        "ck_notifications_type",
        "notifications",
        type_="check",
    )
    op.create_check_constraint(
        "ck_notifications_type",
        "notifications",
        "notification_type IN ("
        "'morning_plan', 'upcoming_task', 'missed_task', 'deadline_warning', "
        "'evening_check_in', 'weekly_review', 'rescheduling_proposal', "
        "'procrastination_alert', 'completion_forecast')",
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM notifications WHERE notification_type IN "
        "('procrastination_alert', 'completion_forecast')"
    )
    op.drop_constraint(
        "ck_notifications_type",
        "notifications",
        type_="check",
    )
    op.create_check_constraint(
        "ck_notifications_type",
        "notifications",
        "notification_type IN ("
        "'morning_plan', 'upcoming_task', 'missed_task', 'deadline_warning', "
        "'evening_check_in', 'weekly_review', 'rescheduling_proposal')",
    )
    op.drop_index(
        op.f("ix_notifications_deduplication_key"),
        table_name="notifications",
    )
    op.drop_column("notifications", "deduplication_key")
