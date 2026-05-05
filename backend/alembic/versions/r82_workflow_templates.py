"""Phase 4 of the Admin Visual Editor — `workflow_templates` +
`tenant_workflow_forks` tables for vertical default workflow
authoring with locked-to-fork merge semantics.

Two new tables:

  * ``workflow_templates`` — admin-authored canvas_state JSONB
    payloads scoped to platform_default OR vertical_default.
    Tenants don't have their own template rows; tenant
    customization happens via ``tenant_workflow_forks``.

  * ``tenant_workflow_forks`` — per-tenant customized canvas_state
    forked from a specific platform/vertical default version.
    When the upstream template advances, dependent forks see
    ``pending_merge_available = true`` but their canvas_state is
    untouched (locked-to-fork semantics).

Same architectural pattern as Phase 2/3:
  - READ-time inheritance resolution (no migration / batch /
    cache invalidation needed when defaults change)
  - Write-side versioning (every save deactivates prior + inserts
    new active row with version + 1)
  - Partial unique on active rows enforces "at most one active
    row per canonical tuple"

Migration head: r81_component_configurations → r82_workflow_templates.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r82_workflow_templates"
down_revision = "r81_component_configurations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    # ── workflow_templates ───────────────────────────────────────
    if "workflow_templates" not in existing:
        op.create_table(
            "workflow_templates",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("scope", sa.String(32), nullable=False),
            sa.Column("vertical", sa.String(32), nullable=True),
            sa.Column("workflow_type", sa.String(96), nullable=False),
            sa.Column("display_name", sa.String(160), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "canvas_state",
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
                "scope IN ('platform_default', 'vertical_default')",
                name="ck_workflow_templates_scope",
            ),
            sa.CheckConstraint(
                """(
                    (scope = 'platform_default' AND vertical IS NULL)
                    OR (scope = 'vertical_default' AND vertical IS NOT NULL)
                )""",
                name="ck_workflow_templates_scope_keys",
            ),
        )

        op.create_index(
            "ix_workflow_templates_active_lookup",
            "workflow_templates",
            ["workflow_type", "scope", "vertical"],
            unique=False,
            postgresql_where=sa.text("is_active = true"),
        )

        # Partial unique: at most one ACTIVE template per
        # (scope, vertical, workflow_type) tuple. Inactive rows
        # accumulate as a versioned audit trail.
        op.create_index(
            "uq_workflow_templates_active",
            "workflow_templates",
            ["scope", "vertical", "workflow_type"],
            unique=True,
            postgresql_where=sa.text("is_active = true"),
        )

    # ── tenant_workflow_forks ────────────────────────────────────
    existing = set(inspector.get_table_names())
    if "tenant_workflow_forks" not in existing:
        op.create_table(
            "tenant_workflow_forks",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.String(36),
                sa.ForeignKey("companies.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("workflow_type", sa.String(96), nullable=False),
            sa.Column(
                "forked_from_template_id",
                sa.String(36),
                sa.ForeignKey("workflow_templates.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "forked_from_version", sa.Integer(), nullable=False
            ),
            sa.Column(
                "canvas_state",
                sa.JSON().with_variant(
                    sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
                    "postgresql",
                ),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "pending_merge_available",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "pending_merge_template_id",
                sa.String(36),
                sa.ForeignKey("workflow_templates.id", ondelete="SET NULL"),
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
        )

        op.create_index(
            "ix_tenant_workflow_forks_lookup",
            "tenant_workflow_forks",
            ["tenant_id", "workflow_type"],
            unique=False,
            postgresql_where=sa.text("is_active = true"),
        )

        # Partial unique: one active fork per
        # (tenant_id, workflow_type). Inactive rows audit trail.
        op.create_index(
            "uq_tenant_workflow_forks_active",
            "tenant_workflow_forks",
            ["tenant_id", "workflow_type"],
            unique=True,
            postgresql_where=sa.text("is_active = true"),
        )

        # Used by `mark_pending_merge` to find every active fork
        # based on a given template version.
        op.create_index(
            "ix_tenant_workflow_forks_template",
            "tenant_workflow_forks",
            ["forked_from_template_id"],
            unique=False,
            postgresql_where=sa.text(
                "is_active = true AND forked_from_template_id IS NOT NULL"
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "tenant_workflow_forks" in existing:
        op.drop_index(
            "ix_tenant_workflow_forks_template",
            table_name="tenant_workflow_forks",
        )
        op.drop_index(
            "uq_tenant_workflow_forks_active",
            table_name="tenant_workflow_forks",
        )
        op.drop_index(
            "ix_tenant_workflow_forks_lookup",
            table_name="tenant_workflow_forks",
        )
        op.drop_table("tenant_workflow_forks")

    if "workflow_templates" in existing:
        op.drop_index(
            "uq_workflow_templates_active",
            table_name="workflow_templates",
        )
        op.drop_index(
            "ix_workflow_templates_active_lookup",
            table_name="workflow_templates",
        )
        op.drop_table("workflow_templates")
