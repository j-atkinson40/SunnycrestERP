"""The R-115 endpoints the union-form Focus reads — Payroll 5b.

⚠️ **THE FIGURES ARE SEEDED AS CHECK LINES, NOT AS TOTALS.** A fixture that
wrote `total_dues` directly would test the serialiser and nothing else: the
form's whole claim is that the number came from what was *deducted*, and the
only way to assert that is to put deduction lines in and read the form out.
So these seed `payroll_checks` + `payroll_check_lines` the way the register
importer does, and let `rows_for_month` find them.

⚠️ **AND THE STAGE IS DRIVEN BY THE CLOCK, WHICH THESE TESTS CANNOT MOVE.**
`GET /r115` stamps the stage with `date.today()`. Rather than monkeypatch the
route, the month under test is chosen RELATIVE to today — a month safely in
the past is always `ready`, and the current month is `filling` until its last
check lands. The pure stage logic is driven across every day of a cycle in
`test_payroll_r115_schedule.py`; this file asserts the endpoint carries what
that module produced, which is the division of labour that keeps both honest.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.models.user import User
from app.services.payroll import r115_schedule, r115_settings
from tests._payroll_switch import payroll_switch
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture
from tests._two_step import tenant_token

_canonical_tenant = make_canonical_tenant_fixture()

HEADERS = {"X-Company-Slug": "testco"}
BASE = "/api/v1/payroll-reports"
SETTINGS = "/api/v1/payroll-reports/settings/union-form"

#: A month comfortably in the past, so its last check date has certainly
#: passed whenever this suite runs. Derived from today rather than fixed, so
#: the suite does not quietly start asserting a future month in 2027.
_TODAY = date.today()
PAST_YEAR, PAST_MONTH = ((_TODAY.year - 1, 12) if _TODAY.month == 1
                         else (_TODAY.year, _TODAY.month - 1))


def _check_dates(year: int, month: int) -> list[date]:
    return r115_schedule.check_dates_in(year, month)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def tokens():
    """An admin (who holds every payroll permission) and a payroll reviewer."""
    from app.database import SessionLocal
    from app.models.role import Role

    db = SessionLocal()
    made = []
    try:
        out = {}
        for slug in ("admin", "payroll"):
            role = (db.query(Role)
                    .filter(Role.company_id == TESTCO_ID, Role.slug == slug)
                    .first())
            if role is None:
                pytest.skip(f"testco has no {slug} role seeded")
            uid = f"r115ep-{slug}"
            if db.query(User).filter(User.id == uid).first() is None:
                db.add(User(id=uid, email=f"{uid}@testco.com",
                            hashed_password="x", first_name="R115",
                            last_name=slug.title(),
                            company_id=TESTCO_ID, role_id=role.id,
                            is_active=True))
                made.append(uid)
            out[slug] = uid
        db.commit()
        yield {k: tenant_token(v, TESTCO_ID) for k, v in out.items()}
    finally:
        for uid in made:
            db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        db.commit()
        db.close()


def _auth(token):
    return {"Authorization": f"Bearer {token}", **HEADERS}


@pytest.fixture
def october_checks():
    """Two union members paid on every check date of the past month.

    Dues are whole cents chosen so the month's total is checkable by hand:
    2 members × 5 checks × $18.00 = $180.00, and 2 × 5 × 40.00 = 400.00 hours.
    ⚠️ The expected totals are written as literals below with that arithmetic
    shown, never computed from the same sum the code under test performs.
    """
    from app.database import SessionLocal
    from app.models.payroll_report import (
        PayrollCheck,
        PayrollCheckLine,
        PayrollRuleSet,
    )

    db = SessionLocal()
    made: list[str] = []
    rule_id = None
    try:
        # ⚠️ **A RULE SET IS REQUIRED, AND NOT BY ACCIDENT.**
        # `resolve_rule_set` refuses to fall back to defaults so that a
        # result records which rules produced it. Lines 5-7 are dues
        # components, so a tenant with no rule set has no computable lines —
        # the endpoint reports that rather than defaulting, and the test for
        # it is `test_a_tenant_with_no_rule_set_gets_a_REASON`.
        existing = (db.query(PayrollRuleSet)
                    .filter(PayrollRuleSet.tenant_id == TESTCO_ID)
                    .first())
        if existing is None:
            rule_id = str(uuid.uuid4())
            db.add(PayrollRuleSet(id=rule_id, tenant_id=TESTCO_ID,
                                  effective_date=date(2020, 1, 1)))
            db.flush()
        # ⚠️ **THIS MONTH IS OWNED BY THIS FIXTURE, NOT INHERITED.** The
        # walk-through seed writes register checks into the same tenant and
        # the same derived month, so a total asserted here was silently the
        # sum of both — 394.25 where the arithmetic said 180.00. A test that
        # asserts on a month's figures must establish that month's contents.
        # The walk re-seeds its own rows before it runs.
        db.execute(text("DELETE FROM payroll_check_lines WHERE check_id IN "
                        "(SELECT id FROM payroll_checks WHERE tenant_id=:t "
                        " AND extract(year from check_date)=:y "
                        " AND extract(month from check_date)=:m)"),
                   {"t": TESTCO_ID, "y": PAST_YEAR, "m": PAST_MONTH})
        db.execute(text("DELETE FROM payroll_checks WHERE tenant_id=:t "
                        "AND extract(year from check_date)=:y "
                        "AND extract(month from check_date)=:m"),
                   {"t": TESTCO_ID, "y": PAST_YEAR, "m": PAST_MONTH})
        for emp_id, person in (("8001", "Alpha, Ann A"), ("8002", "Bravo, Bob B")):
            for i, when in enumerate(_check_dates(PAST_YEAR, PAST_MONTH)):
                cid = str(uuid.uuid4())
                db.add(PayrollCheck(
                    id=cid, tenant_id=TESTCO_ID, emp_id=emp_id, person=person,
                    check_number=f"R115EP-{emp_id}-{i}", check_date=when,
                    source_page=0))
                db.add(PayrollCheckLine(
                    id=str(uuid.uuid4()), tenant_id=TESTCO_ID, check_id=cid,
                    kind="earning", code="Reg", hours=D("40.00"),
                    amount=D("1000.00")))
                db.add(PayrollCheckLine(
                    id=str(uuid.uuid4()), tenant_id=TESTCO_ID, check_id=cid,
                    kind="deduction", code="Union", amount=D("18.00")))
                made.append(cid)
        db.commit()
        yield
    finally:
        # ⚠️ Lines first: the FK from line to check has no cascade declared
        # here, and a teardown that fails halfway leaves rows a later run
        # counts. Same discipline as `_payroll_switch` — put it back as found.
        if made:
            db.execute(text("DELETE FROM payroll_check_lines WHERE check_id = ANY(:ids)"),
                       {"ids": made})
            db.execute(text("DELETE FROM payroll_checks WHERE id = ANY(:ids)"),
                       {"ids": made})
        db.execute(
            text("DELETE FROM payroll_union_forms_r115 WHERE tenant_id=:t "
                 "AND year=:y AND month=:m"),
            {"t": TESTCO_ID, "y": PAST_YEAR, "m": PAST_MONTH})
        if rule_id:
            db.execute(text("DELETE FROM payroll_rule_sets WHERE id=:i"),
                       {"i": rule_id})
        db.commit()
        db.close()


@pytest.fixture
def switch_on():
    with payroll_switch(TESTCO_ID, True):
        yield


# ── GET /r115 — what the Focus loads ─────────────────────────────────────


def test_a_month_with_no_form_yet_still_answers_with_its_STAGE(
        client, tokens, switch_on, october_checks):
    """⚠️ **THE FOCUS OPENS BEFORE THE FORM EXISTS, AND MUST STILL SAY WHERE
    THE MONTH STANDS.** An endpoint that 404'd here would leave the screen
    unable to render the one thing it was opened to show."""
    r = client.get(f"{BASE}/r115", params={"year": PAST_YEAR, "month": PAST_MONTH},
                   headers=_auth(tokens["payroll"]))
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body["form"] is None
    assert body["schedule"]["stage"] == "ready"
    assert body["schedule"]["stage_label"] == "Ready"
    assert body["schedule"]["last_check_date"] == \
        _check_dates(PAST_YEAR, PAST_MONTH)[-1].isoformat()


def test_the_unbuilt_month_carries_a_PREVIEW_with_the_remittance(
        client, tokens, switch_on, october_checks):
    """The figures sit beside the button that creates the form, rather than an
    empty frame with a verb on it."""
    body = client.get(f"{BASE}/r115",
                      params={"year": PAST_YEAR, "month": PAST_MONTH},
                      headers=_auth(tokens["payroll"])).json()
    pv = body["preview"]
    assert pv is not None, body
    # 2 members × 5 checks × $18.00 = $180.00; × 40.00 hours = 400.00.
    assert pv["totals"]["dues_deducted"] == "180.00", pv["totals"]
    # ⚠️ HOURS COMPARED AS A NUMBER, MONEY AS A STRING. Hours serialise
    # without trailing zeros ("400", not "400.00") and the claim here is
    # about the quantity; money's exact formatting IS the claim, because it
    # is what gets printed on the form.
    assert D(pv["totals"]["dues_hours"]) == D("400.00"), pv["totals"]
    assert len(pv["rows"]) == 2
    assert pv["total_remittance"] == "180.00", "the money actually deducted"


def test_LINE_4_IS_THE_EARNINGS_AND_THE_REMITTANCE_IS_ITS_OWN_FIELD(
        client, tokens, switch_on, october_checks):
    """⚠️ **THIS TEST PINS THE CORRECTION OF 2026-11-18.**

    Its first version asserted `line_4 == dues_deducted` and was GREEN — it
    was written from an answer that had conflated line 4 with Total
    Remittance, so the test certified the mistake. CLAUDE.md §11 shape 9: a
    check with full contact, asserting the wrong specification, because the
    expected value came from the same misunderstanding as the code.

    Line 4 is **Total Earnings (excl. lump sum)** — the dues WAGE. The money
    is the un-numbered **Total Remittance**. The four candidate figures are
    deliberately distinct in this fixture, so a line wired to the wrong one
    cannot pass:

        earnings   10 checks x $1,000.00 = 10,000.00   <- line 4
        remittance 10 checks x    $18.00 =    180.00   <- Total Remittance
        hours      10 checks x     40.00 =    400.00   <- line 3
        members                                    2   <- line 2
    """
    body = client.get(f"{BASE}/r115",
                      params={"year": PAST_YEAR, "month": PAST_MONTH},
                      headers=_auth(tokens["payroll"])).json()
    by_key = {ln["key"]: ln for ln in body["lines"]}

    assert by_key["total_earnings"]["number"] == 4
    assert by_key["total_earnings"]["label"] == "Total Earnings (excl. lump sum)"
    assert by_key["total_earnings"]["value"] == "10000.00"

    assert by_key["total_remittance"]["number"] is None, (
        "the remittance is the un-numbered field at the foot, not a line")
    assert by_key["total_remittance"]["value"] == "180.00"

    # The confusion this test exists to prevent, stated as inequalities.
    assert by_key["total_earnings"]["value"] != by_key["total_remittance"]["value"]
    assert by_key["total_earnings"]["value"] != by_key["hours_in_earnings"]["value"]
    assert by_key["total_earnings"]["value"] != by_key["members_paying_dues"]["value"]


def test_every_numbered_line_is_present_in_FORM_ORDER(
        client, tokens, switch_on, october_checks):
    """The print view lays the form out in order, so the server serves it in
    order rather than leaving a screen to sort by a number it inferred."""
    body = client.get(f"{BASE}/r115",
                      params={"year": PAST_YEAR, "month": PAST_MONTH},
                      headers=_auth(tokens["payroll"])).json()
    assert [ln["number"] for ln in body["lines"]] == [1, 2, 3, 4, 5, 6, 7, 8, 9, None]
    assert [ln["key"] for ln in body["lines"]] == [
        "members_in_unit", "members_paying_dues", "hours_in_earnings",
        "total_earnings", "percentage_dues", "per_hour_dues",
        "initiation_fees", "lump_sum", "misc", "total_remittance",
    ]


def test_the_rates_are_printed_on_lines_5_and_6_and_nowhere_else(
        client, tokens, switch_on, october_checks):
    body = client.get(f"{BASE}/r115",
                      params={"year": PAST_YEAR, "month": PAST_MONTH},
                      headers=_auth(tokens["payroll"])).json()
    rates = {ln["number"]: ln["rate"] for ln in body["lines"]}
    assert rates[5] == "1.45"
    assert rates[6] == ".02"
    assert [n for n, r in rates.items() if r is not None] == [5, 6]


def test_lines_8_and_9_are_BLANK_rather_than_zero(
        client, tokens, switch_on, october_checks):
    """⚠️ A zero asserts "none were paid this month"; a blank says the line
    does not apply. No data path feeds either today, so the honest mark is
    the blank."""
    body = client.get(f"{BASE}/r115",
                      params={"year": PAST_YEAR, "month": PAST_MONTH},
                      headers=_auth(tokens["payroll"])).json()
    by_num = {ln["number"]: ln for ln in body["lines"]}
    for n in (8, 9):
        assert by_num[n]["blank"] is True, by_num[n]
        assert by_num[n]["value"] is None, by_num[n]
    # The control: a line that IS computed is not blank.
    assert by_num[7]["blank"] is False and by_num[7]["value"] == "0.00"


def test_line_5_plus_6_plus_7_equals_the_remittance(
        client, tokens, switch_on, october_checks):
    """James's confirmation.

    ⚠️ **IT CANNOT FAIL WHILE LINE 5 IS A PLUG, AND IS ASSERTED ANYWAY** —
    as a statement of the form's shape, not as a check. The figure that CAN
    disagree is `percentage_dues_variance`, asserted in the next test.
    """
    from decimal import Decimal as _D

    body = client.get(f"{BASE}/r115",
                      params={"year": PAST_YEAR, "month": PAST_MONTH},
                      headers=_auth(tokens["payroll"])).json()
    by_num = {ln["number"]: ln for ln in body["lines"]}
    total = _D([ln for ln in body["lines"] if ln["number"] is None][0]["value"])
    assert (_D(by_num[5]["value"]) + _D(by_num[6]["value"])
            + _D(by_num[7]["value"])) == total
    assert body["adds_up"] is True


def test_the_variance_against_the_RULES_is_reported_rather_than_absorbed(
        client, tokens, switch_on, october_checks):
    """⚠️ **THE NUMBER THAT CAN ACTUALLY DISAGREE.** This fixture deducts a
    flat $18.00 per check, which is NOT what the rules compute — a = round2(
    1000 x .0145) = 14.50, b = round2(25 x .6461) = 16.15, so min(a,b) = 14.50
    and c = 0.80, giving 15.30. The register says 18.00. That 2.70 x 10 gap is
    exactly the rules-versus-deduction disagreement the spec measures at 76 of
    629 checks, and the form must SHOW it rather than hide it inside line 5.

        line 5 (plug)       180.00 - 8.00 - 0.00 = 172.00
        computed min(a,b)   14.50 x 10           = 145.00
        variance                                 =  27.00
    """
    from decimal import Decimal as _D

    body = client.get(f"{BASE}/r115",
                      params={"year": PAST_YEAR, "month": PAST_MONTH},
                      headers=_auth(tokens["payroll"])).json()
    assert body["percentage_dues_computed"] == "145.00", body["percentage_dues_computed"]
    assert body["percentage_dues_variance"] == "27.00", body["percentage_dues_variance"]
    by_num = {ln["number"]: ln for ln in body["lines"]}
    assert by_num[5]["value"] == "172.00"
    assert by_num[6]["value"] == "8.00", "round2(40 x .02) = 0.80, x10 checks"
    assert (_D(body["percentage_dues_variance"])
            == _D(by_num[5]["value"]) - _D(body["percentage_dues_computed"]))


def test_a_built_form_is_served_with_the_remittance_and_no_preview(
        client, tokens, switch_on, october_checks):
    """⚠️ A STORED FORM AND TODAY'S RECOMPUTATION MUST NOT APPEAR TOGETHER.
    The stored table is the record of what was sent; showing a fresh preview
    next to it invites reading the wrong one."""
    built = client.post(f"{BASE}/r115",
                        data={"year": PAST_YEAR, "month": PAST_MONTH},
                        headers=_auth(tokens["admin"]))
    assert built.status_code == 200, built.text[:300]

    body = client.get(f"{BASE}/r115",
                      params={"year": PAST_YEAR, "month": PAST_MONTH},
                      headers=_auth(tokens["payroll"])).json()
    assert body["preview"] is None
    form = body["form"]
    assert form["status"] == "draft"
    assert form["total_dues"] == "180.00"
    assert form["total_remittance"] == "180.00"
    assert body["schedule"]["stage"] == "ready"


# ── the lifecycle, in the brief's words ──────────────────────────────────


def test_approve_then_mark_sent_walks_the_stored_flow(
        client, tokens, switch_on, october_checks):
    """filling/ready → **approve** → **mark sent**, which stores
    draft → submitted → filed. The two vocabularies are mapped in one place
    (`r115_schedule.STAGE_LABELS`); this asserts the acts reach the stages."""
    built = client.post(f"{BASE}/r115", data={"year": PAST_YEAR, "month": PAST_MONTH},
                        headers=_auth(tokens["admin"])).json()
    fid = built["id"]

    r = client.post(f"{BASE}/r115/{fid}/status", data={"to_status": "submitted"},
                    headers=_auth(tokens["admin"]))
    assert r.status_code == 200, r.text[:300]
    body = client.get(f"{BASE}/r115", params={"year": PAST_YEAR, "month": PAST_MONTH},
                      headers=_auth(tokens["payroll"])).json()
    assert body["schedule"]["stage"] == "approved"
    assert body["schedule"]["stage_label"] == "Approved"

    r = client.post(f"{BASE}/r115/{fid}/status", data={"to_status": "filed"},
                    headers=_auth(tokens["admin"]))
    assert r.status_code == 200, r.text[:300]
    body = client.get(f"{BASE}/r115", params={"year": PAST_YEAR, "month": PAST_MONTH},
                      headers=_auth(tokens["payroll"])).json()
    assert body["schedule"]["stage"] == "sent"
    assert body["schedule"]["stage_label"] == "Sent"


def test_a_sent_form_refuses_to_move_anywhere(
        client, tokens, switch_on, october_checks):
    """`filed` is terminal by having no entry in `R115_TRANSITIONS`. The
    endpoint must surface that as a refusal rather than a 500."""
    built = client.post(f"{BASE}/r115", data={"year": PAST_YEAR, "month": PAST_MONTH},
                        headers=_auth(tokens["admin"])).json()
    fid = built["id"]
    for to in ("submitted", "filed"):
        client.post(f"{BASE}/r115/{fid}/status", data={"to_status": to},
                    headers=_auth(tokens["admin"]))
    for to in ("draft", "submitted", "filed"):
        r = client.post(f"{BASE}/r115/{fid}/status", data={"to_status": to},
                        headers=_auth(tokens["admin"]))
        assert r.status_code == 409, f"{to}: {r.status_code} {r.text[:200]}"
        assert "terminal" in r.text.lower(), r.text[:200]


# ── the due date ─────────────────────────────────────────────────────────


def test_no_due_day_is_configured_by_default_and_the_date_is_NULL(
        client, tokens, switch_on, october_checks):
    """"No due date set" is the client's wording for this null. The server
    does not send the sentence."""
    r = client.get(SETTINGS, headers=_auth(tokens["admin"]))
    assert r.status_code == 200, r.text[:200]
    assert r.json()[r115_settings.R115_DUE_DAY] is None

    body = client.get(f"{BASE}/r115", params={"year": PAST_YEAR, "month": PAST_MONTH},
                      headers=_auth(tokens["payroll"])).json()
    assert body["schedule"]["due_date"] is None
    assert body["schedule"]["overdue"] is False
    assert "No due date" not in r.text


def test_an_admin_sets_the_day_and_the_form_gains_a_DATE(
        client, tokens, switch_on, october_checks):
    try:
        r = client.put(SETTINGS, data={"due_day": 15}, headers=_auth(tokens["admin"]))
        assert r.status_code == 200, r.text[:200]
        assert r.json()[r115_settings.R115_DUE_DAY] == 15
        assert r.json()["changed"] is True

        body = client.get(f"{BASE}/r115",
                          params={"year": PAST_YEAR, "month": PAST_MONTH},
                          headers=_auth(tokens["payroll"])).json()
        # The 15th of the month AFTER the period.
        y, m = ((PAST_YEAR + 1, 1) if PAST_MONTH == 12
                else (PAST_YEAR, PAST_MONTH + 1))
        assert body["schedule"]["due_date"] == date(y, m, 15).isoformat()
        assert body["schedule"]["due_day_setting"] == 15
    finally:
        client.put(SETTINGS, data={"due_day": ""}, headers=_auth(tokens["admin"]))


def test_clearing_the_day_is_a_real_operation(client, tokens, switch_on):
    """A tenant whose local changed its deadline must be able to get back to
    "we do not know" without inventing a placeholder."""
    client.put(SETTINGS, data={"due_day": 20}, headers=_auth(tokens["admin"]))
    # ⚠️ CLEARING THE DAY IS ITS OWN FIELD NOW. An omitted field is
    # UNCHANGED under the four-field endpoint, so clearing is explicit.
    r = client.put(SETTINGS, data={"due_day": ""}, headers=_auth(tokens["admin"]))
    assert r.status_code == 200, r.text[:200]
    assert r.json()[r115_settings.R115_DUE_DAY] is None
    assert client.get(SETTINGS, headers=_auth(tokens["admin"])).json()[
        r115_settings.R115_DUE_DAY] is None


@pytest.mark.parametrize("bad", [0, 32, 45, -3])
def test_a_day_outside_the_month_is_REFUSED_rather_than_clamped(
        client, tokens, switch_on, bad):
    """⚠️ A 400 means the admin finds out. Clamping would store a number they
    did not choose; storing it unvalidated would make `due_day` read it back
    as unset, and the setting would appear not to have saved."""
    r = client.put(SETTINGS, data={"due_day": bad}, headers=_auth(tokens["admin"]))
    assert r.status_code == 400, f"{bad}: {r.status_code} {r.text[:200]}"
    assert r.json()["detail"]["code"] == "due_day_out_of_range"
    assert client.get(SETTINGS, headers=_auth(tokens["admin"])).json()[
        r115_settings.R115_DUE_DAY] is None


def test_a_no_op_write_records_nothing(client, tokens, switch_on):
    """Same discipline as the data switch: the audit trail stays readable."""
    r = client.put(SETTINGS, data={}, headers=_auth(tokens["admin"]))
    assert r.json()["changed"] is False


def test_the_due_day_is_ADMIN_only(client, tokens, switch_on):
    """⚠️ THE PAYROLL REVIEWER READS THE DEADLINE AND DOES NOT SET IT. It is a
    tenant-level agreement with the local, like the data switch."""
    assert client.get(SETTINGS, headers=_auth(tokens["payroll"])).status_code == 403
    assert client.put(SETTINGS, data={"due_day": 12},
                      headers=_auth(tokens["payroll"])).status_code == 403
    assert client.get(SETTINGS, headers=_auth(tokens["admin"])).json()[
        r115_settings.R115_DUE_DAY] is None


def test_overdue_is_reported_when_the_deadline_has_passed(
        client, tokens, switch_on, october_checks):
    """Driven by setting a deadline that is already behind us, rather than by
    waiting for one to pass."""
    try:
        # Day 1 of the month after a month that has already ended is in the
        # past whenever this runs.
        client.put(SETTINGS, data={"due_day": 1}, headers=_auth(tokens["admin"]))
        body = client.get(f"{BASE}/r115",
                          params={"year": PAST_YEAR, "month": PAST_MONTH},
                          headers=_auth(tokens["payroll"])).json()
        due = date.fromisoformat(body["schedule"]["due_date"])
        if due >= date.today():
            pytest.skip("the 1st of this month has not passed yet")
        assert body["schedule"]["overdue"] is True
    finally:
        client.put(SETTINGS, data={"due_day": ""}, headers=_auth(tokens["admin"]))


# ── the gates that were already there ────────────────────────────────────


def test_the_switch_still_refuses_the_whole_surface(client, tokens):
    """⚠️ NO `switch_on` FIXTURE HERE, AND THE SWITCH IS SET OFF EXPLICITLY
    rather than inherited — the six suites that inherited it are what blanked
    a live note, and this file is not going to add a seventh."""
    with payroll_switch(TESTCO_ID, False):
        r = client.get(f"{BASE}/r115",
                       params={"year": PAST_YEAR, "month": PAST_MONTH},
                       headers=_auth(tokens["payroll"]))
        assert r.status_code == 403, r.text[:200]
        assert r.json()["detail"]["code"] == "payroll_data_disabled"


def test_an_unauthenticated_caller_is_refused(client):
    r = client.get(f"{BASE}/r115", params={"year": PAST_YEAR, "month": PAST_MONTH},
                   headers=HEADERS)
    assert r.status_code in (401, 403), r.status_code


def test_the_due_day_can_be_CLEARED_through_the_endpoint(
        client, tokens, switch_on):
    """⚠️ **THIS WAS NOT POSSIBLE WHEN FIRST BUILT, AND THE 422 LOOKED LIKE A
    TEST BUG.** `due_day` was declared `int | None`, so the empty body a form
    sends when somebody clears the field was rejected as unparseable — the
    deadline could be set and never unset, and the only symptom was a 422 on
    a path nobody had exercised. The field is parsed from a string now:
    omitted is unchanged, empty clears, anything else must be a day.
    """
    client.put(SETTINGS, data={"due_day": 9}, headers=_auth(tokens["admin"]))
    assert client.get(SETTINGS, headers=_auth(tokens["admin"])).json()[
        r115_settings.R115_DUE_DAY] == 9

    r = client.put(SETTINGS, data={"due_day": ""}, headers=_auth(tokens["admin"]))
    assert r.status_code == 200, r.text[:200]
    assert r.json()[r115_settings.R115_DUE_DAY] is None
    assert client.get(SETTINGS, headers=_auth(tokens["admin"])).json()[
        r115_settings.R115_DUE_DAY] is None


def test_a_non_numeric_due_day_is_refused_with_a_reason(client, tokens, switch_on):
    r = client.put(SETTINGS, data={"due_day": "the 15th"},
                   headers=_auth(tokens["admin"]))
    assert r.status_code == 400, r.text[:200]
    assert r.json()["detail"]["code"] == "due_day_not_a_number"


def test_an_omitted_field_leaves_the_others_ALONE(client, tokens, switch_on):
    """⚠️ A PUT that cleared every absent field would wipe the union local
    the moment somebody saved only the due date. Omission is not a clear."""
    try:
        client.put(SETTINGS, data={"local": "14532-17", "plant": "Auburn"},
                   headers=_auth(tokens["admin"]))
        client.put(SETTINGS, data={"due_day": 15}, headers=_auth(tokens["admin"]))
        got = client.get(SETTINGS, headers=_auth(tokens["admin"])).json()
        assert got[r115_settings.R115_LOCAL] == "14532-17", got
        assert got[r115_settings.R115_PLANT] == "Auburn", got
        assert got[r115_settings.R115_DUE_DAY] == 15, got
    finally:
        client.put(SETTINGS, data={"due_day": "", "local": "", "plant": "",
                                   "completed_by": ""},
                   headers=_auth(tokens["admin"]))


def test_the_header_says_NOT_SET_as_a_null_rather_than_a_sentence(
        client, tokens, switch_on, october_checks):
    """⚠️ **A DEFAULTED LOCAL WOULD PRINT ONE LICENSEE'S UNION ON ANOTHER'S
    FILED FORM.** Absent is served as `null` and the screen words it; the
    server does not send "Not set", because a second surface would then have
    to match that sentence by hand."""
    body = client.get(f"{BASE}/r115",
                      params={"year": PAST_YEAR, "month": PAST_MONTH},
                      headers=_auth(tokens["payroll"])).json()
    h = body["header"]
    assert h["local"] is None and h["plant"] is None and h["completed_by"] is None
    assert "Not set" not in repr(h)
    # The facts that are NOT settings are present, which is the control:
    # an all-null header would satisfy the assertions above vacuously.
    assert h["company"], h
    assert h["dues_for_month_of"], h
    assert h["unit"] is None, "unit is blank for this licensee, deliberately"


def test_the_header_carries_the_settings_once_an_admin_sets_them(
        client, tokens, switch_on, october_checks):
    try:
        client.put(SETTINGS, data={"local": "14532-17", "plant": "Auburn",
                                   "completed_by": "S. Walkthrough"},
                   headers=_auth(tokens["admin"]))
        h = client.get(f"{BASE}/r115",
                       params={"year": PAST_YEAR, "month": PAST_MONTH},
                       headers=_auth(tokens["payroll"])).json()["header"]
        assert h["local"] == "14532-17"
        assert h["plant"] == "Auburn"
        assert h["completed_by"] == "S. Walkthrough"
        # Pay period comes from the CHECK DATES the form covers, not the
        # calendar month's edges — the R-115 is grouped by check date.
        dates = _check_dates(PAST_YEAR, PAST_MONTH)
        assert h["pay_period_begin"] == dates[0].isoformat()
        assert h["pay_period_end"] == dates[-1].isoformat()
    finally:
        client.put(SETTINGS, data={"local": "", "plant": "", "completed_by": ""},
                   headers=_auth(tokens["admin"]))


def test_a_form_whose_line_2_exceeds_line_1_WARNS(
        client, tokens, switch_on, october_checks):
    """⚠️ TESTCO'S ROSTER HAS NO UNION MEMBERS, so this fixture's two paying
    members contradict line 1. That is a real state — an unreconciled roster
    — and the form says so rather than filing a contradiction."""
    body = client.get(f"{BASE}/r115",
                      params={"year": PAST_YEAR, "month": PAST_MONTH},
                      headers=_auth(tokens["payroll"])).json()
    by_num = {ln["number"]: ln for ln in body["lines"]}
    if int(by_num[2]["value"]) <= int(by_num[1]["value"]):
        pytest.skip("this tenant's roster covers its payers; nothing to warn about")
    assert body["warnings"], body["lines"]
    assert "bargaining unit" in body["warnings"][0]
