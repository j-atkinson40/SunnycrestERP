"""Create company_entities master CRM table and migration review table.

Adds master_company_id FK to customers, vendors, and cemeteries.

Revision ID: r44_master_company_entities
Revises: r43_seed_new_system_roles
"""

from alembic import op
import sqlalchemy as sa

revision = "r44_master_company_entities"
down_revision = "r43_seed_new_system_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pg_trgm for fuzzy matching during data migration
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ── company_entities — master CRM entity table ──────────────────────────
    op.create_table(
        "company_entities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),

        # Identity
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("legal_name", sa.String(500), nullable=True),

        # Contact
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(500), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),

        # Address
        sa.Column("address_line1", sa.String(500), nullable=True),
        sa.Column("address_line2", sa.String(500), nullable=True),
        sa.Column("city", sa.String(200), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("zip", sa.String(20), nullable=True),
        sa.Column("country", sa.String(100), server_default="US"),

        # Role flags
        sa.Column("is_customer", sa.Boolean, server_default="false"),
        sa.Column("is_vendor", sa.Boolean, server_default="false"),
        sa.Column("is_cemetery", sa.Boolean, server_default="false"),
        sa.Column("is_funeral_home", sa.Boolean, server_default="false"),
        sa.Column("is_licensee", sa.Boolean, server_default="false"),
        sa.Column("is_crematory", sa.Boolean, server_default="false"),
        sa.Column("is_print_shop", sa.Boolean, server_default="false"),

        # Status
        sa.Column("is_active", sa.Boolean, server_default="true"),

        # Notes
        sa.Column("notes", sa.Text, nullable=True),

        # Metadata
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_index("idx_company_entities_tenant", "company_entities", ["company_id"])
    op.create_index("idx_company_entities_name", "company_entities", ["company_id", "name"])
    op.create_index(
        "idx_company_entities_roles",
        "company_entities",
        ["company_id", "is_customer", "is_vendor", "is_cemetery", "is_funeral_home"],
    )

    # ── company_migration_reviews — uncertain matches from data migration ────
    op.create_table(
        "company_migration_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),

        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("source_name", sa.String(500), nullable=True),

        sa.Column("suggested_company_id", sa.String(36), sa.ForeignKey("company_entities.id"), nullable=True),
        sa.Column("suggested_company_name", sa.String(500), nullable=True),
        sa.Column("similarity_score", sa.Numeric(4, 3), nullable=True),

        sa.Column("current_company_id", sa.String(36), sa.ForeignKey("company_entities.id"), nullable=True),

        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("resolved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),

        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── Add master_company_id FK to existing role tables ─────────────────────
    op.add_column("customers", sa.Column("master_company_id", sa.String(36), sa.ForeignKey("company_entities.id"), nullable=True))
    op.add_column("vendors", sa.Column("master_company_id", sa.String(36), sa.ForeignKey("company_entities.id"), nullable=True))
    op.add_column("cemeteries", sa.Column("master_company_id", sa.String(36), sa.ForeignKey("company_entities.id"), nullable=True))


def downgrade() -> None:
    op.drop_column("cemeteries", "master_company_id")
    op.drop_column("vendors", "master_company_id")
    op.drop_column("customers", "master_company_id")
    op.drop_table("company_migration_reviews")
    op.drop_table("company_entities")
