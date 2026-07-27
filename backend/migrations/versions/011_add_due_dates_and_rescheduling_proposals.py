"""Add task due dates and persistent rescheduling proposals.

Revision ID: 011_due_dates_proposals
Revises: 010_merge_park_check_in
Create Date: 2026-07-27
"""

from alembic import op
import sqlalchemy as sa


revision = "011_due_dates_proposals"
down_revision = "010_merge_park_check_in"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "daily_tasks",
        sa.Column(
            "planning_scope",
            sa.String(length=20),
            server_default="daily",
            nullable=False,
        ),
    )
    op.add_column(
        "daily_tasks",
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE daily_tasks AS task
        SET due_at = (
            (task.task_date + 1)::timestamp
            AT TIME ZONE COALESCE(
                (
                    SELECT preference.timezone
                    FROM automation_preferences AS preference
                    WHERE preference.user_id = task.user_id
                ),
                'Asia/Singapore'
            )
        )
        """
    )
    op.alter_column("daily_tasks", "due_at", nullable=False)
    op.create_check_constraint(
        "ck_daily_tasks_planning_scope",
        "daily_tasks",
        "planning_scope IN ('daily', 'weekly')",
    )
    op.create_index(
        op.f("ix_daily_tasks_planning_scope"),
        "daily_tasks",
        ["planning_scope"],
        unique=False,
    )
    op.create_index(
        op.f("ix_daily_tasks_due_at"),
        "daily_tasks",
        ["due_at"],
        unique=False,
    )
    op.add_column(
        "weekly_goals",
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE weekly_goals AS goal
        SET due_at = (
            (goal.week_end + 1)::timestamp
            AT TIME ZONE COALESCE(
                (
                    SELECT preference.timezone
                    FROM automation_preferences AS preference
                    WHERE preference.user_id = goal.user_id
                ),
                'Asia/Singapore'
            )
        )
        """
    )
    op.alter_column("weekly_goals", "due_at", nullable=False)
    op.create_index(
        op.f("ix_weekly_goals_due_at"),
        "weekly_goals",
        ["due_at"],
        unique=False,
    )

    op.create_table(
        "rescheduling_proposals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("proposal_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("expected_minutes", sa.Integer(), nullable=False),
        sa.Column("deduplication_key", sa.String(length=180), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('pending', 'approved', 'rejected', 'applied', 'expired')",
            name="ck_rescheduling_proposals_status",
        ),
        sa.CheckConstraint(
            "proposal_type IN ('rollover', 'reschedule')",
            name="ck_rescheduling_proposals_type",
        ),
        sa.CheckConstraint(
            "expected_minutes >= 0",
            name="ck_rescheduling_proposals_expected_minutes",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deduplication_key"),
    )
    op.create_index(
        op.f("ix_rescheduling_proposals_user_id"),
        "rescheduling_proposals",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rescheduling_proposals_status"),
        "rescheduling_proposals",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rescheduling_proposals_deduplication_key"),
        "rescheduling_proposals",
        ["deduplication_key"],
        unique=True,
    )
    op.create_index(
        op.f("ix_rescheduling_proposals_expires_at"),
        "rescheduling_proposals",
        ["expires_at"],
        unique=False,
    )

    op.create_table(
        "rescheduling_proposal_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("proposal_id", sa.Integer(), nullable=False),
        sa.Column("daily_task_id", sa.Integer(), nullable=False),
        sa.Column("original_date", sa.Date(), nullable=False),
        sa.Column("proposed_date", sa.Date(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "estimated_minutes >= 0",
            name="ck_rescheduling_proposal_items_minutes",
        ),
        sa.ForeignKeyConstraint(
            ["daily_task_id"],
            ["daily_tasks.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["rescheduling_proposals.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "proposal_id",
            "daily_task_id",
            name="uq_rescheduling_proposal_task",
        ),
    )
    op.create_index(
        op.f("ix_rescheduling_proposal_items_proposal_id"),
        "rescheduling_proposal_items",
        ["proposal_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rescheduling_proposal_items_daily_task_id"),
        "rescheduling_proposal_items",
        ["daily_task_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_rescheduling_proposal_items_daily_task_id"),
        table_name="rescheduling_proposal_items",
    )
    op.drop_index(
        op.f("ix_rescheduling_proposal_items_proposal_id"),
        table_name="rescheduling_proposal_items",
    )
    op.drop_table("rescheduling_proposal_items")
    op.drop_index(
        op.f("ix_rescheduling_proposals_expires_at"),
        table_name="rescheduling_proposals",
    )
    op.drop_index(
        op.f("ix_rescheduling_proposals_deduplication_key"),
        table_name="rescheduling_proposals",
    )
    op.drop_index(
        op.f("ix_rescheduling_proposals_status"),
        table_name="rescheduling_proposals",
    )
    op.drop_index(
        op.f("ix_rescheduling_proposals_user_id"),
        table_name="rescheduling_proposals",
    )
    op.drop_table("rescheduling_proposals")
    op.drop_index(op.f("ix_weekly_goals_due_at"), table_name="weekly_goals")
    op.drop_column("weekly_goals", "due_at")
    op.drop_index(op.f("ix_daily_tasks_due_at"), table_name="daily_tasks")
    op.drop_index(op.f("ix_daily_tasks_planning_scope"), table_name="daily_tasks")
    op.drop_constraint(
        "ck_daily_tasks_planning_scope",
        "daily_tasks",
        type_="check",
    )
    op.drop_column("daily_tasks", "due_at")
    op.drop_column("daily_tasks", "planning_scope")
