"""The R-115's numbered lines, in the order the paper form carries them.

⚠️ **THIS FILE EXISTS BECAUSE THE FIELD MAP WAS NOT IN THE REPOSITORY, AND A
BUILD SESSION ASSERTED THAT IT WAS NOT AND THEN BUILT THE WRONG LINE ANYWAY.**

On 2026-11-18 a session searched for "line 4", found nothing, said so, and
asked. The answer it was given — *line 4 is the total dues remitted* — was a
mix-up between line 4 and Total Remittance, and it was built. James corrected
it the same day: **line 4 is Total Earnings (excl. lump sum)**, and the
remittance is its own field at the bottom.

Two things follow, and both are the reason this docstring is long:

  * **The map now lives in the repo** — here, and in
    `docs/specs/payroll-reports.md` §11.8a. It was described in chat and
    nowhere else, which is the condition CLAUDE.md names: a dispatch may only
    cite sources the executor can reach. The next session reads it instead of
    asking.
  * **The original search was a CONSTRUCTED PATTERN.** `grep "line 4"` cannot
    find a map written as "Total Earnings (excl. lump sum)". The absence it
    reported was a failed lookup, not a finding — and it was reported as a
    finding. The repo-wide check that settled it looked for the map's own
    vocabulary (`bargaining`, `lump sum`, `Total Remittance`), which is the
    enumeration that should have run first.

### The lines

    1   Members in bargaining unit      roster, union members
    2   Members paying dues             members with dues > 0 this month
    3   Hours included in earnings      sum of dues hours
    4   Total Earnings (excl. lump sum) sum of dues WAGE          <- not money remitted
    5   Percentage dues    rate 1.45    total - line 6 - line 7
    6   Per-hour dues      rate  .02    sum of each member's weekly rounded `c`
    7   Initiation fees                 count x the rule's fee
    8   Lump sum                        blank unless used
    9   Misc                            blank unless used
        Total Remittance                sum of `Union` deductions   <- the money

⚠️ **LINE 5 IS A PLUG, AND THAT MAKES ITS ARITHMETIC CHECK UNFALSIFIABLE.**
James's rule is `line 5 = total - line 6`, with the confirmation
`line 5 + line 6 + line 7 = total`. Defining 5 that way makes the confirmation
an identity: it cannot fail, whatever the data does, so it is documentation
rather than a check (CLAUDE.md §11 — a check that cannot be made to fail).

So the plug is kept, because the form filed with the union must add up to the
money actually sent — and `percentage_dues_computed` is reported beside it,
derived independently as the sum of each check's `min(a, b)`. The difference
between the two is `percentage_dues_variance`, and it is the rules-vs-register
disagreement the spec already measures at 76 of 629 checks (§11.8). Absorbing
it silently into a plug would hide the one number that says the rules and the
deductions disagree.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.models.payroll_report import PayrollCheck, PayrollReportEmployee
from app.services.payroll.register_dues import (
    DUES_DEDUCTION_CODE,
    actual_dues,
    dues_wage_and_hours,
)
from app.services.payroll.money import round2 as _round2
from app.services.payroll.roster_coverage import EXCUSED_STATUSES
from app.services.payroll.rules import PayrollRules

ZERO = Decimal("0")
CENTS = Decimal("0.01")


@dataclass(frozen=True)
class R115Line:
    """One row of the printed form."""

    #: `None` for the un-numbered Total Remittance row at the foot.
    number: int | None
    key: str
    label: str
    #: "count" | "hours" | "money". Decides how a screen formats it, so the
    #: print view does not carry a per-key format table of its own.
    kind: str
    #: The rate printed beside lines 5 and 6. `None` elsewhere.
    rate: str | None = None
    value: str | None = None
    #: True for 8 and 9 when nothing used them — printed blank, not as "0.00".
    #: ⚠️ A ZERO AND A BLANK ARE DIFFERENT CLAIMS ON A FILED FORM: one says
    #: "none this month", the other says "this line does not apply to us".
    blank: bool = False


def _month_checks(db: Session, *, tenant_id: str, year: int, month: int):
    return (
        db.query(PayrollCheck)
        .filter(PayrollCheck.tenant_id == tenant_id)
        .filter(extract("year", PayrollCheck.check_date) == year)
        .filter(extract("month", PayrollCheck.check_date) == month)
        .all()
    )


#: ⚠️ **A MEMBER WHO LEFT BEFORE THE MONTH IS NOT IN THE UNIT FOR IT.** The
#: roster's statuses are `workers_comp`, `leave`, `left` (see
#: `roster_coverage.EXCUSED_STATUSES`); only `left` removes somebody from the
#: bargaining unit. Being off sick or on comp is still being in the unit.
LEFT_STATUS = "left"

#: The statuses that can put somebody outside the unit — `roster_coverage.
#: EXCUSED_STATUSES`, imported rather than respelled.
#:
#: ⚠️ **WHAT MATTERS IS WHEN THE STATUS BEGAN, NOT WHICH STATUS IT IS —
#: REVISED 2026-11-18, AND THIS IS THE SECOND RULING ON THE SAME LINE.**
#:
#: The first ruling put `workers_comp` and `leave` outside the unit outright,
#: which reached the golden of 13 and was wrong about the reason. James:
#: *"Staring was paid, with union dues taken, on the October 1 and 8 checks,
#: so the union was paid for him in October."* A member on comp from the 8th
#: was in the unit for that month and is out of it from November — exactly
#: the treatment already given to somebody who LEFT mid-month, and there was
#: no principle separating the two.
#:
#: So the test is the DATE:
#:
#:     dues taken in the month         -> INSIDE, whatever the status
#:     status began BEFORE the month   -> outside  (and no dues)
#:     status began DURING the month   -> inside
#:     no status                       -> inside
#:     `left` with no date             -> outside  (and no dues)
#:
#: ⚠️ The dues clause is FIRST and overrides every other line of this table.
#: Added 2026-11-18 after Staring showed the date test and its own reason
#: disagreeing; see `_members_in_unit`.
#:
#: ⚠️ This supersedes `STATUSES_OUTSIDE_UNIT`, which is deleted rather than
#: emptied — an unused frozenset left at module level reads as a switch
#: somebody may still flip.
UNIT_AFFECTING_STATUSES = EXCUSED_STATUSES

def _members_in_unit(db: Session, *, tenant_id: str, year: int, month: int,
                     paying: set[str]) -> dict:
    """Line 1 — union members in the bargaining unit FOR THIS MONTH.

    ⚠️ **NOT "EVERY ROW WITH `is_union_member`", WHICH IS WHAT THIS RETURNED
    AND WAS WRONG BY FIVE.** The reconcile sets that flag for anyone who had
    dues at any point in the year, so Sunnycrest's roster carries 18 while
    October's unit was 13: the difference is people who had already left, and
    one member on workers' comp.

    Two tiers, per James 2026-11-18:

      * **By STATUS** where statuses are set — union members not recorded as
        having left before the month began.
      * **By CHECK** otherwise — union members with a check dated in the
        month. A fallback, because `payroll_status` is nullable and a NULL is
        "not established", never "working normally" (the model says so).

    The tier used is REPORTED rather than assumed, because the two can
    disagree and a reader reconciling a filed form needs to know which
    question produced the number.
    """
    from app.models.payroll_report import PayrollReportEmployee as E

    members = (
        db.query(E)
        .filter(E.tenant_id == tenant_id, E.is_union_member.is_(True))
        .all()
    )
    month_start = date(year, month, 1)
    statuses_set = any(m.payroll_status for m in members)

    counted, excluded = [], []
    for m in members:
        status = (m.payroll_status or "").strip().lower()

        # ⚠️ **DUES IN THE MONTH KEEP A MEMBER IN, WHATEVER THE STATUS SAYS —
        # RULED 2026-11-18, AND IT IS THE RULE'S OWN REASON MADE LITERAL.**
        #
        # The status-date test was a PROXY for "the union was paid for this
        # person". Staring showed the proxy and the reason coming apart: his
        # only October check is the 8th, which pays for work done Sep 27 to
        # Oct 3, so his true comp date may fall in September — and a rule
        # reading the date alone would drop a member the union HAD been paid
        # for, turning line 1 into 12.
        #
        # Two properties follow, and both are worth more than the proxy:
        #   * **line 1 can never be smaller than line 2**, structurally. A
        #     form that contradicts itself stops being expressible rather
        #     than being caught by a warning afterwards.
        #   * the answer stops depending on anybody recording an exact date.
        #     Set Staring's real September date and October is still right.
        if m.payentry_file_number in paying:
            counted.append(m.payentry_file_number)
            continue

        if statuses_set:
            began_before = (
                status in UNIT_AFFECTING_STATUSES
                and m.payroll_status_since is not None
                and m.payroll_status_since < month_start
            )
            # ⚠️ A `left` WITH NO DATE IS EXCLUDED; A COMP OR LEAVE WITH NO
            # DATE IS NOT. "Left, we did not record when" cannot be read as
            # "left during this month" — that would put every undated leaver
            # back into the unit. The other two are different: the member is
            # still a member, so an unknown start date leaves them in, which
            # is the direction that does not drop somebody the union was paid
            # for. Asymmetric on purpose, and James ruled the `left` half.
            left_undated = (status == LEFT_STATUS
                            and m.payroll_status_since is None)
            # Reached only when no dues were taken this month — the
            # keep-in above has already claimed everybody who paid.
            if began_before or left_undated:
                excluded.append({
                    "emp_id": m.payentry_file_number,
                    "name": m.display_name,
                    "reason": (f"status {status!r}"
                               + (f" since {m.payroll_status_since}"
                                  if m.payroll_status_since else
                                  " with no date recorded")),
                })
                continue
            counted.append(m.payentry_file_number)
        else:
            # Fallback: was this member paid at all in the month?
            paid = (
                db.query(PayrollCheck)
                .filter(PayrollCheck.tenant_id == tenant_id,
                        PayrollCheck.emp_id == m.payentry_file_number,
                        extract("year", PayrollCheck.check_date) == year,
                        extract("month", PayrollCheck.check_date) == month)
                .first()
                is not None
            )
            if paid:
                counted.append(m.payentry_file_number)
            else:
                excluded.append({
                    "emp_id": m.payentry_file_number,
                    "name": m.display_name,
                    "reason": "no check dated in the month",
                })

    return {
        "count": len(counted),
        "basis": "payroll_status" if statuses_set else "checks_in_month",
        "roster_union_members": len(members),
        "excluded": excluded,
        #: Members who PAID dues but are not counted in the unit. Should be
        #: empty; if it is not, line 2 exceeds line 1 and the form says so.
        "paying_but_not_counted": sorted(paying - set(counted)),
    }


def _initiation_fees(db: Session, *, tenant_id: str, year: int, month: int
                     ) -> int:
    """Line 7's COUNT — fees recorded as paid inside the month.

    ⚠️ Reads `initiation_fee_paid_date`, the backward-looking fact, not
    `initiation_fee_due`, which is forward-looking ("charge this member next
    time"). The model's own comment is explicit that these are different
    facts and not two copies of one; a form reporting fees COLLECTED must use
    the one that records collection.
    """
    return (
        db.query(PayrollReportEmployee)
        .filter(PayrollReportEmployee.tenant_id == tenant_id,
                extract("year", PayrollReportEmployee.initiation_fee_paid_date) == year,
                extract("month", PayrollReportEmployee.initiation_fee_paid_date) == month)
        .count()
    )


def build_lines(db: Session, *, tenant_id: str, year: int, month: int,
                rules: PayrollRules) -> dict:
    """Every numbered line for one month, plus the figures behind them.

    The money lines come from what was DEDUCTED wherever a deduction exists —
    that is the form's whole claim, and `monthly_dues_remittance` is the
    report kept beside it for what the rules imply (§11.8).
    """
    checks = _month_checks(db, tenant_id=tenant_id, year=year, month=month)

    total_remittance = ZERO
    dues_wage_total = ZERO
    dues_hours_total = ZERO
    per_hour_total = ZERO
    pct_computed_total = ZERO
    members_paying: set[str] = set()

    for check in checks:
        dues = actual_dues(check)
        if dues == 0:
            # No dues line: nothing remitted for this check. An absence, not a
            # zero — same rule `union_remittance_r115` applies to its rows.
            continue
        members_paying.add(check.emp_id)
        total_remittance += dues

        wage, hours = dues_wage_and_hours(check)
        dues_wage_total += wage
        dues_hours_total += hours

        # ⚠️ ROUNDED PER CHECK, THEN SUMMED — "each member's weekly rounded
        # c", James 2026-11-18. Rounding the month's total hours once gives a
        # different cent, and the union is owed the figure the weekly
        # calculations actually produced.
        per_hour_total += _round2(hours * rules.dues_per_hour)

        # The percentage component as the RULES would have it, for the
        # variance below. `min(a, b)` is the capped percentage; see spec §3.
        a = _round2(wage * rules.dues_pct)
        b = _round2((wage / hours) * rules.dues_cap_multiplier) if hours else ZERO
        pct_computed_total += min(a, b) if hours else a

    fee_count = _initiation_fees(db, tenant_id=tenant_id, year=year, month=month)
    initiation_total = (rules.initiation_fee * fee_count).quantize(CENTS)

    # ⚠️ THE PLUG. `line 5 = total - line 6 - line 7` so the filed form adds
    # up to the money actually sent. James's wording was "total − line 6";
    # subtracting line 7 as well is what makes his own confirmation —
    # `5 + 6 + 7 = total` — hold when any initiation fee was collected. The
    # two readings agree in every month with no fees, October included.
    percentage_total = (total_remittance - per_hour_total - initiation_total)

    # ⚠️ **A FORM WHOSE LINE 2 EXCEEDS ITS LINE 1 CONTRADICTS ITSELF, AND
    # NOTHING ELSE WOULD SAY SO.** More members paid dues this month than the
    # roster lists in the bargaining unit — which means the roster has not
    # been reconciled against the register, not that the register is wrong.
    # Caught here because this is the only place both numbers are in hand,
    # and a filed form carrying it is a question from the union rather than a
    # number anybody can defend.
    unit = _members_in_unit(db, tenant_id=tenant_id, year=year, month=month,
                            paying=members_paying)
    members_in_unit = unit["count"]
    warnings: list[str] = []
    if unit["paying_but_not_counted"]:
        warnings.append(
            f"{len(unit['paying_but_not_counted'])} member(s) paid dues this "
            f"month but are not counted in the bargaining unit "
            f"({', '.join(unit['paying_but_not_counted'])}). Line 1 cannot be "
            f"smaller than line 2 — reconcile the roster before filing."
        )
    if unit["basis"] == "checks_in_month" and unit["roster_union_members"]:
        warnings.append(
            "Line 1 counted members with a check dated in the month, because "
            "no payroll statuses are recorded on the roster. Anyone paid in "
            "the month is counted this way, including someone who had left "
            "and was paid without dues being taken, so this number can read "
            "high — set payroll_status for anyone who has left, is on comp or "
            "is on leave, and line 1 will count membership instead."
        )

    lines = [
        R115Line(1, "members_in_unit", "Members in bargaining unit", "count",
                 value=str(members_in_unit)),
        R115Line(2, "members_paying_dues", "Members paying dues", "count",
                 value=str(len(members_paying))),
        # ⚠️ TWO DECIMALS, NOT THE COLUMN'S FOUR. `HOURS` stores 4dp so a
        # weekly figure keeps its precision through a calculation; the FORM
        # shows hours the way the union reads them, and the live October
        # golden is written "2,731.14". `str()` on the Decimal printed
        # "600.0000", which is the storage talking rather than the form.
        R115Line(3, "hours_in_earnings", "Hours included in earnings", "hours",
                 value=f"{dues_hours_total:.2f}"),
        R115Line(4, "total_earnings", "Total Earnings (excl. lump sum)", "money",
                 value=f"{dues_wage_total:.2f}"),
        R115Line(5, "percentage_dues", "Percentage dues", "money",
                 rate="1.45", value=f"{percentage_total:.2f}"),
        R115Line(6, "per_hour_dues", "Per-hour dues", "money",
                 rate=".02", value=f"{per_hour_total:.2f}"),
        R115Line(7, "initiation_fees", "Initiation fees", "money",
                 value=f"{initiation_total:.2f}"),
        # ⚠️ BLANK, NOT ZERO, UNTIL SOMETHING USES THEM. No data path feeds
        # either today; printing "0.00" would assert that none were paid this
        # month, which is a claim nothing here measured.
        R115Line(8, "lump_sum", "Lump sum", "money", blank=True),
        R115Line(9, "misc", "Misc", "money", blank=True),
        R115Line(None, "total_remittance", "Total Remittance", "money",
                 value=f"{total_remittance:.2f}"),
    ]

    return {
        "lines": [vars(line) for line in lines],
        #: Stated, never blocking. The form can still be built, approved and
        #: printed; what it cannot do is carry the contradiction silently.
        "warnings": warnings,
        #: The identity James asked to be confirmed. True by construction
        #: while line 5 is a plug — reported so the print view can SHOW the
        #: arithmetic, never relied on as a check. See the module docstring.
        "adds_up": (percentage_total + per_hour_total + initiation_total
                    == total_remittance),
        #: ⚠️ **THE FIGURE THAT CAN ACTUALLY DISAGREE.** The percentage
        #: component as the rules compute it, beside the plug that absorbs
        #: whatever the register really deducted. A non-zero variance is the
        #: rules-vs-deduction gap the spec measures at 76 of 629 checks — it
        #: belongs on the screen, not inside line 5.
        "percentage_dues_computed": f"{pct_computed_total:.2f}",
        "percentage_dues_variance": f"{percentage_total - pct_computed_total:.2f}",
        "initiation_fee_count": fee_count,
        #: ⚠️ HOW LINE 1 WAS ARRIVED AT, AND WHO IT LEFT OUT. The roster
        #: carries 18 where October's unit was 13; a bare count cannot be
        #: reconciled against the register by anyone, and a form filed with a
        #: union is exactly the document somebody reconciles.
        "unit": unit,
        "check_dates": sorted({c.check_date.isoformat() for c in checks
                               if actual_dues(c) != 0}),
    }


def header_for(company, *, year: int, month: int, check_dates: list[str]) -> dict:
    """The form's header block.

    ⚠️ **EVERY TENANT-SPECIFIC VALUE IS A SETTING WITH NO DEFAULT.** The local
    number, the plant and who completed the form are facts about one licensee's
    agreement with one local. Defaulting them to Sunnycrest's would print
    another tenant's local on a form filed with a union — the
    `is_manufactured` shape from CLAUDE.md §5, where a plausible value nobody
    measured reads as data. Absent renders as "Not set", which is honest and
    is also what gets somebody to go and set it.

    `pay_period_begin/end` are the FIRST AND LAST CHECK DATES the form covers,
    not the calendar month's edges: the R-115 is grouped by check date, and a
    month whose first check falls on the 8th did not begin remitting on the
    1st.
    """
    from app.services.payroll import r115_settings as S

    period = date(year, month, 1)
    return {
        "company": company.name,
        "plant": S.plant(company),
        "local": S.local(company),
        #: Blank on the paper form for this licensee. Carried explicitly so a
        #: reader can see it was left blank deliberately rather than dropped.
        "unit": None,
        "pay_period_begin": check_dates[0] if check_dates else None,
        "pay_period_end": check_dates[-1] if check_dates else None,
        "dues_for_month_of": f"{period:%B %Y}",
        "completed_by": S.completed_by(company),
    }
