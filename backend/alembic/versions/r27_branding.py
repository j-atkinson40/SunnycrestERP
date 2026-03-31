"""r27 — Company branding: website column + onboarding checklist update

Revision ID: r27_branding
Revises: r26_invoice_pdf_fields
Create Date: 2026-03-31
"""

from alembic import op
import sqlalchemy as sa

revision = "r27_branding"
down_revision = "r26_invoice_pdf_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Website URL on companies (used for logo/color scraping)
    op.add_column(
        "companies",
        sa.Column("website", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("companies", "website")
