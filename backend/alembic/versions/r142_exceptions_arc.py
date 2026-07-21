"""Suite — the exceptions arc: credit memos, the write-off verb, the
credit pocket's ledger.

Three pieces of schema for money-correction verbs, all posting through
the Session-Two chokepoint at the service layer:

- `credit_memos` — the memo document (reason REQUIRED, born posted;
  creation IS issuance, mirroring the finance-charge invoice's law).
- `customer_credit_entries` — the pocket's ledger (apply/disburse rows;
  the exit door customer.credit_balance never had).
- invoices gain `amount_credited` + `written_off_amount` +
  `write_off_reason` so `balance_remaining` stays an honest derivation
  (total − paid − credited − written off) everywhere it's read.
"""

from alembic import op
import sqlalchemy as sa

revision = "r142_exceptions_arc"
down_revision = "r141_bank_balance_as_of"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_memos",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=False, index=True),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("invoices.id"), nullable=False, index=True),
        sa.Column("number", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="posted"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_credit_memos_company_number", "credit_memos", ["company_id", "number"], unique=True)

    op.create_table(
        "customer_credit_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=False, index=True),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("invoices.id"), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('apply', 'disburse')", name="ck_credit_entry_kind"),
    )

    op.add_column("invoices", sa.Column("amount_credited", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("invoices", sa.Column("written_off_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("invoices", sa.Column("write_off_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("invoices", "write_off_reason")
    op.drop_column("invoices", "written_off_amount")
    op.drop_column("invoices", "amount_credited")
    op.drop_table("customer_credit_entries")
    op.drop_index("ix_credit_memos_company_number", table_name="credit_memos")
    op.drop_table("credit_memos")
