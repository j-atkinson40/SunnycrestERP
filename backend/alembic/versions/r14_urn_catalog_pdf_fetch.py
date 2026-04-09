"""Add catalog PDF auto-fetch fields to urn_tenant_settings.

Revision ID: r14_urn_catalog_pdf_fetch
Revises: r13_social_service_certificates
Create Date: 2026-04-09
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "r14_urn_catalog_pdf_fetch"
down_revision = "r13_social_service_certificates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "urn_tenant_settings",
        sa.Column("catalog_pdf_hash", sa.String(64), nullable=True),
    )
    op.add_column(
        "urn_tenant_settings",
        sa.Column(
            "catalog_pdf_last_fetched",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "urn_tenant_settings",
        sa.Column("catalog_pdf_r2_key", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("urn_tenant_settings", "catalog_pdf_r2_key")
    op.drop_column("urn_tenant_settings", "catalog_pdf_last_fetched")
    op.drop_column("urn_tenant_settings", "catalog_pdf_hash")
