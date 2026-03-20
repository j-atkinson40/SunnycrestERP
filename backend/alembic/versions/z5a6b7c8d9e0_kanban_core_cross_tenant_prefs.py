"""Add hidden_from_catalog column and set cross-tenant preference defaults.

Revision ID: z5a6b7c8d9e0
Revises: g7h8i9j0k1l2
Create Date: 2026-03-20

"""

from alembic import op
import sqlalchemy as sa

revision = "z5a6b7c8d9e0"
down_revision = "g7h8i9j0k1l2"
branch_labels = None
depends_on = None


def _column_exists(table, column):
    from sqlalchemy import inspect as sa_inspect
    bind = op.get_bind()
    insp = sa_inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def _table_exists(table):
    from sqlalchemy import inspect as sa_inspect
    bind = op.get_bind()
    insp = sa_inspect(bind)
    return table in insp.get_table_names()


def upgrade():
    # 0. Fix quick_quote_templates.tenant_id — must be nullable for system templates
    if _table_exists("quick_quote_templates"):
        op.alter_column(
            "quick_quote_templates",
            "tenant_id",
            existing_type=sa.String(36),
            nullable=True,
        )

    # 1. Add hidden_from_catalog column to extension_definitions
    if not _column_exists("extension_definitions", "hidden_from_catalog"):
        op.add_column(
            "extension_definitions",
            sa.Column("hidden_from_catalog", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        )

    # 2. Mark funeral_kanban_scheduler as cannot_disable + hidden_from_catalog
    op.execute(
        """
        UPDATE extension_definitions
        SET cannot_disable = true,
            hidden_from_catalog = true
        WHERE extension_key = 'funeral_kanban_scheduler'
        """
    )

    # 3. Set default cross-tenant preferences for existing manufacturing tenants
    #    Uses the settings_json JSON blob on the companies table.
    op.execute(
        """
        UPDATE companies
        SET settings_json = COALESCE(settings_json::jsonb, '{}'::jsonb)
            || '{"delivery_notifications_enabled": true,
                "cemetery_delivery_notifications": true,
                "allow_portal_spring_burial_requests": true,
                "accept_legacy_print_submissions": true,
                "cross_tenant_preferences_configured": true}'::jsonb
        WHERE vertical = 'manufacturing'
          AND (
            settings_json IS NULL
            OR NOT (settings_json::jsonb ? 'cross_tenant_preferences_configured')
            OR (settings_json::jsonb ->> 'cross_tenant_preferences_configured')::boolean IS NOT TRUE
          )
        """
    )


def downgrade():
    if _column_exists("extension_definitions", "hidden_from_catalog"):
        op.drop_column("extension_definitions", "hidden_from_catalog")
