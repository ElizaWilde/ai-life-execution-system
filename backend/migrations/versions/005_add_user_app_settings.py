"""Add persisted frontend application settings.

Revision ID: 005_add_user_app_settings
Revises: 004_add_email_notifications
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa


revision = "005_add_user_app_settings"
down_revision = "004_add_email_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_app_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("week_start", sa.String(length=10), nullable=False),
        sa.Column("focus_minutes", sa.Integer(), nullable=False),
        sa.Column("short_break_minutes", sa.Integer(), nullable=False),
        sa.Column("long_break_minutes", sa.Integer(), nullable=False),
        sa.Column("workload", sa.String(length=10), nullable=False),
        sa.Column("theme", sa.String(length=10), nullable=False),
        sa.Column("tone", sa.String(length=20), nullable=False),
        sa.Column("strictness", sa.String(length=20), nullable=False),
        sa.Column("adjustment", sa.String(length=20), nullable=False),
        sa.Column("proactive", sa.Boolean(), nullable=False),
        sa.Column("focus_matters", sa.Boolean(), nullable=False),
        sa.Column("protect_deep_work", sa.Boolean(), nullable=False),
        sa.Column("learn_from_feedback", sa.Boolean(), nullable=False),
        sa.Column("integrations_json", sa.JSON(), nullable=False),
        sa.Column("avatar_data_url", sa.Text(), nullable=True),
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
        sa.CheckConstraint("week_start IN ('Monday', 'Sunday')", name="ck_user_app_settings_week_start"),
        sa.CheckConstraint("focus_minutes IN (25, 45, 60)", name="ck_user_app_settings_focus_minutes"),
        sa.CheckConstraint("short_break_minutes IN (5, 10)", name="ck_user_app_settings_short_break"),
        sa.CheckConstraint("long_break_minutes IN (15, 30)", name="ck_user_app_settings_long_break"),
        sa.CheckConstraint("workload IN ('light', 'medium', 'high')", name="ck_user_app_settings_workload"),
        sa.CheckConstraint("theme IN ('light', 'dark', 'auto')", name="ck_user_app_settings_theme"),
        sa.CheckConstraint("tone IN ('supportive', 'direct', 'reflective')", name="ck_user_app_settings_tone"),
        sa.CheckConstraint("strictness IN ('flexible', 'balanced', 'strict')", name="ck_user_app_settings_strictness"),
        sa.CheckConstraint("adjustment IN ('gentle', 'moderate', 'strong')", name="ck_user_app_settings_adjustment"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_app_settings_user_id"),
    )
    op.create_index(
        op.f("ix_user_app_settings_user_id"),
        "user_app_settings",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_app_settings_user_id"), table_name="user_app_settings")
    op.drop_table("user_app_settings")
