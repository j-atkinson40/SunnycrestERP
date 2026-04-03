"""Create crm_opportunities table for sales pipeline.

Revision ID: r49_crm_opportunities
Revises: r48_manufacturer_profiles_crm_settings
"""

from alembic import op
import sqlalchemy as sa

revision = "r49_crm_opportunities"
down_revision = "r48_manufacturer_profiles_crm_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_opportunities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("master_company_id", sa.String(36), sa.ForeignKey("company_entities.id"), nullable=True),

        sa.Column("prospect_name", sa.String(500), nullable=True),
        sa.Column("prospect_city", sa.String(200), nullable=True),
        sa.Column("prospect_state", sa.String(100), nullable=True),

        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("stage", sa.String(30), nullable=False, server_default="prospect"),
        sa.Column("estimated_annual_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("assigned_to", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("expected_close_date", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("lost_reason", sa.Text, nullable=True),

        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_opportunities_tenant", "crm_opportunities", ["company_id", "stage"])


def downgrade() -> None:
    op.drop_table("crm_opportunities")
