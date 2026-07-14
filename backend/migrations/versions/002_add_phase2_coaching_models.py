"""Add Phase 2 check-in, coaching, and weekly review tables.

Revision ID: 002_add_phase2_coaching_models
Revises: 001_init_mvp_tables
Create Date: 2026-07-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "002_add_phase2_coaching_models"
down_revision = "001_init_mvp_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all Phase 2 persistence tables."""
    op.create_table(
        "daily_check_ins",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("check_in_date", sa.Date(), nullable=False),
        sa.Column("energy_level", sa.String(length=20), nullable=False),
        sa.Column("mood_level", sa.String(length=20), nullable=False),
        sa.Column("sleep_hours", sa.Float(), nullable=False),
        sa.Column("stress_level", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("cycle_day", sa.Integer(), nullable=True),
        sa.Column("cycle_notes", sa.Text(), nullable=True),
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
            "energy_level IN ('depleted', 'low', 'steady', 'high', 'energized')",
            name="ck_daily_check_ins_energy",
        ),
        sa.CheckConstraint(
            "mood_level IN ('struggling', 'low', 'neutral', 'good', 'great')",
            name="ck_daily_check_ins_mood",
        ),
        sa.CheckConstraint(
            "sleep_hours >= 0 AND sleep_hours <= 24",
            name="ck_daily_check_ins_sleep",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "check_in_date",
            name="uq_daily_check_ins_user_date",
        ),
    )
    op.create_index(
        op.f("ix_daily_check_ins_check_in_date"),
        "daily_check_ins",
        ["check_in_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_daily_check_ins_user_id"),
        "daily_check_ins",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "coaching_recommendations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_date", sa.Date(), nullable=False),
        sa.Column("readiness_score", sa.Float(), nullable=False),
        sa.Column("workload_multiplier", sa.Float(), nullable=False),
        sa.Column("workload_level", sa.String(length=20), nullable=False),
        sa.Column("adjustment_reasons_json", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("recommendations_json", sa.JSON(), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
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
            "readiness_score >= 0 AND readiness_score <= 100",
            name="ck_coaching_recommendations_readiness_score",
        ),
        sa.CheckConstraint(
            "workload_multiplier >= 0",
            name="ck_coaching_recommendations_workload_multiplier",
        ),
        sa.CheckConstraint(
            "workload_level IN ('light', 'reduced', 'normal')",
            name="ck_coaching_recommendations_workload_level",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "recommendation_date",
            name="uq_coaching_recommendations_user_date",
        ),
    )
    op.create_index(
        op.f("ix_coaching_recommendations_recommendation_date"),
        "coaching_recommendations",
        ["recommendation_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_coaching_recommendations_user_id"),
        "coaching_recommendations",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "weekly_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("planned_tasks", sa.Integer(), nullable=False),
        sa.Column("completed_tasks", sa.Integer(), nullable=False),
        sa.Column("completion_rate", sa.Float(), nullable=False),
        sa.Column("focus_minutes", sa.Integer(), nullable=False),
        sa.Column("check_in_days", sa.Integer(), nullable=False),
        sa.Column("average_sleep_hours", sa.Float(), nullable=True),
        sa.Column("energy_distribution_json", sa.JSON(), nullable=False),
        sa.Column("mood_distribution_json", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("achievements_json", sa.JSON(), nullable=False),
        sa.Column("obstacles_json", sa.JSON(), nullable=False),
        sa.Column("next_week_actions_json", sa.JSON(), nullable=False),
        sa.Column("context_json", sa.JSON(), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
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
            "week_end >= week_start",
            name="ck_weekly_reviews_date_range",
        ),
        sa.CheckConstraint(
            "planned_tasks >= 0 AND completed_tasks >= 0 "
            "AND focus_minutes >= 0 AND check_in_days >= 0",
            name="ck_weekly_reviews_nonnegative_stats",
        ),
        sa.CheckConstraint(
            "completion_rate >= 0 AND completion_rate <= 1",
            name="ck_weekly_reviews_completion_rate",
        ),
        sa.CheckConstraint(
            "average_sleep_hours IS NULL OR "
            "(average_sleep_hours >= 0 AND average_sleep_hours <= 24)",
            name="ck_weekly_reviews_average_sleep",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "week_start",
            name="uq_weekly_reviews_user_week_start",
        ),
    )
    op.create_index(
        op.f("ix_weekly_reviews_user_id"),
        "weekly_reviews",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_weekly_reviews_week_start"),
        "weekly_reviews",
        ["week_start"],
        unique=False,
    )


def downgrade() -> None:
    """Drop Phase 2 tables in reverse dependency order."""
    op.drop_index(op.f("ix_weekly_reviews_week_start"), table_name="weekly_reviews")
    op.drop_index(op.f("ix_weekly_reviews_user_id"), table_name="weekly_reviews")
    op.drop_table("weekly_reviews")

    op.drop_index(
        op.f("ix_coaching_recommendations_user_id"),
        table_name="coaching_recommendations",
    )
    op.drop_index(
        op.f("ix_coaching_recommendations_recommendation_date"),
        table_name="coaching_recommendations",
    )
    op.drop_table("coaching_recommendations")

    op.drop_index(
        op.f("ix_daily_check_ins_user_id"),
        table_name="daily_check_ins",
    )
    op.drop_index(
        op.f("ix_daily_check_ins_check_in_date"),
        table_name="daily_check_ins",
    )
    op.drop_table("daily_check_ins")
