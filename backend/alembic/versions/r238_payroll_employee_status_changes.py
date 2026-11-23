"""payroll_employee_status_changes — who set a status, when, and from what

⚠️ **r234 ADDED THE STATUS COLUMNS AND NOTHING COULD EVER WRITE THEM.**
Measured on production 2026-11-21: **0 of 30** employees carry a value. Two
production readers depend on them —

  * `r115_form` line 1, which falls back to counting checks and says so;
  * `roster_coverage`, whose `if status in EXCUSED_STATUSES: continue` has
    therefore **never once been taken**, so Staring is flagged every week —
    the exact outcome the 2026-11-10 ruling asked to prevent.

That is CLAUDE.md §11's complete-machinery-behind-an-unprovisioned-entrance,
and the entrance is what this migration opens.

⚠️ **A CHANGE IS A RECORD, NOT AN OVERWRITE** (James, 2026-11-21). A status
decides whether somebody counts on a form filed with a union, so "who said
they left, and when did they say it" has to survive the next edit. The two
columns on `payroll_report_employees` stay as the CURRENT value every reader
already uses; this table is the history behind them, and both are written in
one transaction.

⚠️ **NO BACKFILL, AND NONE IS POSSIBLE.** There are no prior statuses to
record — the columns have never held a value. Inventing history rows from
last-check dates would assert leaving dates nobody measured; a last check is
not a leaving date, which is the whole reason James is looking them up in
Payentry.

Revision ID: r238_payroll_employee_status_changes
Revises: r237_outgoing_copies
Create Date: 2026-11-21
"""
from alembic import op
import sqlalchemy as sa

revision = "r238_payroll_employee_status_changes"
down_revision = "r237_outgoing_copies"
branch_labels = None
depends_on = None

#: Kept in step with `roster_coverage.EXCUSED_STATUSES` plus `active`.
#: ⚠️ `active` is a STATUS somebody chose, distinct from NULL, which means
#: "nobody has said". The r115 line-1 rule turns on that distinction.
STATUSES = ("active", "left", "workers_comp", "leave")


def upgrade() -> None:
    op.create_table(
        "payroll_employee_status_changes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "employee_id", sa.String(36),
            sa.ForeignKey("payroll_report_employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # The new state.
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("since", sa.Date(), nullable=False),
        # ⚠️ THE STATE IT REPLACED, STORED RATHER THAN DERIVED. Reconstructing
        # "what did it used to be" by walking the table in order works until a
        # row is deleted or two land in the same millisecond. The row carries
        # its own before-and-after so it can be read alone.
        sa.Column("previous_status", sa.String(32), nullable=True),
        sa.Column("previous_since", sa.Date(), nullable=True),
        # ⚠️ REQUIRED. A status change with no reason is the thing somebody
        # queries a year later and cannot act on — see `outgoing_copies`'
        # `sent_how`, refused for the same reason.
        sa.Column("reason", sa.String(300), nullable=False),
        sa.Column(
            "changed_by_user_id", sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('active', 'left', 'workers_comp', 'leave')",
            name="ck_payroll_employee_status_change_status",
        ),
        sa.CheckConstraint(
            "length(btrim(reason)) > 0",
            name="ck_payroll_employee_status_change_reason_not_blank",
        ),
    )
    op.create_index("ix_payroll_emp_status_change_employee",
                    "payroll_employee_status_changes",
                    ["employee_id", "changed_at"])
    op.create_index("ix_payroll_emp_status_change_tenant",
                    "payroll_employee_status_changes", ["tenant_id"])


def downgrade() -> None:
    # ⚠️ THIS DROPS THE RECORD OF WHO SAID SOMEBODY LEFT. Safe on the day it
    # ships because the table is new and empty; not safe afterwards. Stated
    # rather than assumed — the same note `r237` carries.
    op.drop_index("ix_payroll_emp_status_change_tenant",
                  table_name="payroll_employee_status_changes")
    op.drop_index("ix_payroll_emp_status_change_employee",
                  table_name="payroll_employee_status_changes")
    op.drop_table("payroll_employee_status_changes")
