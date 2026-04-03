"""Create ai_name_suggestions table and add name_enrichment_enabled to ai_settings.

Revision ID: r55_name_suggestions
Revises: r54_ai_agents
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r55_name_suggestions"
down_revision = "r54_ai_agents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_name_suggestions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("master_company_id", sa.String(36), sa.ForeignKey("company_entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("current_name", sa.String(500), nullable=False),
        sa.Column("current_city", sa.String(200), nullable=True),
        sa.Column("current_state", sa.String(100), nullable=True),
        sa.Column("current_address", sa.String(500), nullable=True),
        sa.Column("suggested_name", sa.String(500), nullable=True),
        sa.Column("suggested_address_line1", sa.String(500), nullable=True),
        sa.Column("suggested_city", sa.String(200), nullable=True),
        sa.Column("suggested_state", sa.String(100), nullable=True),
        sa.Column("suggested_zip", sa.String(20), nullable=True),
        sa.Column("suggested_phone", sa.String(50), nullable=True),
        sa.Column("suggested_website", sa.String(500), nullable=True),
        sa.Column("suggestion_source", sa.String(30), nullable=True),
        sa.Column("google_places_id", sa.String(200), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("source_details", JSONB, nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("reviewed_by", sa.String(36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_name", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_name_suggestions_tenant", "ai_name_suggestions", ["tenant_id", "status"])
    op.add_column("ai_settings", sa.Column("name_enrichment_enabled", sa.Boolean, server_default="true"))


def downgrade() -> None:
    op.drop_column("ai_settings", "name_enrichment_enabled")
    op.drop_table("ai_name_suggestions")
