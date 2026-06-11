"""initial schema

Revision ID: 20260611_0001
Revises:
Create Date: 2026-06-11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260611_0001"
down_revision = None
branch_labels = None
depends_on = None


json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=False),
        sa.Column("email", sa.String(length=180), nullable=False),
        sa.Column("city", sa.String(length=80), nullable=False),
        sa.Column("gender", sa.String(length=40), nullable=False),
        sa.Column("loyalty_tier", sa.String(length=40), nullable=False),
        sa.Column("tags", json_type, nullable=False),
        sa.Column("whatsapp_opt_in", sa.Boolean(), nullable=False),
        sa.Column("sms_opt_in", sa.Boolean(), nullable=False),
        sa.Column("email_opt_in", sa.Boolean(), nullable=False),
        sa.Column("rcs_opt_in", sa.Boolean(), nullable=False),
        sa.Column("last_active_days_ago", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("tool_calls", json_type, nullable=False),
        sa.Column("final_recommendation", json_type, nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "segments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("rules", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("customer_id", sa.String(), nullable=False),
        sa.Column("total", sa.Float(), nullable=False),
        sa.Column("items", json_type, nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("days_ago", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "campaigns",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("agent_run_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("segment_rules", json_type, nullable=False),
        sa.Column("message_template", sa.Text(), nullable=False),
        sa.Column("approved_plan", json_type, nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "approvals",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=False),
        sa.Column("approved_by", sa.String(length=120), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "communications",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=False),
        sa.Column("customer_id", sa.String(), nullable=False),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("recipient", json_type, nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("attributed_revenue", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "customer_id", name="uq_campaign_customer"),
    )
    op.create_table(
        "communication_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("communication_id", sa.String(), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=False),
        sa.Column("customer_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("metadata_json", json_type, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["communication_id"], ["communications.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_communication_events_event_id", "communication_events", ["event_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_communication_events_event_id", table_name="communication_events")
    op.drop_table("communication_events")
    op.drop_table("communications")
    op.drop_table("approvals")
    op.drop_table("campaigns")
    op.drop_table("orders")
    op.drop_table("segments")
    op.drop_table("agent_runs")
    op.drop_table("customers")
