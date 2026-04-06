"""Add billing group support to company_entities, customers, and invoices.

Revision ID: z8a9b0c1d2e3
Revises: z7a8b9c0d1e2
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa

revision = "z8a9b0c1d2e3"
down_revision = "z7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- company_entities: billing group fields ---
    op.add_column(
        "company_entities",
        sa.Column("parent_company_id", sa.String(36), sa.ForeignKey("company_entities.id"), nullable=True),
    )
    op.add_column(
        "company_entities",
        sa.Column("is_billing_group", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "company_entities",
        sa.Column("billing_preference", sa.String(30), server_default="separate", nullable=False),
    )

    op.create_index(
        "idx_ce_parent_company",
        "company_entities",
        ["parent_company_id"],
        postgresql_where=sa.text("parent_company_id IS NOT NULL"),
    )
    op.create_index(
        "idx_ce_billing_group",
        "company_entities",
        ["company_id"],
        postgresql_where=sa.text("is_billing_group = true"),
    )

    # --- customers: billing group customer link ---
    op.add_column(
        "customers",
        sa.Column("billing_group_customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=True),
    )

    # --- invoices: consolidated billing fields ---
    op.add_column(
        "invoices",
        sa.Column("is_consolidated", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "invoices",
        sa.Column("is_split_payment", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "invoices",
        sa.Column("group_company_entity_id", sa.String(36), sa.ForeignKey("company_entities.id"), nullable=True),
    )
    op.add_column(
        "invoices",
        sa.Column("parent_invoice_id", sa.String(36), sa.ForeignKey("invoices.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("invoices", "parent_invoice_id")
    op.drop_column("invoices", "group_company_entity_id")
    op.drop_column("invoices", "is_split_payment")
    op.drop_column("invoices", "is_consolidated")
    op.drop_column("customers", "billing_group_customer_id")
    op.drop_index("idx_ce_billing_group", "company_entities")
    op.drop_index("idx_ce_parent_company", "company_entities")
    op.drop_column("company_entities", "billing_preference")
    op.drop_column("company_entities", "is_billing_group")
    op.drop_column("company_entities", "parent_company_id")
