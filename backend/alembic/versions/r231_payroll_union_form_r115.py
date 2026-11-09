"""Payroll 4 Phase 6 — the R-115 union remittance form and its status flow.

A SECOND report beside `monthly_dues_remittance`, not a replacement (James,
2026-11-09: keep both, named distinctly). That one is built from the hours
export and says what the rules IMPLY; this one is built from the register and
says what was actually DEDUCTED. They disagree on 76 checks in a measured year,
which is exactly why both exist — the form filed with the union must state what
was taken, and the other report is how you learn whether it was right.

⚠️ **`rows` IS THE RECORD OF A FILING, NOT A CACHE OF A QUERY.** Recomputing
the table later from `payroll_checks` gives a different answer the moment an
overlapping register is imported or a check is corrected, and then nothing in
the system says what was actually sent. A form that cannot reproduce its own
filing is not a record of one.

⚠️ **`filed` IS TERMINAL.** Once a figure has gone to the union, changing the
record of what went is not an edit — it is a second filing. A correction is a
NEW form carrying `superseded_by_id` on the old one, which is also why that
column is part of the unique key: one LIVE form per month, any number of
superseded ones.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "r231_payroll_union_form_r115"
down_revision = "r230_payroll_initiation_fee_paid"
branch_labels = None
depends_on = None

HOURS = sa.Numeric(10, 4)
MONEY = sa.Numeric(12, 2)


def upgrade() -> None:
    op.create_table(
        "payroll_union_forms_r115",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("member_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_dues", MONEY, nullable=False, server_default="0"),
        sa.Column("total_hours", HOURS, nullable=False, server_default="0"),
        sa.Column("rows", sa.JSON(), nullable=False),
        sa.Column("superseded_by_id", sa.String(36), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("filed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "year", "month", "superseded_by_id",
                            name="uq_payroll_r115_tenant_year_month"),
        sa.CheckConstraint("status IN ('draft', 'submitted', 'filed')",
                           name="ck_payroll_r115_status"),
        sa.CheckConstraint("month >= 1 AND month <= 12",
                           name="ck_payroll_r115_month"),
    )
    op.create_index("ix_payroll_union_forms_r115_tenant_id",
                    "payroll_union_forms_r115", ["tenant_id"])
    op.create_index("ix_payroll_r115_tenant_period", "payroll_union_forms_r115",
                    ["tenant_id", "year", "month"])


def downgrade() -> None:
    op.drop_table("payroll_union_forms_r115")
