"""Writing effective-dated rates from the register.

⚠️ **`PayrollRate` HAD NO WRITER IN `app/`, AND THAT WAS THE BLOCKER.**
Measured in the week-44 dress rehearsal, 2026-11-23: the table was written
only by two seed scripts, `register_rates.rates_for_week` was called only by
tests, and uploading the real register inserted **1,275 checks and zero
rates**. On a tenant whose rates were never seeded, every employee came back
`missing_rate` and every dues figure was **$0.00** — the whole point of the
weekly Focus.

**The ruling** (James, Payroll 3; restated 2026-11-23): a rate is read from
the register check that first prints it and is effective from the start of
the pay period that check pays. `week_end = check_date - 5`;
`effective_from = week_end - 6`. Resolve by week end only.
"""
from __future__ import annotations

import os
import pathlib
import uuid
from datetime import date
from decimal import Decimal as D

import pytest
from sqlalchemy import text

from app.services.payroll.register_rates import (
    effective_from_check,
    rate_for,
    rate_history,
    rates_for_week,
    week_end_for_check,
)
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

_canonical_tenant = make_canonical_tenant_fixture()


# ── the ruling, as arithmetic ────────────────────────────────────────────


def test_a_check_pays_the_week_that_ended_FIVE_DAYS_EARLIER():
    """⚠️ James's golden: the raise printed on the Thursday 29 October check
    belongs to the week ending **Saturday 24 October**."""
    assert week_end_for_check(date(2026, 10, 29)) == date(2026, 10, 24)
    assert week_end_for_check(date(2026, 10, 29)).strftime("%a") == "Sat"
    # And week 44's own check.
    assert week_end_for_check(date(2026, 11, 5)) == date(2026, 10, 31)


def test_a_rate_is_in_force_from_the_SUNDAY_that_week_began():
    assert effective_from_check(date(2026, 10, 29)) == date(2026, 10, 18)
    assert effective_from_check(date(2026, 10, 18 + 11)).strftime("%a") == "Sun"


def test_THE_RAISE_STARTS_WITH_THE_WEEK_ENDING_OCT_24():
    """⚠️ **THE DEFECT THIS REPLACES.** `rate_history` used to key on the
    CHECK date, so a rate landed five days after the week it belonged to and
    `resolve_rate(..., week_end)` found nothing. Measured in the rehearsal:
    17 of 19 derived rates were invisible to their own week."""
    class _L:
        kind, code, rate = "earning", "Reg", D("30.0000")
    class _C:
        emp_id, check_date, lines = "1", date(2026, 10, 29), [_L()]

    hist = rate_history([_C()])
    assert hist["1"][0].effective_date == date(2026, 10, 18)
    # In force for the week it pays…
    assert rate_for("1", date(2026, 10, 24), hist).reg_rate == D("30.0000")
    # …and for the week after, until something else is printed.
    assert rate_for("1", date(2026, 10, 31), hist).reg_rate == D("30.0000")
    # ⚠️ AND NOT FOR THE WEEK BEFORE IT. The control: without this, keying on
    # any earlier date would pass the two assertions above.
    assert rate_for("1", date(2026, 10, 17), hist) is None


def test_there_is_ONE_RESOLVER_and_it_takes_a_week_end():
    """⚠️ `rates_for_week` took `check_date` and `calculate_week` resolved by
    `week.week_end_date` — two resolvers five days apart, with nothing saying
    so. James: "Keep one resolver, the one that works by week end, and delete
    the check-date one."
    """
    import inspect

    params = inspect.signature(rates_for_week).parameters
    assert "week_end" in params
    assert "check_date" not in params, (
        "the check-date path is back; there must be one resolver")


# ── the real register ────────────────────────────────────────────────────


def _register_or_skip() -> bytes:
    raw = os.environ.get("PAYROLL_REGISTER_PDF")
    if not raw:
        pytest.skip(
            "PAYROLL_REGISTER_PDF must point at a real Payroll Register, "
            "outside the repo. Skipped rather than faked. The arithmetic "
            "above runs in CI; the goldens are held here and by the walk."
        )
    return pathlib.Path(raw).expanduser().read_bytes()


