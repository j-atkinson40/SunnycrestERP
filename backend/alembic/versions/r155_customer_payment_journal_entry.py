"""AR-2 — the link from a customer payment to the entry that booked it.

`create_customer_payment` posts a journal entry as of AR-2. Without a column
pointing at it, "which payments are unposted" is unanswerable — and fail-open
makes that question load-bearing rather than incidental: the decided discipline
is that a payment RECORDS even when it cannot post, so unposted payments are an
expected, recoverable state that something has to be able to enumerate.

It is also what a later NSF reversal needs in order to reverse anything.

PRECEDENTS, both followed here:
  * `reconciliation_transactions.journal_entry_id` (r154) — the same link on the
    other side of the same arc, FK with NO ON DELETE clause.
  * `customer_payments.discount_journal_entry_id` (q2l3) — already on THIS
    table, for the EPD discount entry. This is its sibling: that column links
    the discount, this one links the receipt. Two entries, two links, and
    keeping them separate means neither has to be interpreted by which arc
    wrote it.

FK WITH NO ON DELETE, matching r153/r154: a hard DELETE of an entry that a
recorded payment points at should be REFUSED, not silently unlink the payment
and leave it looking unposted. The one deliberate difference from q2l3 — which
created `discount_journal_entry_id` as a bare VARCHAR(36) with no constraint —
is that this one IS constrained. q2l3's omission is recorded as an open question
(AR-0.1); this column does not repeat it.

Nullable, no backfill. Every existing payment genuinely has no entry: production
holds 5 payments and 0 journal entries platform-wide, so NULL is a true
statement about all of them rather than a placeholder. Whether they post
retroactively is a separate decision.

Additive and idempotent via env.py's `op.add_column` wrapper; the FK follows
r153/r154's DROP-IF-EXISTS+ADD idiom (Postgres has no ADD ... IF NOT EXISTS).
"""

import sqlalchemy as sa
from alembic import op

revision = "r155_customer_payment_journal_entry"
down_revision = "r154_recon_exception_keyword_block"
branch_labels = None
depends_on = None


_CONSTRAINT = "fk_customer_payments_journal_entry"


def upgrade() -> None:
    op.add_column(
        "customer_payments",
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
    )
    op.execute(
        f"ALTER TABLE customer_payments DROP CONSTRAINT IF EXISTS {_CONSTRAINT}"
    )
    op.execute(
        f"ALTER TABLE customer_payments ADD CONSTRAINT {_CONSTRAINT} "
        "FOREIGN KEY (journal_entry_id) REFERENCES journal_entries (id)"
    )


def downgrade() -> None:
    op.execute(
        f"ALTER TABLE customer_payments DROP CONSTRAINT IF EXISTS {_CONSTRAINT}"
    )
    op.drop_column("customer_payments", "journal_entry_id")
