"""Add phases and milestones.

Revision ID: 011_add_phases
Revises: 010_merge_park_check_in
Create Date: 2026-07-23
"""

from alembic import op
import sqlalchemy as sa


revision = "011_add_phases"
down_revision = "010_merge_park_check_in"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "phases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("estimated_focus_minutes", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("end_date >= start_date", name="ck_phases_date_range"),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name="ck_phases_progress"),
        sa.CheckConstraint("estimated_focus_minutes >= 0", name="ck_phases_estimated_focus_minutes"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_phases_user_id"), "phases", ["user_id"], unique=False)
    op.create_index(op.f("ix_phases_start_date"), "phases", ["start_date"], unique=False)
    op.create_index(op.f("ix_phases_end_date"), "phases", ["end_date"], unique=False)
    op.create_index(op.f("ix_phases_status"), "phases", ["status"], unique=False)

    op.create_table(
        "milestones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("phase_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name="ck_milestones_progress"),
        sa.CheckConstraint("position >= 0", name="ck_milestones_position"),
        sa.ForeignKeyConstraint(["phase_id"], ["phases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_milestones_phase_id"), "milestones", ["phase_id"], unique=False)
    op.create_index(op.f("ix_milestones_due_date"), "milestones", ["due_date"], unique=False)
    op.create_index(op.f("ix_milestones_status"), "milestones", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_milestones_status"), table_name="milestones")
    op.drop_index(op.f("ix_milestones_due_date"), table_name="milestones")
    op.drop_index(op.f("ix_milestones_phase_id"), table_name="milestones")
    op.drop_table("milestones")
    op.drop_index(op.f("ix_phases_status"), table_name="phases")
    op.drop_index(op.f("ix_phases_end_date"), table_name="phases")
    op.drop_index(op.f("ix_phases_start_date"), table_name="phases")
    op.drop_index(op.f("ix_phases_user_id"), table_name="phases")
    op.drop_table("phases")
