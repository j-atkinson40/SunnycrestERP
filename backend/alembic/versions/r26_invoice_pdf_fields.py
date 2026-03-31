"""r26 — Invoice PDF fields: deceased_name + invoice_delivery_preference

Revision ID: r26_invoice_pdf_fields
Revises: r25_funeral_home_preferences
Create Date: 2026-03-31
"""

from alembic import op
import sqlalchemy as sa

revision = "r26_invoice_pdf_fields"
down_revision = "r25_funeral_home_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # deceased_name on sales_orders
    op.add_column(
        "sales_orders",
        sa.Column("deceased_name", sa.String(200), nullable=True),
    )

    # deceased_name on invoices (copied from order at creation time)
    op.add_column(
        "invoices",
        sa.Column("deceased_name", sa.String(200), nullable=True),
    )

    # deceased_name on quotes
    op.add_column(
        "quotes",
        sa.Column("deceased_name", sa.String(200), nullable=True),
    )

    # invoice_delivery_preference on customers
    op.add_column(
        "customers",
        sa.Column(
            "invoice_delivery_preference",
            sa.String(30),
            nullable=False,
            server_default="statement_only",
        ),
    )

    # sent_at on invoices (track when email was actually sent)
    op.add_column(
        "invoices",
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )

    # sent_to_email on invoices
    op.add_column(
        "invoices",
        sa.Column("sent_to_email", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sales_orders", "deceased_name")
    op.drop_column("invoices", "deceased_name")
    op.drop_column("quotes", "deceased_name")
    op.drop_column("customers", "invoice_delivery_preference")
    op.drop_column("invoices", "sent_at")
    op.drop_column("invoices", "sent_to_email")
