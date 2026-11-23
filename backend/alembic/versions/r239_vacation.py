"""Vacation pay — Payroll 5c: the rule keys, the records, and the figures behind them

⚠️ **NOTHING HAS EVER COMPUTED A VACATION FIGURE.** Measured 2026-11-23: the
rulebook keys existed, `engine.compute_vacation_pay` and its corrected
successors were written and tested against the real register, and **no code
path in `app/` or `scripts/` called any of them.** No table, no writer, no
surface. That is why this migration is a whole data model rather than a column.

What it adds, and why each exists:

  `payroll_rule_sets.vacation_rate_truncate_dp`
      ⚠️ §11.13 asked for this directly: the 4dp TRUNCATION is the whole of the
      975.47 -> 975.46 correction and lived as a constant in the engine, so it
      was NOT effective-dated — a change would have reached backwards through
      every recomputed figure with nothing to say which rule made the old ones.
      It is the cheapest possible moment to move it: there are no stored
      vacation figures for it to reach back through.

  `payroll_rule_sets.vacation_entitlement_tiers`
      Hours by completed years of service. ⚠️ PLACEHOLDERS, status `assumed` —
      James, 2026-11-23: "the example tiers until I supply Sunnycrest's real
      list."

  `payroll_report_employees.hire_date`
      Years of service. ⚠️ **NULLABLE, AND NULL MEANS NOBODY HAS SAID.** §5: a
      column added to a populated table is nullable unless every existing row
      has been SHOWN to satisfy a value, and nobody has measured a hire date
      for any of these people. `employee_profiles.hire_date` exists but is
      keyed on platform users, which payroll employees are not.

  `payroll_vacations`            a recorded vacation: dates, hours, status
  `payroll_vacation_entitlements` a per-person override, because some
                                 allowances are set by agreement
  `payroll_prior_year_figures`   gross and hours ENTERED when the registers do
                                 not cover the prior year
  `payroll_vacation_payments`    the approved parts, which become Vac and
                                 VacBonus lines on a week's Payentry list

⚠️ **EVERY ENTERED FIGURE CARRIES A REQUIRED, NON-BLANK SOURCE.** James,
2026-11-23: an entered prior-year figure is "stored as a correction record"
with "a required source note". A number somebody typed with no account of
where it came from is the thing nobody can check a year later — the same rule
the status-change `reason` carries, for the same reason.

Revision ID: r239_vacation
Revises: r238_payroll_employee_status_changes
Create Date: 2026-11-23
"""
from alembic import op
import sqlalchemy as sa

revision = "r239_vacation"
down_revision = "r238_payroll_employee_status_changes"
branch_labels = None
depends_on = None

#: A recorded vacation's life. `scheduled` is a pick or an approved request;
#: `paid` means a payment exists; `cancelled` keeps the row rather than
#: deleting it, because "she cancelled" is a fact somebody will ask about.
VACATION_STATUSES = ("scheduled", "paid", "cancelled")


