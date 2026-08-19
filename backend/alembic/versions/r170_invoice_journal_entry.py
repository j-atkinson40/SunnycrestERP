"""INV-1 A-2 — the link from an invoice to the entry that booked it.

`post_invoice_to_ar` posts a journal entry as of A-2. Without a column pointing
at it, "which invoices are unposted" is unanswerable — and fail-open makes that
question load-bearing rather than incidental: an invoice RECORDS even when it
cannot post, so unposted invoices are an expected, recoverable state that
something has to be able to enumerate.

It is also what voiding needs in order to reverse anything.

PRECEDENT, followed exactly: `customer_payments.journal_entry_id` (r155) — the
same link on the other side of the same account. r155's own note applies here
verbatim, including the FK: a hard DELETE of an entry that an issued invoice
points at should be REFUSED, not silently unlink the invoice and leave it
looking unposted. `discount_journal_entry_id` (q2l3) is the counter-example —
a bare VARCHAR(36) with no constraint, recorded as an open question (AR-0.1) —
and this column does not repeat it.

⚠️ NULLABLE, AND NO BACKFILL, AND THE MEASUREMENT SAYS WHY. Re-derived on
PRODUCTION 2026-08-19: `1200 ACCOUNTS RECEIVABLE-TRADE` carries Dr 0.00 against
Cr 33,845.00 over 14 lines, because payments credit AR and invoices have never
debited it. Every existing invoice genuinely has no entry, so NULL is a TRUE
statement about all of them rather than a placeholder.

Whether they post retroactively is INV-1 A-3's question and is deliberately not
answered here — retroactively writing entries into periods is what REV-1 §Q5
established has nothing enforcing it (production has ZERO `period_locks` rows on
every tenant), so a backfill wants its own ruling alongside the period-lock work.

Additive and idempotent via env.py's `op.add_column` wrapper; the FK follows
r153/r154/r155's DROP-IF-EXISTS+ADD idiom (Postgres has no ADD ... IF NOT
EXISTS).

Revision ID: r170_invoice_journal_entry
Revises: r169_completeness_declinations
"""

import sqlalchemy as sa
from alembic import op

revision = "r170_invoice_journal_entry"
down_revision = "r169_completeness_declinations"
branch_labels = None
depends_on = None


_CONSTRAINT = "fk_invoices_journal_entry"


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
    )
    op.execute(f"ALTER TABLE invoices DROP CONSTRAINT IF EXISTS {_CONSTRAINT}")
    op.execute(
        f"ALTER TABLE invoices ADD CONSTRAINT {_CONSTRAINT} "
        "FOREIGN KEY (journal_entry_id) REFERENCES journal_entries (id)"
    )


def downgrade() -> None:
    op.execute(f"ALTER TABLE invoices DROP CONSTRAINT IF EXISTS {_CONSTRAINT}")
    op.drop_column("invoices", "journal_entry_id")
