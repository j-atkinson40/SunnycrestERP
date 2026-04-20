"""Command Bar Platform Phase 1 — pg_trgm indexes for fuzzy entity search.

Spine of the command bar resolver. The resolver runs a single
UNION ALL query across six entity types and scores results by
trigram similarity + recency. Without trigram indexes the
similarity scan is a full-table sequence scan — we'd blow through
the p99 < 300 ms latency budget.

Scope:

  - Ensure the `pg_trgm` extension is installed.
  - GIN indexes with `gin_trgm_ops` on the primary searchable text
    column per entity. We pick one column per table that covers
    the common-case queries; multi-column coverage comes later
    (e.g. Phase 2 saved-view search, Phase 3 space-scoped search).

Entity → index column choices:

  | entity         | table           | column(s)          | reasoning |
  |----------------|-----------------|--------------------|-----------|
  | fh_case        | fh_cases        | deceased_last_name | decedent surname is the hot-path lookup |
  | sales_order    | sales_orders    | number             | "SO-2026-0042" typed verbatim is the dominant case |
  | invoice        | invoices        | number             | same as sales order |
  | contact        | contacts        | name               | "John Smith" / "Smith" |
  | product        | products        | name               | product title is what users type |
  | document       | documents       | title              | document title is the display name |

The GIN index also accelerates `ILIKE '%pattern%'` queries, which
is how the legacy `command_bar_data_search.py` path worked. So the
existing /ai-command/* endpoints get a free performance win from
this migration as well.

CREATE INDEX CONCURRENTLY semantics — we use it everywhere because
these tables may have production rows by the time this migration
runs. CONCURRENTLY requires the migration to run outside a
transaction, hence `transactional_ddl = False` on this revision.
Failures mid-create leave an INVALID index; Postgres provides
`DROP INDEX` to clean it up if needed. No data is ever lost.

Downgrade is straightforward — DROP INDEX for each. The pg_trgm
extension is NOT dropped on downgrade because other parts of the
platform (agent_orchestrator fallback fuzzy match, future CRM
dedupe, etc.) may depend on it.

Revision ID: r31_command_bar_trigram_indexes
Revises: r30_delivery_caller_vault_item
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r31_command_bar_trigram_indexes"
down_revision = "r30_delivery_caller_vault_item"
branch_labels = None
depends_on = None


# (entity_label, index_name, table, column)
# Keep this list in sync with resolver.py's SEARCHABLE_ENTITIES.
_TRIGRAM_INDEXES: list[tuple[str, str, str, str]] = [
    ("fh_case",     "ix_fh_cases_deceased_last_name_trgm",  "fh_cases",     "deceased_last_name"),
    ("sales_order", "ix_sales_orders_number_trgm",          "sales_orders", "number"),
    ("invoice",     "ix_invoices_number_trgm",              "invoices",     "number"),
    ("contact",     "ix_contacts_name_trgm",                "contacts",     "name"),
    ("product",     "ix_products_name_trgm",                "products",     "name"),
    ("document",    "ix_documents_title_trgm",              "documents",    "title"),
]


def upgrade() -> None:
    # Extension — idempotent via `IF NOT EXISTS`, no CONCURRENTLY
    # needed here. Runs inside the default transaction block.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # CONCURRENTLY index creation must run outside a transaction.
    # autocommit_block() exits the normal transactional DDL wrapper
    # for just these statements, then re-enters for the revision
    # version update.
    with op.get_context().autocommit_block():
        for _label, index_name, table, column in _TRIGRAM_INDEXES:
            op.execute(
                f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name} "
                f"ON {table} USING gin ({column} gin_trgm_ops)"
            )


def downgrade() -> None:
    # Same autocommit requirement for DROP CONCURRENTLY.
    with op.get_context().autocommit_block():
        for _label, index_name, _table, _column in reversed(_TRIGRAM_INDEXES):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name}")

    # NOTE: pg_trgm extension is intentionally left installed.
    # Other platform features depend on it (agent_orchestrator
    # fuzzy match, CRM duplicate detection candidate scoring).
