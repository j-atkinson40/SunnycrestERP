"""phase 5c — the constraints that make a duplicate and a wrong tenant unexpressible

This is the removal step of the anomaly-subject arc. Phases 1-4 established a
subject, 5a added the columns, 5b made supersede happen on write, and the
backlog was deduplicated on 2026-09-08. This makes the properties they produced
IMPOSSIBLE TO VIOLATE rather than merely maintained.

⚠️ THREE STATEMENTS, ONE GUARD. Do not split them across migrations.

  1. `tenant_id` NOT NULL
  2. composite FK (agent_job_id, tenant_id) -> agent_jobs (id, tenant_id)
  3. partial UNIQUE index, NULLS NOT DISTINCT, over open rows

(1) AND (2) ARE ONE GUARD IN TWO STATEMENTS. A composite foreign key defaults to
MATCH SIMPLE, under which a row with ANY null in the key passes UNCHECKED. A null
`tenant_id` is precisely what a misfiring listener produces, so the FK alone
fails open in its own target case. Shipped together, a row can neither omit a
tenant nor name one that is not its job's.

WHY THE FK AT ALL, when a `before_insert` listener already derives `tenant_id`:
the listener raises on a SUPPLIED tenant that disagrees with the job, but cannot
catch one it DERIVED wrongly, and it is bypassed entirely by anything that does
not go through the ORM — every `db.execute(text(...))`, every migration, every
psql session. That is not hypothetical: seeding a verification fixture via raw
SQL during 5c prep skipped both listeners and collapsed two tenants into one key.
The listener is the ergonomic half; this is the load-bearing half.

⚠️ THE COMPOSITE FK MUST CARRY `ON DELETE CASCADE`. `agent_job_id` already has a
cascading FK; a second FK over the same parent that defaults to NO ACTION revokes
that cascade, and deleting a job with anomalies begins to raise. Adding a
constraint changes DELETE behaviour as well as INSERT behaviour, and only the
INSERT side is in mind while writing it.

⚠️ (3) MUST BE `NULLS NOT DISTINCT` OR IT DISAGREES WITH THE 5b LISTENER. The
listener groups subjects with `IS NOT DISTINCT FROM`, so NULL subjects MATCH each
other; a default PostgreSQL unique index treats NULLs as DISTINCT and would not
constrain them. Verified on PG 16.13: plain `UNIQUE (a, b)` accepts two
`('t', NULL)` rows, `NULLS NOT DISTINCT` refuses the second. The two halves must
mean the same thing by "duplicate", or the listener refuses to write a row the
index would have permitted -- worse than either behaviour alone. 1,825 rows in
production carried a NULL subject, so this is the majority case, not an edge.

The index predicate is `resolved = false AND superseded_at IS NULL`, which is
`AgentAnomaly.open_filter()` verbatim. A resolved row and a superseded row are
both outside it: a subject may recur any number of times, and each recurrence is
a new row beside the closed ones.

⚠️ TONIGHT'S `ar_collections` RUN IS THE FIRST AGENT WRITE UNDER A LIVE UNIQUE
INDEX. It fires ~23:07 UTC against customer subjects that now hold exactly one
open row each, so the 5b listener supersedes the existing row and then inserts
the new one -- the UPDATE runs first, on the same connection, inside the same
flush, so the old row is already outside the index predicate when the INSERT
lands. If that produces a UNIQUE violation, the listener and this index disagree
about what a duplicate is, and THAT is the failure this migration's design spent
its effort ruling out. It would abort the agent run loudly rather than corrupt
anything, which is the correct failure -- but it is a real signal, not a flake.

IF THIS MIGRATION FAILS TO APPLY, the index found duplicate open rows. As of
2026-09-08 there were none, verified under both groupings. A failure means
something wrote a duplicate between then and the deploy, and the fix is to find
that writer -- not to relax the index.

`ix_agent_anomalies_open` (non-unique, added by r176 over the same columns and
predicate) is dropped: the unique index serves the same lookups and keeping both
would maintain two identical structures.

Index creation is NOT `CONCURRENTLY`. The table held 2,301 rows at authoring, so
the brief lock is not worth losing the migration's transactional rollback.

Revision ID: r177_anomaly_supersede_constraints
Revises: r176_anomaly_supersede_foundation
"""

import sqlalchemy as sa
from alembic import op

revision = "r177_anomaly_supersede_constraints"
down_revision = "r176_anomaly_supersede_foundation"
branch_labels = None
depends_on = None

_OPEN = "resolved = false AND superseded_at IS NULL"


def upgrade() -> None:
    # (1) and (2) are one guard — see the module docstring before splitting them.
    op.alter_column("agent_anomalies", "tenant_id", nullable=False)

    op.create_unique_constraint(
        "uq_agent_jobs_id_tenant", "agent_jobs", ["id", "tenant_id"]
    )
    op.create_foreign_key(
        "fk_agent_anomalies_job_tenant",
        "agent_anomalies", "agent_jobs",
        ["agent_job_id", "tenant_id"], ["id", "tenant_id"],
        # ⚠️ CASCADE IS NOT OPTIONAL HERE, and omitting it is how this migration
        # first failed. `agent_anomalies.agent_job_id` already carries an FK with
        # ON DELETE CASCADE; a second FK over the same parent defaulting to NO
        # ACTION does not merely add a check, it REVOKES the cascade — deleting a
        # job with anomalies starts raising instead of removing them. The gate
        # caught it as 64 teardown errors across unrelated suites.
        #
        # The general shape: adding a constraint changes DELETE behaviour as well
        # as INSERT behaviour, and only the INSERT side is what you are thinking
        # about while writing it.
        ondelete="CASCADE",
    )

    # (3) The index that makes a duplicate unexpressible.
    op.create_index(
        "uq_agent_anomalies_open_subject",
        "agent_anomalies",
        ["tenant_id", "anomaly_type", "entity_type", "entity_id"],
        unique=True,
        postgresql_nulls_not_distinct=True,
        postgresql_where=sa.text(_OPEN),
    )

    op.drop_index("ix_agent_anomalies_open", table_name="agent_anomalies")


def downgrade() -> None:
    """⚠️ THIS RE-PERMITS DUPLICATES AND WRONG TENANTS. It does not delete data,
    and it does not restore any row that was superseded — see r176's downgrade
    docstring for the rollback ORDER (deploy first, then migration) and for why
    dropping `superseded_at` after 5b is a data-loss rollback wearing a
    schema-rollback's shape.
    """
    op.create_index(
        "ix_agent_anomalies_open",
        "agent_anomalies",
        ["tenant_id", "anomaly_type", "entity_type", "entity_id"],
        postgresql_where=sa.text(_OPEN),
    )
    op.drop_index("uq_agent_anomalies_open_subject", table_name="agent_anomalies")
    op.drop_constraint(
        "fk_agent_anomalies_job_tenant", "agent_anomalies", type_="foreignkey"
    )
    op.drop_constraint("uq_agent_jobs_id_tenant", "agent_jobs", type_="unique")
    op.alter_column("agent_anomalies", "tenant_id", nullable=True)
