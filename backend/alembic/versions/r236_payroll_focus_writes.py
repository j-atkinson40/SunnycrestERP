"""Payroll 5a — what the weekly Focus writes: hand corrections and decisions.

⚠️ **NEITHER TABLE MUTATES WHAT WAS PARSED.** `payroll_hours_lines` holds what
Payentry printed and the arc's first rule is that a stored figure must be
re-derivable from the import. A hand correction written over an hours line would
destroy the only copy of the thing being corrected, and the next re-import would
silently undo it. Both of these are append-only overlays carrying their own
attribution, in the manner `payroll_union_forms_r115` already establishes: a
correction is a new row, not an edit.

⚠️ The live-decision index is PARTIAL. One live decision per finding, any number
of superseded ones behind it — a plain unique constraint would turn a change of
mind into an integrity error.

⚠️ **AND IT KEYS ON `superseded_at`, NOT `superseded_by`.** `superseded_by` is a
foreign key to this same table, so it cannot be set until the replacement row
exists — while the replacement cannot be inserted until the old row stops being
live. Liveness has to be settable first, so it is a timestamp; the pointer is
filled in afterwards as provenance. Found by the supersede test failing with a
unique violation, which is the right way to find it.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "r236_payroll_focus_writes"
down_revision = "r235_grant_payroll_upload"
branch_labels = None
depends_on = None

HOURS = sa.Numeric(10, 4)


def upgrade() -> None:
    op.create_table(
        "payroll_hour_corrections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week_end_date", sa.Date(), nullable=False),
        sa.Column("emp_id", sa.String(32), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("pay_type", sa.String(16), nullable=False),
        sa.Column("hours", HOURS, nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("entered_by", sa.String(36),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("entered_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by", sa.String(36),
                  sa.ForeignKey("payroll_hour_corrections.id", ondelete="SET NULL"),
                  nullable=True),
        # Signed: removing hours someone did not work is as legitimate as
        # adding them. The bound catches a decimal-place slip, nothing more.
        sa.CheckConstraint("hours >= -24 AND hours <= 24",
                           name="ck_payroll_hour_correction_plausible"),
    )
    op.create_index("ix_payroll_hour_corrections_tenant_id",
                    "payroll_hour_corrections", ["tenant_id"])
    op.create_index("ix_payroll_hour_corrections_week",
                    "payroll_hour_corrections",
                    ["tenant_id", "week_end_date", "emp_id"])

    op.create_table(
        "payroll_week_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week_end_date", sa.Date(), nullable=False),
        sa.Column("finding_key", sa.String(128), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("note", sa.String(500), nullable=False, server_default=""),
        sa.Column("decided_by", sa.String(36),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by", sa.String(36),
                  sa.ForeignKey("payroll_week_decisions.id", ondelete="SET NULL"),
                  nullable=True),
    )
    op.create_index("ix_payroll_week_decisions_tenant_id",
                    "payroll_week_decisions", ["tenant_id"])
    op.create_index("ix_payroll_week_decisions_week",
                    "payroll_week_decisions", ["tenant_id", "week_end_date"])
    op.create_index("uq_payroll_week_decision_live",
                    "payroll_week_decisions",
                    ["tenant_id", "week_end_date", "finding_key"],
                    unique=True,
                    postgresql_where=sa.text("superseded_at IS NULL"))

    print("[r236] payroll_hour_corrections and payroll_week_decisions created")


def downgrade() -> None:
    op.drop_index("uq_payroll_week_decision_live", "payroll_week_decisions")
    op.drop_index("ix_payroll_week_decisions_week", "payroll_week_decisions")
    op.drop_index("ix_payroll_week_decisions_tenant_id", "payroll_week_decisions")
    op.drop_table("payroll_week_decisions")
    op.drop_index("ix_payroll_hour_corrections_week", "payroll_hour_corrections")
    op.drop_index("ix_payroll_hour_corrections_tenant_id", "payroll_hour_corrections")
    op.drop_table("payroll_hour_corrections")
