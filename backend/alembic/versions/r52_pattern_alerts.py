"""Create ai_pattern_alerts table for pattern recognition.

Revision ID: r52_pattern_alerts
Revises: r51_ai_settings
"""

from alembic import op
import sqlalchemy as sa

revision = "r52_pattern_alerts"
down_revision = "r51_ai_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_pattern_alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("pattern_type", sa.String(50), nullable=True),
        sa.Column("master_company_id", sa.String(36), sa.ForeignKey("company_entities.id"), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("surfaced_in_briefing", sa.Boolean, server_default="false"),
        sa.Column("surfaced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed", sa.Boolean, server_default="false"),
        sa.Column("dismissed_by", sa.String(36), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_pattern_alerts_tenant", "ai_pattern_alerts", ["tenant_id", "dismissed"])


def downgrade() -> None:
    op.drop_table("ai_pattern_alerts")
