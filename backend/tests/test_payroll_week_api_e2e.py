"""Week 44 end to end through the real API and the real database.

upload -> calculate -> report -> approve, plus the refusals.

⚠️ THE GOLDEN FIGURES ARE ASSERTED AT THE FAR END, NOT AT THE ENGINE. The pure
engine tests already prove the arithmetic. What this file proves is that the
numbers SURVIVE the round trip: Numeric column precision, the JSON result blob,
the stored-results read path, and the CSV writer. A rate truncated by a column
type or a Decimal stringified through a float would be invisible to the engine
tests and fatal here (and the measured reason the rate columns are Numeric(12,4)
is that Numeric(12,2) stores the workbook's 35.835 as 35.84).

Uses the canonical `testco` dev tenant. Payroll child tables are swept by the
module fixture; the session-scoped COMPANY LITTER tripwire in conftest watches
what the sweep misses.
"""
from __future__ import annotations

import io
import uuid
from datetime import date
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.deps import get_current_user, get_db
from app.main import app
from app.models.payroll_report import (
    PayrollRate,
    PayrollReportEmployee,
    PayrollRuleSet,
    PayrollWeek,
)
from app.models.user import User
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

PAYROLL_CHILD_TABLES = (
    "payroll_week_results",
    "payroll_week_lines",
    "payroll_weeks",
    "payroll_rates",
    "payroll_rule_sets",
    "payroll_report_employees",
)

_canonical_tenant = make_canonical_tenant_fixture(child_tables=PAYROLL_CHILD_TABLES)

APPROVER_ID = "payroll-test-approver"

WEEK_END = date(2026, 10, 31)
WEEK_NUMBER = 44
CHECK_DATE = date(2026, 11, 5)

# id, reg, personal, ot, reg_rate, typed_ot_rate, expected_dues
WEEK44 = [
    ("E01", "40",    "0", "7",    "30",    "45",     "21.77"),
    ("E02", "40",    "0", "12.8", "24.54", "35.835", "18.68"),
    ("E03", "40",    "0", "7.9",  "24.39", "36.585", "18.02"),
    ("E04", "40",    "0", "2",    "24.39", "36.585", "16.05"),
    ("E05", "36",    "4", "7.68", "24.44", "35.685", "17.91"),
    ("E06", "40",    "0", "7.43", "24.39", "36.585", "17.94"),
    ("E07", "32",    "0", "6.68", "22.34", "32.535", "14.29"),
    ("E08", "40",    "0", "5.83", "22.34", "32.535", "16.19"),
    ("E09", "0",     "0", "0",    "22.34", "32.535", "0.00"),
    ("E10", "31.57", "0", "0.08", "22.34", "32.535", "10.89"),
    ("E11", "32",    "0", "4.9",  "22.34", "32.535", "13.42"),
    ("E12", "40",    "0", "1.37", "22.34", "32.535", "14.43"),
    ("E13", "40",    "0", "1.2",  "22.34", "32.535", "14.34"),
]
TOTAL_DUES = "193.93"
TOTAL_HOURS = "520.44"
TOTAL_WAGE_EXACT = "13236.25275"


def _csv_for_week44() -> bytes:
    """The canonical bridgeable_csv shape. Columns we do not use are omitted on
    purpose, so the parser's default-to-zero path is exercised too."""
    buf = io.StringIO()
    buf.write("file_number,display_name,dept,reg_hrs,personal_hrs,ot_hrs\n")
    for emp, reg, personal, ot, *_ in WEEK44:
        buf.write(f"{emp},Member {emp},PRECAST,{reg},{personal},{ot}\n")
    return buf.getvalue().encode("utf-8")


