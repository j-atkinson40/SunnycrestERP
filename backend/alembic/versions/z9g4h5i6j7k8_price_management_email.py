"""Price management, PDF templates, email infrastructure tables

Revision ID: z9g4h5i6j7k8
Revises: z9f3g4h5i6j7
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "z9g4h5i6j7k8"
down_revision = "z9f3g4h5i6j7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── price_list_versions ──
    op.create_table(
        "price_list_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("label", sa.String(200)),
        sa.Column("notes", sa.Text),
        sa.Column("status", sa.String(50), server_default="draft"),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "version_number", name="uq_plv_tenant_version"),
    )

    # ── price_list_items ──
    op.create_table(
        "price_list_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("version_id", sa.String(36), sa.ForeignKey("price_list_versions.id"), nullable=False, index=True),
        sa.Column("product_name", sa.String(500), nullable=False),
        sa.Column("product_code", sa.String(100)),
        sa.Column("category", sa.String(200)),
        sa.Column("description", sa.Text),
        sa.Column("standard_price", sa.Numeric(10, 2)),
        sa.Column("contractor_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("homeowner_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("previous_standard_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("previous_contractor_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("previous_homeowner_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("unit", sa.String(50), server_default="each"),
        sa.Column("notes", sa.Text),
        sa.Column("display_order", sa.Integer, server_default="0"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── price_list_templates ──
    op.create_table(
        "price_list_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("is_default", sa.Boolean, server_default="false"),
        sa.Column("layout_type", sa.String(50), server_default="grouped"),
        sa.Column("columns", sa.Integer, server_default="1"),
        sa.Column("show_product_codes", sa.Boolean, server_default="true"),
        sa.Column("show_descriptions", sa.Boolean, server_default="true"),
        sa.Column("show_notes", sa.Boolean, server_default="true"),
        sa.Column("show_category_headers", sa.Boolean, server_default="true"),
        sa.Column("logo_position", sa.String(50), server_default="top-left"),
        sa.Column("primary_color", sa.String(7), server_default="#000000"),
        sa.Column("font_family", sa.String(100), server_default="helvetica"),
        sa.Column("header_text", sa.Text),
        sa.Column("footer_text", sa.Text),
        sa.Column("show_effective_date", sa.Boolean, server_default="true"),
        sa.Column("show_page_numbers", sa.Boolean, server_default="true"),
        sa.Column("show_contractor_price", sa.Boolean, server_default="false"),
        sa.Column("show_homeowner_price", sa.Boolean, server_default="false"),
        sa.Column("source_pdf_document_id", sa.String(36), sa.ForeignKey("kb_documents.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── price_update_settings ──
    op.create_table(
        "price_update_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, unique=True),
        sa.Column("rounding_mode", sa.String(50), server_default="none"),
        sa.Column("accept_manufacturer_updates", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── platform_email_settings ──
    op.create_table(
        "platform_email_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, unique=True),
        sa.Column("sending_mode", sa.String(50), server_default="platform"),
        sa.Column("from_name", sa.String(200)),
        sa.Column("reply_to_email", sa.String(500)),
        sa.Column("smtp_host", sa.String(500)),
        sa.Column("smtp_port", sa.Integer, server_default="587"),
        sa.Column("smtp_username", sa.String(500)),
        sa.Column("smtp_password_encrypted", sa.Text),
        sa.Column("smtp_use_tls", sa.Boolean, server_default="true"),
        sa.Column("smtp_from_email", sa.String(500)),
        sa.Column("smtp_verified", sa.Boolean, server_default="false"),
        sa.Column("smtp_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invoice_bcc_email", sa.String(500)),
        sa.Column("price_list_bcc_email", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── email_sends ──
    op.create_table(
        "email_sends",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("sent_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("email_type", sa.String(100)),
        sa.Column("to_email", sa.String(500), nullable=False),
        sa.Column("to_name", sa.String(200)),
        sa.Column("subject", sa.String(500)),
        sa.Column("attachment_type", sa.String(100), nullable=True),
        sa.Column("attachment_name", sa.String(500), nullable=True),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reference_id", sa.String(36), nullable=True),
        sa.Column("reference_type", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("email_sends")
    op.drop_table("platform_email_settings")
    op.drop_table("price_update_settings")
    op.drop_table("price_list_templates")
    op.drop_table("price_list_items")
    op.drop_table("price_list_versions")
