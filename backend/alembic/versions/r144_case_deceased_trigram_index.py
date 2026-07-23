"""fh-case-table-split fix — trigram index on case_deceased.last_name.

The command bar resolver's `fh_case` branch was repointed from the
legacy first-generation `fh_cases` table (March 2026 FH v1; absent
from FUNERAL_HOME_VERTICAL.md's canonical 14-table inventory) to the
canonical FH-1 pair `funeral_cases ⋈ case_deceased`. Deceased names
live on `case_deceased`, so the surname hot-path lookup needs a
trigram GIN there — the exact analogue of r31's
`ix_fh_cases_deceased_last_name_trgm`, which is now orphaned by the
repoint (left in place; it drops in the legacy-FH-v1 retirement arc).

Index target is `last_name` ONLY per the ruled Type B call —
`first_name` searchability is deferred until operator demand.

Latency evidence for the joined resolver branch (50k-case TEMP
replica, GIN bitmap scan → hash join on UNIQUE case_id):
p50 = 1.63 ms / p99 = 3.19 ms — ~10× headroom under the untouched
BLOCKING /command-bar/query gate. Findings:
docs/investigations/2026-07-23-fh-case-table-split.md

CREATE INDEX CONCURRENTLY semantics per the r31 precedent: the
statement must run outside a transaction, so it executes inside
`op.get_context().autocommit_block()`. A mid-create failure leaves
an INVALID index that `DROP INDEX` cleans up; no data is at risk.
pg_trgm is already installed (r31) — no extension step.

Downgrade drops the index (CONCURRENTLY, same autocommit block).

Revision ID: r144_case_deceased_trigram_index
Revises: r143_sales_tax_filing
"""

from __future__ import annotations

from alembic import op


revision = "r144_case_deceased_trigram_index"
down_revision = "r143_sales_tax_filing"
branch_labels = None
depends_on = None


_INDEX_NAME = "ix_case_deceased_last_name_trgm"


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX_NAME} "
            f"ON case_deceased USING gin (last_name gin_trgm_ops)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX_NAME}")

    # pg_trgm extension intentionally untouched (r31 owns it; other
    # platform features depend on it).
