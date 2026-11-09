"""Payroll 4 Phase 1 — the register: checks, their lines, and the import record.

What was actually PAID. `payroll_weeks` holds the HOURS export (what we are
about to pay); these hold the Payentry Payroll Register (the checks it issued).
Separate tables rather than one with a flag, because only one of them is
authoritative about money that left the building.

⚠️ **THE UNIQUE KEY IS (tenant, check number, check date, employee id).** The
number alone is not unique: off-cycle checks are first-class and a person can
hold more than one check on the same date. The natural way to use this is to
pull a fresh year from Payentry and upload it, so a second upload of an
overlapping range must change nothing — a dues figure that doubled because a
register was uploaded twice is the failure that matters here.

⚠️ **`ChSup1` AND `Garn` ROWS LIVE IN `payroll_check_lines` AND NOWHERE ELSE.**
Child support and garnishment must be imported or a check's deduction total
will not add up, and they must never leave the payroll area. The restriction is
at the surfaces, not in the schema; `SENSITIVE_DEDUCTION_CODES` names the codes
and `tests/test_sensitive_deduction_codes.py` holds the line.

The register PDF itself is NOT stored — only `filename`, for tracing an import
back to a download. Keeping the document would be a second copy of the most
sensitive file the tenant has.

Chains off r227 per James's ruling. Checked for a single head before opening
the PR; if the capture session's own r228 has landed by then, this re-points.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "r228_payroll_register_checks"
down_revision = "r227_tenant_invite_email_template"
branch_labels = None
depends_on = None

HOURS = sa.Numeric(10, 4)
MONEY = sa.Numeric(12, 2)
RATE = sa.Numeric(12, 4)


def upgrade() -> None:
    op.create_table(
        "payroll_register_imports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploaded_by_user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("pages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checks_parsed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checks_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checks_duplicate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checks_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary_blocks_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_payroll_register_imports_tenant_id",
                    "payroll_register_imports", ["tenant_id"])

    op.create_table(
        "payroll_checks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("import_id", sa.String(36),
                  sa.ForeignKey("payroll_register_imports.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("emp_id", sa.String(32), nullable=False),
        sa.Column("person", sa.String(160), nullable=False, server_default=""),
        sa.Column("check_number", sa.String(32), nullable=False),
        sa.Column("check_date", sa.Date(), nullable=False),
        sa.Column("check_type", sa.String(32), nullable=True),
        sa.Column("batch", sa.String(32), nullable=True),
        sa.Column("net", MONEY, nullable=True),
        sa.Column("base_rate", RATE, nullable=True),
        sa.Column("printed_total_earnings", MONEY, nullable=True),
        sa.Column("printed_total_hours", HOURS, nullable=True),
        sa.Column("printed_total_deductions", MONEY, nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "check_number", "check_date", "emp_id",
                            name="uq_payroll_check_tenant_number_date_emp"),
    )
    op.create_index("ix_payroll_checks_tenant_id", "payroll_checks", ["tenant_id"])
    op.create_index("ix_payroll_check_tenant_date", "payroll_checks",
                    ["tenant_id", "check_date"])
    op.create_index("ix_payroll_check_tenant_emp", "payroll_checks",
                    ["tenant_id", "emp_id"])

    op.create_table(
        "payroll_check_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("check_id", sa.String(36),
                  sa.ForeignKey("payroll_checks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("description", sa.String(160), nullable=False, server_default=""),
        sa.Column("hours", HOURS, nullable=True),
        sa.Column("rate", RATE, nullable=True),
        # ⚠️ NOT constrained to be positive. A reimbursement is printed as a
        # NEGATIVE deduction — 105 lines across the measured year. A positivity
        # check here would reject real register rows, and storing the absolute
        # value would overstate total deductions by twice the reimbursement.
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("kind IN ('earning', 'tax', 'deduction')",
                           name="ck_payroll_check_line_kind"),
    )
    op.create_index("ix_payroll_check_lines_tenant_id", "payroll_check_lines", ["tenant_id"])
    op.create_index("ix_payroll_check_line_check", "payroll_check_lines", ["check_id"])
    op.create_index("ix_payroll_check_line_tenant_kind_code", "payroll_check_lines",
                    ["tenant_id", "kind", "code"])


def downgrade() -> None:
    op.drop_table("payroll_check_lines")
    op.drop_table("payroll_checks")
    op.drop_table("payroll_register_imports")
