"""Stage the REGISTER BACKFILL that card 2 is asked to report.

⚠️ **THE SURFACE THIS STAGES HAD NO WALK AT ALL.** `payroll-setup.tsx` is the
page James uses to load a register, and no walk in the suite depended on a
single byte of it — so card 2's reply was covered only by jsdom against a
mocked response. #53 returned `rates_written` and the page never read it; the
whole defect lived in the gap this script exists to close.

### What a backfill IS, and why it has to be staged rather than just uploaded

The upload that matters most is the one where **nothing is inserted**. James
re-uploads a register whose checks are already loaded, purely to derive the
effective-dated rates that were never written. So the state this builds is:

    checks       PRESENT   (so every one comes back a duplicate)
    rates        ABSENT    (so the upload has something to write)

Which means importing once, then deleting the rates. An upload onto an empty
tenant would insert 1,275 checks and prove nothing about the case where the
only non-zero number on the page is the rate count.

⚠️ **THE REGISTER HERE IS SYNTHETIC AND THAT IS NOT A COMPROMISE.** The
question a walk answers on this surface is *does the client read the field the
server writes* — and a field name does not depend on whose hours are in the
file. `tests/fixtures/payroll/register_fixture` reproduces the real page
geometry with invented people (`E01`…), so the parser's actual mechanism runs.
James's standing constraint is that real exports stay out of the repository
AND out of test tenants; importing the real register here would put 1,275 real
names into `note5a_clean`, which is the thing I was asked to confirm gone.

### The expectation, hand-derived from the fixture rather than from the writer

All five fixture checks are dated 11/13/2025, and three of the five people
carry an hourly `Reg` rate:

    E01  Reg @ 25.0000     →  a rate
    E02  Reg @ 20.0000     →  a rate
    E03  Reg @ 18.0000     →  a rate
    E04  Sal, no rate      →  NONE, and not missing_rate
    E05  Sal, no rate      →  NONE, and not missing_rate

One check date gives one effective date — `week_end = 11/13 − 5 = 11/08`,
`effective_from = 11/08 − 6 = 11/02` — so the answer is **3 rates effective
2025-11-02**, worked out on paper. The walk asserts that literal. A figure
read back from `write_rates` would agree with any rule at all, including a
wrong one.

Run it against the walk database, after `seed_week44_walkthrough.py` has made
Susan and turned the data switch on:

    SECRET_KEY=… DATABASE_URL=…/note5a_clean \
      python scripts/seed_register_backfill_walkthrough.py

It prints `register_pdf=` — the path to feed the walk as `PW_REGISTER_PDF`.
The file is written OUTSIDE the tree, for the same reason the real one is.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text                                            # noqa: E402

from app.core.security import hash_password                            # noqa: E402
from app.database import SessionLocal                                  # noqa: E402
from app.models.company import Company                                 # noqa: E402
from app.models.payroll_report import PayrollReportEmployee            # noqa: E402
from app.models.role import Role                                       # noqa: E402
from app.models.user import User                                       # noqa: E402
from app.services.payroll.data_gate import PAYROLL_DATA_ENABLED        # noqa: E402

#: ⚠️ **ITS OWN TENANT, AND THE FIRST VERSION OF THIS SHARED `testco`.**
#: Seeding five roster rows into `staging-test-001` took that tenant's payroll
#: roster from 4 people to 9 — and the week-44 walk's
#: `configured_member_missing_from_export` finding is computed over the
#: roster, so answering it no longer cleared it and that walk went red. A
#: fixture that changes a number another walk asserts is not isolated, however
#: carefully its own rows are scoped. This one owns its company outright.
TENANT = "payroll-backfill-walk"
SLUG = "backfillco"
ROLE_ID = "payroll-backfill-walk-admin-role"
USER_ID = "payroll-backfill-walk-admin"

#: A published local-dev credential, in the same category as CLAUDE.md §7's
#: `admin@testco.com / TestAdmin123!`. Guarded by the production refusal below.
ADMIN_EMAIL = "admin@backfillco.example.com"
ADMIN_PASSWORD = "BackfillAdmin123!"

#: The fixture's people, and whether the register prints them an hourly rate.
#: `is_union_member` is irrelevant to the rate writer and is set from the
#: fixture's own expectation so the row is not quietly wrong about something
#: else.
PEOPLE = (
    ("E01", "Alpha, Ann A", True),
    ("E02", "Bravo, Ben B", False),
    ("E03", "Charlie, Cal C", True),
    ("E04", "Delta, Dee D", True),
    ("E05", "Echo, Eve E", False),
)

#: ⚠️ **HAND-DERIVED — see the module docstring.** Three hourly people, one
#: check date. Printed so the walk can fail loudly if the fixture ever changes
#: shape, rather than silently asserting whatever the writer produced.
EXPECTED_RATES = 3
EXPECTED_CHECKS = 5


def _refuse_production() -> None:
    env = (os.environ.get("ENVIRONMENT") or "").strip().lower()
    if env == "production":
        print("FAIL: refusing to run against production")
        raise SystemExit(1)


def main() -> int:
    _refuse_production()

    # The fixture lives under `tests/`, which is not on the path by default.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../tests")
    from fixtures.payroll import register_fixture  # noqa: E402

    pdf = register_fixture.build()
    # ⚠️ Outside the repository. A register — even a synthetic one — is not a
    # thing to leave lying in the tree where the next `git add -A` finds it.
    out = Path(tempfile.gettempdir()) / "cc-synthetic-register.pdf"
    out.write_bytes(pdf)

    db = SessionLocal()
    try:
        # ── the tenant, its admin, and the payroll data switch ──────────────
        # `/payroll/setup` is `adminOnly`, which the frontend reads as
        # `role_slug === "admin"`, so the role's SLUG is load-bearing here and
        # not merely descriptive.
        co = db.get(Company, TENANT)
        if co is None:
            co = Company(id=TENANT, name="Backfill Walk Co", slug=SLUG)
            db.add(co)
            db.flush()
        co.set_setting(PAYROLL_DATA_ENABLED, True)

        if db.get(Role, ROLE_ID) is None:
            db.add(Role(id=ROLE_ID, company_id=TENANT, name="Admin",
                        slug="admin", is_system=True, is_active=True))
            db.flush()
        if db.get(User, USER_ID) is None:
            db.add(User(id=USER_ID, email=ADMIN_EMAIL,
                        hashed_password=hash_password(ADMIN_PASSWORD),
                        first_name="Backfill", last_name="Admin",
                        role_id=ROLE_ID, company_id=TENANT))
            db.flush()

        # ── the roster rows, without which no rate can be STORED ────────────
        # `payroll_rates` hangs off the employee, so a rate printed for
        # somebody with no roster row lands in `no_roster_row` instead. Card 3
        # is what creates these in real life; the walk is about card 2.
        for file_no, name, union in PEOPLE:
            row = db.execute(
                text("SELECT id FROM payroll_report_employees "
                     "WHERE tenant_id=:t AND payentry_file_number=:f"),
                {"t": TENANT, "f": file_no},
            ).first()
            if row is None:
                db.add(PayrollReportEmployee(
                    tenant_id=TENANT, payentry_file_number=file_no,
                    display_name=name, is_union_member=union))
        db.flush()

        # ── import once, so every check is already loaded ───────────────────
        from app.services.payroll.register_import import import_register
        first = import_register(db, tenant_id=TENANT, content=pdf,
                                filename="synthetic-register.pdf",
                                uploaded_by_user_id=None)
        db.commit()

        # ⚠️ **COUNTED, NOT TAKEN FROM `first.rates_written`.** On a re-run the
        # rates already exist, so the pre-import correctly writes ZERO and a
        # guard reading that number fails on a database that is perfectly
        # staged. The precondition is *are the three rates derivable*, which is
        # a count of what is there — the first version of this guard asked the
        # wrong question and printed FAIL beside a correct state, and the only
        # reason that was caught is that the seed's exit status was read.
        derivable = db.execute(
            text("SELECT count(*) FROM payroll_rates WHERE employee_id IN ("
                 "  SELECT id FROM payroll_report_employees"
                 "  WHERE tenant_id=:t AND payentry_file_number = ANY(:f))"),
            {"t": TENANT, "f": [p[0] for p in PEOPLE]},
        ).scalar_one()

        # ── then take the rates away, which is what makes it a BACKFILL ─────
        # ⚠️ Deleted AFTER the commit above, so the checks survive and the
        # rates do not. This is the production state exactly: #53 shipped the
        # writer, and every check loaded before it has no rate.
        #
        # ⚠️ **SCOPED TO THIS FIXTURE'S FIVE PEOPLE, NOT TO THE TENANT.** The
        # first version of this deleted every rate in `staging-test-001` and
        # reported `rates_deleted=7` when the import had written 3 — the other
        # four belong to `seed_week44_walkthrough`, whose walks read them to
        # compute dues. A tenant-wide delete here silently zeroes the dues
        # figures three other walks assert, and the only thing that caught it
        # was printing the row count and finding it bigger than expected.
        deleted = db.execute(
            text("DELETE FROM payroll_rates WHERE employee_id IN ("
                 "  SELECT id FROM payroll_report_employees"
                 "  WHERE tenant_id=:t AND payentry_file_number = ANY(:f))"),
            {"t": TENANT, "f": [p[0] for p in PEOPLE]},
        ).rowcount
        db.commit()

        remaining = db.execute(
            text("SELECT count(*) FROM payroll_rates WHERE employee_id IN ("
                 "  SELECT id FROM payroll_report_employees"
                 "  WHERE tenant_id=:t AND payentry_file_number = ANY(:f))"),
            {"t": TENANT, "f": [p[0] for p in PEOPLE]},
        ).scalar_one()
        checks = db.execute(
            text("SELECT count(*) FROM payroll_checks WHERE tenant_id=:t "
                 "AND check_number LIKE '900%'"),
            {"t": TENANT},
        ).scalar_one()

        print(f"register_pdf={out}")
        print(f"slug={SLUG}")
        print(f"admin_email={ADMIN_EMAIL}")
        print(f"first_import_inserted={first.checks_inserted}")
        print(f"first_import_rates_written={first.rates_written}")
        print(f"rates_derivable={derivable}")
        print(f"rates_deleted={deleted}")
        print(f"rates_now={remaining}")
        print(f"fixture_checks_stored={checks}")
        print(f"expect_rates={EXPECTED_RATES}")
        print(f"expect_duplicates={EXPECTED_CHECKS}")

        # ⚠️ Fail loudly rather than hand the walk a state it cannot test.
        # A walk run against 0 stored checks would upload into an EMPTY
        # tenant, insert five checks, and pass its rate assertion for
        # completely the wrong reason — the green-without-evidence shape.
        if checks != EXPECTED_CHECKS:
            print(f"FAIL: expected {EXPECTED_CHECKS} fixture checks stored, "
                  f"found {checks}. The upload would not be a backfill.")
            return 1
        if remaining != 0:
            print(f"FAIL: {remaining} rates survive, so the upload has "
                  "nothing to write and the walk would assert 0.")
            return 1
        if deleted != EXPECTED_RATES:
            print(f"FAIL: deleted {deleted} rates, expected exactly "
                  f"{EXPECTED_RATES}. Anything more means this script reached "
                  "outside its own five people — `seed_week44_walkthrough`'s "
                  "rates are in the same tenant and three walks read them.")
            return 1
        if derivable != EXPECTED_RATES:
            print(f"FAIL: {derivable} rates are derivable from the stored "
                  f"checks, not the {EXPECTED_RATES} the fixture implies. "
                  "Either the fixture changed shape or the writer did.")
            return 1
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
