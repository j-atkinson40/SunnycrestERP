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

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    rates = relationship(
        "PayrollRate", back_populates="employee", cascade="all, delete-orphan"
    )


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
