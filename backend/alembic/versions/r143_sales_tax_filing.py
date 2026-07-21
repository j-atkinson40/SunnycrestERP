"""Suite — sales-tax accumulation & filing: the three-axis exemption
model, the period accumulator, and the invoice-level tax facts.

Four pieces:
- products.tax_class — the PRODUCT axis. Default 'inherit' (= taxable,
  the default law) so the review surface can show what the operator has
  not yet marked; nothing ships exempt without his word per product.
- tax_certificates — the CERTIFICATE axes: customer-level blanket
  (sales_order_id NULL) and job-level (sales_order_id set). Dated
  validity does the expiry work; vault_document_id references the scan
  when provided (the record stands without it, honestly unattached).
- tax_periods — the accumulator the tax_filing_arc checker probes:
  jurisdiction × period rows derived from invoices' stored truth.
- invoices gain tax_source / tax_reason / tax_jurisdiction /
  exempt_amount — the structured facts accumulation reads going
  forward (history stays NULL, classified honestly as unclassified).
"""

from alembic import op
import sqlalchemy as sa

revision = "r143_sales_tax_filing"
down_revision = "r142_exceptions_arc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("tax_class", sa.String(20), nullable=False, server_default="inherit"),
    )

    op.create_table(
        "tax_certificates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=False, index=True),
        sa.Column("sales_order_id", sa.String(36), sa.ForeignKey("sales_orders.id"), nullable=True, index=True),
        sa.Column("cert_type", sa.String(40), nullable=False),
        sa.Column("cert_number", sa.String(100), nullable=True),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_through", sa.Date(), nullable=True),
        sa.Column("vault_document_id", sa.String(36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "tax_periods",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("period_key", sa.String(20), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("jurisdiction_name", sa.String(120), nullable=False),
        sa.Column("gross_sales", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("taxable_sales", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("exempt_sales", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("exempt_by_class", sa.JSON(), nullable=True),
        sa.Column("tax_computed", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("invoice_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gaps", sa.JSON(), nullable=True),
        sa.Column("last_accumulated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_tax_periods_company_period_jur", "tax_periods",
        ["company_id", "period_key", "jurisdiction_name"], unique=True,
    )

    op.add_column("invoices", sa.Column("tax_source", sa.String(40), nullable=True))
    op.add_column("invoices", sa.Column("tax_reason", sa.Text(), nullable=True))
    op.add_column("invoices", sa.Column("tax_jurisdiction", sa.String(120), nullable=True))
    op.add_column("invoices", sa.Column("exempt_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("invoices", "exempt_amount")
    op.drop_column("invoices", "tax_jurisdiction")
    op.drop_column("invoices", "tax_reason")
    op.drop_column("invoices", "tax_source")
    op.drop_index("ix_tax_periods_company_period_jur", table_name="tax_periods")
    op.drop_table("tax_periods")
    op.drop_table("tax_certificates")
    op.drop_column("products", "tax_class")
