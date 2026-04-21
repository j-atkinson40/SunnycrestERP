"""Workflow Arc Phase 8a — add `scope`, `forked_from_workflow_id`,
`forked_at`, `agent_registry_key` to workflows.

Scope introduces the Core / Vertical / Tenant vocabulary used by the
three-tab workflow builder. Backfill from the existing `tier` field:

  tier == 1 → scope = 'core'     (16 wf_sys_* system workflows)
  tier in (2,3) → scope = 'vertical' (20 vertical-specific workflows)
  tier == 4 → scope = 'tenant'   (0 today; reserved for tenant-created)
  company_id IS NOT NULL → scope = 'tenant' (any that slip through)

`forked_from_workflow_id` + `forked_at` support the Option-A hard-fork
mechanism where a tenant creates an independent copy of a core or
vertical workflow. Platform updates do NOT propagate to forks (Option
A discipline). The existing WorkflowEnrollment + WorkflowStepParam
soft-override path stays unchanged — tenants choose between soft
customization (override parameters while staying enrolled) or hard
fork (take ownership of a copy).

`agent_registry_key` flags workflow rows whose execution is delegated
to the accounting agent system (app/services/agents/agent_runner.py).
These render with a "Built-in implementation" badge in the workflow
builder and are view-only — clicking does NOT open the step-by-step
builder editor. Phase 8b-8f migrates the agents into real workflow
definitions; as migrations complete, the key is cleared on each
transitioned row and the badge disappears.

Safe to run on fresh + existing DBs. Columns added nullable, backfilled,
then scope made NOT NULL with a CHECK constraint.

Revision ID: r36_workflow_scope
Down Revision: r35_briefings_table
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "r36_workflow_scope"
down_revision = "r35_briefings_table"
branch_labels = None
depends_on = None


# wf_sys_* workflow IDs that delegate to AgentRunner.AGENT_REGISTRY
# entries. Other wf_sys_* rows execute via workflow_engine directly
# and don't get the "Built-in implementation" badge.
# Mirrors the audit finding at phase-8a-audit-report #9.
AGENT_BACKED_WORKFLOWS: dict[str, str] = {
    "wf_sys_month_end_close": "month_end_close",
    "wf_sys_ar_collections": "ar_collections",
    "wf_sys_expense_categorization": "expense_categorization",
}


def upgrade() -> None:
    op.add_column(
        "workflows",
        sa.Column("scope", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "workflows",
        sa.Column(
            "forked_from_workflow_id",
            sa.String(length=36),
            nullable=True,
        ),
    )
    op.add_column(
        "workflows",
        sa.Column(
            "forked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "workflows",
        sa.Column(
            "agent_registry_key",
            sa.String(length=100),
            nullable=True,
        ),
    )

    # Backfill scope from existing tier + company_id.
    #   tier==1  → core
    #   tier in (2,3) → vertical
    #   tier==4 OR company_id IS NOT NULL → tenant
    # A nullable scope on a row without a tier match gets "tenant"
    # as a safe default (any tenant-created row going forward has
    # company_id set anyway).
    op.execute(
        """
        UPDATE workflows
        SET scope = CASE
            WHEN tier = 1 THEN 'core'
            WHEN tier IN (2, 3) THEN 'vertical'
            WHEN tier = 4 OR company_id IS NOT NULL THEN 'tenant'
            ELSE 'tenant'
        END
        WHERE scope IS NULL;
        """
    )

    # Backfill agent_registry_key for the 3 wf_sys_* workflows that
    # delegate to AgentRunner agents.
    conn = op.get_bind()
    for workflow_id, agent_key in AGENT_BACKED_WORKFLOWS.items():
        conn.execute(
            sa.text(
                "UPDATE workflows SET agent_registry_key = :key "
                "WHERE id = :wf_id"
            ),
            {"key": agent_key, "wf_id": workflow_id},
        )

    # NOT NULL + CHECK constraint now that backfill is complete.
    op.alter_column(
        "workflows",
        "scope",
        nullable=False,
        server_default=sa.text("'tenant'"),
    )
    op.create_check_constraint(
        "ck_workflows_scope_valid",
        "workflows",
        "scope IN ('core', 'vertical', 'tenant')",
    )

    # FK for forked_from_workflow_id. Self-reference — nullable so
    # unforkable platform workflows + user-created ones both work.
    # ON DELETE SET NULL so deleting a source workflow doesn't
    # cascade-delete forked tenant copies.
    op.create_foreign_key(
        "fk_workflows_forked_from",
        "workflows",
        "workflows",
        ["forked_from_workflow_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Index scope for the three-tab filtering hot path.
    op.create_index(
        "ix_workflows_scope",
        "workflows",
        ["scope"],
    )
    # Partial index on tenant forks for "my tenant's custom workflows"
    # query. Keeps index small (most rows have forked_from NULL).
    op.create_index(
        "ix_workflows_forked_from",
        "workflows",
        ["forked_from_workflow_id"],
        postgresql_where=sa.text("forked_from_workflow_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_workflows_forked_from", table_name="workflows")
    op.drop_index("ix_workflows_scope", table_name="workflows")
    op.drop_constraint(
        "fk_workflows_forked_from", "workflows", type_="foreignkey"
    )
    op.drop_constraint(
        "ck_workflows_scope_valid", "workflows", type_="check"
    )
    op.drop_column("workflows", "agent_registry_key")
    op.drop_column("workflows", "forked_at")
    op.drop_column("workflows", "forked_from_workflow_id")
    op.drop_column("workflows", "scope")
