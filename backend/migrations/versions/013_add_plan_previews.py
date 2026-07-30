"""Add persisted daily and weekly plan previews.

Revision ID: 013_plan_previews
Revises: 012_merge_phase_automation
Create Date: 2026-07-30
"""

from alembic import op
import sqlalchemy as sa


revision = "013_plan_previews"
down_revision = "012_merge_phase_automation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plan_previews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("preview_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("input_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recommended_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("calibration_factor", sa.Float(), nullable=False, server_default="1"),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "preview_type IN ('daily', 'weekly')",
            name="ck_plan_previews_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'expired')",
            name="ck_plan_previews_status",
        ),
        sa.CheckConstraint(
            "input_minutes >= 0 AND recommended_minutes >= 0",
            name="ck_plan_previews_minutes",
        ),
        sa.CheckConstraint(
            "calibration_factor > 0",
            name="ck_plan_previews_calibration_factor",
        ),
    )
    op.create_index("ix_plan_previews_user_id", "plan_previews", ["user_id"])
    op.create_index("ix_plan_previews_preview_type", "plan_previews", ["preview_type"])
    op.create_index("ix_plan_previews_status", "plan_previews", ["status"])
    op.create_index("ix_plan_previews_target_date", "plan_previews", ["target_date"])
    op.create_index("ix_plan_previews_expires_at", "plan_previews", ["expires_at"])


def downgrade() -> None:
    op.drop_table("plan_previews")
