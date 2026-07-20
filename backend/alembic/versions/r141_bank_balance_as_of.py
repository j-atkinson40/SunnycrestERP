"""Suite Season 1 / Session 1 — the cash wire: balances get their as-of.

The census found balances captured at link and never refreshed; now sync
refreshes them and the surface states WHEN. `balance_as_of` is the
honesty column the census's map missed (flagged per dispatch).
"""

from alembic import op
import sqlalchemy as sa

revision = "r141_bank_balance_as_of"
down_revision = "r140_quote_status_declined_to_rejected"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bank_accounts",
        sa.Column("balance_as_of", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bank_accounts", "balance_as_of")
