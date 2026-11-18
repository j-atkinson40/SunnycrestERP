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


# ── the NOTE half, which PR B shipped without ───────────────────────────────
#
# ⚠️ **JAMES ASKED FOR THE CURRENT-WEEK LINE IN BOTH PLACES AND PR B DELIVERED
# ONE.** The Payroll page got it; the note did not, and the note is the first
# screen after sign-in and the one a payroll user LANDS on. She would have
# reached "Nothing needs saying today" and had no way in from there.


@pytest.fixture
def switch_on():
    """Payroll data on for the test, and back to whatever it was afterwards.

    ⚠️ The docstring said "back to absent", and it did exactly that — to a
    tenant whose switch was ON. See `tests/_payroll_switch.py`.
    """
    from tests._payroll_switch import payroll_switch

    with payroll_switch(TESTCO_ID, True):
        yield


def _note(client, token):
    r = client.get("/api/v1/note/today",
                   headers={"Authorization": f"Bearer {token}", **HEADERS})
    assert r.status_code == 200, r.text[:300]
    return r.json()


def _all_text(payload) -> str:
    """Every rendered string in the note, flattened.

    ⚠️ Reads the SPANS. The note renders typed spans rather than a
    `synthesized_text` field, and a test that read the latter would assert
    against something the surface does not display.
    """
    import json
    return json.dumps(payload)


def test_the_note_carries_the_CURRENT_WEEK_when_there_are_no_hours(
        client, token, switch_on):
    """⚠️ CONTENT, NOT STATUS. A 200 with an empty note is the exact failure
    being fixed — "Nothing needs saying today" on the screen she lands on."""
    from app.database import SessionLocal
    from app.models.payroll_report import PayrollWeek

    db = SessionLocal()
    try:
        current_end = _desc(date.today()).week_end_date
        has_row = db.query(PayrollWeek).filter(
            PayrollWeek.tenant_id == TESTCO_ID,
            PayrollWeek.week_end_date == current_end).count()
    finally:
        db.close()
    if has_row:
        pytest.skip("testco already holds the current week; this asserts the "
                    "no-hours state")

    text = _all_text(_note(client, token))
    want = str(_desc(date.today()).week_number)
    assert f"Week " in text, text[:400]
    assert want in text, f"week {want} not in the note: {text[:400]}"
    assert "no hours yet" in text.lower(), text[:400]


def test_the_note_line_addresses_the_week_by_its_END_not_by_a_row_id(
        client, token, switch_on):
    """⚠️ **ASSERTED ON THE ITEM'S OWN FIELDS, NOT ON THE WHOLE JSON.**

    The first version of this test searched the serialised note for the
    week-end string and passed — because that string also appears in
    `subject_id` and `condition_inputs`. A break test that changed the
    addressing left it GREEN, which is CLAUDE.md §11 shape 6: passing for a
    reason unrelated to what it claims.

    `subject_kind` is what the frontend's `focusTarget` switches on to build
    the query parameter, so that is the field pinned here. `payroll_week`
    would mean `week_id=<a date>`, which opens a Focus that cannot load.
    """
    import json

    payload = _note(client, token)
    # ⚠️ `prose`, not `items`. Read off the real payload rather than guessed:
    # the note serialises its composed fragments under `prose`, alongside
    # `standing_set`. A guessed key gave an empty list and an assertion that
    # read as "the line is absent" while the line was right there.
    items = [i for i in (payload.get("prose") or [])
             if "no hours yet" in json.dumps(i)]
    assert items, f"the open-week line is absent: {_all_text(payload)[:400]}"
    item = items[0]
    assert item["subject_kind"] == "payroll_week_end", item
    assert item["subject_id"] == _desc(date.today()).week_end_date.isoformat()
    assert item["target_key"] == "weekly-payroll", item
    assert item["kind"] == "prompt", item


def test_the_note_says_NOTHING_about_payroll_while_the_switch_is_off(
        client, token):
    """⚠️ THE POSITIVE CONTROL IN THE OTHER DIRECTION. Without it, a fragment
    that rendered unconditionally would satisfy both tests above — and would
    invite a tenant holding no payroll data to go and load some."""
    text = _all_text(_note(client, token))
    assert "no hours yet" not in text.lower(), text[:400]


# ── The copy fixes, as served (2026-11-18) ───────────────────────────────
#
# ⚠️ **THE PURE PHRASING IS TESTED IN `test_payroll_week_line_copy.py` ACROSS
# ALL SEVEN DAYS; THESE TWO ASSERT IT ARRIVES.** A correct sentence that the
# endpoint does not carry, and a deadline the payload drops, are both invisible
# to a test of the function that produced them.


def test_the_served_line_carries_TODAYS_wording_and_its_deadline(
        client, token, switch_on):
    """⚠️ Compared against the phrasing functions rather than a transcript, so
    this fails when the payload stops matching them rather than only on the one
    day of the week whose wording someone typed in."""
    import json
    from app.services.fragments.platform_defaults import (
        cutoff_words,
        week_range_words,
    )

    payload = _note(client, token)
    items = [i for i in (payload.get("prose") or [])
             if "no hours yet" in json.dumps(i)]
    if not items:
        pytest.skip("testco already holds the current week; this asserts the "
                    "no-hours state")
    item = items[0]
    w = _desc(date.today())

    assert week_range_words(w.week_start_date, w.week_end_date) in item["text"]
    assert cutoff_words(w.cutoff_at, date.today()) in item["text"]
    # ⚠️ "Nov 8–Nov 14" must be GONE, not merely joined by the new form.
    assert f"{w.week_start_date:%b} {w.week_start_date.day}–{w.week_end_date:%b}" \
        not in item["text"], item["text"]

    # The link names the act, and the deadline travels with the prompt.
    assert item["action_label"] == "Upload hours", item
    assert item["defer_not_after"] == w.cutoff_at.date().isoformat(), item


def test_the_served_line_offers_NO_deferral_once_the_cutoff_is_here(
        client, token, switch_on):
    """⚠️ **ASSERTED AGAINST TODAY'S TRUE STATE, NOT A FIXED EXPECTATION.** The
    honest set depends on which day the suite runs: ahead of the cutoff some
    presets stand, and on or after it none do. Pinning one of those would make
    the test pass on four days a week and fail on three, so it states the rule
    and checks the payload against it.
    """
    import json
    from app.services.note.deferral import allowed_presets

    payload = _note(client, token)
    items = [i for i in (payload.get("prose") or [])
             if "no hours yet" in json.dumps(i)]
    if not items:
        pytest.skip("testco already holds the current week; this asserts the "
                    "no-hours state")
    item = items[0]
    cutoff_day = _desc(date.today()).cutoff_at.date()

    assert item["defer_presets"] == list(
        allowed_presets(today=date.today(), not_after=cutoff_day)
    ), item
    if cutoff_day <= date.today():
        assert item["defer_presets"] == [], (
            "the note offered a deferral on or after the cutoff day", item)
    else:
        assert "tomorrow" in item["defer_presets"], item
        assert "next_month" not in item["defer_presets"], (
            "next month is four weeks past a Wednesday cutoff", item)
