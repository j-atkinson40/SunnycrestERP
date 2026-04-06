"""Add unified import session and staging tables.

Revision ID: z9a0b1c2d3e4
Revises: aa8e8fe9eb0a
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "z9a0b1c2d3e4"
down_revision = "aa8e8fe9eb0a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "unified_import_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, unique=True),
        sa.Column("phase", sa.String(30), server_default="uploading"),
        sa.Column("accounting_source", sa.String(20), nullable=True),
        sa.Column("accounting_status", sa.String(20), server_default="pending"),
        sa.Column("order_history_status", sa.String(20), server_default="pending"),
        sa.Column("cemetery_csv_status", sa.String(20), server_default="pending"),
        sa.Column("funeral_home_csv_status", sa.String(20), server_default="pending"),
        sa.Column("cemetery_csv_content", sa.Text, nullable=True),
        sa.Column("cemetery_csv_mapping", postgresql.JSONB, nullable=True),
        sa.Column("funeral_home_csv_content", sa.Text, nullable=True),
        sa.Column("funeral_home_csv_mapping", postgresql.JSONB, nullable=True),
        sa.Column("processing_summary", postgresql.JSONB, nullable=True),
        sa.Column("processing_error", sa.Text, nullable=True),
        sa.Column("review_decisions", postgresql.JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("staging_customers_count", sa.Integer, server_default="0"),
        sa.Column("staging_cemeteries_count", sa.Integer, server_default="0"),
        sa.Column("staging_funeral_homes_count", sa.Integer, server_default="0"),
        sa.Column("staging_orders_count", sa.Integer, server_default="0"),
        sa.Column("apply_summary", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "import_staging_companies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("unified_import_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_row_id", sa.String(100), nullable=True),
        sa.Column("raw_data", postgresql.JSONB, nullable=True),
        sa.Column("name", sa.String(500), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("city", sa.String(200), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("zip", sa.String(20), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(500), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("contact_name", sa.String(300), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("suggested_type", sa.String(50), nullable=True),
        sa.Column("suggested_contractor_type", sa.String(50), nullable=True),
        sa.Column("classification_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("classification_signals", postgresql.JSONB, nullable=True),
        sa.Column("matched_sources", postgresql.JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column("cross_ref_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("cluster_id", sa.String(36), nullable=True),
        sa.Column("is_cluster_primary", sa.Boolean, server_default="false"),
        sa.Column("review_status", sa.String(20), server_default="pending"),
        sa.Column("reviewed_classification", sa.String(50), nullable=True),
        sa.Column("sage_customer_id", sa.String(100), nullable=True),
        sa.Column("account_number", sa.String(100), nullable=True),
        sa.Column("order_count", sa.Integer, server_default="0"),
        sa.Column("vault_order_count", sa.Integer, server_default="0"),
        sa.Column("appears_as_cemetery_count", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("idx_staging_session", "import_staging_companies", ["session_id"])
    op.create_index(
        "idx_staging_cluster",
        "import_staging_companies",
        ["cluster_id"],
        postgresql_where=sa.text("cluster_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("import_staging_companies")
    op.drop_table("unified_import_sessions")