@pytest.fixture
def roster_and_clean():
    """The roster the register's people need, and no checks or rates."""
    import pdfplumber

    from app.database import SessionLocal
    from app.models.payroll_report import PayrollReportEmployee
    from app.services.payroll.hours_parser import parse_employee_hours

    hours = os.environ.get("PAYROLL_EMPLOYEE_HOURS_PDF")
    if not hours:
        pytest.skip("PAYROLL_EMPLOYEE_HOURS_PDF must point at the real export")
    with pdfplumber.open(pathlib.Path(hours).expanduser()) as f:
        parsed = parse_employee_hours(f)

    db = SessionLocal()
    made: list[str] = []
    try:
        for e in sorted(parsed.emp_ids):
            if not db.query(PayrollReportEmployee).filter(
                    PayrollReportEmployee.tenant_id == TESTCO_ID,
                    PayrollReportEmployee.payentry_file_number == e).first():
                rid = str(uuid.uuid4()); made.append(rid)
                db.add(PayrollReportEmployee(
                    id=rid, tenant_id=TESTCO_ID, payentry_file_number=e,
                    display_name=f"RateGolden {e}", is_union_member=True))
        db.commit()
        yield parsed
    finally:
        db.execute(text("DELETE FROM payroll_rates WHERE employee_id IN "
                        "(SELECT id FROM payroll_report_employees WHERE "
                        " tenant_id=:c AND display_name LIKE 'RateGolden %')"),
                   {"c": TESTCO_ID})
        db.execute(text("DELETE FROM payroll_check_lines WHERE check_id IN "
                        "(SELECT id FROM payroll_checks WHERE tenant_id=:c)"),
                   {"c": TESTCO_ID})
        db.execute(text("DELETE FROM payroll_checks WHERE tenant_id=:c"),
                   {"c": TESTCO_ID})
        db.execute(text("DELETE FROM payroll_register_imports WHERE tenant_id=:c"),
                   {"c": TESTCO_ID})
        if made:
            db.execute(text("DELETE FROM payroll_report_employees WHERE id = ANY(:i)"),
                       {"i": made})
        db.commit()
        db.close()


def _upload(client, token, content):
    from tests._payroll_switch import payroll_switch

    with payroll_switch(TESTCO_ID, True):
        return client.post(
            "/api/v1/payroll-reports/register/upload",
            files={"file": ("register.pdf", content, "application/pdf")},
            headers={"Authorization": f"Bearer {token}",
                     "X-Company-Slug": "testco"})


@pytest.fixture(scope="module")
def client_and_token():
    from fastapi.testclient import TestClient

    from app.database import SessionLocal
    from app.main import app
    from app.models.role import Role
    from app.models.user import User
    from tests._two_step import tenant_token

    db = SessionLocal()
    uid = "rate-writer-admin"
    try:
        role = (db.query(Role)
                .filter(Role.company_id == TESTCO_ID, Role.slug == "admin").first())
        if role is None:
            pytest.skip("testco has no admin role")
        db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        db.add(User(id=uid, email=f"{uid}@testco.com", hashed_password="x",
                    first_name="Rate", last_name="Writer",
                    company_id=TESTCO_ID, role_id=role.id, is_active=True))
        db.commit()
        yield TestClient(app), tenant_token(uid, TESTCO_ID)
    finally:
        db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        db.commit()
        db.close()


def test_the_register_upload_WRITES_RATES_and_says_how_many(
        client_and_token, roster_and_clean):
    client, token = client_and_token
    r = _upload(client, token, _register_or_skip())
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body["checks_inserted"] > 0
    # ⚠️ REPORTED, because James asked to be told — and because a backfill
    # upload inserts zero checks, where "0 inserted" alone reads as nothing
    # having happened.
    assert body["rates_written"] > 0, body["report"].get("rates")


