"""anomaly supersede foundation — tenant_id, wider entity_id, superseded_at

Phase 5a of the anomaly-subject arc. STRUCTURAL ONLY: this migration adds the
three things the supersede key needs and adds NO unique constraint.

⚠️ THE UNIQUE INDEX IS PHASE 5c AND IS DELIBERATELY NOT HERE. It would fail to
create today — 9 colliding groups in production, 192 rows against one
vendor_bill_line. Building it first would force a cleanup decision under the
pressure of a failed migration, which is how a bad production delete gets made.
Phase 5b's supersede-on-write drains the backlog agent by agent; 5c adds the
index once the drain has run. Removal is the last step, per CLAUDE.md §11.

WHAT AND WHY:

1. `tenant_id` — `agent_anomalies` reaches its tenant only through
   `agent_job_id -> agent_jobs.tenant_id`, and a partial unique index cannot
   span tables. After phases 2-3 subjects are deliberately NOT globally unique
   (`fiscal_year:2026` is byte-identical across tenants, which is what makes it
   a stable subject), so a key without a tenant column would collapse two
   tenants' anomalies into one row. Three tenants write anomalies in production.

2. `entity_id` 36 -> 255 — the column was sized for UUIDs, and 36 is already the
   longest value in use. Phase 2-3 composites reach exactly 36
   (`total_expenses:2026-08-01:2026-08-31`), fitting by one character. A
   truncation here would merge two distinct subjects into one key — the
   coarseness failure arriving through the schema instead of through judgement.

3. `superseded_at` — a duplicate must not be marked `resolved=true`. That claims
   a human acted, putting a false statement in the audit trail and biasing every
   "what did operators decide" query toward overstating engagement.

Revision ID: r176_anomaly_supersede_foundation
Revises: r175_note_surface_foundation
"""

import sqlalchemy as sa
from alembic import op

revision = "r176_anomaly_supersede_foundation"
down_revision = "r175_note_surface_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. tenant_id — added nullable, backfilled, then constrained.
    op.add_column(
        "agent_anomalies",
        sa.Column("tenant_id", sa.String(36), nullable=True),
    )
    # agent_job_id is NOT NULL with an FK, so every row resolves a tenant.
    op.execute(
        """
        UPDATE agent_anomalies a
           SET tenant_id = j.tenant_id
        FROM agent_jobs j
        WHERE j.id = a.agent_job_id
          AND a.tenant_id IS NULL
        """
    )
    op.alter_column("agent_anomalies", "tenant_id", nullable=False)
    op.create_index(
        "ix_agent_anomalies_tenant_id", "agent_anomalies", ["tenant_id"]
    )

    # 2. Widen entity_id. Widening a varchar is a catalog-only change in
    #    PostgreSQL — no table rewrite, no lock beyond the brief ACCESS EXCLUSIVE.
    op.alter_column(
        "agent_anomalies",
        "entity_id",
        existing_type=sa.String(36),
        type_=sa.String(255),
        existing_nullable=True,
    )

    # 3. superseded_at.
    op.add_column(
        "agent_anomalies",
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Supports the open-anomaly predicate every reader now uses, and is the
    # index 5c's partial unique will build on.
    op.create_index(
        "ix_agent_anomalies_open",
        "agent_anomalies",
        ["tenant_id", "anomaly_type", "entity_type", "entity_id"],
        postgresql_where=sa.text("resolved = false AND superseded_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_agent_anomalies_open", table_name="agent_anomalies")
    op.drop_column("agent_anomalies", "superseded_at")
    # ⚠️ Narrowing entity_id back to 36 would FAIL on any row holding a longer
    # value, which is the point of widening it. Left at 255 deliberately; a
    # downgrade that silently truncated subjects would be worse than one that
    # leaves a wider column behind.
    op.drop_index("ix_agent_anomalies_tenant_id", table_name="agent_anomalies")
    op.drop_column("agent_anomalies", "tenant_id")
