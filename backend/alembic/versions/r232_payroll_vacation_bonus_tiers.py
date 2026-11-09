"""Payroll 4 Phase 5 — the vacation bonus is a yearly total from day tiers.

James's ruling, 2026-11-09: *"the register is right and the dispatch's goldens
were wrong. Same tiers, different basis."*

The bonus is not a flat amount charged per vacation. It is a YEARLY total built
from the year's entitlement in days — 15.00 a day for days 1-5, 10.00 for 6-10,
6.00 for 11-15, nothing after — then paid in equal parts, one with each vacation
payment. Measured across a year of registers:

     40 h   5 days  ->  75.00        120 h  15 days  -> 155.00
     48 h   6 days  ->  85.00        160 h  20 days  -> 155.00
     80 h  10 days  -> 125.00

⚠️ **155.00 IS A CEILING BECAUSE THE TIERS RUN OUT, NOT BECAUSE OF A CAP RULE.**
Storing a cap would give the same number today and a different number the moment
a tier changed, with nothing to say which rule produced the old figures.

⚠️ **`vacation_bonus` IS NOT DROPPED AND NOT BACKFILLED.** It stays, and
existing rule sets keep NULL tiers, because a payroll week already calculated
under one of them must still re-derive its stored figure. NULL here means "this
rule set predates the tiers" — a real state, distinct from an empty table.
The seed adds the tiers to the new 2026-11-09 set only.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "r232_payroll_vacation_bonus_tiers"
down_revision = "r231_payroll_union_form_r115"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payroll_rule_sets",
        sa.Column("vacation_bonus_day_tiers", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payroll_rule_sets", "vacation_bonus_day_tiers")