def _reset_tenant_payroll(db, tenant_id: str) -> None:
    """Delete this tenant's payroll rows, and ONLY this tenant's.

    ⚠️ **TENANT-SCOPED ON PURPOSE. THE FIRST VERSION WAS `DELETE FROM t WHERE
    1=1`,** which reads as a harmless module-local reset and is not one: these
    tables are shared across tenants, so it would have deleted the seeded
    `sunnycrest` week-44 fixture — and any real payroll data on the same
    database — every time this file ran. A test that mutates state outside its
    own tenant makes every later run measure a different world (CLAUDE.md §11
    "a gate that mutates shared state is not repeatable"), and this one would
    have destroyed the very fixture the staging seed exists to create.

    Child rows are reached through their parents rather than by a bare table
    sweep, because `payroll_week_lines` and `payroll_week_results` carry no
    tenant_id of their own.
    """
    db.execute(text(
        "DELETE FROM payroll_week_results WHERE week_id IN "
        "(SELECT id FROM payroll_weeks WHERE tenant_id = :t)"
    ), {"t": tenant_id})
    db.execute(text(
        "DELETE FROM payroll_week_lines WHERE week_id IN "
        "(SELECT id FROM payroll_weeks WHERE tenant_id = :t)"
    ), {"t": tenant_id})
    db.execute(text("DELETE FROM payroll_weeks WHERE tenant_id = :t"), {"t": tenant_id})
    db.execute(text(
        "DELETE FROM payroll_rates WHERE employee_id IN "
        "(SELECT id FROM payroll_report_employees WHERE tenant_id = :t)"
    ), {"t": tenant_id})
    db.execute(text("DELETE FROM payroll_rule_sets WHERE tenant_id = :t"), {"t": tenant_id})
    db.execute(text(
        "DELETE FROM payroll_report_employees WHERE tenant_id = :t"
    ), {"t": tenant_id})


@pytest.fixture(scope="module")
def seeded():
    """Rule set + 13 anonymized employees + their rates.

    Real employee names are deliberately absent; ids are E01..E13.
    """
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        _reset_tenant_payroll(db, TESTCO_ID)
        db.commit()

        # ⚠️ A REAL USER ROW. `payroll_weeks.approved_by` is FK-constrained to
        # users.id, and that constraint is correct — an approval that names a
        # user who does not exist is not an audit trail. The first version of
        # this fixture used a bare fake id and the FK caught it, which is the
        # constraint doing its job rather than being in the way.
        role_row = db.execute(text(
            "SELECT id FROM roles WHERE slug = 'accountant' LIMIT 1"
        )).first()
        if role_row is not None and db.get(User, APPROVER_ID) is None:
            db.add(User(
                id=APPROVER_ID,
                email="payroll-approver@testco.example.com",
                hashed_password="not-a-real-credential-never-used-for-login",
                first_name="Payroll",
                last_name="Approver",
                role_id=role_row[0],
                company_id=TESTCO_ID,
            ))
            db.flush()

        # ⚠️ THE PAYROLL DATA SWITCH IS TURNED ON HERE, DELIBERATELY AND
        # LOCALLY. It is off by default per tenant (app/services/payroll/
        # data_gate.py) so no payroll export can be imported before tenant
        # invites and two-step sign-in exist. This suite's whole subject is the
        # import path, so it enables the switch for testco and says so —
        # a fixture that quietly worked around the gate would be a fixture that
        # hid the gate's absence if it ever regressed.
        # `test_payroll_data_switch.py` is what proves the OFF state refuses.
        from app.models.company import Company as _Company
        from app.services.payroll.data_gate import PAYROLL_DATA_ENABLED as _KEY

        _co = db.query(_Company).filter(_Company.id == TESTCO_ID).first()
        _co.set_setting(_KEY, True)
        db.commit()

        rule_set = PayrollRuleSet(
            id=str(uuid.uuid4()), tenant_id=TESTCO_ID, effective_date=date(2026, 1, 1)
        )
        db.add(rule_set)

        ids = {}
        for emp, _reg, _pers, _ot, reg_rate, ot_rate, _dues in WEEK44:
            e = PayrollReportEmployee(
                id=str(uuid.uuid4()),
                tenant_id=TESTCO_ID,
                payentry_file_number=emp,
                display_name=f"Member {emp}",
                dept="PRECAST",
                is_union_member=True,
                active=True,
                initiation_fee_due=False,
            )
            db.add(e)
            db.flush()
            ids[emp] = e.id
            db.add(PayrollRate(
                id=str(uuid.uuid4()), employee_id=e.id,
                reg_rate=D(reg_rate), ot_rate=D(ot_rate),
                effective_date=date(2026, 1, 1),
            ))
        db.commit()
        yield {"rule_set_id": rule_set.id, "employee_ids": ids}

        _reset_tenant_payroll(db, TESTCO_ID)
        db.execute(text("DELETE FROM users WHERE id = :i"), {"i": APPROVER_ID})
        # Return the tenant to the default-off state. A test that leaves a
        # safety switch ON is a test that disarms the next run.
        from app.models.company import Company as _Company2
        from app.services.payroll.data_gate import PAYROLL_DATA_ENABLED as _KEY2
        _co2 = db.query(_Company2).filter(_Company2.id == TESTCO_ID).first()
        if _co2 is not None:
            _co2.set_setting(_KEY2, False)
        db.commit()
    finally:
        db.close()


