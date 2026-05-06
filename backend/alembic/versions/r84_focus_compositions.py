"""Focus composition layer (May 2026).

Adds the `focus_compositions` table for canvas-based Focus layout
composition. A composition record specifies WHAT'S ON THE CANVAS
(via the `placements` JSONB array) and CANVAS-LEVEL CONFIGURATION
(via `canvas_config`). Component implementations stay in TS/React;
the composition layer is purely about arrangement.

Inheritance chain (parallel to themes / component_configurations /
workflow_templates):

    platform_default
        + vertical_default(vertical)
            + tenant_override(tenant_id)

Resolution at READ time. Each Focus type has at most one active
composition per scope; absence of a composition means the Focus
falls back to its hard-coded layout (backward compat — no need
to migrate every existing Focus immediately).

Migration head: r83_component_class_configurations → r84_focus_compositions.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r84_focus_compositions"
down_revision = "r83_component_class_configurations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "focus_compositions" in set(inspector.get_table_names()):
        return

    op.create_table(
        "focus_compositions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("vertical", sa.String(32), nullable=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("focus_type", sa.String(96), nullable=False),
        sa.Column(
            "placements",
            sa.JSON().with_variant(
                sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
                "postgresql",
            ),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "canvas_config",
            sa.JSON().with_variant(
                sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
                "postgresql",
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
            name="ck_focus_compositions_scope",
        ),
        sa.CheckConstraint(
            """(
                (scope = 'platform_default'
                    AND vertical IS NULL AND tenant_id IS NULL)
                OR (scope = 'vertical_default'
                    AND vertical IS NOT NULL AND tenant_id IS NULL)
                OR (scope = 'tenant_override'
                    AND vertical IS NULL AND tenant_id IS NOT NULL)
            )""",
            name="ck_focus_compositions_scope_keys",
        ),
    )

    op.create_index(
        "ix_focus_compositions_active_lookup",
        "focus_compositions",
        ["focus_type", "scope", "vertical", "tenant_id"],
        unique=False,
        postgresql_where=sa.text("is_active = true"),
    )

    op.create_index(
        "uq_focus_compositions_active",
        "focus_compositions",
        ["scope", "vertical", "tenant_id", "focus_type"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "focus_compositions" not in set(inspector.get_table_names()):
        return
    op.drop_index(
        "uq_focus_compositions_active", table_name="focus_compositions"
    )
    op.drop_index(
        "ix_focus_compositions_active_lookup", table_name="focus_compositions"
    )
    op.drop_table("focus_compositions")
