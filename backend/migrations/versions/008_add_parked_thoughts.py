"""Add persisted Park thoughts.

Revision ID: 008_add_parked_thoughts
Revises: 007_add_scheduler_notifications
Create Date: 2026-07-20
"""

from alembic import op
import sqlalchemy as sa


revision = "008_add_parked_thoughts"
down_revision = "007_add_scheduler_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parked_thoughts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_parked_thoughts_user_id"),
        "parked_thoughts",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_parked_thoughts_completed"),
        "parked_thoughts",
        ["completed"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_parked_thoughts_completed"), table_name="parked_thoughts")
    op.drop_index(op.f("ix_parked_thoughts_user_id"), table_name="parked_thoughts")
    op.drop_table("parked_thoughts")
