"""Add the email notification delivery system.

Revision ID: 004_add_email_notifications
Revises: 003_add_automation_preferences
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa


revision = "004_add_email_notifications"
down_revision = "003_add_automation_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE automation_preferences SET notification_channel = 'email' "
        "WHERE notification_channel <> 'email'"
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("notification_type", sa.String(length=40), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("recipient", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_notifications_attempt_count"),
        sa.CheckConstraint("channel = 'email'", name="ck_notifications_channel"),
        sa.CheckConstraint("max_attempts >= 1", name="ck_notifications_max_attempts"),
        sa.CheckConstraint(
            "status IN ('pending', 'sending', 'delivered', 'failed')",
            name="ck_notifications_status",
        ),
        sa.CheckConstraint(
            "notification_type IN ("
            "'morning_plan', 'upcoming_task', 'missed_task', 'deadline_warning', "
            "'evening_check_in', 'weekly_review', 'rescheduling_proposal')",
            name="ck_notifications_type",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notifications_notification_type"),
        "notifications",
        ["notification_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_scheduled_at"),
        "notifications",
        ["scheduled_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_status"),
        "notifications",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notifications_user_id"),
        "notifications",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_status"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_scheduled_at"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_notification_type"), table_name="notifications")
    op.drop_table("notifications")