def test_A_RE_UPLOAD_WHERE_EVERY_CHECK_IS_A_DUPLICATE_STILL_BACKFILLS(
        client_and_token, roster_and_clean):
    """⚠️ **THIS IS THE PRODUCTION BACKFILL AND IT IS THE POINT.** James
    re-uploads the register in card 2 onto a tenant that has checks and no
    rates: nothing is inserted, every check is a duplicate, and the rates must
    still be written. A writer that looked only at newly-inserted rows would
    do nothing on exactly the upload meant to fix the gap."""
    from app.database import SessionLocal

    client, token = client_and_token
    first = _upload(client, token, _register_or_skip())
    assert first.status_code == 200
    wrote = first.json()["rates_written"]
    assert wrote > 0

    # The production state: checks present, rates absent.
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM payroll_rates WHERE employee_id IN "
                        "(SELECT id FROM payroll_report_employees WHERE tenant_id=:c)"),
                   {"c": TESTCO_ID})
        db.commit()
    finally:
        db.close()

    again = _upload(client, token, _register_or_skip())
    assert again.status_code == 200
    b = again.json()
    assert b["checks_inserted"] == 0, "the fixture did not reach the duplicate case"
    assert b["checks_duplicate"] > 0
    assert b["rates_written"] == wrote, (
        "a duplicate re-upload must still write the rates — that is the "
        "backfill")


def test_a_second_identical_upload_is_IDEMPOTENT(
        client_and_token, roster_and_clean):
    """Rates already correct: nothing written, and it says `unchanged`."""
    client, token = client_and_token
    _upload(client, token, _register_or_skip())
    again = _upload(client, token, _register_or_skip())
    rates = again.json()["report"]["rates"]
    assert again.json()["rates_written"] == 0
    assert rates["unchanged"] > 0
    assert rates["corrected"] == 0


def test_WEEK_44_RESOLVES_A_RATE_FOR_EVERY_HOURLY_PERSON_WITH_HOURS(
        client_and_token, roster_and_clean):
    """⚠️ **JAMES'S GOLDEN.** 18 people have hours in week 44; 17 are hourly
    and must all resolve the post-raise rate, and the 18th is salaried and is
    NOT `missing_rate` — "Salaried (Sal) people get no rate and are not
    missing_rate"."""
    from app.database import SessionLocal
    from app.models.payroll_report import PayrollCheck
    from app.services.payroll.employment import classify_employment

    client, token = client_and_token
    assert _upload(client, token, _register_or_skip()).status_code == 200

    with_hours = set(roster_and_clean.hours_by_emp())
    db = SessionLocal()
    try:
        checks = db.query(PayrollCheck).filter(
            PayrollCheck.tenant_id == TESTCO_ID).all()
        res = rates_for_week(
            with_hours, week_end=date(2026, 10, 31),
            history=rate_history(checks),
            employment=classify_employment(checks, before=date(2026, 11, 5)))
    finally:
        db.close()

    assert len(with_hours) == 18, len(with_hours)
    assert len(res.rates) == 17, sorted(res.rates)
    assert len(res.salaried) == 1, res.salaried
    assert res.missing == [], res.missing


def test_TWELVE_PEOPLE_GOT_THE_OCT_29_RAISE_effective_from_Oct_18(
        client_and_token, roster_and_clean):
    """⚠️ An independent confirmation of the arithmetic: the spec records that
    twelve employees' Reg rate changed on the real 2026-10-29 check, and the
    writer produces exactly twelve rows effective 2026-10-18 — the Sunday the
    week ending 24 October began."""
    from app.database import SessionLocal

    client, token = client_and_token
    assert _upload(client, token, _register_or_skip()).status_code == 200
    db = SessionLocal()
    try:
        n = db.execute(text("""
            SELECT count(*) FROM payroll_rates r
            JOIN payroll_report_employees e ON e.id = r.employee_id
            WHERE e.tenant_id = :c AND r.effective_date = DATE '2026-10-18'
        """), {"c": TESTCO_ID}).scalar()
    finally:
        db.close()
    assert n == 12, f"{n} rows effective 2026-10-18, expected 12"


def test_a_rate_for_somebody_NOT_ON_THE_ROSTER_is_reported_not_dropped(
        client_and_token, roster_and_clean):
    """`payroll_rates` hangs off the employee row, so a rate for somebody the
    roster does not have cannot be stored — and a roster that is missing
    people is a thing to look at, not a row to discard in silence."""
    client, token = client_and_token
    r = _upload(client, token, _register_or_skip())
    reported = r.json()["report"]["rates"]["no_roster_row"]
    assert isinstance(reported, list)
    # The real register carries people the week-44 hours file does not.
    assert len(reported) > 0
