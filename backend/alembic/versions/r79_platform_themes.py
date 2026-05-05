"""Phase 2 of the Admin Visual Editor — `platform_themes` table for
token-override theming with platform-default → vertical-default →
tenant-override inheritance.

Per CLAUDE.md §14 + the Phase 2 build prompt:
  - One row per (scope, vertical?, tenant_id?, mode) combination
  - `scope` enum: platform_default / vertical_default / tenant_override
  - `mode` enum: light / dark — light + dark are independent records
  - `token_overrides` JSONB: { token_name: override_value, ... }
    Empty {} is valid ("inherit fully from parent scope").
  - `version` integer: incremented on every save (write-side pattern;
    full version history is a Phase 3+ concern)
  - `is_active` boolean: only one active row per scope/vertical/tenant_id/mode
    tuple. Older versions stay rows with is_active=false for audit.

Inheritance happens at READ time, not WRITE time, so changing a
vertical default propagates immediately to every tenant in that
vertical that hasn't overridden the affected tokens.

Migration head: r78_generation_focus_action_payload → r79_platform_themes.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r79_platform_themes"
down_revision = "r78_generation_focus_action_payload"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "platform_themes" in set(inspector.get_table_names()):
        return

    op.create_table(
        "platform_themes",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
        ),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("vertical", sa.String(32), nullable=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column(
            "token_overrides",
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
            name="ck_platform_themes_scope",
        ),
        sa.CheckConstraint(
            "mode IN ('light', 'dark')",
            name="ck_platform_themes_mode",
        ),
        # vertical_default rows MUST carry vertical (and not tenant_id);
        # tenant_override rows MUST carry tenant_id (and not vertical);
        # platform_default rows MUST carry neither.
        sa.CheckConstraint(
            """(
                (scope = 'platform_default'
                    AND vertical IS NULL AND tenant_id IS NULL)
                OR (scope = 'vertical_default'
                    AND vertical IS NOT NULL AND tenant_id IS NULL)
                OR (scope = 'tenant_override'
                    AND vertical IS NULL AND tenant_id IS NOT NULL)
            )""",
            name="ck_platform_themes_scope_keys",
        ),
    )

    # Hot-path lookups: resolving a tenant's theme reads exactly one
    # platform_default + (optional) vertical_default + (optional)
    # tenant_override per mode. The partial index covers active rows
    # only — older versions don't pollute the lookup path.
    op.create_index(
        "ix_platform_themes_active_lookup",
        "platform_themes",
        ["scope", "vertical", "tenant_id", "mode"],
        unique=False,
        postgresql_where=sa.text("is_active = true"),
    )

    # Partial unique: at most one ACTIVE theme per
    # (scope, vertical, tenant_id, mode) tuple. Inactive rows
    # accumulate as a versioned audit trail without violating the
    # uniqueness constraint.
    op.create_index(
        "uq_platform_themes_active",
        "platform_themes",
        ["scope", "vertical", "tenant_id", "mode"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "platform_themes" not in set(inspector.get_table_names()):
        return
    op.drop_index("uq_platform_themes_active", table_name="platform_themes")
    op.drop_index("ix_platform_themes_active_lookup", table_name="platform_themes")
    op.drop_table("platform_themes")
