"""Create MVP tables.

Revision ID: 001_init_mvp_tables
Revises:
Create Date: 2026-07-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "001_init_mvp_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "weekly_goals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("target_minutes", sa.Integer(), nullable=True),
        sa.Column("notion_page_id", sa.String(length=100), nullable=True),
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
            "target_minutes IS NULL OR target_minutes >= 0",
            name="ck_weekly_goals_target_minutes",
        ),
        sa.CheckConstraint("week_end >= week_start", name="ck_weekly_goals_date_range"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("notion_page_id"),
    )
    op.create_index(
        op.f("ix_weekly_goals_status"), "weekly_goals", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_weekly_goals_user_id"), "weekly_goals", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_weekly_goals_week_start"),
        "weekly_goals",
        ["week_start"],
        unique=False,
    )

    op.create_table(
        "daily_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("weekly_goal_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_date", sa.Date(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("raw_model_output", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            "estimated_minutes IS NULL OR estimated_minutes >= 0",
            name="ck_daily_tasks_estimated_minutes",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["weekly_goal_id"], ["weekly_goals.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_daily_tasks_status"), "daily_tasks", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_daily_tasks_task_date"), "daily_tasks", ["task_date"], unique=False
    )
    op.create_index(
        op.f("ix_daily_tasks_user_id"), "daily_tasks", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_daily_tasks_weekly_goal_id"),
        "daily_tasks",
        ["weekly_goal_id"],
        unique=False,
    )

    op.create_table(
        "study_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("daily_task_id", sa.Integer(), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes >= 0",
            name="ck_study_sessions_duration_minutes",
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ck_study_sessions_time_range",
        ),
        sa.ForeignKeyConstraint(
            ["daily_task_id"], ["daily_tasks.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_study_sessions_daily_task_id"),
        "study_sessions",
        ["daily_task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_study_sessions_started_at"),
        "study_sessions",
        ["started_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_study_sessions_status"),
        "study_sessions",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_study_sessions_user_id"),
        "study_sessions",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "daily_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("review_date", sa.Date(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("tomorrow_adjustment", sa.Text(), nullable=True),
        sa.Column("planned_tasks", sa.Integer(), nullable=False),
        sa.Column("completed_tasks", sa.Integer(), nullable=False),
        sa.Column("focus_minutes", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
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
            "planned_tasks >= 0 AND completed_tasks >= 0 AND focus_minutes >= 0",
            name="ck_daily_reviews_nonnegative_stats",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "review_date", name="uq_daily_reviews_user_date"),
    )
    op.create_index(
        op.f("ix_daily_reviews_review_date"),
        "daily_reviews",
        ["review_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_daily_reviews_user_id"), "daily_reviews", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_daily_reviews_user_id"), table_name="daily_reviews")
    op.drop_index(op.f("ix_daily_reviews_review_date"), table_name="daily_reviews")
    op.drop_table("daily_reviews")

    op.drop_index(op.f("ix_study_sessions_user_id"), table_name="study_sessions")
    op.drop_index(op.f("ix_study_sessions_status"), table_name="study_sessions")
    op.drop_index(op.f("ix_study_sessions_started_at"), table_name="study_sessions")
    op.drop_index(op.f("ix_study_sessions_daily_task_id"), table_name="study_sessions")
    op.drop_table("study_sessions")

    op.drop_index(op.f("ix_daily_tasks_weekly_goal_id"), table_name="daily_tasks")
    op.drop_index(op.f("ix_daily_tasks_user_id"), table_name="daily_tasks")
    op.drop_index(op.f("ix_daily_tasks_task_date"), table_name="daily_tasks")
    op.drop_index(op.f("ix_daily_tasks_status"), table_name="daily_tasks")
    op.drop_table("daily_tasks")

    op.drop_index(op.f("ix_weekly_goals_week_start"), table_name="weekly_goals")
    op.drop_index(op.f("ix_weekly_goals_user_id"), table_name="weekly_goals")
    op.drop_index(op.f("ix_weekly_goals_status"), table_name="weekly_goals")
    op.drop_table("weekly_goals")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
