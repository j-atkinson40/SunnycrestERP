"""Add tax rates, jurisdictions, and tax fields on customers/products/invoices.

Revision ID: p3a4b5c6d7e8
Revises: p2a3b4c5d6e7
Create Date: 2026-03-24
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision = "p3a4b5c6d7e8"
down_revision = "p2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tax rates
    op.create_table(
        "tax_rates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("rate_name", sa.String(100), nullable=False),
        sa.Column("rate_percentage", sa.Numeric(6, 4), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default="false"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("gl_account_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "rate_name", name="uq_tax_rate_name"),
    )

    # Tax jurisdictions
    op.create_table(
        "tax_jurisdictions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("jurisdiction_name", sa.String(100), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("county", sa.String(100), nullable=False),
        sa.Column("zip_codes", ARRAY(sa.String(10)), nullable=True),
        sa.Column("tax_rate_id", sa.String(36), sa.ForeignKey("tax_rates.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "state", "county", name="uq_jurisdiction_county"),
    )
    op.create_index("idx_jurisdiction_county", "tax_jurisdictions", ["tenant_id", "state", "county"])

    # Customer tax fields
    op.add_column("customers", sa.Column("tax_status", sa.String(20), server_default="taxable"))
    op.add_column("customers", sa.Column("tax_rate_override_id", sa.String(36), nullable=True))
    op.add_column("customers", sa.Column("exemption_certificate", sa.String(100), nullable=True))
    op.add_column("customers", sa.Column("exemption_expiry", sa.Date(), nullable=True))
    op.add_column("customers", sa.Column("exemption_verified", sa.Boolean(), server_default="false"))
    op.add_column("customers", sa.Column("exemption_notes", sa.Text(), nullable=True))

    # Product taxability
    op.add_column("products", sa.Column("taxability", sa.String(20), server_default="customer_based"))
    op.add_column("products", sa.Column("tax_rate_override_id", sa.String(36), nullable=True))

    # Invoice delivery address + tax totals
    op.add_column("invoices", sa.Column("delivery_state", sa.String(2), nullable=True))
    op.add_column("invoices", sa.Column("delivery_county", sa.String(100), nullable=True))
    op.add_column("invoices", sa.Column("delivery_zip", sa.String(10), nullable=True))
    op.add_column("invoices", sa.Column("subtotal_before_tax", sa.Numeric(12, 2), server_default="0"))
    op.add_column("invoices", sa.Column("total_tax_amount", sa.Numeric(12, 2), server_default="0"))

    # Invoice line tax fields
    op.add_column("invoice_lines", sa.Column("taxable", sa.Boolean(), server_default="true"))
    op.add_column("invoice_lines", sa.Column("tax_rate_id", sa.String(36), nullable=True))
    op.add_column("invoice_lines", sa.Column("tax_jurisdiction_id", sa.String(36), nullable=True))
    op.add_column("invoice_lines", sa.Column("tax_rate_percentage", sa.Numeric(6, 4), server_default="0"))
    op.add_column("invoice_lines", sa.Column("tax_amount", sa.Numeric(12, 2), server_default="0"))
    op.add_column("invoice_lines", sa.Column("tax_exempt_reason", sa.Text(), nullable=True))
    op.add_column("invoice_lines", sa.Column("tax_resolution_method", sa.String(30), nullable=True))


def downgrade() -> None:
    for col in ["tax_resolution_method", "tax_exempt_reason", "tax_amount", "tax_rate_percentage",
                 "tax_jurisdiction_id", "tax_rate_id", "taxable"]:
        op.drop_column("invoice_lines", col)
    for col in ["total_tax_amount", "subtotal_before_tax", "delivery_zip", "delivery_county", "delivery_state"]:
        op.drop_column("invoices", col)
    op.drop_column("products", "tax_rate_override_id")
    op.drop_column("products", "taxability")
    for col in ["exemption_notes", "exemption_verified", "exemption_expiry",
                 "exemption_certificate", "tax_rate_override_id", "tax_status"]:
        op.drop_column("customers", col)
    op.drop_index("idx_jurisdiction_county")
    op.drop_table("tax_jurisdictions")
    op.drop_table("tax_rates")
