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

⚠️ BEFORE YOU ROLL THIS BACK — READ `downgrade()`. Two properties are true
today and stop being true once phase 5b lands, and the second one is a
data-loss rollback wearing a schema-rollback's shape.

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
    # ⚠️ DELIBERATELY LEFT NULLABLE. NOT NULL BELONGS IN A LATER MIGRATION.
    #
    # Migrations run inside the deploy (railway-start.sh, under the boot lock,
    # before uvicorn starts), and Railway keeps the OLD container serving while
    # the new one boots. So there is a window in which the new SCHEMA is live
    # and the OLD CODE is still handling traffic -- and the old code does not
    # set `tenant_id` and has no before_insert listener. A NOT NULL here would
    # make every anomaly insert fail for the length of that window, against
    # `expense_categorization` on a */15 cron and the nightly agents.
    #
    # This is expand/contract: widen now, tighten once the writer is live.
    # NOT NULL rides the phase-5c migration, which is already gated on 5b's
    # drain and by then is many deploys downstream of the listener.
    #
    # Correctness in the meantime does not depend on the constraint: the
    # `before_insert` listener on AgentAnomaly derives tenant_id from the job on
    # every insert, and `test_tenant_is_derived_from_the_job_not_supplied` pins
    # it. The column being nullable is a statement about the deploy window, not
    # about whether rows get a tenant.
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
    """⚠️ READ THIS BEFORE ROLLING BACK. Two things, both easy to miss under
    the pressure that makes someone reach for a rollback.

    1. ROLLBACK HAS AN ORDER: DEPLOY FIRST, THEN MIGRATION.
       The application code references `tenant_id` and `superseded_at`. Dropping
       those columns underneath running new code breaks it immediately. Revert
       the deploy, let the old container take traffic, and only then downgrade.

    2. ⚠️ THIS IS LOSSLESS TODAY AND WILL NOT BE AFTER PHASE 5b.
       Phase 5a writes `superseded_at` nowhere, so dropping it loses nothing.
       Once 5b's supersede-on-write is live, that column is the ONLY record of
       which anomalies the machine replaced. Dropping it does not merely lose a
       timestamp — every superseded row silently becomes open work again in
       every count, badge and triage queue, because `open_filter()` reads
       exactly that column. At the time 5a landed that would have been 240 rows
       reappearing against 11 real decisions.

       So this is a safe escape hatch for 5a and is NOT one after 5b. If you are
       rolling back post-5b, dump `(id, superseded_at)` for every non-null row
       first, or you are deleting the answer rather than the question.

    `entity_id` is deliberately left at 255 — see the inline note below.
    """
    op.drop_index("ix_agent_anomalies_open", table_name="agent_anomalies")
    op.drop_column("agent_anomalies", "superseded_at")
    # ⚠️ Narrowing entity_id back to 36 would FAIL on any row holding a longer
    # value, which is the point of widening it. Left at 255 deliberately; a
    # downgrade that silently truncated subjects would be worse than one that
    # leaves a wider column behind.
    op.drop_index("ix_agent_anomalies_tenant_id", table_name="agent_anomalies")
    op.drop_column("agent_anomalies", "tenant_id")