def upgrade() -> None:
    # ── the two effective-dated rule keys ────────────────────────────────
    #
    # ⚠️ SERVER DEFAULTS ARE SAFE HERE AND I CHECKED RATHER THAN ASSUMED: both
    # are the values the engine already used as constants, so every existing
    # rule set keeps behaving exactly as it did. That is §5's test — the value
    # written to existing rows is one that was already true of them, not a
    # plausible figure nobody measured.
    op.add_column("payroll_rule_sets", sa.Column(
        "vacation_rate_truncate_dp", sa.Integer(), nullable=False,
        server_default="4"))
    op.add_column("payroll_rule_sets", sa.Column(
        "vacation_entitlement_tiers", sa.JSON(), nullable=True))

    # ⚠️ NULLABLE, AND IT STAYS NULL. Nobody has measured a hire date.
    op.add_column("payroll_report_employees", sa.Column(
        "hire_date", sa.Date(), nullable=True))

    op.create_table(
        "payroll_vacations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("employee_id", sa.String(36),
                  sa.ForeignKey("payroll_report_employees.id",
                                ondelete="CASCADE"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("hours", sa.Numeric(10, 4), nullable=False),
        sa.Column("status", sa.String(16), nullable=False,
                  server_default="scheduled"),
        #: Why it is on the calendar: a union pick, or an approved request.
        sa.Column("source", sa.String(300), nullable=False),
        sa.Column("created_by_user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('scheduled', 'paid', 'cancelled')",
                           name="ck_payroll_vacation_status"),
        sa.CheckConstraint("end_date >= start_date",
                           name="ck_payroll_vacation_dates"),
        sa.CheckConstraint("hours > 0", name="ck_payroll_vacation_hours"),
        sa.CheckConstraint("length(btrim(source)) > 0",
                           name="ck_payroll_vacation_source_not_blank"),
    )
    op.create_index("ix_payroll_vacation_tenant_emp", "payroll_vacations",
                    ["tenant_id", "employee_id"])
    op.create_index("ix_payroll_vacation_tenant_start", "payroll_vacations",
                    ["tenant_id", "start_date"])

    op.create_table(
        "payroll_vacation_entitlements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("employee_id", sa.String(36),
                  sa.ForeignKey("payroll_report_employees.id",
                                ondelete="CASCADE"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("hours", sa.Numeric(10, 4), nullable=False),
        sa.Column("source", sa.String(300), nullable=False),
        sa.Column("set_by_user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("set_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("hours >= 0",
                           name="ck_payroll_vac_entitlement_hours"),
        sa.CheckConstraint("length(btrim(source)) > 0",
                           name="ck_payroll_vac_entitlement_source_not_blank"),
        # One override per person per year. A second is an EDIT, and the
        # service replaces rather than accumulating, so "what is her allowance"
        # has one answer.
        sa.UniqueConstraint("tenant_id", "employee_id", "year",
                            name="uq_payroll_vac_entitlement"),
    )

    op.create_table(
        "payroll_prior_year_figures",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("employee_id", sa.String(36),
                  sa.ForeignKey("payroll_report_employees.id",
                                ondelete="CASCADE"), nullable=False),
        #: The year the figures are ABOUT — 2025 for a 2026 vacation.
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("gross", sa.Numeric(12, 2), nullable=False),
        sa.Column("hours", sa.Numeric(10, 4), nullable=False),
        #: ⚠️ REQUIRED AND NON-BLANK. "2025 Vac Calc tab" is the whole value of
        #: the record: a typed figure whose origin nobody can name is a figure
        #: nobody can check.
        sa.Column("source", sa.String(300), nullable=False),
        sa.Column("entered_by_user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("entered_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("gross >= 0", name="ck_payroll_prior_gross"),
        sa.CheckConstraint("hours > 0", name="ck_payroll_prior_hours"),
        sa.CheckConstraint("length(btrim(source)) > 0",
                           name="ck_payroll_prior_source_not_blank"),
        sa.UniqueConstraint("tenant_id", "employee_id", "year",
                            name="uq_payroll_prior_year_figures"),
    )

    op.create_table(
        "payroll_vacation_payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("vacation_id", sa.String(36),
                  sa.ForeignKey("payroll_vacations.id", ondelete="CASCADE"),
                  nullable=False),
        #: ⚠️ **THE POSITION AMONG THE YEAR'S VACATION PAYMENTS — NOT AMONG
        #: THIS VACATION'S CHECKS.** The two are easy to conflate and I did,
        #: first writing `part_count <= 3` because the Focus offers "1, 2 or 3
        #: checks". The golden that caught it is `160 h -> 38.75 x4`: the bonus
        #: is a YEARLY total "paid in equal parts, one with each vacation
        #: payment" (§11.11), and a 160-hour entitlement is normally taken as
        #: four separate weeks. A cap of 3 would have refused the fourth.
        #:
        #: Both are stored because the cent placement is
        #: `round2(total*i/n) - round2(total*(i-1)/n)` — a part cannot be
        #: re-derived without knowing which of how many it is.
        sa.Column("part_index", sa.Integer(), nullable=False),
        sa.Column("part_count", sa.Integer(), nullable=False),
        sa.Column("week_end_date", sa.Date(), nullable=False),
        #: ⚠️ TWO SEPARATELY-ROUNDED LINES, because that is what the register
        #: pays — §3.1. Folding them into one total is the superseded form.
        sa.Column("vac_pay", sa.Numeric(12, 2), nullable=False),
        sa.Column("vac_bonus", sa.Numeric(12, 2), nullable=False),
        #: The rate this part was paid at, stored so a line can be read back
        #: without re-deriving it from figures that may since have changed.
        sa.Column("rate", sa.Numeric(12, 4), nullable=True),
        sa.Column("hours", sa.Numeric(10, 4), nullable=False),
        #: Which rule set produced it — the same discipline as
        #: `payroll_week_results.rule_set_id`, so a figure can always name its
        #: rules.
        sa.Column("rule_set_id", sa.String(36),
                  sa.ForeignKey("payroll_rule_sets.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("approved_by_user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("part_index >= 1 AND part_index <= part_count",
                           name="ck_payroll_vac_payment_part"),
        sa.CheckConstraint("part_count >= 1",
                           name="ck_payroll_vac_payment_part_count"),
        sa.UniqueConstraint("vacation_id", "part_index",
                            name="uq_payroll_vac_payment_part"),
    )
    op.create_index("ix_payroll_vac_payment_tenant_week",
                    "payroll_vacation_payments",
                    ["tenant_id", "week_end_date"])


def downgrade() -> None:
    # ⚠️ THIS DROPS RECORDED VACATIONS AND APPROVED PAY. Safe on the day it
    # ships because the tables are new and empty; not safe afterwards. Stated
    # rather than assumed — the same note r237 and r238 carry.
    op.drop_index("ix_payroll_vac_payment_tenant_week",
                  table_name="payroll_vacation_payments")
    op.drop_table("payroll_vacation_payments")
    op.drop_table("payroll_prior_year_figures")
    op.drop_table("payroll_vacation_entitlements")
    op.drop_index("ix_payroll_vacation_tenant_start",
                  table_name="payroll_vacations")
    op.drop_index("ix_payroll_vacation_tenant_emp",
                  table_name="payroll_vacations")
    op.drop_table("payroll_vacations")
    op.drop_column("payroll_report_employees", "hire_date")
    op.drop_column("payroll_rule_sets", "vacation_entitlement_tiers")
    op.drop_column("payroll_rule_sets", "vacation_rate_truncate_dp")
