"""Seed the week-44 walkthrough fixture — LOCAL ONLY, for the Playwright walk.

⚠️ **NOT A DEPLOY SEED, AND DELIBERATELY NOT IN THE SEED MANIFEST.** It turns
the payroll data switch ON and creates a user. Both are correct for a throwaway
local database and wrong everywhere else, so it is a script run by hand with an
explicit database in the environment.

⚠️ **NO REAL CREDENTIAL IS CREATED OR USED.** The test user's password hash is
a literal that cannot be signed in with; the walk establishes its session by
injecting a token minted with the app's own signing key, which is the local
`SECRET_KEY`. Nothing here touches Payentry or a real identity.

The fixture is built to produce the finding the walk is about: a union member
who is configured and active but absent from the hours export, which is
`configured_member_missing_from_export` — Stevenson's case.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import date
from decimal import Decimal as D

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal                                  # noqa: E402
from app.models.company import Company                                 # noqa: E402
from app.models.payroll_report import (                                # noqa: E402
    PayrollHoursImport,
    PayrollHoursLine,
    PayrollRate,
    PayrollReportEmployee,
    PayrollRuleSet,
    PayrollWeek,
    PayrollWeekLine,
)
from app.models.role import Role                                       # noqa: E402
from app.models.role_permission import RolePermission                  # noqa: E402
from app.models.user import User                                       # noqa: E402
from app.services.payroll import service as payroll_service            # noqa: E402
from app.services.payroll.data_gate import PAYROLL_DATA_ENABLED        # noqa: E402
from sqlalchemy import text                                            # noqa: E402

TENANT = "staging-test-001"           # testco, the canonical local tenant
SLUG = "testco"
USER_ID = "walk-payroll-user"
ROLE_ID = "area-probe-walk-payroll"   # `area-probe-` is exempt from the
                                      # undeclared-areas membership test
WEEK_END = date(2026, 10, 31)
CHECK_DATE = date(2026, 11, 5)
IN_WEEK = date(2026, 10, 28)

#: (file number, name, reg, ot, rate, in the export?)
PEOPLE = [
    ("9001", "Coyne, Daniel",     "40.00", "0.00", "22.50", True),
    ("9002", "Hunt, Nikolas",     "32.00", "6.00", "24.00", True),
    ("9003", "Thurston, Raymond", "40.00", "2.00", "23.25", True),
    # ⚠️ The finding the walk is about: configured, active, union — and absent
    # from the hours export. No week line, no hours line.
    ("12008", "Stevenson, Marcus", None, None, "16.05", False),
]


def main() -> int:
    db = SessionLocal()
    try:
        co = db.query(Company).filter(Company.id == TENANT).first()
        if co is None:
            print(f"FAIL: tenant {TENANT} not found — run the role/tenant seed first")
            return 1

        # ── wipe anything this script made before ────────────────────────
        db.execute(text("DELETE FROM payroll_hour_corrections WHERE tenant_id=:t"), {"t": TENANT})
        db.execute(text("DELETE FROM payroll_week_decisions WHERE tenant_id=:t"), {"t": TENANT})
        db.execute(text("DELETE FROM payroll_week_results WHERE week_id IN "
                        "(SELECT id FROM payroll_weeks WHERE tenant_id=:t)"), {"t": TENANT})
        db.execute(text("DELETE FROM payroll_week_lines WHERE week_id IN "
                        "(SELECT id FROM payroll_weeks WHERE tenant_id=:t)"), {"t": TENANT})
        db.execute(text("DELETE FROM payroll_weeks WHERE tenant_id=:t"), {"t": TENANT})
        db.execute(text("DELETE FROM payroll_hours_lines WHERE tenant_id=:t"), {"t": TENANT})
        db.execute(text("DELETE FROM payroll_hours_imports WHERE tenant_id=:t"), {"t": TENANT})
        db.execute(text("DELETE FROM payroll_rates WHERE employee_id IN "
                        "(SELECT id FROM payroll_report_employees WHERE tenant_id=:t)"), {"t": TENANT})
        db.execute(text("DELETE FROM payroll_report_employees WHERE tenant_id=:t"), {"t": TENANT})
        db.execute(text("DELETE FROM payroll_rule_sets WHERE tenant_id=:t"), {"t": TENANT})
        db.execute(text("DELETE FROM note_fragment_renders WHERE user_id=:u"), {"u": USER_ID})
        db.execute(text("DELETE FROM daily_notes WHERE user_id=:u"), {"u": USER_ID})
        db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": USER_ID})
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": USER_ID})
        db.execute(text("DELETE FROM role_permissions WHERE role_id=:r"), {"r": ROLE_ID})
        db.execute(text("DELETE FROM roles WHERE id=:r"), {"r": ROLE_ID})
        db.commit()

        # ── the switch, on for this tenant only ──────────────────────────
        co.set_setting(PAYROLL_DATA_ENABLED, True)

        # ── Susan's role: area-limited to payroll, change level ──────────
        db.add(Role(id=ROLE_ID, company_id=TENANT, name="Payroll (walkthrough)",
                    slug="area-probe-walk-payroll", is_system=False, is_active=True,
                    limited_to_areas=["payroll"]))
        db.flush()
        for key in ("payroll.view", "payroll.approve", "payroll.upload"):
            db.add(RolePermission(role_id=ROLE_ID, permission_key=key))
        db.add(User(id=USER_ID, email="susan.walkthrough@testco.example.com",
                    hashed_password="not-a-credential-cannot-be-signed-in-with",
                    first_name="Susan", last_name="Walkthrough",
                    role_id=ROLE_ID, company_id=TENANT))

        db.add(PayrollRuleSet(id=str(uuid.uuid4()), tenant_id=TENANT,
                              effective_date=date(2026, 1, 1)))

        emp_ids = {}
        for fn, name, _reg, _ot, rate, _in_export in PEOPLE:
            e = PayrollReportEmployee(
                id=str(uuid.uuid4()), tenant_id=TENANT, payentry_file_number=fn,
                display_name=name, dept="PRECAST", is_union_member=True,
                active=True, initiation_fee_due=False,
            )
            db.add(e)
            db.flush()
            emp_ids[fn] = e.id
            db.add(PayrollRate(id=str(uuid.uuid4()), employee_id=e.id,
                               reg_rate=D(rate), ot_rate=D(rate) * D("1.5"),
                               effective_date=date(2026, 1, 1)))

        hours_import = PayrollHoursImport(
            id=str(uuid.uuid4()), tenant_id=TENANT, source_kind="employee_hours",
            file_sha256="0" * 64, filename="walkthrough-employee-hours.pdf",
            week_end_date=WEEK_END, rows_parsed=3, report={},
        )
        db.add(hours_import)
        db.flush()

        week = PayrollWeek(id=str(uuid.uuid4()), tenant_id=TENANT, week_number=44,
                           week_end_date=WEEK_END, check_date=CHECK_DATE,
                           status="imported")
        db.add(week)
        db.flush()

        for fn, name, reg, ot, _rate, in_export in PEOPLE:
            if not in_export:
                continue
            db.add(PayrollWeekLine(id=str(uuid.uuid4()), week_id=week.id,
                                   employee_id=emp_ids[fn],
                                   reg_hrs=D(reg), ot_hrs=D(ot)))
            db.add(PayrollHoursLine(
                id=str(uuid.uuid4()), tenant_id=TENANT, import_id=hours_import.id,
                week_end_date=WEEK_END, emp_id=fn, name=name,
                work_date=IN_WEEK, pay_type="REG", hours=D("8.00")))
        db.commit()

        payroll_service.calculate_week(db, week)
        db.commit()

        # ⚠️ Checked through `week_focus`, which is what the SCREEN reads —
        # not through `calculate_week`, which does not raise the roster
        # mismatch at all. Checking the wrong source is how this control first
        # reported "(none)" for a fixture that was correct.
        from app.services.payroll import week_focus as wf

        focus = wf.week_focus(db, week)
        codes = sorted({f["code"] for f in focus["findings"]})
        print(f"week_id={week.id}")
        print(f"user_id={USER_ID}")
        print(f"company_id={TENANT}")
        print(f"slug={SLUG}")
        print(f"status={week.status}")
        print(f"flag_codes={','.join(codes) or '(none)'}")
        if "configured_member_missing_from_export" not in codes:
            # ⚠️ A control. The walk is ABOUT this finding; if the fixture
            # stopped producing it the walk would still pass while testing
            # nothing, so the seed refuses instead.
            print("FAIL: the fixture did not produce "
                  "configured_member_missing_from_export")
            return 1
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
