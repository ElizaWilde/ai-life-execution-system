"""Add audits, idempotent commands, procrastination events, and forecasts.

Revision ID: 014_intelligence_commands
Revises: 013_plan_previews
Create Date: 2026-07-30
"""

from alembic import op
import sqlalchemy as sa


revision = "014_intelligence_commands"
down_revision = "013_plan_previews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_audits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_key", sa.String(180), nullable=False),
        sa.Column("trigger_source", sa.String(40), nullable=False),
        sa.Column("automation_type", sa.String(60), nullable=False),
        sa.Column("service_name", sa.String(100), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("decision_json", sa.JSON(), nullable=False),
        sa.Column("records_changed_json", sa.JSON(), nullable=False),
        sa.Column("confirmation_status", sa.String(20), nullable=False, server_default="not_required"),
        sa.Column("execution_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("execution_status IN ('pending', 'running', 'completed', 'failed', 'cancelled')", name="ck_automation_audits_execution_status"),
        sa.CheckConstraint("confirmation_status IN ('not_required', 'pending', 'confirmed', 'rejected')", name="ck_automation_audits_confirmation_status"),
    )
    for column in ("user_id", "action_key", "trigger_source", "automation_type", "execution_status"):
        op.create_index(f"ix_automation_audits_{column}", "automation_audits", [column], unique=column == "action_key")

    op.create_table(
        "automation_commands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("command_text", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(50), nullable=False),
        sa.Column("parameters_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False),
        sa.Column("response_message", sa.Text(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('pending_confirmation', 'completed', 'rejected', 'failed', 'unknown')", name="ck_automation_commands_status"),
    )
    for column in ("user_id", "idempotency_key", "intent", "status"):
        op.create_index(f"ix_automation_commands_{column}", "automation_commands", [column], unique=column == "idempotency_key")

    op.create_table(
        "procrastination_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("detection_key", sa.String(180), nullable=False),
        sa.Column("detection_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("related_task_ids_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("recommended_intervention", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("severity IN ('low', 'medium', 'high')", name="ck_procrastination_events_severity"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_procrastination_events_confidence"),
        sa.CheckConstraint("status IN ('active', 'resolved', 'dismissed')", name="ck_procrastination_events_status"),
    )
    for column in ("user_id", "detection_key", "detection_type", "severity", "status", "detected_at"):
        op.create_index(f"ix_procrastination_events_{column}", "procrastination_events", [column], unique=column == "detection_key")

    op.create_table(
        "forecast_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weekly_goal_id", sa.Integer(), sa.ForeignKey("weekly_goals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("forecast_key", sa.String(180), nullable=False),
        sa.Column("forecast_date", sa.Date(), nullable=False),
        sa.Column("completion_probability", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("remaining_minutes", sa.Integer(), nullable=False),
        sa.Column("remaining_days", sa.Integer(), nullable=False),
        sa.Column("required_daily_minutes", sa.Integer(), nullable=False),
        sa.Column("current_daily_minutes", sa.Integer(), nullable=False),
        sa.Column("risk_factors_json", sa.JSON(), nullable=False),
        sa.Column("data_json", sa.JSON(), nullable=False),
        sa.Column("recommended_adjustment", sa.Text(), nullable=False),
        sa.Column("actual_outcome", sa.String(30), nullable=True),
        sa.Column("predicted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("completion_probability >= 0 AND completion_probability <= 1", name="ck_forecast_history_probability"),
        sa.CheckConstraint("risk_level IN ('low', 'medium', 'high')", name="ck_forecast_history_risk"),
    )
    for column in ("user_id", "weekly_goal_id", "forecast_key", "forecast_date", "risk_level", "predicted_at"):
        op.create_index(f"ix_forecast_history_{column}", "forecast_history", [column], unique=column == "forecast_key")


def downgrade() -> None:
    op.drop_table("forecast_history")
    op.drop_table("procrastination_events")
    op.drop_table("automation_commands")
    op.drop_table("automation_audits")
