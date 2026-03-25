"""Add licensee transfer system.

Revision ID: q3m4n5o6p7q8
Revises: q2l3m4n5o6p7
Create Date: 2026-03-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "q3m4n5o6p7q8"
down_revision = "q2l3m4n5o6p7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "licensee_transfers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("transfer_number", sa.String(30), nullable=False),
        # Parties
        sa.Column("home_tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("area_tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=True, index=True),
        sa.Column("area_licensee_name", sa.String(200), nullable=True),
        sa.Column("area_licensee_contact", sa.Text(), nullable=True),
        sa.Column("is_platform_transfer", sa.Boolean(), server_default="true"),
        # Status
        sa.Column("status", sa.String(30), server_default="pending"),
        # Source order
        sa.Column("source_order_id", sa.String(36), nullable=True),
        # Funeral details
        sa.Column("funeral_home_customer_id", sa.String(36), nullable=True),
        sa.Column("funeral_home_name", sa.String(200), nullable=True),
        sa.Column("deceased_name", sa.String(200), nullable=True),
        sa.Column("service_date", sa.Date(), nullable=True),
        # Cemetery
        sa.Column("cemetery_name", sa.String(200), nullable=True),
        sa.Column("cemetery_address", sa.Text(), nullable=True),
        sa.Column("cemetery_city", sa.String(100), nullable=True),
        sa.Column("cemetery_state", sa.String(2), nullable=True),
        sa.Column("cemetery_county", sa.String(100), nullable=True),
        sa.Column("cemetery_zip", sa.String(10), nullable=True),
        sa.Column("cemetery_place_id", sa.String(200), nullable=True),
        # Items
        sa.Column("transfer_items", JSONB, server_default="[]"),
        sa.Column("special_instructions", sa.Text(), nullable=True),
        # Timing
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
        # Billing chain
        sa.Column("area_order_id", sa.String(36), nullable=True),
        sa.Column("area_invoice_id", sa.String(36), nullable=True),
        sa.Column("home_vendor_bill_id", sa.String(36), nullable=True),
        sa.Column("home_passthrough_invoice_id", sa.String(36), nullable=True),
        # Pricing
        sa.Column("area_charge_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("markup_percentage", sa.Numeric(5, 2), server_default="0"),
        sa.Column("passthrough_amount", sa.Numeric(12, 2), nullable=True),
        # Decline/cancel
        sa.Column("decline_reason", sa.Text(), nullable=True),
        sa.Column("cancelled_by", sa.String(36), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        # Audit
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_transfer_number", "licensee_transfers", ["home_tenant_id", "transfer_number"])

    op.create_table(
        "transfer_notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("transfer_id", sa.String(36), sa.ForeignKey("licensee_transfers.id"), nullable=False, index=True),
        sa.Column("recipient_tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("notification_type", sa.String(30), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Transfer number sequence on tenant_settings
    op.add_column("tenant_settings", sa.Column("transfer_number_prefix", sa.String(10), server_default="TRF"))
    op.add_column("tenant_settings", sa.Column("transfer_number_next", sa.Integer(), server_default="1001"))

    # Order fields for transfer linkage
    op.add_column("orders", sa.Column("out_of_area_self_handled", sa.Boolean(), server_default="false"))
    op.add_column("orders", sa.Column("transfer_id", sa.String(36), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "transfer_id")
    op.drop_column("orders", "out_of_area_self_handled")
    op.drop_column("tenant_settings", "transfer_number_next")
    op.drop_column("tenant_settings", "transfer_number_prefix")
    op.drop_table("transfer_notifications")
    op.drop_table("licensee_transfers")
