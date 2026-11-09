"""Local check: dues from pay lines, against a real year of registers.

    python scripts/check_register_dues.py ~/Downloads/<register>.pdf

⚠️ **NOT A CI TEST, AND DELIBERATELY SO.** It needs a real Payentry export, and
a real export never enters the repository. What CI holds is the code map, the
formula and the classifier, pinned to an anonymised fixture with hand-derived
figures (`tests/test_payroll_register_dues.py`). This script is how the map was
MEASURED, and it is here so the measurement can be repeated against a fresh
year rather than trusted because it was written down once.

⚠️ **THE ANSWER KEY IS THE REGISTER'S OWN `Union` DEDUCTION.** This does not
check that dues are "right" in any absolute sense — it checks that the figure
the rules imply equals the figure Payentry actually took. A disagreement may be
a wrong map, a wrong rulebook value, or the accountant working from a different
week; the classifier names the shape and a person settles it.

Prints no names. Employee ids only.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.payroll.register_dues import (            # noqa: E402
    DUES_HOURS_CODES,
    DUES_WAGE_CODES,
    classify_difference,
    dues_for_check,
)
from app.services.payroll.register_parser import parse_register   # noqa: E402
from app.services.payroll.rules import DEFAULT_RULES              # noqa: E402

#: What the measurement found when the map was settled. Printed beside the
#: current figure so a drift is visible rather than inferred — and stated as a
#: measurement on one year, not as a guarantee about any other.
BASELINE_MATCHED = 553
BASELINE_UNION_LINES = 629


def main(path: str) -> int:
    with pdfplumber.open(path) as pdf:
        result = parse_register(pdf)

    if result.failed:
        print(f"⚠️  {len(result.failed)} checks failed validation — the parse is "
              "wrong somewhere, so every figure below is suspect.")
        for chk, why in result.failed[:5]:
            print(f"      emp {chk.emp_id} chk {chk.check_number}: {why}")

    rows = [dues_for_check(c, DEFAULT_RULES) for c in result.checks]
    dues_rows = [r for r in rows if r.actual != 0]
    matched = [r for r in dues_rows if r.matches]
    missed = [r for r in dues_rows if not r.matches]

    print(f"checks parsed                 {len(result.checks)}")
    print(f"checks with a Union deduction {len(dues_rows)}"
          f"      measured baseline: {BASELINE_UNION_LINES}")
    print(f"dues figures that MATCH       {len(matched)}"
          f"      measured baseline: {BASELINE_MATCHED}")
    print(f"dues figures that MISS        {len(missed)}")
    print(f"distinct employees with dues  {len({r.emp_id for r in dues_rows})}")
    print()
    print(f"dues wage codes   {' '.join(sorted(DUES_WAGE_CODES))}")
    print(f"dues hours codes  {' '.join(sorted(DUES_HOURS_CODES))}")
    print()

    print("misses by shape:")
    buckets: dict[str, list] = defaultdict(list)
    for row in missed:
        buckets[classify_difference(row)].append(row)
    for name in sorted(buckets, key=lambda k: -len(buckets[k])):
        rows_ = buckets[name]
        print(f"  {len(rows_):>4}  {name}")
        for row in rows_[:3]:
            print(f"          emp {row.emp_id:<4} chk {row.check_number:<7} "
                  f"{row.check_date}  computed={row.computed.dues} "
                  f"actual={row.actual} diff={row.difference}")
        if len(rows_) > 3:
            print(f"          ... {len(rows_) - 3} more")

    print()
    per = Counter(r.emp_id for r in missed)
    print("misses per employee id: " +
          ", ".join(f"{e}:{n}" for e, n in sorted(per.items(), key=lambda kv: -kv[1])))

    # ── the Sick question, asked explicitly every run ────────────────────────
    #
    # ⚠️ REPORTED, NEVER ACTED ON. The accountant settled on 2026-11-03 that
    # sick is out of both dues wage and dues hours. If a miss would become a
    # match by including its sick hours, that is evidence a person should see —
    # and it is still not a reason for this script to change a rulebook flag.
    print()
    with_sick = [r for r in missed
                 if any(l.kind == "earning" and l.code == "Sick"
                        for l in next(c for c in result.checks
                                      if c.emp_id == r.emp_id
                                      and (c.check_number or "") == r.check_number).lines)]
    print(f"missing checks carrying a Sick line: {len(with_sick)}")
    fixed_by_sick = []
    for chk in result.checks:
        row = dues_for_check(chk, DEFAULT_RULES)
        if row.actual == 0 or row.matches:
            continue
        sick_hours = sum((l.hours or Decimal("0") for l in chk.lines
                          if l.kind == "earning" and l.code == "Sick"), Decimal("0"))
        if not sick_hours:
            continue
        from app.services.payroll.engine import dues_from_wage_and_hours
        if dues_from_wage_and_hours(row.dues_wage, row.dues_hours + sick_hours,
                                    DEFAULT_RULES).dues == row.actual:
            fixed_by_sick.append((chk, sick_hours))
    print(f"  of those, including the sick HOURS would make it match: "
          f"{len(fixed_by_sick)}")
    for chk, hours in fixed_by_sick:
        print(f"      emp {chk.emp_id} chk {chk.check_number} {chk.check_date}  "
              f"sick_hours={hours}")
    print("  (the flag is not changed by this script — reported only)")

    return 0 if len(matched) >= BASELINE_MATCHED else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
