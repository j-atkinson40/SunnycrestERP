"""customer_payments.returned_at + returned_reason — a returned payment is a
state the row could not previously express.

N-1+2. `CustomerPayment` had 28 columns and none of them state: a payment was
alive or `deleted_at`, nothing else. That is enough while the only way to undo
one is a VOID, which says "this should never have been recorded" and erases the
row. It is not enough for a RETURNED payment, which says "this happened and the
bank took it back" — the attempt is exactly what you want visible when the same
customer's cheque bounces twice.

WHY BOTH TREATMENTS NEED THIS, correcting the investigation's own framing:
the report said Treatment A (reverse the payment) needed no schema and B
(separate entry) did. That was wrong. Ruling out the soft-delete for A means a
reversed payment carries NO mark — and `void_payment` does not delete the
application rows either, it only adjusts the invoices they point at. Without a
marker the row would sit there looking like a live, applied payment while the
invoices no longer reflect it: actively misleading, not merely unmarked. The
schema cost does not separate the two treatments.

No backfill. Every existing payment is not-returned, which is what NULL says.
"""
from alembic import op
import sqlalchemy as sa

revision = "r156_customer_payment_returned"
down_revision = "r155_customer_payment_journal_entry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customer_payments",
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "customer_payments",
        sa.Column("returned_reason", sa.Text(), nullable=True),
    )
    # Returned payments are a small minority and are always read AS a set
    # ("what came back this month", "has this customer bounced before"), so the
    # index is partial on the state rather than covering the whole table.
    op.create_index(
        "ix_customer_payments_returned",
        "customer_payments",
        ["company_id", "returned_at"],
        postgresql_where=sa.text("returned_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_customer_payments_returned", table_name="customer_payments")
    op.drop_column("customer_payments", "returned_reason")
    op.drop_column("customer_payments", "returned_at")
