"""Phase R-0 of the Runtime-Aware Editor — `dashboard_layouts` table.

Closes the pre-existing scope-inheritance gap for dashboard widget
arrangements. Today `user_widget_layouts` is per-user only with no
vertical/tenant default layer; widget defaults come from each
WidgetDefinition's in-code `default_position`. This table introduces
3-tier authoring (`platform_default → vertical_default → tenant_default`)
so the platform admin can author "the canonical funeral home dashboard"
and tenants in that vertical inherit it; users can still override per-
user via the existing user_widget_layouts table.

Mirrors the architectural pattern of platform_themes (r79),
component_configurations (r81), focus_compositions (r84):
  - One row per (scope, vertical?, tenant_id?, page_context) tuple.
  - Write-side versioning: every save deactivates the prior active
    row + inserts a new active row with version+1.
  - Inactive rows accumulate as an audit trail (partial unique on
    is_active=true keeps that consistent).
  - Inheritance computed at READ time so a vertical_default change
    propagates to every tenant in that vertical that hasn't overridden.

`layout_config` JSONB shape mirrors what user_widget_layouts already
stores: list of `{widget_id, enabled, position, size, config}` entries.
The widget_service.get_user_layout resolution refactors to walk
user_override → tenant_default → vertical_default → platform_default →
in-code WIDGET_DEFINITIONS fallback.

Migration head: r86_document_template_vertical_tier → r87_dashboard_layouts.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r87_dashboard_layouts"
down_revision = "r86_document_template_vertical_tier"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "dashboard_layouts" in set(inspector.get_table_names()):
        return

    op.create_table(
        "dashboard_layouts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("vertical", sa.String(32), nullable=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("page_context", sa.String(96), nullable=False),
        sa.Column(
            "layout_config",
            sa.JSON().with_variant(
                sa.dialects.postgresql.JSONB(astext_type=sa.Text()), "postgresql"
            ),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "scope IN ('platform_default', 'vertical_default', 'tenant_default')",
            name="ck_dashboard_layouts_scope",
        ),
        # Scope-key shape: platform_default rows carry neither vertical
        # nor tenant_id; vertical_default rows carry vertical but not
        # tenant_id; tenant_default rows carry tenant_id but not vertical.
        sa.CheckConstraint(
            """(
                (scope = 'platform_default'
                    AND vertical IS NULL AND tenant_id IS NULL)
                OR (scope = 'vertical_default'
                    AND vertical IS NOT NULL AND tenant_id IS NULL)
                OR (scope = 'tenant_default'
                    AND vertical IS NULL AND tenant_id IS NOT NULL)
            )""",
            name="ck_dashboard_layouts_scope_keys",
        ),
    )

    # Hot-path lookup index. Resolving a tenant's dashboard reads
    # exactly one platform_default + (optional) vertical_default +
    # (optional) tenant_default per page_context. The partial index
    # covers active rows only.
    op.create_index(
        "ix_dashboard_layouts_active_lookup",
        "dashboard_layouts",
        ["scope", "vertical", "tenant_id", "page_context"],
        unique=False,
        postgresql_where=sa.text("is_active = true"),
    )

    # Partial unique: at most one ACTIVE layout per
    # (scope, vertical, tenant_id, page_context) tuple.
    op.create_index(
        "uq_dashboard_layouts_active",
        "dashboard_layouts",
        ["scope", "vertical", "tenant_id", "page_context"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "dashboard_layouts" not in set(inspector.get_table_names()):
        return
    op.drop_index("uq_dashboard_layouts_active", table_name="dashboard_layouts")
    op.drop_index("ix_dashboard_layouts_active_lookup", table_name="dashboard_layouts")
    op.drop_table("dashboard_layouts")
