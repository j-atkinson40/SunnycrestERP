"""add multi-tenant platform layer: hierarchy, network, fees

Revision ID: x8y9z0a1b2c3
Revises: w7x8y9z0a1b2
Create Date: 2026-03-14

"""
from alembic import op
import sqlalchemy as sa

revision = "x8y9z0a1b2c3"
down_revision = "w7x8y9z0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Company hierarchy columns ---
    op.add_column(
        "companies",
        sa.Column(
            "parent_company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "companies",
        sa.Column("hierarchy_level", sa.String(20), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column("hierarchy_path", sa.String(500), nullable=True),
    )
    op.create_index(
        "ix_companies_parent", "companies", ["parent_company_id"]
    )

    # --- Network Relationships ---
    op.create_table(
        "network_relationships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "requesting_company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column(
            "target_company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column("relationship_type", sa.String(30), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="pending"
        ),
        sa.Column("permissions", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "approved_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_network_rel_requesting",
        "network_relationships",
        ["requesting_company_id"],
    )
    op.create_index(
        "ix_network_rel_target",
        "network_relationships",
        ["target_company_id"],
    )
    op.create_index(
        "ix_network_rel_pair",
        "network_relationships",
        ["requesting_company_id", "target_company_id"],
        unique=True,
    )

    # --- Network Transactions ---
    op.create_table(
        "network_transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "relationship_id",
            sa.String(36),
            sa.ForeignKey("network_relationships.id"),
            nullable=False,
        ),
        sa.Column(
            "source_company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column(
            "target_company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column("transaction_type", sa.String(50), nullable=False),
        sa.Column("source_record_type", sa.String(50), nullable=True),
        sa.Column("source_record_id", sa.String(36), nullable=True),
        sa.Column("target_record_type", sa.String(50), nullable=True),
        sa.Column("target_record_id", sa.String(36), nullable=True),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="pending"
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_network_tx_relationship",
        "network_transactions",
        ["relationship_id"],
    )
    op.create_index(
        "ix_network_tx_source",
        "network_transactions",
        ["source_company_id"],
    )
    op.create_index(
        "ix_network_tx_target",
        "network_transactions",
        ["target_company_id"],
    )
    op.create_index(
        "ix_network_tx_created",
        "network_transactions",
        ["created_at"],
    )

    # --- Fee Rate Configs ---
    op.create_table(
        "fee_rate_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("transaction_type", sa.String(50), nullable=False),
        sa.Column(
            "fee_type",
            sa.String(30),
            nullable=False,
            server_default="transaction_percent",
        ),
        sa.Column(
            "rate",
            sa.Numeric(10, 4),
            nullable=False,
            server_default="0.0000",
        ),
        sa.Column(
            "min_fee",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column("max_fee", sa.Numeric(10, 2), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_fee_rate_tx_type", "fee_rate_configs", ["transaction_type"]
    )

    # --- Platform Fees ---
    op.create_table(
        "platform_fees",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "network_transaction_id",
            sa.String(36),
            sa.ForeignKey("network_transactions.id"),
            nullable=False,
        ),
        sa.Column(
            "fee_rate_config_id",
            sa.String(36),
            sa.ForeignKey("fee_rate_configs.id"),
            nullable=True,
        ),
        sa.Column("fee_type", sa.String(30), nullable=False),
        sa.Column("rate", sa.Numeric(10, 4), nullable=False),
        sa.Column(
            "base_amount",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "calculated_amount",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "currency", sa.String(3), nullable=False, server_default="USD"
        ),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="pending"
        ),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "waived_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("waived_reason", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_platform_fee_tx",
        "platform_fees",
        ["network_transaction_id"],
    )
    op.create_index(
        "ix_platform_fee_status", "platform_fees", ["status"]
    )


def downgrade() -> None:
    op.drop_table("platform_fees")
    op.drop_table("fee_rate_configs")
    op.drop_table("network_transactions")
    op.drop_table("network_relationships")
    op.drop_index("ix_companies_parent", table_name="companies")
    op.drop_column("companies", "hierarchy_path")
    op.drop_column("companies", "hierarchy_level")
    op.drop_column("companies", "parent_company_id")
