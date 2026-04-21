"""Workflow Arc Phase 8d — add publication_state to urn_catalog_sync_logs.

Staging infrastructure for the wf_sys_catalog_fetch triage migration.
Today the catalog fetch pipeline (`UrnCatalogScraper.fetch_catalog_pdf`
+ `WilbertIngestionService.ingest_from_pdf`) auto-publishes every
catalog run that changes the MD5 hash — there's no admin gate between
"Wilbert shipped a new catalog" and "tenant's urn_products rows got
upserted in production." Phase 8d introduces a triage-first step: the
scraper stages the ingestion (parses the PDF, persists extracted
products into a staging representation), creates a catalog_fetch_triage
queue item, and waits for admin approve/reject before applying the
changes to the live catalog.

The staging representation is persisted on `urn_catalog_sync_logs.*`
already (the row captures products_added/updated/discontinued + a
diff-ready snapshot via the existing extracted-products JSON). What's
missing is a state field that answers "has this ingestion been
published yet or is it awaiting review?"

    publication_state VARCHAR(16) NOT NULL DEFAULT 'published'
    CHECK IN ('pending_review', 'published', 'rejected', 'superseded')

Semantics:
  - 'pending_review'  → staged, not applied. Triage queue item exists.
  - 'published'       → ingestion applied to live catalog (approved by
                        triage OR auto-published via legacy path).
  - 'rejected'        → admin rejected via triage; ingestion discarded.
                        Next fetch can still land an updated catalog.
  - 'superseded'      → an older pending row was overtaken by a newer
                        fetch that was approved first; terminal state.

Backfill rule: every pre-r39 row had its changes applied immediately
(there was no gate), so the safe retroactive state is 'published'.
That makes historical reporting correct without a data-dance.

Partial index on `publication_state = 'pending_review'` supports the
triage-queue hot path (`SELECT ... WHERE publication_state =
'pending_review' ORDER BY started_at DESC LIMIT N`) without
maintaining an index over the much larger 'published' partition.

Revision ID: r39_catalog_publication_state
Down Revision: r38_fix_vertical_scope_backfill
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "r39_catalog_publication_state"
down_revision = "r38_fix_vertical_scope_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add nullable first so the server_default fills existing rows
    # before we tighten NOT NULL + CHECK.
    op.add_column(
        "urn_catalog_sync_logs",
        sa.Column(
            "publication_state",
            sa.String(length=16),
            nullable=True,
            server_default=sa.text("'published'"),
        ),
    )
    # Belt-and-suspenders: explicit backfill for any row the
    # server_default didn't catch (shouldn't exist, but idempotent).
    op.execute(
        """
        UPDATE urn_catalog_sync_logs
        SET publication_state = 'published'
        WHERE publication_state IS NULL;
        """
    )
    op.alter_column(
        "urn_catalog_sync_logs",
        "publication_state",
        nullable=False,
        server_default=sa.text("'published'"),
    )
    op.create_check_constraint(
        "ck_urn_catalog_sync_logs_publication_state",
        "urn_catalog_sync_logs",
        "publication_state IN "
        "('pending_review', 'published', 'rejected', 'superseded')",
    )
    # Partial index — only the small pending-review partition matters
    # for the triage queue's hot path. 'published' rows dominate the
    # table over time and never need an index on this column.
    op.create_index(
        "ix_urn_catalog_sync_logs_pending_review",
        "urn_catalog_sync_logs",
        ["started_at"],
        postgresql_where=sa.text("publication_state = 'pending_review'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_urn_catalog_sync_logs_pending_review",
        table_name="urn_catalog_sync_logs",
    )
    op.drop_constraint(
        "ck_urn_catalog_sync_logs_publication_state",
        "urn_catalog_sync_logs",
        type_="check",
    )
    op.drop_column("urn_catalog_sync_logs", "publication_state")
