"""D-11 U-2 — the vocabulary unifies: declined → rejected (conditional no-op).

The investigation's census found ZERO rows carrying either word in any
environment; this migration proves the no-op live with its own census
line, and stands ready if a stray row appeared between census and ship.
Reversible in the mechanical sense (rejected→declined would also touch
rows that were born "rejected" legitimately — the downgrade is a no-op
by design; the alias mapping is one-way vocabulary healing).
"""

from alembic import op
import sqlalchemy as sa

revision = "r140_quote_status_declined_to_rejected"
down_revision = "r139_quote_tax_reason"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    count = conn.execute(
        sa.text("SELECT count(*) FROM quotes WHERE status = 'declined'")
    ).scalar()
    print(f"[r140 census] quotes with status='declined': {count} "
          f"({'mapping to rejected' if count else 'no-op proven'})")
    if count:
        conn.execute(
            sa.text("UPDATE quotes SET status = 'rejected' WHERE status = 'declined'")
        )


def downgrade() -> None:
    # Deliberate no-op: born-rejected rows are indistinguishable from
    # mapped ones, and the census said zero existed anyway.
    pass
