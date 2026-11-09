"""Payroll 4 Phase 3 — per-key provenance on `payroll_rule_sets`.

James's ruling, 2026-11-09: extend `payroll_rule_sets`; do NOT add a
`payroll_rules` table.

⚠️ **NO VALUE MOVES AND NO VALUE IS COPIED.** Every rule's value stays in its
own typed column. This column answers a different question — who settled this
key, and how sure are we — which the rulebook has needed since Payroll 1,
where seven of ten values faithfully reproduced the accountant's workbook and
three were open questions, with nothing in the data to tell them apart. A
reader seeing `sick_in_dues_hours = True` could not know whether that was a
decision or a placeholder.

Statuses are `confirmed`, `measured`, `assumed`, `disputed`; `rule_provenance`
in `app/services/payroll/rules.py` validates them and requires a substantive
source, because a status with no source is indistinguishable from a confident
assumption.

Backfilled as `assumed` for every existing row and key: that is exactly what
those values were. Backfilling them as `confirmed` would have been a lie
written by a migration.
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

revision = "r229_payroll_rule_provenance"
down_revision = "r228_payroll_register_checks"
branch_labels = None
depends_on = None

#: Spelled out rather than imported from the application: a migration must keep
#: doing what it did when it ran, even after the application's list changes.
_KEYS_AT_THIS_REVISION = (
    "dues_pct", "dues_cap_multiplier", "dues_per_hour", "initiation_fee",
    "vacation_increment", "vacation_bonus", "stonebucks_per_ton",
    "sick_in_dues_wage", "sick_in_dues_hours", "remittance_group_by",
)

_BACKFILL = json.dumps({
    key: {"status": "assumed",
          "source": "the accountant's workbook, reproduced in Payroll 1; "
                    "not confirmed by anyone"}
    for key in _KEYS_AT_THIS_REVISION
})


def upgrade() -> None:
    op.add_column(
        "payroll_rule_sets",
        sa.Column("rule_provenance", sa.JSON(), nullable=False,
                  server_default=sa.text("'{}'")),
    )
    # ⚠️ Backfilled as `assumed`, which is what these values actually were.
    op.execute(
        sa.text("UPDATE payroll_rule_sets SET rule_provenance = :p "
                "WHERE rule_provenance IS NULL OR rule_provenance::text = '{}'")
        .bindparams(p=_BACKFILL)
    )


def downgrade() -> None:
    op.drop_column("payroll_rule_sets", "rule_provenance")
