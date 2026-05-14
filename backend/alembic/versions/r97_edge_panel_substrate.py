"""Edge Panel Substrate sub-arc B-1.5 — two-table greenfield schema.

Introduces a separate two-tier inheritance chain for edge-panels,
independent of the Focus Template Inheritance chain (cores → templates
→ compositions) shipped in r96. Edge-panels are pure composition; no
Tier 1 core analogue. Two tiers:

    edge_panel_templates       (Tier 2, platform_default | vertical_default)
        ← edge_panel_compositions   (Tier 3, per-tenant lazy fork delta)

The legacy R-5.0 edge-panel storage rode atop `focus_compositions` via
`kind='edge_panel'` + `pages` JSONB. Sub-arc A's r96 migration dropped
that storage when it greenfield-recreated `focus_compositions` against
the Tier 3 Focus delta shape. Edge-panels were homeless. B-1.5 rehouses
them as a separate primitive.

Locked decisions (see docs/investigations/2026-05-14-edge-panel-substrate.md
+ DECISIONS.md 2026-05-14 sub-arc B-1.5 entry):

  1. Separate primitive — NOT extension of focus_templates.
  2. Two tiers (platform_default | vertical_default) — no Tier 1.
  3. Recursive page-keyed Tier 3 delta vocabulary; reuses R-5.0 +
     R-5.1 User-preference shape verbatim + per-page
     placement_geometry_overrides.
  4. Lazy fork at Tier 3 (row on first edit; pre-edit = bare Tier 2).
  5. Live cascade v1; forward-compat `inherits_from_template_version`
     ships day one (v1 resolver ignores).
  6. Tier 2 deletion: RESTRICT when Tier 3 forks exist; mirrors r96.

Spec-Override Discipline (CLAUDE.md §12): build spec named the
revision `r97_edge_panel_substrate`. Current alembic head verified as
`r96_focus_template_inheritance`. No drift.

Greenfield: no rows to migrate (the legacy single-table edge-panel
storage was already dropped by r96). Reversible: downgrade drops
both tables. Re-up creates them empty; the seed script must re-run.

Migration head: r96_focus_template_inheritance → r97_edge_panel_substrate.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r97_edge_panel_substrate"
down_revision = "r96_focus_template_inheritance"
branch_labels = None
depends_on = None


def _existing_tables(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    existing = _existing_tables(bind)

    # ── edge_panel_templates (Tier 2). ──
    if "edge_panel_templates" not in existing:
        op.create_table(
            "edge_panel_templates",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("scope", sa.String(32), nullable=False),
            sa.Column("vertical", sa.String(32), nullable=True),
            sa.Column("panel_key", sa.String(96), nullable=False),
            sa.Column("display_name", sa.String(160), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "pages",
                sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "canvas_config",
                sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
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
                server_default=sa.text("true"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("created_by", sa.String(36), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("updated_by", sa.String(36), nullable=True),
            sa.ForeignKeyConstraint(
                ["vertical"],
                ["verticals.slug"],
                name="fk_edge_panel_templates_vertical",
                ondelete="RESTRICT",
            ),
            sa.CheckConstraint(
                "scope IN ('platform_default', 'vertical_default')",
                name="ck_edge_panel_templates_scope",
            ),
            sa.CheckConstraint(
                "("
                "(scope = 'platform_default' AND vertical IS NULL)"
                " OR (scope = 'vertical_default' AND vertical IS NOT NULL)"
                ")",
                name="ck_edge_panel_templates_scope_vertical_correlation",
            ),
        )

        op.create_index(
            "ix_edge_panel_templates_active",
            "edge_panel_templates",
            ["scope", "vertical", "panel_key"],
            unique=True,
            postgresql_where=sa.text("is_active = true"),
        )
        op.create_index(
            "ix_edge_panel_templates_lookup",
            "edge_panel_templates",
            ["panel_key", "scope", "vertical"],
            postgresql_where=sa.text("is_active = true"),
        )

    # ── edge_panel_compositions (Tier 3 lazy fork). ──
    if "edge_panel_compositions" not in existing:
        op.create_table(
            "edge_panel_compositions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.String(36),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "inherits_from_template_id",
                sa.String(36),
                sa.ForeignKey(
                    "edge_panel_templates.id", ondelete="RESTRICT"
                ),
                nullable=False,
            ),
            sa.Column(
                "inherits_from_template_version",
                sa.Integer(),
                nullable=False,
            ),
            sa.Column(
                "deltas",
                sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "canvas_config_overrides",
                sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
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
                server_default=sa.text("true"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("created_by", sa.String(36), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("updated_by", sa.String(36), nullable=True),
        )

        op.create_index(
            "ix_edge_panel_compositions_active",
            "edge_panel_compositions",
            ["tenant_id", "inherits_from_template_id"],
            unique=True,
            postgresql_where=sa.text("is_active = true"),
        )
        op.create_index(
            "ix_edge_panel_compositions_tenant_template",
            "edge_panel_compositions",
            ["tenant_id", "inherits_from_template_id"],
        )


def downgrade() -> None:
    """Drop both edge-panel substrate tables. Rows are not preserved."""
    bind = op.get_bind()
    existing = _existing_tables(bind)

    if "edge_panel_compositions" in existing:
        op.drop_table("edge_panel_compositions")
    if "edge_panel_templates" in existing:
        op.drop_table("edge_panel_templates")
