"""Create missing tables on production — charge_library_items and quick_quote_templates.

These tables exist in earlier migrations but were not created on production
due to stale inspector state within the same upgrade transaction.
Uses raw SQL CREATE TABLE IF NOT EXISTS to bypass the idempotent wrapper.

Revision ID: r7_create_missing
Revises: r6_ai_training
Create Date: 2026-03-25
"""

import sqlalchemy as sa
from alembic import op

revision = "r7_create_missing"
down_revision = "r6_ai_training"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use raw SQL with IF NOT EXISTS — bypasses the monkey-patched op.create_table
    # and works reliably regardless of inspector caching

    op.execute("""
        CREATE TABLE IF NOT EXISTS charge_library_items (
            id VARCHAR(36) PRIMARY KEY,
            tenant_id VARCHAR(36) NOT NULL REFERENCES companies(id),
            charge_key VARCHAR(100) NOT NULL,
            charge_name VARCHAR(255) NOT NULL,
            category VARCHAR(50) NOT NULL,
            description TEXT,
            is_enabled BOOLEAN NOT NULL DEFAULT false,
            is_system BOOLEAN NOT NULL DEFAULT true,
            pricing_type VARCHAR(30) NOT NULL DEFAULT 'variable',
            fixed_amount NUMERIC(12,2),
            per_mile_rate NUMERIC(8,2),
            free_radius_miles NUMERIC(8,2),
            zone_config TEXT,
            guidance_min NUMERIC(12,2),
            guidance_max NUMERIC(12,2),
            variable_placeholder VARCHAR(255),
            auto_suggest BOOLEAN NOT NULL DEFAULT false,
            auto_suggest_trigger VARCHAR(100),
            invoice_label VARCHAR(255),
            sort_order INTEGER DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_charge_library_tenant_key UNIQUE (tenant_id, charge_key)
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_charge_library_items_tenant_id
        ON charge_library_items(tenant_id)
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS quick_quote_templates (
            id VARCHAR(36) PRIMARY KEY,
            tenant_id VARCHAR(36) REFERENCES companies(id),
            template_name VARCHAR(255) NOT NULL,
            display_label VARCHAR(100) NOT NULL,
            display_description TEXT,
            icon VARCHAR(50),
            product_line VARCHAR(50) NOT NULL,
            sort_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT true,
            is_system_template BOOLEAN DEFAULT false,
            line_items TEXT,
            variable_fields TEXT,
            slide_over_width INTEGER DEFAULT 640,
            primary_action VARCHAR(20) DEFAULT 'split',
            quote_template_key VARCHAR(100),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_quick_quote_templates_tenant_id
        ON quick_quote_templates(tenant_id)
    """)


def downgrade() -> None:
    # Don't drop — these tables may have data from the original migrations
    pass