@pytest.fixture(scope="module")
def client(seeded):
    """TestClient with the accountant role and testco tenant."""
    from app.database import SessionLocal

    db = SessionLocal()
    row = db.execute(text(
        "SELECT id FROM roles WHERE slug = 'accountant' LIMIT 1"
    )).first()
    if row is None:
        db.close()
        pytest.skip("no 'accountant' role in this database — run the role seed")
    accountant_role_id = row[0]
    db.close()

    class _User:
        # ⚠️ NOT `role_id = role_id`. A class body cannot read an enclosing
        # function local of the same name — it resolves to the global scope and
        # raises NameError. Caught because 26 tests ERRORED rather than failed,
        # which is the distinction CLAUDE.md §11 insists on: an erroring test
        # asserts nothing, so "same errors before and after" proves nothing.
        id = APPROVER_ID
        company_id = TESTCO_ID
        role_id = accountant_role_id
        email = "accountant@testco.com"
        is_active = True

    def _override_db():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    def _as_accountant():
        return _User()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _as_accountant
    try:
        c = TestClient(app)
        c.restore_accountant = _as_accountant   # used by the role-gate test
        yield c
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


BASE = "/api/v1/payroll-reports"


def test_formats_endpoint_shows_payentry_as_unverified(client):
    """The stop is VISIBLE, not only enforced.

    Someone looking for the Payentry format learns it is unverified here, rather
    than from a 422 after preparing an upload.
    """
    r = client.get(f"{BASE}/formats")
    assert r.status_code == 200
    formats = {f["format_key"]: f for f in r.json()["formats"]}
    assert formats["payentry"]["verified"] is False
    assert formats["bridgeable_csv"]["verified"] is True


def test_upload_through_the_unverified_payentry_mapping_is_refused(client):
    """⚠️ FAIL CLOSED. A guessed mapping that half-matched a real export would
    produce confidently wrong dues, which is worse than a refusal."""
    r = client.post(
        f"{BASE}/weeks/upload",
        files={"file": ("export.csv", _csv_for_week44(), "text/csv")},
        data={"week_number": WEEK_NUMBER, "week_end_date": WEEK_END.isoformat(),
              "format_key": "payentry"},
    )
    assert r.status_code == 422
    assert "verified=false" in r.json()["detail"]


