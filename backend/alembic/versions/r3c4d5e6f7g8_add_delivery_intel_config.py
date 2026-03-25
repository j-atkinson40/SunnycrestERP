"""Add delivery intelligence config JSONB.

Revision ID: r3c4d5e6f7g8
Revises: r2b3c4d5e6f7
Create Date: 2026-03-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "r3c4d5e6f7g8"
down_revision = "r2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant_settings", sa.Column("delivery_intelligence_config", JSONB, nullable=True))

    # Backfill for tenants with delivery intelligence already enabled
    op.execute("""
        UPDATE tenant_settings
        SET delivery_intelligence_config = '{"enabled": true, "show_operations_board_zone": true, "scheduling_warnings_enabled": true, "conflict_alerts_enabled": true, "block_suggestions_enabled": true, "blanket_block_reassessment_enabled": true, "weekly_review_alerts_enabled": true, "minimum_days_to_flag": 14, "flag_at_risk_level": "moderate"}'::jsonb
        WHERE delivery_intelligence_enabled = true
        AND delivery_intelligence_config IS NULL
    """)


def downgrade() -> None:
    op.drop_column("tenant_settings", "delivery_intelligence_config")
