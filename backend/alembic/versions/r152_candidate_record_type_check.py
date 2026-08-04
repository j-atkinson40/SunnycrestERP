"""Books Review Arc B B-5 — bound candidate_record_type with a CHECK.

`reconciliation_match_candidates.candidate_record_type` was String(30) with no
constraint. B-5 adds `payment_group` (a one-to-many combined candidate), and that
is the moment to bound the column rather than let it drift the way `match_status`
did (nine undocumented values). CHECK over the known set; extend it deliberately
in a migration when a new candidate kind appears.

Known values: customer_payment / vendor_payment (the payment pool), invoice /
vendor_bill (the open-balance fallback, A-2), payment_group (B-5 one-to-many).
"""

from alembic import op

revision = "r152_candidate_record_type_check"
down_revision = "r151_reconciliation_flags"
branch_labels = None
depends_on = None

_TYPES = "'customer_payment', 'vendor_payment', 'invoice', 'vendor_bill', 'payment_group'"


def upgrade() -> None:
    # Idempotent (drop-if-exists + add), matching r149's CHECK pattern.
    op.execute(
        "ALTER TABLE reconciliation_match_candidates "
        "DROP CONSTRAINT IF EXISTS ck_recon_candidate_record_type"
    )
    op.execute(
        "ALTER TABLE reconciliation_match_candidates "
        "ADD CONSTRAINT ck_recon_candidate_record_type "
        f"CHECK (candidate_record_type IN ({_TYPES}))"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE reconciliation_match_candidates "
        "DROP CONSTRAINT IF EXISTS ck_recon_candidate_record_type"
    )
