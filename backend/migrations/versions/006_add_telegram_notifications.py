"""Add Telegram notification delivery.

Revision ID: 006_add_telegram_notifications
Revises: 005_add_user_app_settings
Create Date: 2026-07-17
"""

from alembic import op
import sqlalchemy as sa


revision = "006_add_telegram_notifications"
down_revision = "005_add_user_app_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "automation_preferences",
        sa.Column("telegram_chat_id", sa.String(length=40), nullable=True),
    )
    op.drop_constraint(
        "ck_notifications_channel",
        "notifications",
        type_="check",
    )
    op.create_check_constraint(
        "ck_notifications_channel",
        "notifications",
        "channel IN ('email', 'telegram')",
    )


def downgrade() -> None:
    op.execute("UPDATE notifications SET channel = 'email' WHERE channel = 'telegram'")
    op.drop_constraint(
        "ck_notifications_channel",
        "notifications",
        type_="check",
    )
    op.create_check_constraint(
        "ck_notifications_channel",
        "notifications",
        "channel = 'email'",
    )
    op.drop_column("automation_preferences", "telegram_chat_id")
