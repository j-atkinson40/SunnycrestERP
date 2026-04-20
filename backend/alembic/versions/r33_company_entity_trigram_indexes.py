"""Phase 4 — GIN trigram index on company_entities.name for NL extraction.

Phase 4 (Natural Language Creation with Live Overlay) resolves entity-
typed fields — `case.funeral_home`, `sales_order.customer`,
`contact.company` — against the CRM's `company_entities` table during
the overlay extraction pass. The hot-path matcher uses pg_trgm
`similarity(name, :query)` with a strict <30ms per-field latency
budget. An existing btree on `(company_id, name)` doesn't serve
similarity queries; we need a dedicated GIN trigram index.

The Phase 1 resolver (r31) already searched six other tables
(fh_cases.deceased_last_name, sales_orders.number, invoices.number,
contacts.name, products.name, documents.title) with GIN trigram
indexes. r33 extends the same pattern to company_entities, but keeps
the resolver local to `nl_creation/entity_resolver.py` rather than
bolting onto the Phase 1 `SEARCHABLE_ENTITIES` tuple (that's a Phase 5
coordinated nav/search unification — noted in the audit).

Uses `CREATE INDEX CONCURRENTLY IF NOT EXISTS ... USING gin (name
gin_trgm_ops)` inside `op.get_context().autocommit_block()` — same
mechanism Phase 1/2 (r31/r32) used. Safe on a live table.

pg_trgm extension is assumed present (installed by r31). The
statement is additive — downgrade drops the index but leaves the
extension in place (other callers depend on it).

Revision ID: r33_company_entity_trigram_indexes
Revises: r32_saved_view_indexes
"""

from __future__ import annotations

from alembic import op


revision = "r33_company_entity_trigram_indexes"
down_revision = "r32_saved_view_indexes"
branch_labels = None
depends_on = None


_INDEXES = [
    (
        "ix_company_entities_name_trgm",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_company_entities_name_trgm "
        "ON company_entities USING gin (name gin_trgm_ops)",
    ),
]


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for _, sql in _INDEXES:
            op.execute(sql)


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for name, _ in reversed(_INDEXES):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
