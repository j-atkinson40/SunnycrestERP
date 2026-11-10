"""Pay rates, taken from the register rather than typed in — Payroll 3.

James's ruling, 2026-11-10: *"Rates: from the payroll register. Each emp_id's
rate for a week is the printed Reg rate on their most recent check dated on or
before that week's check date, stored effective-dated. OT rate = 1.5 x that
rate."*

⚠️ **WHICH MEANS A RAISE ARRIVES BY ITSELF.** Measured on the real register:
twelve employees' Reg rate changed on the 2026-10-29 check (employee 1 went
26.0400 to 30.0000). Week 44's check is dated 2026-11-05, so the most recent
rate on or before it is the post-raise one — without anybody typing a number.
A hand-maintained rate table would have been wrong for twelve people that
week, silently, until somebody noticed.

⚠️ **"MOST RECENT ON OR BEFORE" IS NOT "THE WEEK'S OWN CHECK".** Employee 25's
2026-11-05 check prints no Reg rate at all (he was on vacation), so the rule
has to look further back and finds 24.3900 from 2026-10-29. Reading only the
week's own check would have made him `missing_rate` for a week he was paid at
a known rate.

⚠️ **A MISSING RATE IS A FLAG, NEVER A GUESS.** Five of the thirty employees
in a year of registers have no printed Reg rate anywhere — they are salaried,
and `Sal` lines carry no rate. The amount divided by the hours would produce a
plausible number for them and it would not be their rate. James: *"don't infer
one from amount / hours without telling me how many."* Nothing here infers.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

#: The register prints rates on `Reg` earning lines. `OT` lines print their own
#: rate too, but it is not always 1.5x and the ruling is to derive OT from the
#: Reg rate, so only this code is read.
RATE_SOURCE_CODE = "Reg"

#: James, 2026-11-10. Note this DIFFERS from the workbook, where 9 of 13
#: week-44 members carried a typed OT rate that was not 1.5x — see
#: `test_payroll_dues_golden`. The register-derived path uses 1.5x by ruling.
OT_MULTIPLIER = Decimal("1.5")


#: ⚠️ **READ AT THE CHECK DATE, STORED EFFECTIVE FROM THE WEEK IT PAYS.**
#: James's rule is stated in terms of the week's CHECK date — "the printed Reg
#: rate on their most recent check dated on or before that week's check date".
#: But `service.resolve_rate` looks for a rate effective on or before the
#: week's END date, which is five days earlier. Storing the rate at the check
#: date therefore misses by exactly that lag, and `calculate_week` flags
#: `missing_rate` for EVERY employee — measured: all 18 of week 44.
#:
#: So the two dates have different jobs. The check date is where the rate is
#: READ; the week it pays is where it is EFFECTIVE.
CHECK_LAG_DAYS = 5


def week_end_for_check_date(check_date: date) -> date:
    """The week-end date a check pays for. Inverse of `check_date_for_week`."""
    from datetime import timedelta
    return check_date - timedelta(days=CHECK_LAG_DAYS)


@dataclass(frozen=True)
class RateAt:
    #: The check date the rate was read from.
    effective_date: date
    reg_rate: Decimal

    @property
    def week_effective_date(self) -> date:
        """The week-end date from which this rate should be stored effective.

        ⚠️ Use THIS when writing `payroll_rates`, not `effective_date`. See the
        note above `week_end_for_check_date`.
        """
        return week_end_for_check_date(self.effective_date)

    @property
    def ot_rate(self) -> Decimal:
        # ⚠️ Quantized to the 4 decimals the register prints and the RATE
        # column stores. 30.0000 * 1.5 is 45.00000 in Decimal, and letting a
        # 5-decimal value reach a Numeric(12,4) column means the database
        # decides the rounding instead of this line.
        return (self.reg_rate * OT_MULTIPLIER).quantize(Decimal("0.0001"))


def rate_history(checks) -> dict[str, list[RateAt]]:
    """Every printed Reg rate per employee, oldest first.

    Takes anything with `emp_id`, `check_date` and `lines` — a parsed
    `RegisterCheck` or a stored `PayrollCheck`.
    """
    seen: dict[str, dict[date, Decimal]] = {}
    for chk in checks:
        if not chk.emp_id or chk.check_date is None:
            continue
        for line in chk.lines:
            if (line.kind == "earning" and line.code == RATE_SOURCE_CODE
                    and line.rate is not None):
                # ⚠️ One rate per (employee, check date). A check with two Reg
                # lines at different rates would be a mid-week change; the
                # later-read one wins and the disagreement is invisible, so
                # `rate_conflicts` reports those separately.
                seen.setdefault(chk.emp_id, {})[chk.check_date] = line.rate
    return {emp: [RateAt(d, r) for d, r in sorted(per.items())]
            for emp, per in seen.items()}


def rate_conflicts(checks) -> list[tuple[str, date, list[Decimal]]]:
    """Checks printing more than one distinct Reg rate for one employee.

    ⚠️ Reported because `rate_history` has to pick one and picking silently is
    how a mid-week rate change becomes an unexplained cent.
    """
    per: dict[tuple[str, date], set[Decimal]] = {}
    for chk in checks:
        if not chk.emp_id or chk.check_date is None:
            continue
        for line in chk.lines:
            if (line.kind == "earning" and line.code == RATE_SOURCE_CODE
                    and line.rate is not None):
                per.setdefault((chk.emp_id, chk.check_date), set()).add(line.rate)
    return [(emp, when, sorted(rates))
            for (emp, when), rates in sorted(per.items())
            if len(rates) > 1]


def rate_for(emp_id: str, as_of: date, history: dict[str, list[RateAt]]
             ) -> RateAt | None:
    """The rate in force for `emp_id` on `as_of`, or None.

    "Most recent printed Reg rate dated on or before `as_of`."
    """
    entries = history.get(emp_id) or ()
    applicable = [e for e in entries if e.effective_date <= as_of]
    return applicable[-1] if applicable else None


@dataclass
class RateResolution:
    """Rates for a week, and the people who have none."""

    rates: dict[str, RateAt]
    missing: list[str]

    @property
    def missing_count(self) -> int:
        """⚠️ The number James asked to be told rather than papered over."""
        return len(self.missing)


def rates_for_week(emp_ids, *, check_date: date,
                   history: dict[str, list[RateAt]]) -> RateResolution:
    """Resolve every employee's rate for one week's check date."""
    rates: dict[str, RateAt] = {}
    missing: list[str] = []
    for emp_id in sorted(emp_ids, key=lambda e: (len(e), e)):
        found = rate_for(emp_id, check_date, history)
        if found is None:
            missing.append(emp_id)
        else:
            rates[emp_id] = found
    return RateResolution(rates=rates, missing=missing)
