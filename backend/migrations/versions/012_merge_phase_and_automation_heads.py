"""Merge phase planning and automation migration heads.

Revision ID: 012_merge_phase_automation
Revises: 011_add_phases, 011_due_dates_proposals
Create Date: 2026-07-27
"""


revision = "012_merge_phase_automation"
down_revision = ("011_add_phases", "011_due_dates_proposals")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