def test_01_upload_creates_the_week(client):
    r = client.post(
        f"{BASE}/weeks/upload",
        files={"file": ("week44.csv", _csv_for_week44(), "text/csv")},
        data={"week_number": WEEK_NUMBER, "week_end_date": WEEK_END.isoformat(),
              "format_key": "bridgeable_csv"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    week = body["week"]

    assert week["week_number"] == WEEK_NUMBER
    assert week["week_end_date"] == WEEK_END.isoformat()
    assert week["check_date"] == CHECK_DATE.isoformat(), "check_date = week_end + 5 days"
    assert week["status"] == "imported"
    assert week["source_file_hash"], "the source file hash is recorded"
    assert body["import"]["rows_parsed"] == 13
    assert body["import"]["rows_persisted"] == 13
    assert body["import"]["rows_skipped"] == 0


def test_02_calculate_reproduces_every_golden_total(client):
    week_id = client.get(f"{BASE}/weeks").json()["weeks"][0]["id"]
    r = client.post(f"{BASE}/weeks/{week_id}/calculate")
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["members_calculated"] == 13
    t = body["totals"]
    assert t["row_count"] == 13, "every row is in every total"
    assert t["dues"] == TOTAL_DUES
    assert t["dues_hours"] == TOTAL_HOURS
    assert t["dues_wage"] == TOTAL_WAGE_EXACT
    assert t["dues_wage_rounded"] == "13236.25"
    assert body["week"]["status"] == "calculated"

    # The typed OT rates survived the Numeric(12,4) round trip. Nine of thirteen
    # are not 1.5x, and each raises exactly one warning.
    flags = body["flags"]
    ot = [f for f in flags if f["code"] == "ot_rate_not_one_and_a_half"]
    assert len(ot) == 9, f"expected 9 non-1.5x warnings, got {len(ot)}"
    assert all(f["severity"] == "warning" for f in ot), "never an error — it is the normal case"
    assert body["summary"]["errors"] == 0


@pytest.mark.parametrize("emp,_r,_p,_o,_rr,_or,expected_dues", WEEK44, ids=[w[0] for w in WEEK44])
def test_03_each_member_dues_survives_the_round_trip(client, emp, _r, _p, _o, _rr, _or, expected_dues):
    week_id = client.get(f"{BASE}/weeks").json()["weeks"][0]["id"]
    rows = client.get(f"{BASE}/weeks/{week_id}/reports/weekly_dues_detail").json()["rows"]
    row = next(r for r in rows if r["file_number"] == emp)
    assert row["dues"] == expected_dues, f"{emp} dues through the API"


def test_04_detail_report_csv_states_its_own_denominator(client):
    week_id = client.get(f"{BASE}/weeks").json()["weeks"][0]["id"]
    r = client.get(f"{BASE}/weeks/{week_id}/reports/weekly_dues_detail?fmt=csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    body = r.text
    assert "TOTAL (n=13)" in body, "the total row carries its population"
    assert TOTAL_DUES in body
    assert body.count("\n") == 15, "header + 13 members + total"


def test_05_deduction_report(client):
    week_id = client.get(f"{BASE}/weeks").json()["weeks"][0]["id"]
    body = client.get(f"{BASE}/weeks/{week_id}/reports/employee_dues_deduction").json()
    assert len(body["rows"]) == 13
    assert body["totals"]["dues"] == TOTAL_DUES
    assert body["totals"]["row_count"] == 13
    assert {c["key"] for c in body["columns"]} == {"file_number", "display_name", "dues"}


def test_06_monthly_remittance_groups_week44_into_october(client):
    """Week 44 ends 2026-10-31 and its check date is 2026-11-05, so the grouping
    setting decides the month. Default is week_end_date -> October."""
    r = client.get(f"{BASE}/reports/monthly-dues-remittance?year=2026&month=10")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["meta"]["group_by"] == "week_end_date"
    assert body["meta"]["weeks_included"] == [WEEK_END.isoformat()]
    assert body["totals"]["dues"] == TOTAL_DUES
    assert body["totals"]["row_count"] == 13

    nov = client.get(f"{BASE}/reports/monthly-dues-remittance?year=2026&month=11").json()
    assert nov["totals"]["row_count"] == 0, "not November under week_end_date grouping"


def test_07_approve_locks_the_week(client):
    week_id = client.get(f"{BASE}/weeks").json()["weeks"][0]["id"]
    r = client.post(f"{BASE}/weeks/{week_id}/approve")
    assert r.status_code == 200, r.text
    assert r.json()["locked"] is True
    week = r.json()["week"]
    assert week["status"] == "approved"
    assert week["approved_by"] == APPROVER_ID
    assert week["approved_at"]


def test_08_recalculating_an_approved_week_is_refused(client):
    week_id = client.get(f"{BASE}/weeks").json()["weeks"][0]["id"]
    r = client.post(f"{BASE}/weeks/{week_id}/calculate")
    assert r.status_code == 409, r.text
    assert "approved" in r.json()["detail"]


def test_09_reimporting_an_approved_week_is_refused(client):
    r = client.post(
        f"{BASE}/weeks/upload",
        files={"file": ("week44.csv", _csv_for_week44(), "text/csv")},
        data={"week_number": WEEK_NUMBER, "week_end_date": WEEK_END.isoformat(),
              "format_key": "bridgeable_csv"},
    )
    assert r.status_code == 409, r.text


def test_10_approving_twice_is_refused(client):
    week_id = client.get(f"{BASE}/weeks").json()["weeks"][0]["id"]
    r = client.post(f"{BASE}/weeks/{week_id}/approve")
    assert r.status_code == 409


def test_11_reports_still_readable_after_approval(client):
    """Approval locks WRITES, not reads. The figures must remain citable."""
    week_id = client.get(f"{BASE}/weeks").json()["weeks"][0]["id"]
    body = client.get(f"{BASE}/weeks/{week_id}/reports/weekly_dues_detail").json()
    assert body["totals"]["dues"] == TOTAL_DUES
    assert body["totals"]["row_count"] == 13


def test_12_a_role_without_the_payroll_permission_is_refused(client):
    """⚠️ ENFORCED AT THE ENDPOINT, not in the UI. The gate is the only thing
    standing between a token holder and another department's payroll.

    Renamed from `test_12_a_non_accounting_role_is_refused`: the question is no
    longer "is your role named accountant" but "do you hold payroll.view", and a
    test name that still says accounting would send the next reader to the wrong
    mechanism.
    """
    from app.database import SessionLocal

    db = SessionLocal()
    row = db.execute(text("SELECT id FROM roles WHERE slug = 'driver' LIMIT 1")).first()
    db.close()
    if row is None:
        pytest.skip("no 'driver' role in this database")

    class _Driver:
        id = "payroll-test-driver"   # never writes, so needs no users row
        company_id = TESTCO_ID
        role_id = row[0]
        email = "driver@testco.com"
        is_active = True

    app.dependency_overrides[get_current_user] = lambda: _Driver()
    try:
        for method, path in (
            ("get", f"{BASE}/weeks"),
            ("get", f"{BASE}/formats"),
            ("get", f"{BASE}/reports/monthly-dues-remittance?year=2026&month=10"),
        ):
            r = getattr(client, method)(path)
            assert r.status_code == 403, f"{method} {path} must refuse a driver"
            # ⚠️ UPDATED 2026-11-03 WITH THE MECHANISM, NOT JUST THE MESSAGE.
            # This asserted the old slug gate's prose ("...is the tenant's
            # accounting responsibility"). The gate is now
            # `require_permission("payroll.view")`, so the refusal names the
            # permission instead. Asserting the permission KEY rather than a
            # sentence means the next copy edit does not break the test while a
            # change to what is actually required still does.
            detail = r.json()["detail"]
            assert "payroll.view" in str(detail), (
                f"{method} {path} refused, but not for the payroll permission: {detail}"
            )
    finally:
        # Restore the accountant the fixture installed, rather than rebuilding
        # one here — two producers of the same test identity would drift.
        app.dependency_overrides[get_current_user] = client.restore_accountant
