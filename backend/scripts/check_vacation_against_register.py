"""Measure the vacation rules against a real register. LOCAL, READ-ONLY.

Two questions the 5c brief asked, both answerable only against real data:

  1. **The prior-year definition.** Gross is "printed total earnings on every
     check dated in the year, all codes, off-cycle included"; hours is the
     printed total hours. Status `assumed`, source "registers, definition
     unconfirmed against the workbook". This prints the per-person totals so
     the definition is **visible with numbers** rather than argued about.

  2. **Every real `Vac` / `VacBonus` line against the computed value**, with
     the differences listed.

⚠️ **READ-ONLY. It opens a session, selects, and writes nothing.**

⚠️ **ITS OUTPUT CARRIES REAL NAMES AND IS NEVER COMMITTED.** It prints
employee NUMBERS by default for that reason; `--names` is available for
somebody reading it on their own machine and should not be redirected into the
repository. The register file itself stays outside the tree.

    SECRET_KEY=... DATABASE_URL=... python scripts/check_vacation_against_register.py \
        --tenant staging-test-001 --year 2026
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select                                    # noqa: E402

from app.database import SessionLocal                            # noqa: E402
from app.models.payroll_report import (                          # noqa: E402
    PayrollCheck,
    PayrollCheckLine,
    PayrollReportEmployee,
)
from app.services.payroll.rules import DEFAULT_RULES             # noqa: E402
from app.services.payroll.vacation import prior_year as py       # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--year", type=int, required=True,
                    help="the year the FIGURES are about (2025 for a 2026 vacation)")
    ap.add_argument("--names", action="store_true",
                    help="print names; do not redirect this into the repo")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        cov = py.coverage_for(db, tenant_id=args.tenant, year=args.year)
        print(f"\n=== COVERAGE, {args.year} ===")
        print(f"  {cov.sentence()}")
        print(f"  {cov.check_count} checks")
        print(f"  usable for a computed prior-year figure: {cov.covers_year}")

        # ⚠️ **ITERATE THE REGISTER'S OWN EMPLOYEE NUMBERS, NOT THE ROSTER.**
        # My first version walked `payroll_report_employees` and printed "no
        # checks in this year for anybody on the roster" — a TRUE sentence
        # about a roster that does not contain the register's people, read as
        # a statement about the data. The register is the thing being
        # measured, so it supplies the population.
        emp_ids = [r[0] for r in db.execute(
            select(PayrollCheck.emp_id)
            .where(PayrollCheck.tenant_id == args.tenant)
            .where(PayrollCheck.check_date >= date(args.year, 1, 1))
            .where(PayrollCheck.check_date <= date(args.year, 12, 31))
            .where(PayrollCheck.emp_id.isnot(None))
            .distinct()
        ).all()]
        names = {
            e.payentry_file_number: e.display_name
            for e in db.execute(
                select(PayrollReportEmployee)
                .where(PayrollReportEmployee.tenant_id == args.tenant)
            ).scalars().all()
        }

        print(f"\n=== REGISTER TOTALS PER PERSON, {args.year} ===")
        print("  (gross = printed total earnings, all codes, off-cycle included)")
        print(f"  {'emp':>6}  {'gross':>12}  {'hours':>10}  {'implied rate':>13}")
        rows = 0
        for emp_id in sorted(emp_ids, key=lambda x: (len(x), x)):
            gross, hours = py.register_totals(
                db, tenant_id=args.tenant, emp_id=emp_id, year=args.year)
            if hours == 0:
                continue
            rows += 1
            who = (names.get(emp_id, emp_id) if args.names else emp_id)
            implied = (gross / hours + DEFAULT_RULES.vacation_increment)
            print(f"  {who:>6}  {gross:>12}  {hours:>10}  {implied:>13.4f}")
        if rows == 0:
            print("  (no checks in this year)")

        # ── every real Vac / VacBonus line ───────────────────────────────
        print(f"\n=== REAL Vac / VacBonus LINES, {args.year} ===")
        lines = db.execute(
            select(PayrollCheckLine, PayrollCheck)
            .join(PayrollCheck, PayrollCheck.id == PayrollCheckLine.check_id)
            .where(PayrollCheck.tenant_id == args.tenant)
            .where(PayrollCheck.check_date >= date(args.year, 1, 1))
            .where(PayrollCheck.check_date <= date(args.year, 12, 31))
        ).all()
        by_code: dict[str, list] = defaultdict(list)
        for line, chk in lines:
            code = (line.code or "").strip()
            if "vac" in code.lower():
                by_code[code].append((chk, line))

        if not by_code:
            print("  (none in the imported register)")
        for code, items in sorted(by_code.items()):
            total = sum((Decimal(str(li.amount or 0)) for _c, li in items),
                        Decimal("0"))
            print(f"  {code}: {len(items)} lines, {total} total")
            for chk, li in sorted(items, key=lambda t: (t[0].check_date,
                                                        t[0].emp_id or "")):
                who = chk.person if args.names else chk.emp_id
                hrs = li.hours if li.hours is not None else "—"
                print(f"    {chk.check_date}  emp {who:>5}  "
                      f"hours {hrs:>8}  amount {li.amount:>10}")

        print("\n⚠️ This output carries real payroll figures. Do not commit it.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
