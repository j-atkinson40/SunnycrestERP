"""Component class configuration layer (May 2026).

Adds the `component_class_configurations` table for class-scoped
prop overrides (e.g., "all widgets share this shadow elevation").
The class layer slots into the inheritance chain between
registration defaults and platform-specific defaults:

    registration_default
        + class_default (NEW — this migration)
            + platform_default (component_configurations table)
                + vertical_default
                    + tenant_override

Also extends the `component_configurations.component_kind` CHECK
constraint to permit the four new ComponentKinds added this phase
(`entity-card`, `button`, `form-input`, `surface-card`).

Migration head: r82_workflow_templates → r83_component_class_configurations.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r83_component_class_configurations"
down_revision = "r82_workflow_templates"
branch_labels = None
depends_on = None


# Canonical ComponentKind enum post-class-layer (8 baseline + 4 new).
# Mirrors the frontend ComponentKind type union at
# `frontend/src/lib/visual-editor/registry/types.ts`.
COMPONENT_KIND_VALUES = [
    "widget",
    "focus",
    "focus-template",
    "document-block",
    "pulse-widget",
    "workflow-node",
    "layout",
    "composite",
    # New for class-configuration phase (May 2026):
    "entity-card",
    "button",
    "form-input",
    "surface-card",
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ── Step 1: extend component_configurations.component_kind CHECK ──
    # The existing constraint enumerates only the 8 baseline kinds.
    # Class-configuration phase introduces 4 new kinds; without this
    # extension a class default written for `entity-card` would fail.
    if "component_configurations" in set(inspector.get_table_names()):
        op.drop_constraint(
            "ck_component_configs_kind",
            "component_configurations",
            type_="check",
        )
        kinds_sql = ", ".join(f"'{k}'" for k in COMPONENT_KIND_VALUES)
        op.create_check_constraint(
            "ck_component_configs_kind",
            "component_configurations",
            f"component_kind IN ({kinds_sql})",
        )

    # ── Step 2: new table component_class_configurations ──
    if "component_class_configurations" in set(inspector.get_table_names()):
        return

    op.create_table(
        "component_class_configurations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("component_class", sa.String(64), nullable=False),
        sa.Column(
            "prop_overrides",
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
        # The 9 v1 classes — same vocabulary as ComponentKind for
        # v1 (each class corresponds 1:1 to a Kind). Future
        # multi-class support can extend this with non-Kind class
        # names (e.g., "primary-action") via a separate migration.
        sa.CheckConstraint(
            "component_class IN ("
            "'widget', 'focus', 'focus-template', 'document-block', "
            "'pulse-widget', 'workflow-node', 'layout', 'composite', "
            "'entity-card', 'button', 'form-input', 'surface-card'"
            ")",
            name="ck_component_class_configs_class",
        ),
    )

    op.create_index(
        "ix_component_class_configs_active_lookup",
        "component_class_configurations",
        ["component_class"],
        unique=False,
        postgresql_where=sa.text("is_active = true"),
    )

    # Partial unique: at most one active row per component_class.
    op.create_index(
        "uq_component_class_configs_active",
        "component_class_configurations",
        ["component_class"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Reverse step 2.
    if "component_class_configurations" in set(inspector.get_table_names()):
        op.drop_index(
            "uq_component_class_configs_active",
            table_name="component_class_configurations",
        )
        op.drop_index(
            "ix_component_class_configs_active_lookup",
            table_name="component_class_configurations",
        )
        op.drop_table("component_class_configurations")

    # Reverse step 1: shrink component_kind CHECK back to baseline 8.
    if "component_configurations" in set(inspector.get_table_names()):
        op.drop_constraint(
            "ck_component_configs_kind",
            "component_configurations",
            type_="check",
        )
        op.create_check_constraint(
            "ck_component_configs_kind",
            "component_configurations",
            "component_kind IN ('widget', 'focus', 'focus-template', "
            "'document-block', 'pulse-widget', 'workflow-node', 'layout', "
            "'composite')",
        )
