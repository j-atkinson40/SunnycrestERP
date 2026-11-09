"""Local check: the R-115 for one month, against a real register.

    python scripts/check_r115_october.py <register.pdf> [year] [month]

Defaults to October 2026, which James named: *"Build the Phase 6 October local
check by check date: checks dated Oct 1, 8, 15, 22, 29."*

⚠️ Not a CI test — it needs a real export, and a real export never enters the
repository. CI holds the report shape and the status flow against hand-built
rows (`tests/test_payroll_r115.py`). Prints employee ids, never names.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.payroll.register_dues import (          # noqa: E402
    actual_dues, dues_wage_and_hours)
from app.services.payroll.register_parser import parse_register   # noqa: E402
from app.services.payroll.reports import (                 # noqa: E402
    R115Row, to_csv, union_remittance_r115)

#: What James named. Asserted rather than assumed: if the register's October
#: check dates are not these, the month is not the month he checked.
EXPECTED_OCTOBER_2026_DATES = ["2026-10-01", "2026-10-08", "2026-10-15",
                               "2026-10-22", "2026-10-29"]


def main(path: str, year: int, month: int) -> int:
    with pdfplumber.open(path) as pdf:
        result = parse_register(pdf)

    rows = []
    for check in result.checks:
        dues = actual_dues(check)
        if dues == 0:
            continue
        _wage, hours = dues_wage_and_hours(check)
        rows.append(R115Row(
            emp_id=check.emp_id, display_name=check.emp_id,   # id, not the name
            check_date=check.check_date, check_number=check.check_number or "",
            dues_deducted=dues, dues_hours=hours))

    table = union_remittance_r115(rows, year=year, month=month)
    print(f"R-115  {year}-{month:02d}   grouped by {table.meta['group_by']}")
    print(f"  source: {table.meta['source']}")
    print(f"  check dates included: {table.meta['check_dates_included']}")
    print(f"  check rows in this month: {table.meta['check_rows_considered']}"
          f"  of {table.meta['check_rows_available']} with dues in the file")
    print()
    print(to_csv(table))

    ok = True
    if (year, month) == (2026, 10):
        got = table.meta["check_dates_included"]
        if got != EXPECTED_OCTOBER_2026_DATES:
            print(f"⚠️  October 2026 check dates are {got}, not the "
                  f"{EXPECTED_OCTOBER_2026_DATES} the ruling named.")
            ok = False
        else:
            print("✓ the five October check dates are exactly the ones named "
                  "in the ruling.")

    # ⚠️ A positive control: an empty table would satisfy every statement above.
    if not table.rows:
        print("⚠️  the form is EMPTY — nothing was measured, so nothing above "
              "is evidence.")
        ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1],
                          int(sys.argv[2]) if len(sys.argv) > 2 else 2026,
                          int(sys.argv[3]) if len(sys.argv) > 3 else 10))
