"""Add classification fields to company_entities.

Revision ID: r50_company_classification
Revises: r49_crm_opportunities
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r50_company_classification"
down_revision = "r49_crm_opportunities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("company_entities", sa.Column("customer_type", sa.String(50), nullable=True))
    op.add_column("company_entities", sa.Column("contractor_type", sa.String(50), nullable=True))
    op.add_column("company_entities", sa.Column("is_aggregate", sa.Boolean, server_default="false"))
    op.add_column("company_entities", sa.Column("classification_confidence", sa.Numeric(4, 3), nullable=True))
    op.add_column("company_entities", sa.Column("classification_source", sa.String(30), nullable=True))
    op.add_column("company_entities", sa.Column("classification_reasons", JSONB, server_default="'[]'"))
    op.add_column("company_entities", sa.Column("classification_reviewed_by", sa.String(36), nullable=True))
    op.add_column("company_entities", sa.Column("classification_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("company_entities", sa.Column("is_active_customer", sa.Boolean, server_default="false"))
    op.add_column("company_entities", sa.Column("first_order_year", sa.Integer, nullable=True))
    op.add_column("company_entities", sa.Column("google_places_id", sa.String(200), nullable=True))
    op.add_column("company_entities", sa.Column("google_places_type", sa.String(100), nullable=True))

    op.create_index("idx_ce_customer_type", "company_entities", ["company_id", "customer_type"])
    op.create_index("idx_ce_classification", "company_entities", ["company_id", "classification_source"])


def downgrade() -> None:
    op.drop_index("idx_ce_classification")
    op.drop_index("idx_ce_customer_type")
    for col in ("customer_type", "contractor_type", "is_aggregate", "classification_confidence",
                "classification_source", "classification_reasons", "classification_reviewed_by",
                "classification_reviewed_at", "is_active_customer", "first_order_year",
                "google_places_id", "google_places_type"):
        op.drop_column("company_entities", col)
