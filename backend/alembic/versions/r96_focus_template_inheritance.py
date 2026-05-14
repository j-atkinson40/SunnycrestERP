"""Focus Template Inheritance sub-arc A — three-table schema substrate.

Introduces the three-tier Focus inheritance chain:

    focus_cores (Tier 1, platform-owned)
        ← focus_templates (Tier 2, platform_default | vertical_default)
            ← focus_compositions (Tier 3, per-tenant delta over template)

Greenfield drop-and-recreate of `focus_compositions`: the May 2026 layer
is repurposed as Tier 3 (tenant delta over a chosen template). Existing
rows are lost — no production tenants depend on `focus_compositions`
yet (no FKs point into the table; only 2 seeded vertical_default rows
in dev environments).

Locked decisions (see DECISIONS.md 2026-05-13 entries + investigation
docs/investigations/2026-05-14-focus-template-inheritance.md):

  1. Three tables, not single-table-with-discriminator.
  2. Greenfield drop-and-recreate of `focus_compositions`.
  3. `deltas` shape is contract, not schema-enforced. Sub-arc B owns
     the service-layer validator.
  4. Forward-compat `inherits_from_*_version` columns ship now; v1
     resolver (sub-arc B) ignores them. Versioned-snapshot inheritance
     lands in a future sub-arc.
  5. Core-as-placement: cores appear in templates' `rows` JSONB with
     `is_core: true`. Discriminator in JSONB, not column. Validation
     in sub-arc B.

Spec-Override Discipline (CLAUDE.md §12): build spec named the
revision `r96_focus_template_inheritance`. Actual current head
confirmed via `alembic heads` is `r95_verticals_table`. No drift.

Pattern mirrors r87_dashboard_layouts (table-exists short-circuit at
top of upgrade()) and r84_focus_compositions (JSONB columns with
`'[]'::jsonb` / `'{}'::jsonb` server defaults).

Migration head: r95_verticals_table → r96_focus_template_inheritance.

Reversibility: downgrade drops the three new tables AND recreates
`focus_compositions` in its R-5.0 shape so the prior state is
recoverable. Rows are NOT preserved across the round-trip — this
is a greenfield substrate change.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r96_focus_template_inheritance"
down_revision = "r95_verticals_table"
branch_labels = None
depends_on = None


def _existing_tables(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    existing = _existing_tables(bind)

    # ── Step 1: drop the prior `focus_compositions` (greenfield repurpose). ──
    # Confirmed via grep that no other table FKs into focus_compositions.
    if "focus_compositions" in existing:
        op.drop_table("focus_compositions")

    # ── Step 2: focus_cores (Tier 1, platform-owned). ──
    op.create_table(
        "focus_cores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("core_slug", sa.String(96), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("registered_component_kind", sa.String(32), nullable=False),
        sa.Column("registered_component_name", sa.String(96), nullable=False),
        sa.Column(
            "default_starting_column",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "default_column_span",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("12"),
        ),
        sa.Column(
            "default_row_index",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "min_column_span",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("6"),
        ),
        sa.Column(
            "max_column_span",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("12"),
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
        sa.CheckConstraint(
            "default_starting_column >= 0 AND default_starting_column < 12",
            name="ck_focus_cores_default_starting_column",
        ),
        sa.CheckConstraint(
            "default_column_span >= 1 AND default_column_span <= 12",
            name="ck_focus_cores_default_column_span",
        ),
        sa.CheckConstraint(
            "default_starting_column + default_column_span <= 12",
            name="ck_focus_cores_default_geometry_within_grid",
        ),
        sa.CheckConstraint(
            "min_column_span >= 1 AND min_column_span <= 12",
            name="ck_focus_cores_min_column_span",
        ),
        sa.CheckConstraint(
            "max_column_span >= min_column_span AND max_column_span <= 12",
            name="ck_focus_cores_max_column_span",
        ),
        sa.CheckConstraint(
            "default_column_span >= min_column_span AND default_column_span <= max_column_span",
            name="ck_focus_cores_default_within_min_max",
        ),
    )

    op.create_index(
        "ix_focus_cores_active_slug",
        "focus_cores",
        ["core_slug"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    # ── Step 3: focus_templates (Tier 2, platform_default | vertical_default). ──
    op.create_table(
        "focus_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("vertical", sa.String(32), nullable=True),
        sa.Column("template_slug", sa.String(96), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "inherits_from_core_id",
            sa.String(36),
            sa.ForeignKey("focus_cores.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("inherits_from_core_version", sa.Integer(), nullable=False),
        sa.Column(
            "rows",
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
            name="fk_focus_templates_vertical",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "scope IN ('platform_default', 'vertical_default')",
            name="ck_focus_templates_scope",
        ),
        sa.CheckConstraint(
            "("
            "(scope = 'platform_default' AND vertical IS NULL)"
            " OR (scope = 'vertical_default' AND vertical IS NOT NULL)"
            ")",
            name="ck_focus_templates_scope_vertical_correlation",
        ),
    )

    op.create_index(
        "ix_focus_templates_active",
        "focus_templates",
        ["scope", "vertical", "template_slug"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "ix_focus_templates_lookup",
        "focus_templates",
        ["template_slug", "scope", "vertical", "is_active"],
    )

    # ── Step 4: focus_compositions (Tier 3, repurposed greenfield). ──
    op.create_table(
        "focus_compositions",
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
            sa.ForeignKey("focus_templates.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "inherits_from_template_version", sa.Integer(), nullable=False
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
        "ix_focus_compositions_active_per_tenant_template",
        "focus_compositions",
        ["tenant_id", "inherits_from_template_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "ix_focus_compositions_tenant_template",
        "focus_compositions",
        ["tenant_id", "inherits_from_template_id"],
    )


def downgrade() -> None:
    """Drop the three new tables and recreate `focus_compositions` in
    its R-5.0 (pre-r96) shape so prior state is recoverable. Rows are
    NOT preserved across the round-trip — this is a greenfield
    substrate change.
    """
    bind = op.get_bind()
    existing = _existing_tables(bind)

    if "focus_compositions" in existing:
        op.drop_table("focus_compositions")
    if "focus_templates" in existing:
        op.drop_table("focus_templates")
    if "focus_cores" in existing:
        op.drop_table("focus_cores")

    # Recreate `focus_compositions` in its r91 / R-5.0 shape so a
    # downgrade leaves the schema where r95_verticals_table left it.
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
            "rows",
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
            "kind",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'focus'"),
        ),
        sa.Column(
            "pages",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
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
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
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
        sa.CheckConstraint(
            "kind IN ('focus', 'edge_panel')",
            name="ck_focus_compositions_kind",
        ),
    )
