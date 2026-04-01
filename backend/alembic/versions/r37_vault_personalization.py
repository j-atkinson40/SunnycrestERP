"""Add vault personalization system — tables, columns, and indexes.

Revision ID: r37_vault_personalization
Revises: r36_driver_portal_settings
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r37_vault_personalization"
down_revision = "r36_driver_portal_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Product personalization fields ───────────────────────────────────
    op.add_column("products", sa.Column("has_personalization", sa.Boolean, server_default="false"))
    op.add_column("products", sa.Column("personalization_tier", sa.String(30), nullable=True))

    # ── Personalization data on order/quote lines ────────────────────────
    op.add_column("sales_order_lines", sa.Column("personalization_data", JSONB, nullable=True))
    op.add_column("quote_lines", sa.Column("personalization_data", JSONB, nullable=True))

    # ── Legacy photo flag on orders/quotes ───────────────────────────────
    op.add_column("sales_orders", sa.Column("legacy_photo_pending", sa.Boolean, server_default="false"))
    op.add_column("quotes", sa.Column("legacy_photo_pending", sa.Boolean, server_default="false"))

    # ── Personalization production tasks ─────────────────────────────────
    op.create_table(
        "order_personalization_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("sales_orders.id"), nullable=True),
        sa.Column("quote_id", sa.String(36), sa.ForeignKey("quotes.id"), nullable=True),
        sa.Column("order_line_id", sa.String(36), nullable=True),
        sa.Column("task_type", sa.String(30), nullable=False),
        sa.Column("inscription_name", sa.Text, nullable=True),
        sa.Column("inscription_dates", sa.Text, nullable=True),
        sa.Column("inscription_additional", sa.Text, nullable=True),
        sa.Column("print_name", sa.String(200), nullable=True),
        sa.Column("print_image_url", sa.Text, nullable=True),
        sa.Column("symbol", sa.String(100), nullable=True),
        sa.Column("is_custom_legacy", sa.Boolean, server_default="false"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("completed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_pers_tasks_order", "order_personalization_tasks", ["order_id"], postgresql_where=sa.text("order_id IS NOT NULL"))
    op.create_index("idx_pers_tasks_company_status", "order_personalization_tasks", ["company_id", "status"])

    # ── Personalization photo attachments ─────────────────────────────────
    op.create_table(
        "order_personalization_photos",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("sales_orders.id"), nullable=True),
        sa.Column("quote_id", sa.String(36), sa.ForeignKey("quotes.id"), nullable=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("order_personalization_tasks.id"), nullable=True),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_url", sa.Text, nullable=False),
        sa.Column("file_size", sa.Integer, nullable=True),
        sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("notes", sa.Text, nullable=True),
    )
    op.create_index("idx_pers_photos_order", "order_personalization_photos", ["order_id"], postgresql_where=sa.text("order_id IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("idx_pers_photos_order", table_name="order_personalization_photos")
    op.drop_table("order_personalization_photos")
    op.drop_index("idx_pers_tasks_company_status", table_name="order_personalization_tasks")
    op.drop_index("idx_pers_tasks_order", table_name="order_personalization_tasks")
    op.drop_table("order_personalization_tasks")
    op.drop_column("quotes", "legacy_photo_pending")
    op.drop_column("sales_orders", "legacy_photo_pending")
    op.drop_column("quote_lines", "personalization_data")
    op.drop_column("sales_order_lines", "personalization_data")
    op.drop_column("products", "personalization_tier")
    op.drop_column("products", "has_personalization")
