"""Safety-net migration: ensure all catalog-related columns exist.

Several migrations (c3, d4, r8) were in orphaned branches before r10 merged
them.  If r10 failed silently on Railway the server started anyway and those
columns were never created, causing the confirm-import endpoint to 500.

This migration uses the env.py monkey-patched op.add_column (idempotent — skips
if the column already exists) so it is safe to run on any database state.

Revision ID: r12_catalog_safety_net
Revises: r11_invoice_review_fields
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa

revision = "r12_catalog_safety_net"
down_revision = "r11_invoice_review_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── products ─────────────────────────────────────────────────────────────
    op.add_column("products", sa.Column("price_without_our_product", sa.Numeric(10, 2), nullable=True))
    op.add_column("products", sa.Column("has_conditional_pricing", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("products", sa.Column("is_call_office", sa.Boolean(), nullable=False, server_default="false"))

    # ── product_bundles ───────────────────────────────────────────────────────
    op.add_column("product_bundles", sa.Column("has_conditional_pricing", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("product_bundles", sa.Column("standalone_price", sa.Numeric(10, 2), nullable=True))
    op.add_column("product_bundles", sa.Column("with_vault_price", sa.Numeric(10, 2), nullable=True))
    op.add_column("product_bundles", sa.Column("vault_qualifier_categories", sa.Text(), nullable=False, server_default='["burial_vault","urn_vault"]'))

    # ── price_list_imports ────────────────────────────────────────────────────
    op.add_column("price_list_imports", sa.Column("billing_terms_json", sa.Text(), nullable=True))

    # ── price_list_import_items — conditional pricing ─────────────────────────
    op.add_column("price_list_import_items", sa.Column("extracted_price_with_vault", sa.Numeric(12, 2), nullable=True))
    op.add_column("price_list_import_items", sa.Column("extracted_price_standalone", sa.Numeric(12, 2), nullable=True))
    op.add_column("price_list_import_items", sa.Column("has_conditional_pricing", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("price_list_import_items", sa.Column("is_bundle_price_variant", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("price_list_import_items", sa.Column("parent_bundle_import_item_id", sa.String(36), nullable=True))
    op.add_column("price_list_import_items", sa.Column("price_variant_type", sa.String(20), nullable=True))

    # ── price_list_import_items — call-office / charge fields ─────────────────
    op.add_column("price_list_import_items", sa.Column("is_call_office", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("price_list_import_items", sa.Column("charge_category", sa.String(50), nullable=True))
    op.add_column("price_list_import_items", sa.Column("charge_key_suggestion", sa.String(100), nullable=True))
    op.add_column("price_list_import_items", sa.Column("charge_match_type", sa.String(30), nullable=True))
    op.add_column("price_list_import_items", sa.Column("matched_charge_id", sa.String(36), nullable=True))
    op.add_column("price_list_import_items", sa.Column("matched_charge_name", sa.String(255), nullable=True))
    op.add_column("price_list_import_items", sa.Column("charge_key_to_use", sa.String(100), nullable=True))
    op.add_column("price_list_import_items", sa.Column("pricing_type_suggestion", sa.String(30), nullable=True))
    op.add_column("price_list_import_items", sa.Column("enable_on_import", sa.Boolean(), nullable=False, server_default="true"))

    # ── charge_library_items — conditional pricing ────────────────────────────
    op.add_column("charge_library_items", sa.Column("has_conditional_pricing", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("charge_library_items", sa.Column("with_vault_price", sa.Numeric(12, 2), nullable=True))
    op.add_column("charge_library_items", sa.Column("standalone_price", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    # No-op downgrade — these columns belong to the schema; removing them would
    # break the application.  Rollback by deploying an older git revision.
    pass
