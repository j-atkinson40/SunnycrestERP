"""Weekly payroll reports — union dues, vacation pay, stonebucks.

Reporting only. These tables record what an imported Payentry export said, what
the rules were when it was calculated, and what came out. They do not run
payroll and have no connection to the planned Check integration.

⚠️ EVERY RESULT TRACES TO ITS INPUTS AND ITS RULES. `payroll_week_result` carries
`rule_set_id` and `rate_ids`, and `payroll_week_line.raw` keeps the original
import row verbatim. A dues figure that cannot be re-derived from stored rows is
a number nobody can defend to a union auditor, which is the whole reason the
accountant's workbook is being replaced.

Spec: docs/specs/payroll-reports.md
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Hours carry 4 decimals: the workbook records quarter and hundredth hours
# (31.57, 7.68, 12.8), and 4 leaves room for a third decimal without a
# migration. Money is 2. Rates are 4 — the workbook's typed OT rates run to
# three decimals (35.835, 36.585), so Numeric(12, 2) would SILENTLY TRUNCATE
# them and every dues figure on this tenant would be wrong by a little.
HOURS = Numeric(10, 4)
MONEY = Numeric(12, 2)
RATE = Numeric(12, 4)

WEEK_STATUSES = ("imported", "calculated", "approved")


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PayrollReportEmployee(Base):
    """A person the dues reports can be about.

    Distinct from `users` and from any HR employee record on purpose: this is
    the payroll-reporting roster, keyed by the Payentry file number that arrives
    in the export. A member who leaves goes `active=False`; rows are never
    deleted, because historical weeks still reference them.
    """

    __tablename__ = "payroll_report_employees"
    __table_args__ = (
        UniqueConstraint("tenant_id", "payentry_file_number",
                         name="uq_payroll_employee_tenant_file_number"),
        Index("ix_payroll_employee_tenant_active", "tenant_id", "active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    payentry_file_number: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dept: Mapped[str | None] = mapped_column(String(64), nullable=True)

    is_union_member: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ⚠️ NULLABLE ON PURPOSE. A member whose join date was never recorded is not
    # a member who joined today, and not one who joined at epoch. NULL means
    # "not established" and stays distinguishable from a measured date
    # (CLAUDE.md §5).
    union_join_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    initiation_fee_due: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ⚠️ Payroll 4 Phase 4. A DIFFERENT FACT from `initiation_fee_due`, not a
    # second copy of it: that one is forward-looking ("charge this member a fee
    # next time dues arise"), this one records that a fee WAS charged, and when.
    #
    # It exists because Phase 2 needed it and could not have it. Six checks in
    # the measured year carry dues exactly 10.00 above what the member's pay
    # lines imply — the fee — but only 2 of the 6 are that member's first
    # `Union` check in the register's window. So "first check seen" is a wrong
    # rule: it would charge four established members a fee they had already
    # paid, and would miss anyone whose membership began before whatever range
    # of registers happened to be uploaded. Membership history is a fact about
    # the person, so it lives here and `dues_for_check` takes the answer from
    # its caller.
    #
    # NULLABLE ON PURPOSE: NULL means "not established", which is not the same
    # as "never paid one" (CLAUDE.md §5).
    initiation_fee_paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ⚠️ Payroll 3. Why a person with no hours this week is not a problem.
    # NULL means "no reason recorded", which is exactly the state the roster
    # coverage check flags — it is NOT a synonym for "working normally".
    # Measured need: Staring has been on workers_comp since the 2026-10-08
    # check, so he appears in the last four registers and has no week-44
    # hours, and without this column he would be flagged every week forever.
    #: ⚠️ **NULL MEANS NOBODY HAS SAID, AND IT IS NULL FOR EVERYONE TODAY.**
    #: Years of service drive the vacation entitlement tiers, so a missing hire
    #: date is a stated absence rather than "hired today" — `entitlement_for`
    #: refuses to guess and says which person it needs a date for.
    #:
    #: ⚠️ Declared here as well as in `r239`, because a DB column the model
    #: omits is UNREACHABLE — CLAUDE.md §5 records exactly that happening to
    #: `products.variant_template_id`, and the drift guard cannot see it in
    #: either direction.
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payroll_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payroll_status_since: Mapped[date | None] = mapped_column(Date, nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    rates = relationship(
        "PayrollRate", back_populates="employee", cascade="all, delete-orphan"
    )


#: The statuses an employee can be put into. ⚠️ `active` is a STATUS somebody
#: CHOSE; NULL is "nobody has said". The R-115's line-1 rule turns on exactly
#: that distinction, so the two must stay tellable apart.
PAYROLL_EMPLOYEE_STATUSES = ("active", "left", "workers_comp", "leave")


class PayrollEmployeeStatusChange(Base):
    """One recorded change to an employee's payroll status.

    ⚠️ **A CHANGE IS A RECORD, NOT AN OVERWRITE** (James, 2026-11-21). The
    status decides whether somebody counts on a form filed with a union, so
    "who said they left, and when did they say it" must survive the next
    edit. `payroll_report_employees.payroll_status` stays as the CURRENT
    value every existing reader uses; this is the history behind it, and the
    two are written in one transaction.

    ⚠️ **`since` IS THE DAY THE STATUS BEGAN; `changed_at` IS WHEN SOMEBODY
    TYPED IT.** They are routinely months apart — a leaver recorded in
    November who left in June — and conflating them would put the wrong date
    into the R-115's line-1 rule, which compares `since` against the month.
    """

    __tablename__ = "payroll_employee_status_changes"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'left', 'workers_comp', 'leave')",
            name="ck_payroll_employee_status_change_status",
        ),
        CheckConstraint(
            "length(btrim(reason)) > 0",
            name="ck_payroll_employee_status_change_reason_not_blank",
        ),
        Index("ix_payroll_emp_status_change_employee",
              "employee_id", "changed_at"),
        Index("ix_payroll_emp_status_change_tenant", "tenant_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False)
    employee_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("payroll_report_employees.id", ondelete="CASCADE"),
        nullable=False)

    status: Mapped[str] = mapped_column(String(32), nullable=False)
    since: Mapped[date] = mapped_column(Date, nullable=False)

    #: What it replaced, stored rather than derived — see the migration.
    previous_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    previous_since: Mapped[date | None] = mapped_column(Date, nullable=True)

    #: Required. A status change nobody explained is one nobody can act on.
    reason: Mapped[str] = mapped_column(String(300), nullable=False)

    changed_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now)


class PayrollRate(Base):
    """Effective-dated pay rates.

    ⚠️ `ot_rate` IS NULLABLE AND NULL IS A RULE, NOT A GAP. NULL means "derive
    it as reg_rate * 1.5". A typed value means "the workbook typed this", and in
    week 44 nine of thirteen members carry a typed OT rate that is NOT 1.5x. The
    two cases produce different dues, so collapsing NULL to a stored 1.5x value
    at write time would destroy the distinction and silently change answers for
    every member whose real OT rate differs.
    """

    __tablename__ = "payroll_rates"
    __table_args__ = (
        UniqueConstraint("employee_id", "effective_date",
                         name="uq_payroll_rate_employee_effective"),
        Index("ix_payroll_rate_employee_effective", "employee_id", "effective_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payroll_report_employees.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    reg_rate: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    ot_rate: Mapped[Decimal | None] = mapped_column(RATE, nullable=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    employee = relationship("PayrollReportEmployee", back_populates="rates")


class PayrollRuleSet(Base):
    """Effective-dated dues / vacation / stonebucks constants.

    Defaults reproduce the accountant's workbook. `sick_in_dues_wage`,
    `sick_in_dues_hours` and `remittance_group_by` are flags because the
    workbook's behaviour is under review, not because it is optional — see spec
    §7.2 and §7.3.
    """

    __tablename__ = "payroll_rule_sets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "effective_date",
                         name="uq_payroll_rule_set_tenant_effective"),
        CheckConstraint(
            "remittance_group_by IN ('week_end_date', 'check_date')",
            name="ck_payroll_rule_set_remittance_group_by",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)

    dues_pct: Mapped[Decimal] = mapped_column(
        Numeric(8, 6), nullable=False, default=Decimal("0.0145")
    )
    dues_cap_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(8, 6), nullable=False, default=Decimal("0.6461")
    )
    dues_per_hour: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, default=Decimal("0.02")
    )
    initiation_fee: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("10.00")
    )
    vacation_increment: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, default=Decimal("0.65")
    )
    vacation_bonus: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("75.00")
    )
    # ⚠️ Payroll 4 Phase 5. SUPERSEDES `vacation_bonus` above, which is kept
    # only so rule sets predating the tiers still reproduce their own figures.
    # The bonus is a YEARLY total built from the entitlement in days — 15.00 a
    # day for days 1-5, 10.00 for 6-10, 6.00 for 11-15, nothing after — not a
    # flat amount per vacation. 75.00 is what the tiers give for five days,
    # which is why a flat 75.00 looked correct for a year.
    #
    # NULLABLE: a NULL means "this rule set predates the tiers", which is a
    # real and different thing from an empty tier table.
    #: ⚠️ **ADDED WITH `r239`, AND DECLARED HERE TOO — I FORGOT, AND THE
    #: ENDPOINT TESTS CAUGHT IT WITH `'PayrollRuleSet' object has no attribute
    #: 'vacation_entitlement_tiers'`.** I had written the guard for exactly
    #: this two files earlier, on `hire_date`: a DB column the model omits is
    #: UNREACHABLE, and the drift guard cannot see it in either direction
    #: (CLAUDE.md §5). Knowing the rule did not stop me breaking it; the tests
    #: did, which is the argument for driving the endpoint rather than the
    #: service.
    vacation_rate_truncate_dp: Mapped[int] = mapped_column(
        Integer, nullable=False, default=4, server_default="4")
    #: Hours by completed years of service. NULL on a rule set made before 5c,
    #: which means NOBODY CHOSE — not "no vacation".
    vacation_entitlement_tiers: Mapped[list | None] = mapped_column(
        JSON, nullable=True)
    vacation_bonus_day_tiers: Mapped[list | None] = mapped_column(
        JSON, nullable=True
    )
    stonebucks_per_ton: Mapped[Decimal] = mapped_column(
        MONEY, nullable=False, default=Decimal("11.00")
    )

    sick_in_dues_wage: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sick_in_dues_hours: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    remittance_group_by: Mapped[str] = mapped_column(
        String(16), nullable=False, default="week_end_date"
    )

    #: Payroll 4 Phase 3. Per-key `{status, source}` — see
    #: `rules.rule_provenance`. ⚠️ NO VALUE LIVES HERE: every rule's value
    #: stays in its own typed column above, which is its only home. This
    #: answers "who said so, and how sure are we", which Payroll 1 could not
    #: express — seven of these ten values were the accountant's workbook
    #: reproduced faithfully and three were open questions, and nothing in the
    #: data told them apart.
    rule_provenance: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PayrollWeek(Base):
    """One imported payroll week.

    `status` is a one-way gate: imported -> calculated -> approved. Approval
    LOCKS the week; recalculating an approved week is refused at the service
    layer, not merely discouraged in the UI.
    """

    __tablename__ = "payroll_weeks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "week_end_date",
                         name="uq_payroll_week_tenant_week_end"),
        CheckConstraint(
            "status IN ('imported', 'calculated', 'approved')",
            name="ck_payroll_week_status",
        ),
        Index("ix_payroll_week_tenant_status", "tenant_id", "status"),
        Index("ix_payroll_week_tenant_check_date", "tenant_id", "check_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    week_end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # check_date = week_end_date + 5 days. Stored rather than derived because
    # the monthly remittance report can group by it, and a grouping key that is
    # recomputed on every read is a grouping key that can change under a stored
    # report.
    check_date: Mapped[date] = mapped_column(Date, nullable=False)

    # ⚠️ NULLABLE. A week entered by hand has no source file, and a sentinel
    # hash would assert a file that does not exist.
    source_file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="imported")
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    calculated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    lines = relationship(
        "PayrollWeekLine", back_populates="week", cascade="all, delete-orphan"
    )
    results = relationship(
        "PayrollWeekResult", back_populates="week", cascade="all, delete-orphan"
    )
    approver = relationship("User", foreign_keys=[approved_by])


class PayrollWeekLine(Base):
    """One employee's row from the import, verbatim plus parsed.

    ⚠️ `winter_hrs` AND `weeks_pay` ARE STORED AND ARE NOT DUES INPUTS. Neither
    appears in the dues_wage or dues_hours formula as specified. Whether
    `winter_hrs` ought to join the other hour columns in dues_hours is an open
    question (spec §7.5), pinned by a characterization test so it cannot be
    settled by accident.
    """

    __tablename__ = "payroll_week_lines"
    __table_args__ = (
        UniqueConstraint("week_id", "employee_id", name="uq_payroll_week_line_week_employee"),
        Index("ix_payroll_week_line_employee", "employee_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    week_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payroll_weeks.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payroll_report_employees.id", ondelete="CASCADE"),
        nullable=False
    )

    reg_hrs: Mapped[Decimal] = mapped_column(HOURS, nullable=False, default=Decimal("0"))
    ny_covid_hrs: Mapped[Decimal] = mapped_column(HOURS, nullable=False, default=Decimal("0"))
    ot_hrs: Mapped[Decimal] = mapped_column(HOURS, nullable=False, default=Decimal("0"))
    ot2_hrs: Mapped[Decimal] = mapped_column(HOURS, nullable=False, default=Decimal("0"))
    personal_hrs: Mapped[Decimal] = mapped_column(HOURS, nullable=False, default=Decimal("0"))
    sick_hrs: Mapped[Decimal] = mapped_column(HOURS, nullable=False, default=Decimal("0"))
    bereavement_hrs: Mapped[Decimal] = mapped_column(HOURS, nullable=False, default=Decimal("0"))
    winter_hrs: Mapped[Decimal] = mapped_column(HOURS, nullable=False, default=Decimal("0"))
    vac_hrs: Mapped[Decimal] = mapped_column(HOURS, nullable=False, default=Decimal("0"))

    stonebucks_amt: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0.00"))
    misc_amt: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0.00"))
    vac_amt: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0.00"))
    weeks_pay: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0.00"))

    # The original import row, untouched. The parsed columns above are an
    # interpretation; this is the evidence.
    raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    week = relationship("PayrollWeek", back_populates="lines")
    employee = relationship("PayrollReportEmployee")


class PayrollWeekResult(Base):
    """A computed report row, with the provenance to re-derive it.

    One row per (week, employee, report_key). `rule_set_id` and `rate_ids`
    record WHICH rules and WHICH rate rows produced `values`, so a figure
    questioned months later can be reproduced exactly even after the rules or
    the rates have moved on.
    """

    __tablename__ = "payroll_week_results"
    __table_args__ = (
        UniqueConstraint("week_id", "employee_id", "report_key",
                         name="uq_payroll_week_result_week_employee_report"),
        Index("ix_payroll_week_result_week_report", "week_id", "report_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    week_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payroll_weeks.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payroll_report_employees.id", ondelete="CASCADE"),
        nullable=False
    )
    report_key: Mapped[str] = mapped_column(String(64), nullable=False)

    # Column is named "values" per the schema spec. The attribute is
    # `values_json` because `values` collides with Mapping.values on any
    # dict-like access and reads as a method at every call site.
    values_json: Mapped[dict] = mapped_column("values", JSON, nullable=False)

    rule_set_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payroll_rule_sets.id"), nullable=False
    )
    rate_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    week = relationship("PayrollWeek", back_populates="results")
    employee = relationship("PayrollReportEmployee")
    rule_set = relationship("PayrollRuleSet")


# ─────────────────────────────────────────────────────────────────────────────
# Payroll 4 — the register. What was actually PAID.
#
# `payroll_weeks` and `payroll_week_lines` above hold the HOURS export: what we
# are about to pay. These three hold the Payroll Register: the checks Payentry
# issued, with their earnings, taxes and deductions exactly as printed. The two
# are deliberately separate tables rather than one with a flag, because they
# answer different questions and only one of them is authoritative about money
# that left the building.
# ─────────────────────────────────────────────────────────────────────────────

CHECK_LINE_KINDS = ("earning", "tax", "deduction")


class PayrollRegisterImport(Base):
    """One upload of one register PDF, and what reading it produced.

    ⚠️ **THE REPORT IS STORED, NOT JUST SHOWN.** `report` keeps the unknown
    codes, the employee ids with more than one candidate name, and the
    `Union`+`Sal` anomalies from this parse. An import whose anomalies were
    only ever rendered into a response is an import nobody can audit later —
    and these are exactly the findings that need a person, so they have to
    outlive the request that produced them.

    The PDF itself is NOT stored. It carries names, pay rates, child support
    and garnishment lines; the parsed rows are what the reports need, and
    keeping the source document would be a second copy of the most sensitive
    file the tenant has.
    """

    __tablename__ = "payroll_register_imports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    uploaded_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    #: The name the file arrived under, for tracing an import back to a
    #: download. Not a path: nothing is written to disk.
    filename: Mapped[str] = mapped_column(String(255), nullable=False)

    pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checks_parsed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checks_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Already present under the same idempotency key, so not inserted again.
    checks_duplicate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checks_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Page and company TOTAL blocks. Counted so "0 failures" cannot hide a
    #: block-detection change that started swallowing real checks.
    summary_blocks_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    report: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PayrollCheck(Base):
    """One check, as the register printed it.

    ⚠️ **IDEMPOTENT ON (check number, check date, employee id).** The number
    alone is not unique: off-cycle checks are first-class and a person can hold
    more than one check on the same date. Re-uploading a register that overlaps
    one already imported must change nothing, because the natural way to use
    this is to pull a fresh year and upload it — and a dues figure that doubled
    because a register was uploaded twice is the failure mode that matters.

    ⚠️ **THE PRINTED TOTALS ARE STORED ALONGSIDE THE LINES, ON PURPOSE.** They
    are what the parse was validated against, and keeping them means a later
    reader can re-check the arithmetic without the PDF. A check whose lines
    stop agreeing with its printed totals is a parse fault that can then be
    found by a query rather than only at import time.
    """

    __tablename__ = "payroll_checks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "check_number", "check_date", "emp_id",
                         name="uq_payroll_check_tenant_number_date_emp"),
        Index("ix_payroll_check_tenant_date", "tenant_id", "check_date"),
        Index("ix_payroll_check_tenant_emp", "tenant_id", "emp_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    import_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("payroll_register_imports.id", ondelete="SET NULL"),
        nullable=True
    )

    #: The Payentry employee id, as printed. A string because it is an
    #: identifier, not a quantity — leading zeros and any future prefix must
    #: survive a round trip.
    emp_id: Mapped[str] = mapped_column(String(32), nullable=False)
    #: The display name resolved for this employee at import, by frequency
    #: across the register. Kept on the check because a register is a
    #: historical document: the name it printed is the name it printed.
    person: Mapped[str] = mapped_column(String(160), nullable=False, default="")

    check_number: Mapped[str] = mapped_column(String(32), nullable=False)
    check_date: Mapped[date] = mapped_column(Date, nullable=False)
    #: "Reg", or an off-cycle label. Off-cycle checks count for dues.
    check_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    batch: Mapped[str | None] = mapped_column(String(32), nullable=True)

    net: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    base_rate: Mapped[Decimal | None] = mapped_column(RATE, nullable=True)

    printed_total_earnings: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    printed_total_hours: Mapped[Decimal | None] = mapped_column(HOURS, nullable=True)
    printed_total_deductions: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)

    source_page: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    lines: Mapped[list["PayrollCheckLine"]] = relationship(
        back_populates="check", cascade="all, delete-orphan"
    )


class PayrollCheckLine(Base):
    """One earnings, tax or deduction line on a check.

    ⚠️ **`ChSup1` AND `Garn` LIVE HERE AND NOWHERE ELSE.** Child support and
    garnishment are real deductions and the register must import them, or a
    check's deduction total will not add up. What they must never do is leave
    the payroll area: they are readable line by line by a payroll user and they
    never appear in a note, a summary, a report total or any Opas text outside
    it. `SENSITIVE_DEDUCTION_CODES` names them and
    `tests/test_sensitive_deduction_codes.py` holds the line.

    ⚠️ **A NEGATIVE AMOUNT IS STORED NEGATIVE.** Reimbursements (`CellReimb`,
    `BootReim`, `GasReim`, `Med2Reim`) are printed as negative deductions —
    measured: 105 lines across the year. Storing the absolute value would
    overstate total deductions by twice the reimbursement and break the
    agreement with the printed total that validates the parse.
    """

    __tablename__ = "payroll_check_lines"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('earning', 'tax', 'deduction')",
            name="ck_payroll_check_line_kind",
        ),
        Index("ix_payroll_check_line_check", "check_id"),
        Index("ix_payroll_check_line_tenant_kind_code", "tenant_id", "kind", "code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    check_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payroll_checks.id", ondelete="CASCADE"), nullable=False
    )

    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(String(160), nullable=False, default="")

    hours: Mapped[Decimal | None] = mapped_column(HOURS, nullable=True)
    rate: Mapped[Decimal | None] = mapped_column(RATE, nullable=True)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    check: Mapped["PayrollCheck"] = relationship(back_populates="lines")


#: The R-115's status flow. Forward only, and `filed` is TERMINAL — the same
#: discipline as an approved payroll week, for the same reason: once a figure
#: has been sent to the union, changing the record of what was sent is not an
#: edit, it is a second filing. A correction is a new form, not a mutation.
R115_STATUSES = ("draft", "submitted", "filed")

#: Which status may follow which. Absent from this map means "nowhere" —
#: `filed` is terminal by having no entry rather than by a special case.
R115_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "draft": ("submitted",),
    "submitted": ("filed", "draft"),
}


class PayrollUnionFormR115(Base):
    """One month's union remittance form, and where it is in its flow.

    ⚠️ **THE SNAPSHOT IS THE RECORD, NOT A CACHE.** `rows` holds the table as
    it stood when the form was submitted. Recomputing it later from
    `payroll_checks` would give a DIFFERENT answer the moment a register for
    an overlapping range is imported, or a check is corrected — and then
    nothing in the system would say what was actually sent to the union. A form
    that cannot reproduce its own filing is not a record of a filing.

    ⚠️ Keyed on (tenant, year, month) so one month has one form. A correction
    is a new form with a later `supersedes` link, never an edit to a filed one.
    """

    __tablename__ = "payroll_union_forms_r115"
    __table_args__ = (
        UniqueConstraint("tenant_id", "year", "month", "superseded_by_id",
                         name="uq_payroll_r115_tenant_year_month"),
        CheckConstraint(
            "status IN ('draft', 'submitted', 'filed')",
            name="ck_payroll_r115_status",
        ),
        CheckConstraint("month >= 1 AND month <= 12", name="ck_payroll_r115_month"),
        Index("ix_payroll_r115_tenant_period", "tenant_id", "year", "month"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")

    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_dues: Mapped[Decimal] = mapped_column(MONEY, nullable=False,
                                                default=Decimal("0.00"))
    total_hours: Mapped[Decimal] = mapped_column(HOURS, nullable=False,
                                                 default=Decimal("0"))
    #: The table as filed, with its own meta — including the check dates it
    #: covered, so a reader can check them against the payroll calendar.
    rows: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    #: A correction supersedes rather than replaces. NULL on the live form, so
    #: the unique key admits any number of superseded ones.
    superseded_by_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    filed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now)


# ─────────────────────────────────────────────────────────────────────────────
# Payroll 3 — hours in. The raw evidence behind a week.
#
# `payroll_week_lines` holds the INTERPRETATION a calculation reads: hours in
# buckets. These hold what the files actually said, per line, immutable. The
# distinction matters because a week's figures have to be defensible to a union
# auditor, and "this is what Payentry's report printed" is the only thing that
# settles a disagreement about a bucket.
#
# ⚠️ **CORRECTIONS ARE NEW RECORDS, NEVER EDITS** (the brief). An import batch
# is identified by its file hash, so re-uploading the same file is detectable
# and a changed file is a different batch sitting beside the first.
# ─────────────────────────────────────────────────────────────────────────────

HOURS_SOURCE_KINDS = ("employee_hours", "punch_location")


class PayrollHoursImport(Base):
    """One upload of one file, and what reading it produced."""

    __tablename__ = "payroll_hours_imports"
    __table_args__ = (
        CheckConstraint("source_kind IN ('employee_hours', 'punch_location')",
                        name="ck_payroll_hours_import_kind"),
        Index("ix_payroll_hours_import_tenant_week", "tenant_id", "week_end_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    #: ⚠️ sha256 of the bytes. The only reliable way to tell "they uploaded the
    #: same file again" from "they uploaded a corrected file" — the filename
    #: cannot, and Payentry regenerates reports with a new timestamp each time.
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    week_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    uploaded_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rows_parsed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Findings from parsing and validation, stored so they outlive the request.
    report: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PayrollHoursLine(Base):
    """One pay line exactly as the Employee Hours report printed it.

    ⚠️ **IMMUTABLE.** No `updated_at`, and nothing updates these rows. A
    correction is a new import batch.
    """

    __tablename__ = "payroll_hours_lines"
    __table_args__ = (
        Index("ix_payroll_hours_line_import", "import_id"),
        Index("ix_payroll_hours_line_tenant_week_emp",
              "tenant_id", "week_end_date", "emp_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True)
    import_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payroll_hours_imports.id", ondelete="CASCADE"),
        nullable=False)
    week_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    #: The Payentry employee number. ⚠️ The key, always — Payentry spells one
    #: real name "Micheal" and a long name collides with the dept column.
    emp_id: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    home_dept: Mapped[str | None] = mapped_column(String(16), nullable=True)
    worked_dept: Mapped[str | None] = mapped_column(String(16), nullable=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    pay_type: Mapped[str] = mapped_column(String(16), nullable=False)
    #: ⚠️ Signed. The automatic lunch deduction prints as -0.50 and a 0.00 line
    #: is real; both are stored as printed.
    hours: Mapped[Decimal] = mapped_column(HOURS, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PayrollPunch(Base):
    """One clock event.

    ⚠️ **NO COORDINATES, BY DESIGN** (James, 2026-11-10). Payroll does not use
    them and location history on thirty people is a liability for no benefit.
    `has_location` records only that a punch came from a phone rather than the
    kiosk. There is deliberately no latitude, longitude, accuracy or IP column
    for one to be written into later.
    """

    __tablename__ = "payroll_punches"
    __table_args__ = (
        Index("ix_payroll_punch_tenant_week", "tenant_id", "week_end_date"),
        Index("ix_payroll_punch_tenant_name_at", "tenant_id", "person_name",
              "punch_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True)
    import_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payroll_hours_imports.id", ondelete="CASCADE"),
        nullable=False)
    week_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    #: ⚠️ The punch file carries NO employee number — only a name. The emp_id
    #: is resolved by matching and may legitimately be NULL until a person
    #: confirms the mapping; an unresolved punch is a finding, not a guess.
    emp_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    person_name: Mapped[str] = mapped_column(String(160), nullable=False)
    dept: Mapped[str | None] = mapped_column(String(32), nullable=True)
    punch_at: Mapped[datetime] = mapped_column(DateTime(timezone=False),
                                               nullable=False)
    has_location: Mapped[bool] = mapped_column(Boolean, nullable=False,
                                               default=False)
    origin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PayrollNameAlias(Base):
    """A punch-file name confirmed to be a particular employee.

    ⚠️ **A PERSON CONFIRMS EACH ONE. NOTHING IS FUZZY-MATCHED SILENTLY**
    (James, 2026-11-10). Payentry spells one real name "Micheal"; that mapping
    to employee 22 is the first alias. Normalised exact matching happens
    automatically; anything unmatched or ambiguous is a finding that waits for
    a human, and the human's answer lands here.
    """

    __tablename__ = "payroll_name_aliases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "normalised_name",
                         name="uq_payroll_name_alias_tenant_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True)
    #: The name as it appears in the punch file, normalised.
    normalised_name: Mapped[str] = mapped_column(String(160), nullable=False)
    #: The name as printed, kept so a reader can see what was matched.
    raw_name: Mapped[str] = mapped_column(String(160), nullable=False)
    emp_id: Mapped[str] = mapped_column(String(32), nullable=False)
    confirmed_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PayrollShiftRule(Base):
    """When a department is expected to start and end.

    ⚠️ Carries `status` from the Payroll 4 provenance vocabulary.
    `default_unconfirmed` means these hours are in force because the punch
    detectors need something, not because anyone agreed them — and every
    finding derived from the rule reports that status with it.
    """

    __tablename__ = "payroll_shift_rules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "dept_code", "effective_date",
                         name="uq_payroll_shift_rule_tenant_dept_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True)
    dept_code: Mapped[str] = mapped_column(String(16), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    shift_start: Mapped[str] = mapped_column(String(5), nullable=False)   # "06:30"
    shift_end: Mapped[str] = mapped_column(String(5), nullable=False)     # "15:30"
    status: Mapped[str] = mapped_column(String(32), nullable=False,
                                        default="default_unconfirmed")
    source: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


#: ─────────────────────────────────────────── Payroll 5a: the Focus's writes
#:
#: ⚠️ **NEITHER OF THESE MUTATES WHAT WAS PARSED.** `payroll_hours_lines` and
#: `payroll_checks` hold what Payentry printed, and the arc's first rule is that
#: a stored figure must be re-derivable from the import. A hand correction that
#: overwrote an hours line would destroy the only copy of the thing being
#: corrected, and the next re-import would silently undo it.
#:
#: So both tables are APPEND-ONLY OVERLAYS carrying their own attribution, in
#: the manner `PayrollUnionFormR115` already establishes for the union form: "a
#: correction is a new form, not a mutation." Superseding keeps the history
#: readable — what was decided, by whom, and what it replaced.


class PayrollHourCorrection(Base):
    """One hand-entered hours correction for one person, day and pay type.

    ⚠️ **SIGNED, AND A DELTA RATHER THAN A REPLACEMENT.** The parsed line stays
    as printed and this is added to it, so "Payentry shows 6.5, it was 8" is
    entered as +1.5 and the arithmetic stays visible. A replacement value would
    make the correction unreadable without also knowing what it replaced, and
    that is exactly what gets lost when the import is refreshed.

    ⚠️ There may be NO parsed line to correct: a punch that never made it into
    Payentry's export is the commonest real case, and the correction is then the
    only row for that day. So this is not a foreign key to an hours line.
    """

    __tablename__ = "payroll_hour_corrections"
    __table_args__ = (
        Index("ix_payroll_hour_corrections_week",
              "tenant_id", "week_end_date", "emp_id"),
        # ⚠️ A SIGNED CHECK, NOT A POSITIVE ONE. A correction removing hours
        # someone did not work is as legitimate as one adding hours.
        #
        # ⚠️ **±168, NOT ±24, AND THE FIRST VERSION WAS ±24.** The reasoning was
        # "no single day's correction is plausibly more than a day" — true of a
        # day and false of the job. The commonest real correction is a WEEK of
        # hours that never reached Payentry at all, entered against one date;
        # Stevenson's is 40 REG. At ±24 that insert raised a CheckViolation and
        # surfaced as a 500. Found by walking the screen, not by any test —
        # every test entered small numbers, because I wrote them against the
        # constraint I had just written.
        #
        # 168 is one week, which is the largest span a single week's correction
        # can legitimately describe. It still catches a decimal-place slip,
        # which is all a bound at this level can honestly claim to do.
        CheckConstraint("hours >= -168 AND hours <= 168",
                        name="ck_payroll_hour_correction_plausible"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    week_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    #: The Payentry employee number, as everywhere else in this arc. Never the
    #: name — Payentry spells one real name "Micheal".
    emp_id: Mapped[str] = mapped_column(String(32), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    pay_type: Mapped[str] = mapped_column(String(16), nullable=False)
    hours: Mapped[Decimal] = mapped_column(HOURS, nullable=False)

    #: ⚠️ REQUIRED, AND ENFORCED AT THE EDGE TOO. A correction without a reason
    #: is unreviewable six weeks later, which is when anybody asks.
    reason: Mapped[str] = mapped_column(String(500), nullable=False)

    entered_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    #: ⚠️ Corrections ACCUMULATE rather than supersede — two corrections on one
    #: day are two deltas and both count. These columns exist for withdrawing
    #: one that was entered in error, and the same convention as decisions is
    #: used deliberately: `superseded_at` is what "live" means everywhere in
    #: this arc, so there is one answer to that question rather than two.
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    superseded_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("payroll_hour_corrections.id", ondelete="SET NULL"),
        nullable=True
    )


class PayrollWeekDecision(Base):
    """What was decided about one finding on one week.

    ⚠️ Keyed on the FINDING, not on a row id, because a finding is recomputed
    from the imports every time the week is looked at. Keying on anything
    derived from the run would lose the decision the moment the week was
    recalculated — the same mistake `subject_kind` forbids for fragments.
    """

    __tablename__ = "payroll_week_decisions"
    __table_args__ = (
        Index("ix_payroll_week_decisions_week", "tenant_id", "week_end_date"),
        # ⚠️ PARTIAL: one LIVE decision per finding, and any number of
        # superseded ones behind it. A plain unique constraint would make the
        # second decision on a finding an integrity error rather than a change
        # of mind.
        # ⚠️ KEYED ON `superseded_at`, NOT ON `superseded_by`, AND THE REASON
        # IS AN ORDERING DEADLOCK I HIT BUILDING THIS.
        #
        # `superseded_by` is a foreign key to this same table, so it cannot be
        # set until the replacement row exists. But the replacement cannot be
        # inserted while the old row is still live, because this index forbids
        # two live decisions on one finding. Liveness therefore has to be
        # something settable BEFORE the new row exists — a timestamp. The
        # pointer is then filled in afterwards, as provenance rather than as
        # state.
        Index("uq_payroll_week_decision_live",
              "tenant_id", "week_end_date", "finding_key",
              unique=True, postgresql_where=text("superseded_at IS NULL")),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    week_end_date: Mapped[date] = mapped_column(Date, nullable=False)

    #: Stable identity of the finding: "<kind>:<emp_id>[:<date>]". Built by
    #: `week_focus.finding_key`, never by a caller.
    finding_key: Mapped[str] = mapped_column(String(128), nullable=False)

    #: What was decided. Validated against a declared set at the edge rather
    #: than by an enum column, so adding an outcome does not need a migration —
    #: but it IS validated, because an unrecognised outcome renders as nothing.
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    decided_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    #: NULL while this is the live decision. Set when a later one replaces it.
    #: ⚠️ THIS, not `superseded_by`, is what "live" means — see the index above.
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    #: Which decision replaced this one. Provenance, filled in after the
    #: replacement exists; never read to decide whether a row is live.
    superseded_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("payroll_week_decisions.id", ondelete="SET NULL"),
        nullable=True
    )


# ─────────────────────────────────────────────────────────────────────────────
# Payroll 5c — vacation.
#
# ⚠️ **BEFORE THIS, VACATION PAY WAS COMPUTED NOWHERE.** The rulebook keys, the
# engine and the goldens all existed; no table, no writer, no surface, and no
# caller in `app/` or `scripts/`. These four tables are the data model the rule
# never had.
# ─────────────────────────────────────────────────────────────────────────────

#: A recorded vacation's life. `cancelled` keeps the row rather than deleting
#: it — "she cancelled" is a fact somebody will ask about.
VACATION_STATUSES = ("scheduled", "paid", "cancelled")


class PayrollVacation(Base):
    """A vacation somebody has picked or been approved for."""

    __tablename__ = "payroll_vacations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payroll_report_employees.id", ondelete="CASCADE"),
        nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False,
                                        default="scheduled")
    #: Why it is on the calendar — a union pick, or an approved request.
    source: Mapped[str] = mapped_column(String(300), nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=_now)


class PayrollVacationEntitlement(Base):
    """A per-person allowance override, because some are set by agreement.

    ⚠️ ONE PER PERSON PER YEAR, enforced by a unique constraint. A second is an
    EDIT and the service replaces, so "what is her allowance" has one answer.
    """

    __tablename__ = "payroll_vacation_entitlements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payroll_report_employees.id", ondelete="CASCADE"),
        nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    source: Mapped[str] = mapped_column(String(300), nullable=False)
    set_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    set_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                             default=_now)


class PayrollPriorYearFigures(Base):
    """Prior-year gross and hours ENTERED, when the registers cannot give them.

    ⚠️ **THE SOURCE IS REQUIRED AND NON-BLANK.** "2025 Vac Calc tab" is the
    whole value of the record: a typed figure whose origin nobody can name is a
    figure nobody can check a year later. Same rule as a status change's
    `reason`, for the same reason.
    """

    __tablename__ = "payroll_prior_year_figures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payroll_report_employees.id", ondelete="CASCADE"),
        nullable=False)
    #: The year the figures are ABOUT — 2025 for a 2026 vacation.
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    gross: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    source: Mapped[str] = mapped_column(String(300), nullable=False)
    entered_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=_now)


class PayrollVacationPayment(Base):
    """One approved part of a vacation's pay — a `Vac` and a `VacBonus` line.

    ⚠️ **TWO SEPARATELY-ROUNDED AMOUNTS, because that is what the register
    pays** (spec §3.1). Folding them into one total is the superseded form.

    ⚠️ `part_index` AND `part_count` are both stored: the bonus cent placement
    is `round2(total*i/n) - round2(total*(i-1)/n)`, so a part cannot be
    re-derived without knowing which of how many it is.
    """

    __tablename__ = "payroll_vacation_payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True)
    vacation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payroll_vacations.id", ondelete="CASCADE"),
        nullable=False)
    part_index: Mapped[int] = mapped_column(Integer, nullable=False)
    part_count: Mapped[int] = mapped_column(Integer, nullable=False)
    week_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    vac_pay: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    vac_bonus: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    #: Stored so a line reads back without re-deriving it from figures that may
    #: since have changed.
    rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    hours: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    #: ⚠️ WHICH RULES MADE IT — the same discipline as
    #: `payroll_week_results.rule_set_id`, so a figure can always name them.
    rule_set_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("payroll_rule_sets.id", ondelete="SET NULL"),
        nullable=True)
    approved_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  default=_now)
