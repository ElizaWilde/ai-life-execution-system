"""Merge Park and check-in preference migration branches.

Revision ID: 010_merge_park_check_in
Revises: 008_add_parked_thoughts, 009_add_check_in_preferences
Create Date: 2026-07-20
"""


revision = "010_merge_park_check_in"
down_revision = ("008_add_parked_thoughts", "009_add_check_in_preferences")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
