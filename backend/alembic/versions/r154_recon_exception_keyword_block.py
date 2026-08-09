"""Ledger Posting arc L-2 — why a keyword row did not book, on the exception.

Before L-2 a keyword row (`bank_fee` / `payroll` / `nsf`) never reached the
Books Review queue: the ladder short-circuited, set a status, and produced
neither candidates nor an exception. L-2 makes booking the licence to clear, so
a keyword row whose GL accounts do not resolve now becomes an exception — and
that is a THIRD kind of exception, distinct from the two the queue has carried
since B-3:

    ranked  — candidates present; pick one
    coding  — no candidates; the operator must say what this is
    config  — the system KNOWS what this is; it has nowhere to book it   ← new

The third kind needs the operator to change configuration, not to code a row
item by item. Falling through to the coding card would ask the wrong question
of the wrong person, so the discriminator is persisted rather than inferred.

Two columns, both nullable — NULL on every pre-L-2 row and on every ordinary
ranked/coding exception, which is exactly the "not a config problem" reading:

  keyword_classification  bank_fee | payroll | nsf — what the ladder decided
  blocked_reason          keyword_gl_unmapped | keyword_gl_dangling
                          | contra_gl_unset | contra_gl_dangling | period_locked

No CHECK constraint on either. The vocabulary is code-fixed in
`app/services/reconciliation_gl.py` and read back by the card; a CHECK here
would pin a string set that L-3 is expected to extend, and the write path is a
single service function, not user input. (Contrast r152, which DID check
`candidate_record_type` — that column is written from several call sites.)

Also adds `reconciliation_transactions.journal_entry_id` — the link from a
cleared row to the entry it booked. Without it the arc's central claim ("the
reconciliation and the ledger agree") is unfalsifiable on real data: you could
count both sides but never join them. FK with NO ON DELETE clause, for the same
reason r153 took that position — a hard DELETE of an entry that a cleared bank
transaction points at should be REFUSED, not silently unlink the row and leave
it cleared against nothing.

Additive and idempotent via env.py's `op.add_column` wrapper. The FK follows
r153's DROP-IF-EXISTS+ADD idiom (Postgres has no ADD ... IF NOT EXISTS).
"""

import sqlalchemy as sa
from alembic import op

revision = "r154_recon_exception_keyword_block"
down_revision = "r153_financial_account_gl_fk"
branch_labels = None
depends_on = None


_JE_CONSTRAINT = "fk_recon_transactions_journal_entry"


def upgrade() -> None:
    op.add_column(
        "reconciliation_exceptions",
        sa.Column("keyword_classification", sa.String(20), nullable=True),
    )
    op.add_column(
        "reconciliation_exceptions",
        sa.Column("blocked_reason", sa.String(30), nullable=True),
    )
    op.add_column(
        "reconciliation_transactions",
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
    )
    op.execute(
        f"ALTER TABLE reconciliation_transactions DROP CONSTRAINT IF EXISTS {_JE_CONSTRAINT}"
    )
    op.execute(
        f"ALTER TABLE reconciliation_transactions ADD CONSTRAINT {_JE_CONSTRAINT} "
        "FOREIGN KEY (journal_entry_id) REFERENCES journal_entries (id)"
    )


def downgrade() -> None:
    op.execute(
        f"ALTER TABLE reconciliation_transactions DROP CONSTRAINT IF EXISTS {_JE_CONSTRAINT}"
    )
    op.drop_column("reconciliation_transactions", "journal_entry_id")
    op.drop_column("reconciliation_exceptions", "blocked_reason")
    op.drop_column("reconciliation_exceptions", "keyword_classification")
