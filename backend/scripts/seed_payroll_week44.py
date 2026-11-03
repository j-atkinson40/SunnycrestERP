"""Week 44 payroll dues fixture — anonymized, ensure-only.

Seeds the `sunnycrest` tenant with the rule set, the thirteen anonymized
week-44 members, their rates, and the week itself, so the payroll dues reports
have something real to run against on staging.

⚠️ **ENSURE-ONLY AND PRESERVE-AWARE, FOR THE REASON `seed_sunnycrest.py` GIVES
IN CAPITALS.** On staging the sunnycrest tenant was created BY HAND and holds the
operator's authored work. That file's warning is *"THIS SEED IS NOT THE HAZARD. A
DROP-AND-RESEED AROUND IT IS."* So this script:

  - creates only what is genuinely missing, keyed on natural keys;
  - NEVER deletes, truncates, or clean-and-reseeds anything;
  - never touches a row it did not create;
  - leaves an existing week's lines alone — if the week exists, it is the
    operator's and this script reports and stops rather than replacing it;
  - refuses on ENVIRONMENT=production.

⚠️ **THE NAMES ARE FAKE AND THAT IS DELIBERATE.** Members are `E01`..`E13` with
display names "Member E01".. — the dispatch requires real names kept out of
fixtures, and a staging tenant is not the place for a union roster.

Idempotent. Exit 0 whether it created anything or not.

    python -m scripts.seed_payroll_week44                 # sunnycrest
    python -m scripts.seed_payroll_week44 --tenant-slug testco
    python -m scripts.seed_payroll_week44 --dry-run

Spec: docs/specs/payroll-reports.md
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import date
from decimal import Decimal as D

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal                      # noqa: E402
from app.models.company import Company                     # noqa: E402
from app.models.payroll_report import (                     # noqa: E402
    PayrollRate,
    PayrollReportEmployee,
    PayrollRuleSet,
    PayrollWeek,
    PayrollWeekLine,
)
from app.services.payroll.service import CHECK_DATE_OFFSET  # noqa: E402

TAG = "[seed_payroll_week44]"

DEFAULT_SLUG = "sunnycrest"
RULES_EFFECTIVE = date(2026, 1, 1)
WEEK_NUMBER = 44
WEEK_END = date(2026, 10, 31)

# file_number, reg, personal, ot, reg_rate, typed_ot_rate
# The typed OT rates are the workbook's own and are frequently NOT 1.5x — that
# asymmetry is the point of the fixture, not an error in it.
MEMBERS = [
    ("E01", "40",    "0", "7",    "30",    "45"),
    ("E02", "40",    "0", "12.8", "24.54", "35.835"),
    ("E03", "40",    "0", "7.9",  "24.39", "36.585"),
    ("E04", "40",    "0", "2",    "24.39", "36.585"),
    ("E05", "36",    "4", "7.68", "24.44", "35.685"),
    ("E06", "40",    "0", "7.43", "24.39", "36.585"),
    ("E07", "32",    "0", "6.68", "22.34", "32.535"),
    ("E08", "40",    "0", "5.83", "22.34", "32.535"),
    ("E09", "0",     "0", "0",    "22.34", "32.535"),
    ("E10", "31.57", "0", "0.08", "22.34", "32.535"),
    ("E11", "32",    "0", "4.9",  "22.34", "32.535"),
    ("E12", "40",    "0", "1.37", "22.34", "32.535"),
    ("E13", "40",    "0", "1.2",  "22.34", "32.535"),
]

#: What a correct calculation of this fixture produces. Printed so the operator
#: can check the seeded week against a figure rather than against a feeling.
EXPECTED = {"dues": "193.93", "dues_hours": "520.44", "dues_wage": "13236.25275"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-slug", default=DEFAULT_SLUG)
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be created; write nothing")
    parser.add_argument("--idempotent", action="store_true",
                        help="explicit-intent alias for the default behaviour")
    args = parser.parse_args()

    if os.environ.get("ENVIRONMENT") == "production":
        print(f"{TAG} ENVIRONMENT=production — refusing. "
              f"This is a synthetic fixture with fake member names; it has no "
              f"business in a real union roster.")
        return 1

    db = SessionLocal()
    created: list[str] = []
    skipped: list[str] = []
    try:
        company = db.query(Company).filter(Company.slug == args.tenant_slug).first()
        if company is None:
            print(f"{TAG} no tenant with slug {args.tenant_slug!r}. "
                  f"This seed does NOT create tenants — run the tenant seed first. "
                  f"Nothing written.")
            return 1
        tenant_id = company.id
        print(f"{TAG} tenant {args.tenant_slug!r} -> {tenant_id}")

        # --- rule set (ensure) ---
        rule_set = (
            db.query(PayrollRuleSet)
            .filter(PayrollRuleSet.tenant_id == tenant_id,
                    PayrollRuleSet.effective_date == RULES_EFFECTIVE)
            .first()
        )
        if rule_set is None:
            rule_set = PayrollRuleSet(
                id=str(uuid.uuid4()), tenant_id=tenant_id,
                effective_date=RULES_EFFECTIVE,
            )
            if not args.dry_run:
                db.add(rule_set)
                db.flush()
            created.append(f"rule_set@{RULES_EFFECTIVE}")
        else:
            # ⚠️ LEFT BYTE-UNTOUCHED. If the accountant has already tuned a rate
            # or flipped a sick flag, that is their decision and it survives.
            skipped.append(f"rule_set@{RULES_EFFECTIVE} (exists — not modified)")

        # --- employees + rates (ensure, keyed on file number) ---
        emp_ids: dict[str, str] = {}
        for file_number, _reg, _pers, _ot, reg_rate, ot_rate in MEMBERS:
            emp = (
                db.query(PayrollReportEmployee)
                .filter(PayrollReportEmployee.tenant_id == tenant_id,
                        PayrollReportEmployee.payentry_file_number == file_number)
                .first()
            )
            if emp is None:
                emp = PayrollReportEmployee(
                    id=str(uuid.uuid4()), tenant_id=tenant_id,
                    payentry_file_number=file_number,
                    display_name=f"Member {file_number}",
                    dept="PRECAST",
                    is_union_member=True, active=True,
                    initiation_fee_due=False,
                )
                if not args.dry_run:
                    db.add(emp)
                    db.flush()
                created.append(f"employee {file_number}")
            else:
                skipped.append(f"employee {file_number} (exists)")
            emp_ids[file_number] = emp.id

            if args.dry_run and emp.id is None:
                continue
            rate = (
                db.query(PayrollRate)
                .filter(PayrollRate.employee_id == emp.id,
                        PayrollRate.effective_date == RULES_EFFECTIVE)
                .first()
            )
            if rate is None:
                if not args.dry_run:
                    db.add(PayrollRate(
                        id=str(uuid.uuid4()), employee_id=emp.id,
                        reg_rate=D(reg_rate), ot_rate=D(ot_rate),
                        effective_date=RULES_EFFECTIVE,
                    ))
                created.append(f"rate {file_number} {reg_rate}/{ot_rate}")
            else:
                skipped.append(f"rate {file_number} (exists — not modified)")

        # --- the week + its lines (ensure; an existing week is left alone) ---
        week = (
            db.query(PayrollWeek)
            .filter(PayrollWeek.tenant_id == tenant_id,
                    PayrollWeek.week_end_date == WEEK_END)
            .first()
        )
        if week is None:
            week = PayrollWeek(
                id=str(uuid.uuid4()), tenant_id=tenant_id,
                week_number=WEEK_NUMBER, week_end_date=WEEK_END,
                check_date=WEEK_END + CHECK_DATE_OFFSET,
                source_file_hash=None,          # keyed in, not imported
                status="imported",
            )
            if not args.dry_run:
                db.add(week)
                db.flush()
            created.append(f"week {WEEK_NUMBER} w/e {WEEK_END}")

            for file_number, reg, personal, ot, _rr, _orr in MEMBERS:
                if not args.dry_run:
                    db.add(PayrollWeekLine(
                        id=str(uuid.uuid4()), week_id=week.id,
                        employee_id=emp_ids[file_number],
                        reg_hrs=D(reg), personal_hrs=D(personal), ot_hrs=D(ot),
                        raw={"source": "seed_payroll_week44", "file_number": file_number},
                    ))
                created.append(f"line {file_number}")
        else:
            # ⚠️ DOES NOT REPLACE. An existing week may be approved, or may hold
            # the operator's real imported data. Replacing it here would be the
            # drop-and-reseed this file exists to avoid.
            skipped.append(
                f"week {WEEK_NUMBER} w/e {WEEK_END} (exists, status="
                f"{week.status!r} — lines NOT replaced)"
            )

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

    finally:
        db.close()

    verb = "would create" if args.dry_run else "created"
    print(f"{TAG} {verb} {len(created)} row(s); left {len(skipped)} existing row(s) alone")
    for item in created:
        print(f"{TAG}   + {item}")
    for item in skipped:
        print(f"{TAG}   = {item}")
    print(f"{TAG} a correct calculation of this week yields: "
          f"dues={EXPECTED['dues']} hours={EXPECTED['dues_hours']} "
          f"wage={EXPECTED['dues_wage']} over 13 members")
    print(f"{TAG} done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
