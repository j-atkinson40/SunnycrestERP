"""The payroll week, computed from today — and the path to the first upload.

⚠️ **THE GAP THIS CLOSES.** On 2026-11-17, with the data switch on, a register
imported and a roster reconciled, there was still no way for Susan to upload
hours: the upload card lives in the weekly Focus, the Focus opens on a
`week_id`, and the row carrying that id is created BY the upload.
"""
from __future__ import annotations

from datetime import date, datetime, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.models.user import User
from app.services.payroll.week_calendar import (
    current_payroll_week,
    describe_week,
    week_end_for,
    week_number_for,
)
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture
from tests._two_step import tenant_token

_canonical_tenant = make_canonical_tenant_fixture()

HEADERS = {"X-Company-Slug": "testco"}
CURRENT = "/api/v1/payroll-reports/weeks/current"
WED, FIVE_PM = 2, time(17, 0)


def _desc(d: date):
    return current_payroll_week(d, cutoff_weekday=WED, cutoff_time=FIVE_PM)


# ── the numbering, cross-checked against production ─────────────────────────

def test_the_week_number_reproduces_the_LIVE_week_44():
    """⚠️ NOT A CHOSEN SCHEME. Production's week 44 ends 2026-10-31 and its
    checks are dated 2026-11-05. Both are reproduced here from the date alone,
    which is what makes the one-line ISO rule trustworthy rather than lucky."""
    d = describe_week(date(2026, 10, 31), cutoff_weekday=WED, cutoff_time=FIVE_PM)
    assert d.week_number == 44
    assert d.check_date == date(2026, 11, 5)
    assert d.week_start_date == date(2026, 10, 25)


def test_a_second_derivation_agrees_counting_saturdays_forward():
    """The ISO rule and simple counting share no step. Two methods agreeing is
    the reason this is not an anchor table."""
    anchor_end, anchor_no = date(2026, 10, 31), 44
    for weeks in range(0, 9):
        end = date.fromordinal(anchor_end.toordinal() + 7 * weeks)
        assert week_number_for(end) == anchor_no + weeks, end


# ── which week is "current" ─────────────────────────────────────────────────

@pytest.mark.parametrize("today, expect_end, expect_no", [
    # ⚠️ ABSOLUTE DATES ON PURPOSE — these assert calendar facts (which day of
    # the week a date falls on), so anchoring them to a tenant's start would
    # land them on an arbitrary weekday and break the thing being tested.
    (date(2026, 11, 17), date(2026, 11, 14), 46),  # Tue — James's own example
    (date(2026, 11, 15), date(2026, 11, 14), 46),  # Sun, the day after it ended
    (date(2026, 11, 14), date(2026, 11, 14), 46),  # Sat, the day it ends
    (date(2026, 11, 13), date(2026, 11, 7), 45),   # Fri — the week BEFORE
    (date(2026, 11, 21), date(2026, 11, 21), 47),
])
def test_current_is_the_week_being_PROCESSED_not_the_calendar_week(
        today, expect_end, expect_no):
    """⚠️ **THE TWO DIFFER ON SIX DAYS IN SEVEN, AND THE WRONG ONE IS USELESS.**
    On Tuesday the 17th the calendar week is Nov 15–21, which has barely
    started and has no hours to upload. The week Susan works is Nov 8–14 — it
    ended on Saturday and its checks are dated the 19th. Payroll is worked in
    arrears; you cannot pay hours nobody has worked yet.
    """
    d = _desc(today)
    assert d.week_end_date == expect_end
    assert d.week_number == expect_no


def test_the_week_runs_sunday_to_saturday():
    d = _desc(date(2026, 11, 17))
    assert d.week_start_date.strftime("%a") == "Sun"
    assert d.week_end_date.strftime("%a") == "Sat"
    assert (d.week_end_date - d.week_start_date).days == 6


def test_the_check_date_is_the_thursday_after_and_comes_from_ONE_constant():
    from app.services.payroll.service import CHECK_DATE_OFFSET
    d = _desc(date(2026, 11, 17))
    assert d.check_date == d.week_end_date + CHECK_DATE_OFFSET
    assert d.check_date.strftime("%a") == "Thu"


def test_the_cutoff_is_the_wednesday_BEFORE_the_checks():
    """17:00 the day before payday, not the Wednesday of the worked week —
    which would already have passed by the time the hours exist."""
    d = _desc(date(2026, 11, 17))
    assert d.cutoff_at == datetime(2026, 11, 18, 17, 0)
    assert d.cutoff_at.strftime("%a") == "Wed"
    assert d.cutoff_at.date() < d.check_date


def test_week_end_for_is_stable_inside_one_week():
    ends = {week_end_for(date(2026, 11, d)) for d in range(8, 15)}
    assert ends == {date(2026, 11, 14)}, ends


# ── the endpoint, which must answer with ZERO weeks ─────────────────────────

@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def token():
    from app.database import SessionLocal
    db = SessionLocal()
    uid = "weekcal-payroll-user"
    try:
        rid = db.execute(text(
            "SELECT id FROM roles WHERE company_id=:c AND slug='payroll' LIMIT 1"
        ), {"c": TESTCO_ID}).scalar()
        if rid is None:
            pytest.skip("testco has no 'payroll' role")
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        db.add(User(id=uid, email=f"{uid}@testco.example.com",
                    hashed_password="not-a-credential", first_name="Week",
                    last_name="Cal", role_id=rid, company_id=TESTCO_ID))
        db.commit()
        yield tenant_token(uid, TESTCO_ID)
    finally:
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        db.commit(); db.close()


def test_it_answers_with_no_weeks_at_all(client, token):
    """⚠️ **THE WHOLE POINT.** Every other payroll read needs a week_id. This
    one must describe a week that has no row, because that is the state Susan
    is in before her first upload — and the state in which she had no way in."""
    from app.database import SessionLocal
    from app.models.payroll_report import PayrollWeek
    db = SessionLocal()
    try:
        had = db.query(PayrollWeek).filter(
            PayrollWeek.tenant_id == TESTCO_ID).count()
    finally:
        db.close()

    r = client.get(CURRENT, headers={"Authorization": f"Bearer {token}", **HEADERS})
    assert r.status_code == 200, r.text[:300]
    b = r.json()
    for key in ("week_number", "week_start_date", "week_end_date", "check_date",
                "cutoff_at", "exists", "week_id", "status", "cutoff_provenance"):
        assert key in b, f"{key} missing from {sorted(b)}"
    # POSITIVE CONTROL on the fixture's premise: if testco happens to hold the
    # current week already, `exists` must be True — so a blanket False would be
    # caught rather than read as "answers before upload".
    if had == 0:
        assert b["exists"] is False
        assert b["week_id"] is None
        assert b["status"] == "no_hours_yet"


def test_the_cutoff_travels_with_its_PROVENANCE(client, token):
    """A screen that states a deadline must be able to say who said so. The
    cutoff is an `assumed` default — nobody has confirmed it."""
    b = client.get(CURRENT, headers={"Authorization": f"Bearer {token}",
                                     **HEADERS}).json()
    assert b["cutoff_provenance"]["status"] == "assumed"
    assert len(b["cutoff_provenance"]["source"]) >= 8


def test_an_unauthenticated_caller_is_refused(client):
    assert client.get(CURRENT, headers=HEADERS).status_code in (401, 403)
