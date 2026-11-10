"""Payroll 3 — why a person with no hours this week is not a problem.

The roster coverage check asks: every hourly person paid in the last four
registers either has hours this week, or a recorded reason. Without somewhere
to record the reason, the check flags the same people every week and is
switched off within a fortnight.

⚠️ **NULL IS NOT "WORKING NORMALLY".** NULL means no reason has been recorded,
which is precisely the state the check exists to surface. `workers_comp`,
`leave` and `left` are reasons; absence is a question.

Measured need: Staring has been on workers_comp since the 2026-10-08 check, so
he appears in the last four registers with no week-44 hours. Without this he
would be flagged every week forever, and a check that cries wolf weekly stops
being read.

A separate migration from r233 rather than an edit to it: r233 is already
applied, and rewriting an applied migration to add a column is how two
databases end up disagreeing about what r233 means.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "r234_payroll_employee_status"
down_revision = "r233_payroll_hours_in"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payroll_report_employees",
                  sa.Column("payroll_status", sa.String(32), nullable=True))
    op.add_column("payroll_report_employees",
                  sa.Column("payroll_status_since", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("payroll_report_employees", "payroll_status_since")
    op.drop_column("payroll_report_employees", "payroll_status")
