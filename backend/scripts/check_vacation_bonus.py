"""Local check: vacation pay and bonus against a real year of registers.

    python scripts/check_vacation_bonus.py <register.pdf>

⚠️ Not a CI test — it needs a real export, and a real export never enters the
repository. CI holds the tiers, the split rule and the goldens against
hand-derived figures (`tests/test_payroll_vacation_bonus.py`). This script is
how the tiers and the split rule were MEASURED, and it is here so the
measurement can be repeated against a fresh year.

It answers three questions:

  1. Does the yearly bonus the tiers compute equal what was actually paid, for
     every entitlement?
  2. Does the cent placement match? (`allocate_cumulative` vs the
     largest-remainder allocator, so the evidence that chose one stays visible.)
  3. Is the number of bonus parts the entitlement in weeks? Every person-year
     where it is not is REPORTED, per the ruling.

Prints employee ids, never names.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from decimal import Decimal as D
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.payroll.engine import (                   # noqa: E402
    _allocate_exact, allocate_cumulative, vacation_bonus_for_year)
from app.services.payroll.register_parser import parse_register   # noqa: E402
from app.services.payroll.rules import (                    # noqa: E402
    DEFAULT_RULES, VACATION_HOURS_PER_DAY)

#: Measured when the rule was settled, printed beside the current figure so a
#: drift is visible rather than inferred. One year, not a guarantee.
BASELINE = {"groups": 13, "bonus_lines": 29, "tier_matches": 12,
            "discriminating_groups": 1, "entitlements_without_hours": 1}


def entitlement_groups(checks):
    """A person's bonus lines grouped into entitlements.

    ⚠️ **NOT GROUPED BY CALENDAR YEAR.** Four of the eleven entitlements span
    the year boundary — paid in December and again the following July, August
    and September — so a calendar-year grouping splits them into a 1-part and a
    3-part group, each of which divides evenly and therefore cannot discriminate
    the split rule. Grouped instead by a running total reaching a tier value,
    which is what an entitlement IS.
    """
    tiers = {vacation_bonus_for_year(D(h) * VACATION_HOURS_PER_DAY, DEFAULT_RULES)
             for h in (5, 6, 10, 15, 20)}
    per_emp = defaultdict(list)
    for check in checks:
        for line in check.lines:
            if line.kind == "earning" and line.code == "VacBonus":
                per_emp[check.emp_id].append((check.check_date, line.amount))

    groups = []
    for emp_id, lines in per_emp.items():
        run, total = [], D("0")
        for when, amount in sorted(lines):
            run.append((when, amount))
            total += amount
            if total in tiers:
                groups.append((emp_id, list(run), total))
                run, total = [], D("0")
        if run:
            groups.append((emp_id, list(run), total))   # incomplete: reported
    return sorted(groups, key=lambda g: (int(g[0]) if g[0].isdigit() else 0,
                                         g[1][0][0]))


def main(path: str) -> int:
    with pdfplumber.open(path) as pdf:
        result = parse_register(pdf)

    # ⚠️ **HOURS ARE SCOPED TO THE ENTITLEMENT, NOT TO THE EMPLOYEE.** My first
    # version summed every `Vac` hour a person had in the file, which is wrong
    # for anyone with two entitlements in it: employee 28 has one in November
    # 2025 and another in August 2026, and both groups were then measured
    # against the same 48 hours. That produced a "the tiers say 85.00, the
    # register paid 75.00" line that was my aggregation, not a finding — the
    # worst kind of false alarm, because it looks exactly like a real one.
    vac_lines = defaultdict(list)
    for check in result.checks:
        for line in check.lines:
            if line.kind == "earning" and line.code == "Vac":
                vac_lines[check.emp_id].append((check.check_date, line.hours,
                                                line.amount))

    def hours_for(emp_id, first, last):
        """Vacation hours between a bonus group's first and last payment.

        The range rather than the exact dates, because one vacation payment can
        span two checks: employee 25's June vacation is a `Vac` line of 622.32
        on one check and 414.84 on the next, with the bonus part on the first.

        Returns (hours, printed) — `printed` is False when the register showed
        an amount with NO hours column, which it does for 2 of the 42 `Vac`
        lines in the year. Absent hours are NOT zero hours, and a tier lookup
        on them would invent an entitlement.
        """
        total, any_printed, any_line = D("0"), False, False
        for when, hours, _amount in vac_lines.get(emp_id, ()):
            if when is None or not (first <= when <= last):
                continue
            any_line = True
            if hours is not None:
                total += hours
                any_printed = True
        return total, (any_printed or not any_line)

    groups = entitlement_groups(result.checks)
    bonus_lines = sum(len(g[1]) for g in groups)
    print(f"entitlement groups {len(groups):>3}   baseline {BASELINE['groups']}")
    print(f"bonus lines        {bonus_lines:>3}   baseline {BASELINE['bonus_lines']}")
    print()

    tier_ok = cum_ok = lr_ok = discriminating = 0
    no_hours = 0
    anomalies: list[str] = []
    print(f"{'emp':<5}{'total':<9}{'hrs':<8}{'days':<7}{'tiers say':<11}"
          f"{'parts':<6}{'cent placement':<16}check")
    for emp_id, lines, total in groups:
        first, last = lines[0][0], lines[-1][0]
        hours, printed = hours_for(emp_id, first, last)
        days = hours / VACATION_HOURS_PER_DAY if hours else D("0")
        expected_total = vacation_bonus_for_year(hours, DEFAULT_RULES)
        actual = [a for _, a in lines]
        n = len(actual)

        cum = list(allocate_cumulative(total, n))
        frac = D(1) / D(n)
        lr = list(_allocate_exact(total, [frac] * n))
        if cum != lr:
            discriminating += 1
        cum_ok += cum == actual
        lr_ok += lr == actual
        tier_ok += (printed and expected_total == total)

        placement = ("both agree" if cum == lr == actual
                     else "CUMULATIVE" if cum == actual
                     else "largest-rem" if lr == actual else "NEITHER")
        if not printed:
            # ⚠️ Not counted as a tier mismatch. The register printed no hours
            # for this entitlement, so there is nothing to check the tiers
            # against — reporting it as a disagreement would be inventing one.
            no_hours += 1
            mark = "hours not printed — tiers not checkable"
        else:
            mark = "ok" if expected_total == total else f"TIERS SAY {expected_total}"
        print(f"{emp_id:<5}{str(total):<9}{str(hours):<8}{str(days):<7}"
              f"{str(expected_total):<11}{n:<6}{placement:<16}{mark}")

        # ⚠️ Parts should be the entitlement in weeks. Report where it is not.
        weeks = hours / VACATION_HOURS_PER_DAY / D(5) if hours else D("0")
        if printed and weeks != n:
            in_range = [(d, h, a) for d, h, a in sorted(vac_lines[emp_id])
                        if d and first <= d <= last]
            anomalies.append(
                f"  emp {emp_id} ({first}..{last}): {n} bonus part(s) but "
                f"{hours} vacation hours = {weeks} week(s). Vac lines: "
                + ", ".join(f"{d} {h}h {a}" for d, h, a in in_range)
            )

    print()
    checkable = len(groups) - no_hours
    print(f"yearly totals the tiers reproduce : {tier_ok} of {checkable} checkable"
          f"   ({no_hours} entitlement(s) printed no hours)")
    print(f"cent placement — cumulative       : {cum_ok} of {len(groups)}")
    print(f"cent placement — largest-remainder: {lr_ok} of {len(groups)}")
    print(f"groups that can tell them apart   : {discriminating}"
          f"   baseline {BASELINE['discriminating_groups']}")
    if discriminating == 0:
        print("  ⚠️ NO group discriminates in this file, so it is no evidence "
              "for either split rule. Do not read the counts above as support.")

    print()
    print("⚠️  parts that are not the entitlement in weeks — per the ruling, "
          "reported and not resolved here:")
    if anomalies:
        for line in anomalies:
            print(line)
    else:
        print("  none")

    # ⚠️ A positive control: zero groups would satisfy every count above.
    if not groups:
        print("\n⚠️  NO entitlement groups found — nothing was measured.")
        return 1
    return 0 if (tier_ok == checkable and cum_ok == len(groups)) else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
