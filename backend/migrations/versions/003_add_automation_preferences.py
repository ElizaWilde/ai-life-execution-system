"""Add Phase 3 user automation preferences.

Revision ID: 003_add_automation_preferences
Revises: 002_add_phase2_coaching_models
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa


revision = "003_add_automation_preferences"
down_revision = "002_add_phase2_coaching_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(length=100), nullable=False),
        sa.Column("morning_reminder_time", sa.Time(), nullable=False),
        sa.Column("evening_review_time", sa.Time(), nullable=False),
        sa.Column("notification_channel", sa.String(length=20), nullable=False),
        sa.Column("automatic_rescheduling_enabled", sa.Boolean(), nullable=False),
        sa.Column("confirmation_required", sa.Boolean(), nullable=False),
        sa.Column("max_reminders_per_day", sa.Integer(), nullable=False),
        sa.Column("quiet_hours_start", sa.Time(), nullable=False),
        sa.Column("quiet_hours_end", sa.Time(), nullable=False),
        sa.Column("working_days_json", sa.JSON(), nullable=False),
        sa.Column("preferred_study_periods_json", sa.JSON(), nullable=False),
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
        sa.CheckConstraint(
            "notification_channel IN ('in_app', 'email', 'telegram')",
            name="ck_automation_preferences_notification_channel",
        ),
        sa.CheckConstraint(
            "max_reminders_per_day >= 0 AND max_reminders_per_day <= 20",
            name="ck_automation_preferences_max_reminders",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_automation_preferences_user_id"),
    )
    op.create_index(
        op.f("ix_automation_preferences_user_id"),
        "automation_preferences",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_automation_preferences_user_id"),
        table_name="automation_preferences",
    )
    op.drop_table("automation_preferences")
