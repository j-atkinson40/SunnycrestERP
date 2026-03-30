"""Historical order import tables.

Revision ID: r24_historical_order_import
Revises: r23_quote_cemetery
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r24_historical_order_import"
down_revision = "r23_quote_cemetery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── historical_order_imports ────────────────────────────────────────────
    op.create_table(
        "historical_order_imports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("source_filename", sa.String(300), nullable=True),
        sa.Column("source_system", sa.String(50), nullable=True),
        # Row counts
        sa.Column("total_rows", sa.Integer(), server_default="0"),
        sa.Column("imported_rows", sa.Integer(), server_default="0"),
        sa.Column("skipped_rows", sa.Integer(), server_default="0"),
        sa.Column("error_rows", sa.Integer(), server_default="0"),
        # Enrichment counts
        sa.Column("customers_created", sa.Integer(), server_default="0"),
        sa.Column("customers_matched", sa.Integer(), server_default="0"),
        sa.Column("cemeteries_created", sa.Integer(), server_default="0"),
        sa.Column("cemeteries_matched", sa.Integer(), server_default="0"),
        sa.Column("fh_cemetery_pairs_created", sa.Integer(), server_default="0"),
        # Column mapping (AI-generated + user-confirmed)
        sa.Column("column_mapping", JSONB(), server_default="{}"),
        sa.Column("mapping_confidence", JSONB(), server_default="{}"),
        # Results
        sa.Column("warnings", JSONB(), server_default="[]"),
        sa.Column("errors", JSONB(), server_default="[]"),
        sa.Column("recommended_templates", JSONB(), server_default="[]"),
        # File content cache (used by /run after /parse)
        sa.Column("raw_csv_content", sa.Text(), nullable=True),
        # Dates
        sa.Column("cutover_date", sa.Date(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("initiated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index(
        "idx_historical_order_imports_company",
        "historical_order_imports",
        ["company_id"],
    )

    # ── historical_orders ───────────────────────────────────────────────────
    op.create_table(
        "historical_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column(
            "import_id",
            sa.String(36),
            sa.ForeignKey("historical_order_imports.id"),
            nullable=False,
        ),
        # Resolved references
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("cemetery_id", sa.String(36), sa.ForeignKey("cemeteries.id"), nullable=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=True),
        # Raw values (preserved from source)
        sa.Column("raw_funeral_home", sa.String(200), nullable=True),
        sa.Column("raw_cemetery", sa.String(200), nullable=True),
        sa.Column("raw_product", sa.String(200), nullable=True),
        sa.Column("raw_equipment", sa.String(100), nullable=True),
        # Order details
        sa.Column("scheduled_date", sa.Date(), nullable=True),
        sa.Column("service_time", sa.Time(), nullable=True),
        sa.Column("service_place_type", sa.String(50), nullable=True),
        sa.Column("equipment_description", sa.String(200), nullable=True),
        sa.Column("equipment_mapped", sa.String(100), nullable=True),
        sa.Column("quantity", sa.Integer(), server_default="1"),
        sa.Column("fulfillment_type", sa.String(50), nullable=True),
        sa.Column("delivery_location_type", sa.String(20), server_default="cemetery"),
        sa.Column("is_spring_surcharge", sa.Boolean(), server_default="false"),
        sa.Column("order_method", sa.String(20), nullable=True),
        sa.Column("csr_name", sa.String(50), nullable=True),
        sa.Column("source_order_number", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        # Match quality
        sa.Column("funeral_home_match_confidence", sa.Float(), nullable=True),
        sa.Column("cemetery_match_confidence", sa.Float(), nullable=True),
        sa.Column("product_match_confidence", sa.Float(), nullable=True),
        sa.Column("needs_review", sa.Boolean(), server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_historical_orders_company", "historical_orders", ["company_id"])
    op.create_index(
        "idx_historical_orders_import", "historical_orders", ["import_id"]
    )
    op.create_index(
        "idx_historical_orders_customer", "historical_orders", ["customer_id"]
    )
    op.create_index(
        "idx_historical_orders_cemetery", "historical_orders", ["cemetery_id"]
    )
    op.create_index(
        "idx_historical_orders_date",
        "historical_orders",
        ["company_id", "scheduled_date"],
    )

    # ── Add profile_data JSONB to entity_behavioral_profiles ───────────────
    op.add_column(
        "entity_behavioral_profiles",
        sa.Column("profile_data", JSONB(), server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("entity_behavioral_profiles", "profile_data")
    op.drop_table("historical_orders")
    op.drop_table("historical_order_imports")
