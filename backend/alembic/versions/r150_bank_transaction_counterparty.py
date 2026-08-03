"""Books Review Arc B B-1 — persist Plaid's structured counterparty signal.

Plaid's /transactions/sync returns `merchant_name`, `merchant_entity_id`, and a
`counterparties` array on every transaction. The sync (`_apply_fields`) flattened
`merchant_name` into the free-text `description` and dropped `merchant_entity_id` +
`counterparties` entirely. This adds three additive, nullable columns so the RAW
signal lands going forward — every day it doesn't is data that can't be recovered
without re-fetching history. Merchant→customer RESOLUTION stays deferred; this is
persistence only.

Additive columns only; backfill is not possible (the discarded structure is gone
for pre-r150 rows) and not attempted.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r150_bank_transaction_counterparty"
down_revision = "r149_reconciliation_payment_claims"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bank_transactions", sa.Column("merchant_name", sa.String(255), nullable=True))
    op.add_column("bank_transactions", sa.Column("merchant_entity_id", sa.String(64), nullable=True))
    op.add_column("bank_transactions", sa.Column("counterparties", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("bank_transactions", "counterparties")
    op.drop_column("bank_transactions", "merchant_entity_id")
    op.drop_column("bank_transactions", "merchant_name")
