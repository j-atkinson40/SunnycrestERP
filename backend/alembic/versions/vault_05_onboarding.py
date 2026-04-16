"""Manufacturing vertical onboarding tables."""

from alembic import op
import sqlalchemy as sa

revision = "vault_05_onboarding"
down_revision = "vault_04_multi_location"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- wilbert_territories table ---
    op.create_table(
        "wilbert_territories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("territory_code", sa.String(100), nullable=False, unique=True),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("counties", sa.JSON, nullable=True),
        sa.Column("zip_codes", sa.JSON, nullable=True),
        sa.Column("lat_bounds", sa.JSON, nullable=True),
        sa.Column("lng_bounds", sa.JSON, nullable=True),
        sa.Column("confirmed_by_company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- wilbert_program_enrollments table ---
    op.create_table(
        "wilbert_program_enrollments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("program_code", sa.String(50), nullable=False),
        sa.Column("program_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("territory_ids", sa.JSON, nullable=True),
        sa.Column("uses_vault_territory", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("enabled_product_ids", sa.JSON, nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("program_type", sa.String(50), server_default="wilbert", nullable=True),
        sa.Column("fulfillment_path", sa.String(50), nullable=True),
        sa.Column("personalization_config", sa.JSON, nullable=True),
        sa.Column("permissions_config", sa.JSON, nullable=True),
        sa.Column("notifications_config", sa.JSON, nullable=True),
        sa.Column("fulfillment_config", sa.JSON, nullable=True),
        sa.Column("payout_config", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_wilbert_program_company", "wilbert_program_enrollments", ["company_id"])
    op.create_index(
        "uq_program_per_company",
        "wilbert_program_enrollments",
        ["company_id", "program_code"],
        unique=True,
    )

    # --- historical_products table ---
    op.create_table(
        "historical_products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("original_name", sa.String(500), nullable=False),
        sa.Column("normalized_name", sa.String(500), nullable=False),
        sa.Column("manufacturer", sa.String(255), nullable=True),
        sa.Column("canonical_product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("equivalency_note", sa.Text, nullable=True),
        sa.Column("is_orderable", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("import_session_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_historical_products_company", "historical_products", ["company_id"])

    # --- product_aliases table ---
    op.create_table(
        "product_aliases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("alias_text", sa.String(500), nullable=False),
        sa.Column("alias_text_normalized", sa.String(500), nullable=False),
        sa.Column("canonical_product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("historical_product_id", sa.String(36), sa.ForeignKey("historical_products.id"), nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("source", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("is_confirmed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_product_aliases_company_normalized",
        "product_aliases",
        ["company_id", "alias_text_normalized"],
    )

    # --- import_sessions table ---
    op.create_table(
        "import_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("file_name", sa.String(500), nullable=True),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("source_system", sa.String(100), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("total_records", sa.Integer, nullable=False, server_default="0"),
        sa.Column("matched_records", sa.Integer, nullable=False, server_default="0"),
        sa.Column("unmatched_records", sa.Integer, nullable=False, server_default="0"),
        sa.Column("duplicate_records", sa.Integer, nullable=False, server_default="0"),
        sa.Column("imported_records", sa.Integer, nullable=False, server_default="0"),
        sa.Column("skipped_records", sa.Integer, nullable=False, server_default="0"),
        sa.Column("date_range_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_range_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("column_mapping", sa.JSON, nullable=True),
        sa.Column("product_matches", sa.JSON, nullable=True),
        sa.Column("customer_matches", sa.JSON, nullable=True),
        sa.Column("error_log", sa.JSON, nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_import_sessions_company", "import_sessions", ["company_id"])

    # --- configurable_item_registry table (platform-wide) ---
    op.create_table(
        "configurable_item_registry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("registry_type", sa.String(100), nullable=False),
        sa.Column("item_key", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("tier", sa.Integer, nullable=False),
        sa.Column("vertical", sa.String(50), nullable=False),
        sa.Column("tags", sa.JSON, nullable=True),
        sa.Column("default_config", sa.JSON, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "uq_registry_item_key",
        "configurable_item_registry",
        ["registry_type", "item_key"],
        unique=True,
    )

    # --- tenant_item_config table ---
    op.create_table(
        "tenant_item_config",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("registry_id", sa.String(36), sa.ForeignKey("configurable_item_registry.id"), nullable=True),
        sa.Column("item_key", sa.String(200), nullable=False),
        sa.Column("registry_type", sa.String(100), nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_custom", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("config", sa.JSON, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_tenant_item_config_company_type", "tenant_item_config", ["company_id", "registry_type"])

    # --- Add columns to companies table ---
    op.add_column("companies", sa.Column("onboarding_status", sa.String(50), nullable=True, server_default="pending"))
    op.add_column("companies", sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("companies", sa.Column("onboarding_metadata", sa.JSON, nullable=True))
    op.add_column("companies", sa.Column("wilbert_vault_territory", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "wilbert_vault_territory")
    op.drop_column("companies", "onboarding_metadata")
    op.drop_column("companies", "onboarding_completed_at")
    op.drop_column("companies", "onboarding_status")

    op.drop_table("tenant_item_config")
    op.drop_table("configurable_item_registry")
    op.drop_table("import_sessions")
    op.drop_table("product_aliases")
    op.drop_table("historical_products")
    op.drop_table("wilbert_program_enrollments")
    op.drop_table("wilbert_territories")
