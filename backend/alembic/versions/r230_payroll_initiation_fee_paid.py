"""Payroll 4 Phase 4 — record that an initiation fee WAS paid, and when.

Extends `payroll_report_employees`. James's ruling: extend; no second copy of
any fact.

⚠️ **THIS IS NOT A SECOND COPY OF `initiation_fee_due`.** That column is
forward-looking — charge this member a fee next time dues arise. This one is
historical: a fee was charged, on this date.

⚠️ **AND IT EXISTS BECAUSE PHASE 2 NEEDED IT AND COULD NOT HAVE IT.** Six
checks in the measured year carry dues exactly 10.00 above what the member's
own pay lines imply. Only 2 of those 6 are that member's first `Union` check
inside the register's window, so inferring the fee from "first check seen"
would charge four established members a fee they had already paid and miss
anyone whose membership began before whatever range of registers happened to
be uploaded. Membership history is a fact about a person, not a property of an
upload window.

NULLABLE, and NULL means "not established" — which is not "never paid one".
Every existing row starts NULL, because nothing in the system has ever
recorded this and a migration must not invent it.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "r230_payroll_initiation_fee_paid"
down_revision = "r229_payroll_rule_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payroll_report_employees",
        sa.Column("initiation_fee_paid_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payroll_report_employees", "initiation_fee_paid_date")
