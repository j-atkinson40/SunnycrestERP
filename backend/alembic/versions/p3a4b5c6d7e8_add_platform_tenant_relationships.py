"""Add generalized platform_tenant_relationships table.

Revision ID: p3a4b5c6d7e8
Revises: p2a3b4c5d6e7
Create Date: 2026-03-23
"""

import sqlalchemy as sa
from alembic import op

revision = "p3a4b5c6d7e8"
down_revision = "p2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_tenant_relationships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("supplier_tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("relationship_type", sa.String(100), nullable=False),
        sa.Column("billing_enabled", sa.Boolean(), server_default="false"),
        sa.Column("billing_enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("billing_enabled_by", sa.String(36), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("connected_by", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("legacy_fh_relationship_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id", "supplier_tenant_id", "relationship_type",
            name="uq_platform_tenant_rel",
        ),
    )

    # Migrate existing fh_manufacturer_relationships into platform_tenant_relationships
    op.execute("""
        INSERT INTO platform_tenant_relationships (
            id, tenant_id, supplier_tenant_id, relationship_type,
            billing_enabled, billing_enabled_at, billing_enabled_by,
            connected_at, status, legacy_fh_relationship_id, created_at
        )
        SELECT
            gen_random_uuid()::text,
            funeral_home_tenant_id,
            manufacturer_tenant_id,
            'manufacturer_funeral_home',
            COALESCE(platform_billing_enabled, false),
            platform_billing_enabled_at,
            platform_billing_enabled_by,
            created_at,
            'active',
            id,
            created_at
        FROM fh_manufacturer_relationships
        WHERE funeral_home_tenant_id IS NOT NULL
          AND manufacturer_tenant_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """)

    # Add relationship_type to received_statements for supplier label context
    op.add_column(
        "received_statements",
        sa.Column("relationship_type", sa.String(100), nullable=True, server_default="manufacturer_funeral_home"),
    )


def downgrade() -> None:
    op.drop_column("received_statements", "relationship_type")
    op.drop_table("platform_tenant_relationships")
