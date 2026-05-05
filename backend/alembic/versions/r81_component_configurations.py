"""Phase 3 of the Admin Visual Editor — `component_configurations`
table for per-component prop overrides with platform-default →
vertical-default → tenant-override inheritance.

Mirrors the platform_themes shape (r79) verbatim: same scope enum,
same scope-key CHECK constraint, same active-row partial unique,
same write-side versioning. Configuration overrides are NOT
mode-specific (most component config is mode-agnostic — a widget's
density doesn't differ light vs. dark).

Compound key: (scope, vertical?, tenant_id?, component_kind,
component_name) identifies a unique active row. Inactive rows
accumulate as a versioned audit trail.

Migration head: r80_step2_urn_vault_template_type → r81_component_configurations.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r81_component_configurations"
down_revision = "r80_step2_urn_vault_template_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "component_configurations" in set(inspector.get_table_names()):
        return

    op.create_table(
        "component_configurations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("vertical", sa.String(32), nullable=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("component_kind", sa.String(32), nullable=False),
        sa.Column("component_name", sa.String(96), nullable=False),
        sa.Column(
            "prop_overrides",
            sa.JSON().with_variant(
                sa.dialects.postgresql.JSONB(astext_type=sa.Text()), "postgresql"
            ),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
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
            "scope IN ('platform_default', 'vertical_default', 'tenant_override')",
            name="ck_component_configs_scope",
        ),
        # Same scope-key shape rule as platform_themes.
        sa.CheckConstraint(
            """(
                (scope = 'platform_default'
                    AND vertical IS NULL AND tenant_id IS NULL)
                OR (scope = 'vertical_default'
                    AND vertical IS NOT NULL AND tenant_id IS NULL)
                OR (scope = 'tenant_override'
                    AND vertical IS NULL AND tenant_id IS NOT NULL)
            )""",
            name="ck_component_configs_scope_keys",
        ),
        sa.CheckConstraint(
            "component_kind IN ('widget', 'focus', 'focus-template', "
            "'document-block', 'pulse-widget', 'workflow-node', 'layout', "
            "'composite')",
            name="ck_component_configs_kind",
        ),
    )

    # Hot-path lookup: resolve a component's effective configuration
    # across the inheritance chain.
    op.create_index(
        "ix_component_configs_active_lookup",
        "component_configurations",
        ["component_kind", "component_name", "scope", "vertical", "tenant_id"],
        unique=False,
        postgresql_where=sa.text("is_active = true"),
    )

    # Partial unique: one active row per
    # (scope, vertical, tenant_id, component_kind, component_name).
    op.create_index(
        "uq_component_configs_active",
        "component_configurations",
        ["scope", "vertical", "tenant_id", "component_kind", "component_name"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "component_configurations" not in set(inspector.get_table_names()):
        return
    op.drop_index("uq_component_configs_active", table_name="component_configurations")
    op.drop_index("ix_component_configs_active_lookup", table_name="component_configurations")
    op.drop_table("component_configurations")
