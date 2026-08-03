"""Books Review Phase 2 Arc A-1b — purpose-built reconciliation exception model.

Two tables. Decided (do not re-open):
  * reconciliation_match_candidates keys to the TRANSACTION, not the exception —
    scoring produces candidates for every non-keyword transaction, so auto-committed
    matches keep the audit trail of what else was considered. The exception exists
    only for transactions that do NOT auto-commit; it reads candidates through the
    transaction.
  * reconciliation_exceptions carries identity + resolution state + a flag link, but
    NOT a copy of the transaction's match_status — the source transaction remains
    authority on whether the item is still open (queue build filters on it). No
    stored card-form discriminator: the card form derives from candidate
    presence/absence at display time.

Purpose-built rather than overloading AgentAnomaly: AgentAnomaly.agent_job_id is a
NOT NULL FK to agent_jobs, and a reconciliation exception is not produced by an agent
job — reusing it would mean fabricating a sentinel job row every run (lying to the
schema; the period_locks->agent_jobs smell, done deliberately). See A-1a report.

flag_id / chosen_candidate_id are nullable String(36) WITHOUT FK constraints here:
the flag table is Arc B (the workspace), and chosen_candidate_id avoids a circular
FK; both gain constraints when their targets land.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r148_reconciliation_exceptions"
down_revision = "r147_plaid_last_error_at"
branch_labels = None
depends_on = None

# Rejection-reason enum — the HARD gates a candidate can fail. Structured code; the
# measured value rides in rejection_detail (JSONB, e.g. {"days_diff": 6}). A NULL
# reason = a viable/proposed candidate (ranked by score). Extend via a drop-if-exists
# + recreate in a later migration if A-2 surfaces a new hard gate.
#   OUTSIDE_DATE_WINDOW / DIRECTION_MISMATCH — the current ladder's gates.
#   ALREADY_CLAIMED     — the payment-claim backstop (A-3).
#   AMOUNT_MISMATCH     — NEW with A-2's band: a candidate inside the amount band but
#                         beyond the exact-match tolerance is viable-but-rejected; the
#                         exact-amount ladder never had this gate because it keyed on
#                         exact amounts. Added now so A-2 needs no CHECK migration.
_REJECTION_CODES = (
    "'OUTSIDE_DATE_WINDOW', 'DIRECTION_MISMATCH', 'ALREADY_CLAIMED', 'AMOUNT_MISMATCH'"
)
_CAND_REASON_CK = (
    f"rejection_reason IS NULL OR rejection_reason IN ({_REJECTION_CODES})"
)


def upgrade() -> None:
    op.create_table(
        "reconciliation_match_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        # Candidates key to the TRANSACTION (not the exception) — decided.
        sa.Column("reconciliation_transaction_id", sa.String(36),
                  sa.ForeignKey("reconciliation_transactions.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("candidate_record_type", sa.String(30), nullable=False),  # customer_payment | vendor_payment
        sa.Column("candidate_record_id", sa.String(36), nullable=False),
        sa.Column("score", sa.Numeric(4, 3), nullable=False),
        sa.Column("rank", sa.Integer, nullable=False),  # 1 = best; ordering within the txn's set
        sa.Column("rejection_reason", sa.String(40), nullable=True),  # NULL = viable proposal
        sa.Column("rejection_detail", JSONB, nullable=True),  # measured value, e.g. {"days_diff": 6}
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        # A candidate payment appears at most once per transaction.
        sa.UniqueConstraint("reconciliation_transaction_id", "candidate_record_type",
                            "candidate_record_id", name="uq_recon_candidate_per_txn"),
        sa.CheckConstraint(_CAND_REASON_CK, name="ck_recon_candidate_rejection_reason"),
    )

    op.create_table(
        "reconciliation_exceptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        # The SOURCE row — authority on open/closed; queue build filters on its
        # match_status. One exception per transaction.
        sa.Column("reconciliation_transaction_id", sa.String(36),
                  sa.ForeignKey("reconciliation_transactions.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("reconciliation_run_id", sa.String(36),
                  sa.ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        # Flag/park link — the flag table lands in Arc B (workspace); no FK yet.
        sa.Column("flag_id", sa.String(36), nullable=True),
        # Resolution state (workspace record — NOT the transaction's match_status).
        sa.Column("chosen_candidate_id", sa.String(36), nullable=True),  # candidate accepted on resolve
        sa.Column("resolved", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("resolved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        # One exception per transaction (re-scoring upserts, never duplicates).
        sa.UniqueConstraint("reconciliation_transaction_id", name="uq_recon_exception_per_txn"),
    )


def downgrade() -> None:
    op.drop_table("reconciliation_exceptions")
    op.drop_table("reconciliation_match_candidates")
