"""Books Review Phase 2 Arc A-3 — the durable payment-claim table.

A-2 derived "is this payment already reconciled?" from existing auto_cleared
transactions. A-3 makes it a first-class, DB-enforced fact:

  * reconciliation_payment_claims with UNIQUE(payment_id) — a payment (customer
    OR vendor) can be claimed by AT MOST ONE reconciliation transaction. This is
    the concurrency guard: two runs racing to clear the same payment resolve at
    the database, not in application memory. The loser catches the UNIQUE
    violation and records ALREADY_CLAIMED — it does NOT swallow-and-proceed.
  * The claim cascades from the transaction (ondelete=CASCADE): deleting a
    reconciliation transaction releases its claim, so the payment is matchable
    again.

BACKFILL: every existing auto_cleared transaction that matched a payment gets a
claim row (ON CONFLICT DO NOTHING), so a re-run after this deploy does not
re-claim a payment that a prior run already cleared. If historical data already
double-cleared a payment (the very bug A-2/A-3 close), only the first row wins
the claim; the rest are left as-is (historical, untouched).

Also extends the r148 candidate rejection-reason CHECK with PERIOD_LOCKED — an
exact payment match whose transaction date falls in a locked accounting period
is viable-but-gated: recorded as a candidate, never auto-committed.
"""

from alembic import op
import sqlalchemy as sa

revision = "r149_reconciliation_payment_claims"
down_revision = "r148_reconciliation_exceptions"
branch_labels = None
depends_on = None

# The r148 codes + PERIOD_LOCKED (A-3). Kept as a literal so the CHECK alter and
# the ORM model (app/models/financial_account.py) stay in lockstep.
_CODES_R149 = (
    "'OUTSIDE_DATE_WINDOW', 'DIRECTION_MISMATCH', 'ALREADY_CLAIMED', "
    "'AMOUNT_MISMATCH', 'PERIOD_LOCKED'"
)
_CODES_R148 = (
    "'OUTSIDE_DATE_WINDOW', 'DIRECTION_MISMATCH', 'ALREADY_CLAIMED', 'AMOUNT_MISMATCH'"
)


def _set_candidate_check(codes: str) -> None:
    # DROP IF EXISTS + ADD is idempotent (re-run replaces the constraint).
    op.execute(
        "ALTER TABLE reconciliation_match_candidates "
        "DROP CONSTRAINT IF EXISTS ck_recon_candidate_rejection_reason"
    )
    op.execute(
        "ALTER TABLE reconciliation_match_candidates "
        "ADD CONSTRAINT ck_recon_candidate_rejection_reason "
        f"CHECK (rejection_reason IS NULL OR rejection_reason IN ({codes}))"
    )


def upgrade() -> None:
    op.create_table(
        "reconciliation_payment_claims",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("payment_type", sa.String(30), nullable=False),  # customer_payment | vendor_payment
        sa.Column("payment_id", sa.String(36), nullable=False),
        # The transaction that holds the claim. CASCADE: deleting it frees the payment.
        sa.Column("reconciliation_transaction_id", sa.String(36),
                  sa.ForeignKey("reconciliation_transactions.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("reconciliation_run_id", sa.String(36),
                  sa.ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        # THE guard: one claim per payment. The race loser trips this.
        sa.UniqueConstraint("payment_id", name="uq_recon_payment_claim_payment_id"),
    )

    # Extend the candidate CHECK with PERIOD_LOCKED.
    _set_candidate_check(_CODES_R149)

    # Backfill claims from existing auto_cleared payment matches. ON CONFLICT
    # DO NOTHING: a historical double-clear yields ONE claim (first wins), the
    # rest are left untouched. gen_random_uuid() is built in on PG13+.
    op.execute(
        """
        INSERT INTO reconciliation_payment_claims
            (id, tenant_id, payment_type, payment_id,
             reconciliation_transaction_id, reconciliation_run_id, created_at)
        SELECT gen_random_uuid()::text, t.tenant_id, t.matched_record_type,
               t.matched_record_id, t.id, t.reconciliation_run_id, now()
        FROM reconciliation_transactions t
        WHERE t.match_status = 'auto_cleared'
          AND t.matched_record_id IS NOT NULL
          AND t.matched_record_type IN ('customer_payment', 'vendor_payment')
        ON CONFLICT (payment_id) DO NOTHING
        """
    )


def downgrade() -> None:
    _set_candidate_check(_CODES_R148)
    op.drop_table("reconciliation_payment_claims")
