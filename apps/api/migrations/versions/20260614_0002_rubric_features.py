"""rubric feature additions

Revision ID: 20260614_0002
Revises: 20260611_0001
Create Date: 2026-06-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260614_0002"
down_revision = "20260611_0001"
branch_labels = None
depends_on = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("customers", sa.Column("global_opt_out", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("customers", sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("attributed_communication_id", sa.String(), nullable=True))
    op.add_column("orders", sa.Column("attributed_campaign_id", sa.String(), nullable=True))
    op.add_column("orders", sa.Column("attributed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("communications", sa.Column("variant_label", sa.String(length=80), nullable=True))
    op.add_column("communications", sa.Column("channel_priority", json_type, nullable=False, server_default="[]"))
    op.add_column("communications", sa.Column("fallback_of_communication_id", sa.String(), nullable=True))
    op.create_foreign_key("fk_orders_attributed_communication", "orders", "communications", ["attributed_communication_id"], ["id"])
    op.create_foreign_key("fk_orders_attributed_campaign", "orders", "campaigns", ["attributed_campaign_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_orders_attributed_campaign", "orders", type_="foreignkey")
    op.drop_constraint("fk_orders_attributed_communication", "orders", type_="foreignkey")
    op.drop_column("communications", "fallback_of_communication_id")
    op.drop_column("communications", "channel_priority")
    op.drop_column("communications", "variant_label")
    op.drop_column("orders", "attributed_at")
    op.drop_column("orders", "attributed_campaign_id")
    op.drop_column("orders", "attributed_communication_id")
    op.drop_column("customers", "unsubscribed_at")
    op.drop_column("customers", "global_opt_out")
