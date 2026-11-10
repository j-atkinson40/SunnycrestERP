"""Payroll 3 — hours in: imports, raw hour lines, punches, name aliases, shifts.

`payroll_week_lines` holds the INTERPRETATION a calculation reads — hours in
buckets. These hold what the files actually said, per line, immutable, so a
week's figures stay defensible: "this is what Payentry's report printed" is the
only thing that settles a disagreement about a bucket.

⚠️ **CORRECTIONS ARE NEW RECORDS, NEVER EDITS.** An import batch is identified
by the sha256 of its bytes, which is the only reliable way to tell "they
uploaded the same file again" from "they uploaded a corrected file" — the
filename cannot, because Payentry stamps a fresh timestamp into every
regenerated report.

⚠️ **`payroll_punches` HAS NO COORDINATE COLUMNS AND THAT IS THE DESIGN**
(James, 2026-11-10): payroll does not use them and holding location history on
thirty people is a liability for no benefit. One boolean, `has_location`,
records that a punch came from a phone rather than the kiosk. There is
deliberately no latitude, longitude, accuracy or IP column for one to be
written into later.

⚠️ **`payroll_punches.emp_id` IS NULLABLE ON PURPOSE.** The punch export
carries no employee number, only a name, and Payentry spells one real name
"Micheal". A name that cannot be matched exactly after normalising leaves
emp_id NULL and raises a finding; a person's answer is stored in
`payroll_name_aliases`. Nothing is fuzzy-matched silently.

Chains off r232.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "r233_payroll_hours_in"
down_revision = "r232_payroll_vacation_bonus_tiers"
branch_labels = None
depends_on = None

HOURS = sa.Numeric(10, 4)


def upgrade() -> None:
    op.create_table(
        "payroll_hours_imports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("week_end_date", sa.Date(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rows_parsed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("source_kind IN ('employee_hours', 'punch_location')",
                           name="ck_payroll_hours_import_kind"),
    )
    op.create_index("ix_payroll_hours_imports_tenant_id",
                    "payroll_hours_imports", ["tenant_id"])
    op.create_index("ix_payroll_hours_import_tenant_week",
                    "payroll_hours_imports", ["tenant_id", "week_end_date"])

    op.create_table(
        "payroll_hours_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("import_id", sa.String(36),
                  sa.ForeignKey("payroll_hours_imports.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("week_end_date", sa.Date(), nullable=False),
        sa.Column("emp_id", sa.String(32), nullable=False),
        sa.Column("name", sa.String(160), nullable=False, server_default=""),
        sa.Column("home_dept", sa.String(16), nullable=True),
        sa.Column("worked_dept", sa.String(16), nullable=True),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("pay_type", sa.String(16), nullable=False),
        # ⚠️ SIGNED and NOT constrained positive. The automatic lunch
        # deduction prints as -0.50 and a 0.00 line is real; both are stored
        # exactly as printed. 36 hours-only lines in the real register's
        # sibling report carry hours with no money at all.
        sa.Column("hours", HOURS, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_payroll_hours_lines_tenant_id",
                    "payroll_hours_lines", ["tenant_id"])
    op.create_index("ix_payroll_hours_line_import", "payroll_hours_lines",
                    ["import_id"])
    op.create_index("ix_payroll_hours_line_tenant_week_emp", "payroll_hours_lines",
                    ["tenant_id", "week_end_date", "emp_id"])

    op.create_table(
        "payroll_punches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("import_id", sa.String(36),
                  sa.ForeignKey("payroll_hours_imports.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("week_end_date", sa.Date(), nullable=False),
        sa.Column("emp_id", sa.String(32), nullable=True),
        sa.Column("person_name", sa.String(160), nullable=False),
        sa.Column("dept", sa.String(32), nullable=True),
        sa.Column("punch_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("has_location", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("origin", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_payroll_punches_tenant_id", "payroll_punches", ["tenant_id"])
    op.create_index("ix_payroll_punch_tenant_week", "payroll_punches",
                    ["tenant_id", "week_end_date"])
    op.create_index("ix_payroll_punch_tenant_name_at", "payroll_punches",
                    ["tenant_id", "person_name", "punch_at"])

    op.create_table(
        "payroll_name_aliases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("normalised_name", sa.String(160), nullable=False),
        sa.Column("raw_name", sa.String(160), nullable=False),
        sa.Column("emp_id", sa.String(32), nullable=False),
        sa.Column("confirmed_by_user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "normalised_name",
                            name="uq_payroll_name_alias_tenant_name"),
    )
    op.create_index("ix_payroll_name_aliases_tenant_id",
                    "payroll_name_aliases", ["tenant_id"])

    op.create_table(
        "payroll_shift_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dept_code", sa.String(16), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("shift_start", sa.String(5), nullable=False),
        sa.Column("shift_end", sa.String(5), nullable=False),
        sa.Column("status", sa.String(32), nullable=False,
                  server_default="default_unconfirmed"),
        sa.Column("source", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "dept_code", "effective_date",
                            name="uq_payroll_shift_rule_tenant_dept_date"),
    )
    op.create_index("ix_payroll_shift_rules_tenant_id",
                    "payroll_shift_rules", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("payroll_shift_rules")
    op.drop_table("payroll_name_aliases")
    op.drop_table("payroll_punches")
    op.drop_table("payroll_hours_lines")
    op.drop_table("payroll_hours_imports")
