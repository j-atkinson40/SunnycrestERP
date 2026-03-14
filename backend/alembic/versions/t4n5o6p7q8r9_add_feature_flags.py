"""Add feature flags system.

Revision ID: t4n5o6p7q8r9
Revises: s3m4n5o6p7q8
Create Date: 2026-03-14
"""

import uuid

from alembic import op
import sqlalchemy as sa

revision = "t4n5o6p7q8r9"
down_revision = "s3m4n5o6p7q8"
branch_labels = None
depends_on = None

# Seed data — 7 initial feature flags
_SEED_FLAGS = [
    {
        "key": "module.purchasing",
        "name": "Purchasing & AP Module",
        "description": "Purchase orders, vendor bills, payments, and AP aging reports.",
        "category": "modules",
        "default_enabled": True,
        "is_global": False,
    },
    {
        "key": "module.inventory",
        "name": "Inventory Management",
        "description": "Stock tracking, production entries, write-offs, and Sage export.",
        "category": "modules",
        "default_enabled": True,
        "is_global": False,
    },
    {
        "key": "module.sales",
        "name": "Sales & Customers",
        "description": "Customer database, pricing tiers, and sales workflows.",
        "category": "modules",
        "default_enabled": True,
        "is_global": False,
    },
    {
        "key": "module.hr",
        "name": "HR & Time Tracking",
        "description": "Employee profiles, onboarding, performance notes, and time tracking.",
        "category": "modules",
        "default_enabled": False,
        "is_global": False,
    },
    {
        "key": "feature.ai_assistant",
        "name": "AI Assistant",
        "description": "Natural language commands for inventory and AP operations.",
        "category": "features",
        "default_enabled": True,
        "is_global": False,
    },
    {
        "key": "feature.sage_export",
        "name": "Sage 100 Export",
        "description": "CSV export formatted for Sage 100 import.",
        "category": "features",
        "default_enabled": True,
        "is_global": False,
    },
    {
        "key": "feature.csv_import",
        "name": "CSV Import",
        "description": "Bulk import for products, customers, and vendors via CSV upload.",
        "category": "features",
        "default_enabled": True,
        "is_global": False,
    },
]


def upgrade() -> None:
    # feature_flags — global flag definitions
    op.create_table(
        "feature_flags",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(50), nullable=False, server_default="general"),
        sa.Column("default_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_global", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # tenant_feature_flags — per-tenant overrides
    op.create_table(
        "tenant_feature_flags",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("flag_id", sa.String(36), sa.ForeignKey("feature_flags.id"), nullable=False, index=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "flag_id", name="uq_tenant_flag"),
    )

    # flag_audit_logs — blocked request logging + toggle history
    op.create_table(
        "flag_audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("flag_key", sa.String(100), nullable=False, index=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("endpoint", sa.String(500), nullable=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Seed the 7 initial flags
    flags_table = sa.table(
        "feature_flags",
        sa.column("id", sa.String),
        sa.column("key", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("category", sa.String),
        sa.column("default_enabled", sa.Boolean),
        sa.column("is_global", sa.Boolean),
    )

    rows = []
    for flag in _SEED_FLAGS:
        rows.append({
            "id": str(uuid.uuid4()),
            "key": flag["key"],
            "name": flag["name"],
            "description": flag["description"],
            "category": flag["category"],
            "default_enabled": flag["default_enabled"],
            "is_global": flag["is_global"],
        })
    op.bulk_insert(flags_table, rows)


def downgrade() -> None:
    op.drop_table("flag_audit_logs")
    op.drop_table("tenant_feature_flags")
    op.drop_table("feature_flags")
