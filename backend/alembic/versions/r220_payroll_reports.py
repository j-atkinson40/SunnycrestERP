"""Weekly payroll reports — six tables for the union dues module.

Dispatch (James, 2026-11-03): replace the accountant's Excel workbook for weekly
union dues reporting. Reporting only — this does not run payroll and does not
touch the planned Check integration. Spec: docs/specs/payroll-reports.md

### Purely additive

Six new tables, no change to any existing table, no backfill, no data written.
Nothing in accounting, the reconciliation payroll bucket, or the anomaly tables
is touched — `reconciliation_gl.payroll` remains the deliberately-unmapped
classification it was, and is unrelated to this module beyond sharing a word.

### What is nullable, and why

⚠️ **NO COLUMN HERE ASSERTS A VALUE NOBODY MEASURED** (CLAUDE.md §5, "a
migration must leave 'not established' distinguishable from a measured value").
Because the tables are new and empty, every default below applies only to rows
this module itself creates — but three columns are nullable on semantics rather
than convenience, and collapsing any of them would change answers:

    payroll_rates.ot_rate              NULL means "derive as reg_rate * 1.5".
                                       A typed value means "the workbook typed
                                       this". In week 44, NINE of thirteen
                                       members carry a typed OT rate that is NOT
                                       1.5x, and the two cases produce different
                                       dues. Storing a computed 1.5x in place of
                                       NULL would be a plausible value that
                                       silently destroys the distinction — the
                                       exact shape §5 warns about.

    payroll_report_employees
        .union_join_date               A member whose join date was never
                                       recorded did not join today.

    payroll_weeks.source_file_hash     A week keyed in by hand has no source
                                       file; a sentinel would assert one.

`payroll_week_lines` hour and amount columns default to 0 rather than NULL
because an absent column in a payroll export means "no hours of this kind",
which IS a measurement — the export enumerates every category for every
employee. That is a claim about the export format and is recorded here so it can
be revisited if a real Payentry sample disagrees; the parser is deliberately
unwritten pending that sample (spec §7.4).

### What each FK does on DELETE, both halves

⚠️ **STATED BECAUSE A CONSTRAINT DEFINES BEHAVIOUR ON DELETE AS WELL AS ON
INSERT** (CLAUDE.md §5). Taking the `ON DELETE` default silently is how a delete
that used to work starts raising.

    tenant_id -> companies.id            ON DELETE CASCADE
        A purged tenant takes its payroll rows with it. Matches the cascade
        other tenant-scoped columns use, so a company delete is not newly
        blocked by this module.

    employee_id -> payroll_report_employees.id   ON DELETE CASCADE
    week_id     -> payroll_weeks.id              ON DELETE CASCADE
        Children follow their parent.

    approved_by -> users.id              ON DELETE NO ACTION  (the default,
                                         chosen deliberately)
        ⚠️ THE OTHER HALF: deleting a user who approved a payroll week now
        RAISES until that week is gone. That is intended — an approval that
        silently lost its approver is not an audit trail — and it matches the
        dominant convention here (195 of 284 FKs to `users.id` are NO ACTION;
        69 are SET NULL, 20 CASCADE). The cost is that any routine deleting
        users must clear payroll weeks first, so `tests/_cleanup.py` was
        extended in the same change, with the payroll statements ordered before
        its users delete. Verified both directions: deleting the user first
        raises `payroll_weeks_approved_by_fkey`, and the helper's order
        completes.

### Rate precision is load-bearing

`payroll_rates.reg_rate` / `ot_rate` are Numeric(12, 4), not (12, 2). The
workbook's typed OT rates run to three decimals — 35.835, 36.585, 32.535 — and
Numeric(12, 2) would TRUNCATE them on write, with no error, making every dues
figure on this tenant wrong by a little. Hours are Numeric(10, 4) for the same
reason (31.57, 7.68, 12.8, and room for a third decimal).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "r220_payroll_reports"
down_revision = "r219_capture_held_words"
branch_labels = None
depends_on = None


HOURS = sa.Numeric(10, 4)
MONEY = sa.Numeric(12, 2)
RATE = sa.Numeric(12, 4)


def upgrade() -> None:
    op.create_table(
        "payroll_report_employees",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("payentry_file_number", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("dept", sa.String(64), nullable=True),
        sa.Column("is_union_member", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("union_join_date", sa.Date(), nullable=True),
        sa.Column("initiation_fee_due", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "payentry_file_number",
                            name="uq_payroll_employee_tenant_file_number"),
    )
    op.create_index("ix_payroll_report_employees_tenant_id",
                    "payroll_report_employees", ["tenant_id"])
    op.create_index("ix_payroll_employee_tenant_active",
                    "payroll_report_employees", ["tenant_id", "active"])

    op.create_table(
        "payroll_rates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "employee_id", sa.String(36),
            sa.ForeignKey("payroll_report_employees.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("reg_rate", RATE, nullable=False),
        # NULL = derive as reg_rate * 1.5. See module docstring.
        sa.Column("ot_rate", RATE, nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("employee_id", "effective_date",
                            name="uq_payroll_rate_employee_effective"),
    )
    op.create_index("ix_payroll_rates_employee_id", "payroll_rates", ["employee_id"])
    op.create_index("ix_payroll_rate_employee_effective",
                    "payroll_rates", ["employee_id", "effective_date"])

    op.create_table(
        "payroll_rule_sets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("dues_pct", sa.Numeric(8, 6), nullable=False, server_default="0.0145"),
        sa.Column("dues_cap_multiplier", sa.Numeric(8, 6), nullable=False,
                  server_default="0.6461"),
        sa.Column("dues_per_hour", sa.Numeric(8, 4), nullable=False, server_default="0.02"),
        sa.Column("initiation_fee", MONEY, nullable=False, server_default="10.00"),
        sa.Column("vacation_increment", sa.Numeric(8, 4), nullable=False,
                  server_default="0.65"),
        sa.Column("vacation_bonus", MONEY, nullable=False, server_default="75.00"),
        sa.Column("stonebucks_per_ton", MONEY, nullable=False, server_default="11.00"),
        # Flags because the workbook's sick-time asymmetry is under review, not
        # because it is optional. Defaults reproduce the workbook. Spec §7.2.
        sa.Column("sick_in_dues_wage", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sick_in_dues_hours", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("remittance_group_by", sa.String(16), nullable=False,
                  server_default="week_end_date"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "effective_date",
                            name="uq_payroll_rule_set_tenant_effective"),
        sa.CheckConstraint("remittance_group_by IN ('week_end_date', 'check_date')",
                           name="ck_payroll_rule_set_remittance_group_by"),
    )
    op.create_index("ix_payroll_rule_sets_tenant_id", "payroll_rule_sets", ["tenant_id"])

    op.create_table(
        "payroll_weeks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id", sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column("week_end_date", sa.Date(), nullable=False),
        sa.Column("check_date", sa.Date(), nullable=False),
        sa.Column("source_file_hash", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="imported"),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "week_end_date",
                            name="uq_payroll_week_tenant_week_end"),
        sa.CheckConstraint("status IN ('imported', 'calculated', 'approved')",
                           name="ck_payroll_week_status"),
    )
    op.create_index("ix_payroll_weeks_tenant_id", "payroll_weeks", ["tenant_id"])
    op.create_index("ix_payroll_week_tenant_status", "payroll_weeks", ["tenant_id", "status"])
    op.create_index("ix_payroll_week_tenant_check_date",
                    "payroll_weeks", ["tenant_id", "check_date"])

    op.create_table(
        "payroll_week_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "week_id", sa.String(36),
            sa.ForeignKey("payroll_weeks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "employee_id", sa.String(36),
            sa.ForeignKey("payroll_report_employees.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("reg_hrs", HOURS, nullable=False, server_default="0"),
        sa.Column("ny_covid_hrs", HOURS, nullable=False, server_default="0"),
        sa.Column("ot_hrs", HOURS, nullable=False, server_default="0"),
        sa.Column("ot2_hrs", HOURS, nullable=False, server_default="0"),
        sa.Column("personal_hrs", HOURS, nullable=False, server_default="0"),
        sa.Column("sick_hrs", HOURS, nullable=False, server_default="0"),
        sa.Column("bereavement_hrs", HOURS, nullable=False, server_default="0"),
        # Stored, and NOT a dues input as specified. Spec §7.5 open question.
        sa.Column("winter_hrs", HOURS, nullable=False, server_default="0"),
        sa.Column("vac_hrs", HOURS, nullable=False, server_default="0"),
        sa.Column("stonebucks_amt", MONEY, nullable=False, server_default="0.00"),
        sa.Column("misc_amt", MONEY, nullable=False, server_default="0.00"),
        sa.Column("vac_amt", MONEY, nullable=False, server_default="0.00"),
        # Stored, and NOT a dues input as specified. Spec §7.5 open question.
        sa.Column("weeks_pay", MONEY, nullable=False, server_default="0.00"),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                  comment="The original import row, verbatim. The parsed columns "
                          "are an interpretation; this is the evidence."),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("week_id", "employee_id",
                            name="uq_payroll_week_line_week_employee"),
    )
    op.create_index("ix_payroll_week_lines_week_id", "payroll_week_lines", ["week_id"])
    op.create_index("ix_payroll_week_line_employee", "payroll_week_lines", ["employee_id"])

    op.create_table(
        "payroll_week_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "week_id", sa.String(36),
            sa.ForeignKey("payroll_weeks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "employee_id", sa.String(36),
            sa.ForeignKey("payroll_report_employees.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("report_key", sa.String(64), nullable=False),
        sa.Column("values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rule_set_id", sa.String(36),
                  sa.ForeignKey("payroll_rule_sets.id"), nullable=False),
        sa.Column("rate_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                  comment="The payroll_rates rows this result resolved through, so a "
                          "figure stays reproducible after rates move on."),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("week_id", "employee_id", "report_key",
                            name="uq_payroll_week_result_week_employee_report"),
    )
    op.create_index("ix_payroll_week_results_week_id", "payroll_week_results", ["week_id"])
    op.create_index("ix_payroll_week_result_week_report",
                    "payroll_week_results", ["week_id", "report_key"])


def downgrade() -> None:
    # Reverse creation order — children before parents.
    op.drop_table("payroll_week_results")
    op.drop_table("payroll_week_lines")
    op.drop_table("payroll_weeks")
    op.drop_table("payroll_rule_sets")
    op.drop_table("payroll_rates")
    op.drop_table("payroll_report_employees")
