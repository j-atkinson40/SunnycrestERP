"""Urn Sales extension — 6 tables.

Revision ID: r11_urn_sales
Revises: r10_agent_infra
Create Date: 2026-04-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "r11_urn_sales"
down_revision = "r10_agent_infra"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- urn_products ---
    op.create_table(
        "urn_products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("sku", sa.String(100), nullable=True),
        sa.Column("source_type", sa.String(20), nullable=False, server_default="drop_ship"),
        sa.Column("material", sa.String(50), nullable=True),
        sa.Column("style", sa.String(200), nullable=True),
        sa.Column("available_colors", postgresql.JSONB, nullable=True),
        sa.Column("is_keepsake_set", sa.Boolean, server_default="false"),
        sa.Column("companion_skus", postgresql.JSONB, nullable=True),
        sa.Column("engravable", sa.Boolean, server_default="true"),
        sa.Column("photo_etch_capable", sa.Boolean, server_default="false"),
        sa.Column("available_fonts", postgresql.JSONB, nullable=True),
        sa.Column("base_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("retail_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("image_url", sa.String(2000), nullable=True),
        sa.Column("wilbert_catalog_url", sa.String(2000), nullable=True),
        sa.Column("discontinued", sa.Boolean, server_default="false"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_urn_products_tenant_sku", "urn_products", ["tenant_id", "sku"]
    )
    op.create_index(
        "ix_urn_products_tenant_source", "urn_products", ["tenant_id", "source_type"]
    )

    # --- urn_inventory ---
    op.create_table(
        "urn_inventory",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "urn_product_id",
            sa.String(36),
            sa.ForeignKey("urn_products.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("qty_on_hand", sa.Integer, server_default="0"),
        sa.Column("qty_reserved", sa.Integer, server_default="0"),
        sa.Column("reorder_point", sa.Integer, server_default="0"),
        sa.Column("reorder_qty", sa.Integer, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    # --- urn_orders ---
    op.create_table(
        "urn_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("case_id", sa.String(36), nullable=True),
        sa.Column(
            "funeral_home_id",
            sa.String(36),
            sa.ForeignKey("company_entities.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("fh_contact_email", sa.String(500), nullable=True),
        sa.Column(
            "urn_product_id",
            sa.String(36),
            sa.ForeignKey("urn_products.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("fulfillment_type", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Integer, server_default="1"),
        sa.Column("need_by_date", sa.Date, nullable=True),
        sa.Column("delivery_method", sa.String(30), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("wilbert_order_ref", sa.String(100), nullable=True),
        sa.Column("tracking_number", sa.String(200), nullable=True),
        sa.Column("expected_arrival_date", sa.Date, nullable=True),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("unit_retail", sa.Numeric(12, 2), nullable=True),
        sa.Column("intake_channel", sa.String(30), server_default="'manual'"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_urn_orders_status", "urn_orders", ["status"])

    # --- urn_engraving_jobs ---
    op.create_table(
        "urn_engraving_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "urn_order_id",
            sa.String(36),
            sa.ForeignKey("urn_orders.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("piece_label", sa.String(50), nullable=False, server_default="'main'"),
        sa.Column("engraving_line_1", sa.String(500), nullable=True),
        sa.Column("engraving_line_2", sa.String(500), nullable=True),
        sa.Column("engraving_line_3", sa.String(500), nullable=True),
        sa.Column("engraving_line_4", sa.String(500), nullable=True),
        sa.Column("font_selection", sa.String(200), nullable=True),
        sa.Column("color_selection", sa.String(200), nullable=True),
        sa.Column("photo_file_id", sa.String(36), nullable=True),
        sa.Column("generated_form_snapshot", postgresql.JSONB, nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "proof_status",
            sa.String(30),
            nullable=False,
            server_default="'not_submitted'",
        ),
        sa.Column("proof_file_id", sa.String(36), nullable=True),
        sa.Column("proof_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fh_approval_token", sa.String(200), nullable=True, unique=True),
        sa.Column(
            "fh_approval_token_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("fh_approved_by_name", sa.String(300), nullable=True),
        sa.Column("fh_approved_by_email", sa.String(500), nullable=True),
        sa.Column("fh_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fh_change_request_notes", sa.Text, nullable=True),
        sa.Column(
            "approved_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_notes", sa.Text, nullable=True),
        sa.Column("resubmission_count", sa.Integer, server_default="0"),
        sa.Column("verbal_approval_flagged", sa.Boolean, server_default="false"),
        sa.Column("verbal_approval_transcript_excerpt", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    # --- urn_catalog_sync_logs ---
    op.create_table(
        "urn_catalog_sync_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("products_added", sa.Integer, server_default="0"),
        sa.Column("products_updated", sa.Integer, server_default="0"),
        sa.Column("products_discontinued", sa.Integer, server_default="0"),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="'running'"
        ),
        sa.Column("error_message", sa.Text, nullable=True),
    )

    # --- urn_tenant_settings ---
    op.create_table(
        "urn_tenant_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("ancillary_window_days", sa.Integer, server_default="3"),
        sa.Column("supplier_lead_days", sa.Integer, server_default="7"),
        sa.Column(
            "fh_approval_token_expiry_days", sa.Integer, server_default="3"
        ),
        sa.Column("proof_email_address", sa.String(500), nullable=True),
        sa.Column("wilbert_submission_email", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("urn_tenant_settings")
    op.drop_table("urn_catalog_sync_logs")
    op.drop_table("urn_engraving_jobs")
    op.drop_table("urn_orders")
    op.drop_table("urn_inventory")
    op.drop_table("urn_products")
