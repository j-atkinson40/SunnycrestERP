"""Vacation pay — Payroll 5c.

⚠️ **BEFORE THIS, VACATION PAY WAS COMPUTED NOWHERE IN THE PRODUCT.** Measured
2026-11-23: the rulebook keys existed, the engine was written and tested
against the real register, and **no code path in `app/` or `scripts/` called
any of it.** No table, no writer, no surface. Fourth unprovisioned entrance of
the arc, after `payroll_status`, the Employee Hours parser and `PayrollPunch`.

⚠️ **THE GOLDENS ARE JAMES'S, STATED AS LITERALS.** Not computed from the
engine — a test that derives its expectation from the code under test agrees
with a wrong engine as readily as a right one.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest

from app.services.payroll.engine import allocate_cumulative, vacation_bonus_for_year
from app.services.payroll.rules import DEFAULT_RULES, RULE_FIELDS, PayrollRules
from app.services.payroll.vacation import entitlement as ent
from app.services.payroll.vacation import pay as vac_pay
from app.services.payroll.vacation.pay import VacationPayUnavailable

R = DEFAULT_RULES

#: Hunt's prior year, from the accountant's workbook Vac Calc tab — the one
#: case in the year whose rate is not already exact to 4dp, and therefore the
#: only one that can tell truncation from rounding (§11.13).
HUNT_GROSS = D("33062.74")
HUNT_HOURS = D("1512.36")


# ── the goldens ──────────────────────────────────────────────────────────


def test_HUNT_40h_first_week_is_900_46_plus_75_00():
    """⚠️ **THE CENT THAT TRUNCATION MOVES.** Rounding the rate to 4dp gives
    900.47 and so does leaving it unrounded; only truncation gives 900.46,
    which is what Hunt's real 2026 Vac line says."""
    p = vac_pay.union_pay(
        hours=40, prior_year_gross=HUNT_GROSS, prior_year_hours=HUNT_HOURS,
        entitlement_hours=40, rules=R, checks=1,
        bonus_part_start=1, bonus_part_count=1)
    assert p.rate == D("22.5116")
    assert len(p.parts) == 1
    assert p.parts[0].vac_pay == D("900.46")
    assert p.parts[0].vac_bonus == D("75.00")
    # ⚠️ TWO LINES, NOT ONE TOTAL. The register pays them separately; folding
    # them is the superseded form.
    assert p.parts[0].total == D("975.46")


@pytest.mark.parametrize("hours, parts, expected", [
    (40, 1, ["75.00"]),
    (48, 1, ["85.00"]),
    (80, 2, ["62.50", "62.50"]),
    # ⚠️ THE ONE GROUP IN THE MEASURED YEAR THAT DISCRIMINATES. Cumulative
    # gives 51.67/51.66/51.67; largest-remainder gives 51.67/51.67/51.66. The
    # register chose cumulative. The other 12 groups divide into exactly equal
    # cents and cannot tell the two apart (§11.11).
    (120, 3, ["51.67", "51.66", "51.67"]),
    # 20 days, and the tiers run out at 15 — 155.00 is a CEILING, not a cap.
    (160, 4, ["38.75", "38.75", "38.75", "38.75"]),
])
def test_the_bonus_goldens(hours, parts, expected):
    total = vacation_bonus_for_year(hours, R)
    got = [str(x) for x in allocate_cumulative(total, parts)]
    assert got == expected
    assert sum(allocate_cumulative(total, parts)) == total


def test_NON_UNION_16h_at_20_is_320_and_NO_BONUS():
    """⚠️ The bonus comes from the union agreement's day tiers. Paying it to
    somebody not covered by that agreement would invent an entitlement."""
    p = vac_pay.non_union_pay(hours=16, regular_rate=D("20.00"))
    assert p.parts[0].vac_pay == D("320.00")
    assert p.parts[0].vac_bonus == D("0.00")
    assert p.bonus_year_total is None
    assert p.union is False


# ── the truncation, now an effective-dated key ───────────────────────────


def test_the_rate_truncation_is_a_RULEBOOK_KEY_and_is_READ():
    """⚠️ §11.13 asked for this and James ruled it in the 5c brief. It was a
    constant in the engine, so changing it would have reached BACKWARDS through
    every recomputed figure with nothing to say which rule made the old ones.

    The control is the second assertion: a different dp must give a different
    rate, or the key is decorative."""
    assert "vacation_rate_truncate_dp" in RULE_FIELDS, (
        "not in RULE_FIELDS means no column, which means not effective-dated")
    at4 = vac_pay.union_pay(
        hours=40, prior_year_gross=HUNT_GROSS, prior_year_hours=HUNT_HOURS,
        entitlement_hours=40, rules=R).rate
    at2 = vac_pay.union_pay(
        hours=40, prior_year_gross=HUNT_GROSS, prior_year_hours=HUNT_HOURS,
        entitlement_hours=40,
        rules=replace(R, vacation_rate_truncate_dp=2)).rate
    assert at4 == D("22.5116")
    assert at2 == D("22.51"), "the key is not being read"


def test_a_nonsense_truncation_is_refused_when_the_RULE_is_made():
    """⚠️ NOT at calculate time. `quantize` raises on an exponent outside the
    Decimal context, so an unbounded int would turn every vacation rate into an
    InvalidOperation hours after somebody typed it."""
    with pytest.raises(ValueError, match="between 0 and 8"):
        PayrollRules(vacation_rate_truncate_dp=50)


# ── entitlement ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("years, hours", [
    (0, "40"), (1, "40"), (2, "80"), (5, "80"),
    (6, "120"), (15, "120"), (16, "160"), (40, "160"),
])
def test_the_service_tiers(years, hours):
    assert ent.hours_for_service(years, R) == D(hours)


def test_years_are_COMPLETED_not_elapsed_and_rounded():
    """⚠️ Somebody hired on 1 March has not completed a year on 28 February,
    and a tier boundary is exactly where that pays somebody differently."""
    assert ent.completed_years(date(2020, 3, 1), on=date(2026, 2, 28)) == 5
    assert ent.completed_years(date(2020, 3, 1), on=date(2026, 3, 1)) == 6


def test_a_rule_set_with_NO_TIERS_yields_nothing_rather_than_zero():
    """A rule set made before 5c has NULL tiers. That is "nobody chose", which
    is not "no vacation" — the service says so instead of answering 0."""
    assert ent.hours_for_service(5, replace(R, vacation_entitlement_tiers=())) is None


# ── what cannot be worked out, and says so ───────────────────────────────


def test_NO_PRIOR_HOURS_refuses_and_names_the_remedy():
    """⚠️ Not a division by zero, and not a zero. A rate built from no hours is
    undefined, and the sentence has to tell somebody what to do next."""
    with pytest.raises(VacationPayUnavailable, match="prior-year figures"):
        vac_pay.union_pay(hours=40, prior_year_gross=D("1000"),
                          prior_year_hours=D("0"), entitlement_hours=40, rules=R)


def test_NO_REGULAR_RATE_refuses_for_a_non_union_person():
    with pytest.raises(VacationPayUnavailable, match="regular pay rate"):
        vac_pay.non_union_pay(hours=16, regular_rate=D("0"))


@pytest.mark.parametrize("checks", [0, 4, -1])
def test_only_ONE_TWO_or_THREE_checks(checks):
    """The Focus's first question is 1, 2 or 3. Anything else is refused here
    rather than producing a split nobody asked for."""
    with pytest.raises(VacationPayUnavailable, match="1, 2 or 3 checks"):
        vac_pay.union_pay(hours=40, prior_year_gross=HUNT_GROSS,
                          prior_year_hours=HUNT_HOURS, entitlement_hours=40,
                          rules=R, checks=checks)


# ── splitting one vacation across checks ─────────────────────────────────


def test_splitting_hours_across_checks_SUMS_TO_THE_HOURS():
    """⚠️ The HOURS are split, not the pay. Splitting the pay would round twice
    and could miss the total by a cent."""
    p = vac_pay.union_pay(
        hours=40, prior_year_gross=HUNT_GROSS, prior_year_hours=HUNT_HOURS,
        entitlement_hours=120, rules=R, checks=3,
        bonus_part_start=1, bonus_part_count=3)
    assert sum(part.hours for part in p.parts) == D("40")
    assert len(p.parts) == 3


def test_a_vacations_checks_take_CONSECUTIVE_bonus_parts_of_the_year():
    """⚠️ **THE DISTINCTION THAT COST ME A CHECK CONSTRAINT.** The bonus is a
    YEARLY total paid "in equal parts, one with each vacation payment" — so the
    parts are indexed across the YEAR, not across one vacation's checks. I
    first wrote `part_count <= 3` in the migration because the Focus offers 1,
    2 or 3 checks; the `160 h -> 38.75 x4` golden refused it."""
    p = vac_pay.union_pay(
        hours=80, prior_year_gross=HUNT_GROSS, prior_year_hours=HUNT_HOURS,
        entitlement_hours=160, rules=R, checks=2,
        bonus_part_start=3, bonus_part_count=4)
    assert [part.index for part in p.parts] == [3, 4]
    assert [str(part.vac_bonus) for part in p.parts] == ["38.75", "38.75"]
    assert all(part.count == 4 for part in p.parts)


# ═════════════════════════════════════════════════════════════════════════
# The endpoints — driven over HTTP, because a service-level test would have
# passed throughout the entire period the hours upload was broken, and that
# lesson is four days old.
# ═════════════════════════════════════════════════════════════════════════

import uuid                                                      # noqa: E402

from fastapi.testclient import TestClient                        # noqa: E402
from sqlalchemy import text                                      # noqa: E402

from app.main import app                                         # noqa: E402
from app.models.user import User                                 # noqa: E402
from tests._payroll_switch import payroll_switch                 # noqa: E402
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture  # noqa: E402
from tests._two_step import tenant_token                         # noqa: E402

_canonical_tenant = make_canonical_tenant_fixture()

BASE = "/api/v1/payroll-reports"
HEADERS = {"X-Company-Slug": "testco"}


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def tokens():
    from app.database import SessionLocal
    from app.models.role import Role
    from app.models.role_permission import RolePermission

    db = SessionLocal()
    made, roles = [], []
    try:
        out = {}
        role = (db.query(Role)
                .filter(Role.company_id == TESTCO_ID, Role.slug == "payroll").first())
        if role is None:
            pytest.skip("testco has no payroll role")
        uid = "vac-payroll"
        db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        db.add(User(id=uid, email=f"{uid}@testco.com", hashed_password="x",
                    first_name="Vac", last_name="Payroll",
                    company_id=TESTCO_ID, role_id=role.id, is_active=True))
        made.append(uid)
        out["payroll"] = uid

        # ⚠️ A GENUINE VIEW-ONLY ACTOR. The seeded `payroll` role HOLDS
        # `payroll.approve`, so a refusal test written against it gets a 201
        # and reads as a missing check — that exact mistake has cost a
        # debugging cycle twice in this arc.
        rid = str(uuid.uuid4())
        for (old,) in db.execute(text(
                "SELECT id FROM roles WHERE company_id=:c AND slug='vac-view'"),
                {"c": TESTCO_ID}).fetchall():
            db.execute(text("DELETE FROM role_permissions WHERE role_id=:r"), {"r": old})
            db.execute(text("DELETE FROM roles WHERE id=:r"), {"r": old})
        db.add(Role(id=rid, company_id=TESTCO_ID, name="vac-view",
                    slug="vac-view", is_system=False, is_active=True))
        db.flush()
        db.add(RolePermission(id=str(uuid.uuid4()), role_id=rid,
                              permission_key="payroll.view"))
        uid2 = "vac-viewonly"
        db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid2})
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid2})
        db.add(User(id=uid2, email=f"{uid2}@testco.com", hashed_password="x",
                    first_name="View", last_name="Only", company_id=TESTCO_ID,
                    role_id=rid, is_active=True))
        made.append(uid2)
        roles.append(rid)
        out["viewonly"] = uid2
        db.commit()
        yield {k: tenant_token(v, TESTCO_ID) for k, v in out.items()}
    finally:
        for u in made:
            db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": u})
            db.execute(text("DELETE FROM users WHERE id=:u"), {"u": u})
        for r in roles:
            db.execute(text("DELETE FROM role_permissions WHERE role_id=:r"), {"r": r})
            db.execute(text("DELETE FROM roles WHERE id=:r"), {"r": r})
        db.commit()
        db.close()


def _auth(tok):
    return {"Authorization": f"Bearer {tok}", **HEADERS}


@pytest.fixture
def switch_on():
    with payroll_switch(TESTCO_ID, True):
        yield


@pytest.fixture
def member():
    """A union member with a hire date, so service tiers resolve."""
    from app.database import SessionLocal
    from app.models.payroll_report import PayrollReportEmployee

    db = SessionLocal()
    eid = str(uuid.uuid4())
    try:
        db.add(PayrollReportEmployee(
            id=eid, tenant_id=TESTCO_ID, payentry_file_number="VAC-1",
            display_name="Vacation, Test", is_union_member=True,
            hire_date=date(2014, 1, 6)))
        db.commit()
        yield eid
    finally:
        for t in ("payroll_vacation_payments",):
            db.execute(text(
                f"DELETE FROM {t} WHERE vacation_id IN "
                "(SELECT id FROM payroll_vacations WHERE employee_id=:e)"),
                {"e": eid})
        for t in ("payroll_vacations", "payroll_vacation_entitlements",
                  "payroll_prior_year_figures"):
            db.execute(text(f"DELETE FROM {t} WHERE employee_id=:e"), {"e": eid})
        db.execute(text("DELETE FROM payroll_report_employees WHERE id=:e"),
                   {"e": eid})
        db.commit()
        db.close()


def test_the_pane_says_WHAT_IS_MISSING_rather_than_showing_zeros(
        client, tokens, switch_on, member):
    """⚠️ The state every employee is in today: no prior-year figures, because
    the registers do not cover 2025. "0 left" and "we do not know" are
    different facts and the pane must not collapse them."""
    r = client.get(f"{BASE}/employees/{member}/vacation", params={"year": 2026},
                   headers=_auth(tokens["payroll"]))
    assert r.status_code == 200, r.text[:400]
    b = r.json()
    assert b["union_member"] is True
    # ⚠️ **11 COMPLETED YEARS, NOT 12, AND THE AS-OF DATE IS WHY.** Hired
    # 2014-01-06; the allowance is resolved as of 1 January, and the twelfth
    # year completes on the 6th. I expected 12 and the test was right — which
    # is the completed-not-elapsed rule doing its job at a boundary five days
    # wide. Either way it lands in the 15-year tier: 120 hours.
    assert b["entitlement"]["hours"] == "120"
    assert b["entitlement"]["basis"] == "service_tiers"
    assert b["entitlement"]["years_of_service"] == 11
    assert b["prior_year"]["usable"] is False
    assert b["prior_year"]["basis"] == "unavailable"
    # ⚠️ THE COVERAGE SENTENCE, which is what makes the refusal actionable.
    assert "2025" in b["prior_year"]["coverage"]


def test_an_entered_prior_year_figure_NEEDS_ITS_SOURCE(
        client, tokens, switch_on, member):
    for blank in ("", "   "):
        r = client.put(f"{BASE}/employees/{member}/prior-year/2025",
                       data={"gross": "33062.74", "hours": "1512.36",
                             "source": blank},
                       headers=_auth(tokens["payroll"]))
        assert r.status_code in (400, 422), f"{blank!r}: {r.status_code}"


def test_entering_HUNTS_figures_makes_the_pay_computable_and_it_is_900_46(
        client, tokens, switch_on, member):
    """⚠️ **THE WHOLE FEATURE, END TO END OVER HTTP.** Enter the workbook
    figures, record a vacation, read the working: 900.46 + 75.00."""
    assert client.put(
        f"{BASE}/employees/{member}/prior-year/2025",
        data={"gross": "33062.74", "hours": "1512.36",
              "source": "2025 Vac Calc tab"},
        headers=_auth(tokens["payroll"])).status_code == 201

    # 40 hours, so the bonus total is 75.00 in a single payment.
    assert client.put(
        f"{BASE}/employees/{member}/entitlement/2026",
        data={"hours": "40", "source": "agreement, 2026"},
        headers=_auth(tokens["payroll"])).status_code == 201

    made = client.post(f"{BASE}/employees/{member}/vacation",
                       data={"start_date": "2026-11-16", "end_date": "2026-11-20",
                             "hours": "40", "source": "union pick"},
                       headers=_auth(tokens["payroll"]))
    assert made.status_code == 201, made.text[:300]
    vid = made.json()["id"]

    r = client.get(f"{BASE}/vacations/{vid}/pay", params={"checks": 1},
                   headers=_auth(tokens["payroll"]))
    assert r.status_code == 200, r.text[:400]
    w = r.json()["working"]
    assert w is not None, r.json()["unavailable"]
    assert w["rate"] == "22.5116"
    assert w["rate_truncate_dp"] == 4
    assert w["parts"][0]["vac_pay"] == "900.46"
    assert w["parts"][0]["vac_bonus"] == "75.00"
    assert r.json()["union"] is True


def test_approving_writes_BOTH_lines_and_refuses_a_second_time(
        client, tokens, switch_on, member):
    """⚠️ A second approval would pay the week twice AND move every other
    bonus part's cents, because the divisor is the year's payment count."""
    client.put(f"{BASE}/employees/{member}/prior-year/2025",
               data={"gross": "33062.74", "hours": "1512.36",
                     "source": "2025 Vac Calc tab"},
               headers=_auth(tokens["payroll"]))
    client.put(f"{BASE}/employees/{member}/entitlement/2026",
               data={"hours": "40", "source": "agreement"},
               headers=_auth(tokens["payroll"]))
    vid = client.post(f"{BASE}/employees/{member}/vacation",
                      data={"start_date": "2026-11-16", "end_date": "2026-11-20",
                            "hours": "40", "source": "union pick"},
                      headers=_auth(tokens["payroll"])).json()["id"]

    ok = client.post(f"{BASE}/vacations/{vid}/approve",
                     data={"checks": 1, "week_end_date": "2026-11-21"},
                     headers=_auth(tokens["payroll"]))
    assert ok.status_code == 201, ok.text[:400]
    pay = ok.json()["payments"]
    assert len(pay) == 1
    assert pay[0]["vac_pay"] == "900.46"
    assert pay[0]["vac_bonus"] == "75.00"
    assert ok.json()["vacation"]["status"] == "paid"

    again = client.post(f"{BASE}/vacations/{vid}/approve",
                        data={"checks": 1, "week_end_date": "2026-11-21"},
                        headers=_auth(tokens["payroll"]))
    assert again.status_code == 409, again.text[:200]


def test_an_OVERLAPPING_vacation_is_refused(client, tokens, switch_on, member):
    """Two rows for one week pay it twice — and because the bonus divisor is
    the year's payment count, a duplicate moves every other part's cents."""
    first = client.post(f"{BASE}/employees/{member}/vacation",
                        data={"start_date": "2026-07-06", "end_date": "2026-07-10",
                              "hours": "40", "source": "union pick"},
                        headers=_auth(tokens["payroll"]))
    assert first.status_code == 201
    clash = client.post(f"{BASE}/employees/{member}/vacation",
                        data={"start_date": "2026-07-08", "end_date": "2026-07-14",
                              "hours": "40", "source": "second pick"},
                        headers=_auth(tokens["payroll"]))
    assert clash.status_code == 400
    assert "overlaps" in clash.text


def test_recording_and_approving_need_payroll_approve_reading_does_not(
        client, tokens, switch_on, member):
    assert client.get(f"{BASE}/employees/{member}/vacation",
                      headers=_auth(tokens["viewonly"])).status_code == 200
    denied = client.post(f"{BASE}/employees/{member}/vacation",
                         data={"start_date": "2026-05-04", "end_date": "2026-05-08",
                               "hours": "40", "source": "x"},
                         headers=_auth(tokens["viewonly"]))
    assert denied.status_code == 403, denied.text[:200]
    # The control: the same request from somebody who holds it succeeds.
    assert client.post(f"{BASE}/employees/{member}/vacation",
                       data={"start_date": "2026-05-04", "end_date": "2026-05-08",
                             "hours": "40", "source": "union pick"},
                       headers=_auth(tokens["payroll"])).status_code == 201


def test_the_data_switch_gates_the_whole_surface(client, tokens, member):
    with payroll_switch(TESTCO_ID, False):
        r = client.get(f"{BASE}/employees/{member}/vacation",
                       headers=_auth(tokens["payroll"]))
        assert r.status_code == 403, r.text[:200]


# ── the registry itself ──────────────────────────────────────────────────


def test_EVERY_platform_fragment_registers_and_the_payroll_four_are_there():
    """⚠️ **WRITTEN BECAUSE I SILENTLY DELETED FIVE FRAGMENTS AND NO TEST
    NOTICED.**

    Adding the vacation-pay fragment, I put its condition `def` in the middle
    of `seed()`'s body. A top-level `def` ENDS the enclosing function, so
    `seed()` returned early and registered one fragment instead of nine — the
    union form, the weekly dues, the anomaly watchlist, the compliance flags
    and the tasks line all stopped existing.

    Nothing went red. The whole backend suite passed. It surfaced only when I
    probed `/note/today` during the walk-through and saw one line where there
    should have been two, which is the *reading the screenshot* lesson arriving
    through a different door.

    ⚠️ A COUNT ALONE WOULD NOT HAVE CAUGHT IT EITHER, had I written one
    carelessly: `>= 1` passes. The assertion is on the SET, because membership
    is the property that matters and equal cardinality is not identity — this
    repo has a recorded instance of two parties counting six and meaning
    different sixes.
    """
    from app.services.fragments.registry import get_registry

    ids = set(get_registry())
    expected_payroll = {
        "payroll_week_open",
        "payroll_union_form_due",
        "payroll_vacation_pay",
        "weekly_dues",
    }
    missing = expected_payroll - ids
    assert not missing, (
        f"these payroll fragments did not register: {sorted(missing)}. A "
        "top-level `def` inside `seed()` ends the function and silently drops "
        "everything after it."
    )
    # And the non-payroll ones, so a future edit cannot truncate `seed()`
    # past them either.
    assert {"anomaly_watchlist", "compliance_flags", "tasks_due_today"} <= ids


# ── the NON-UNION path, which shipped broken ─────────────────────────────


@pytest.fixture
def non_union_member():
    """Somebody not in the union, with a pay rate on file."""
    from app.database import SessionLocal
    from app.models.payroll_report import PayrollRate, PayrollReportEmployee

    db = SessionLocal()
    eid = str(uuid.uuid4())
    try:
        db.add(PayrollReportEmployee(
            id=eid, tenant_id=TESTCO_ID, payentry_file_number="VAC-NU",
            display_name="Office, Test", is_union_member=False,
            hire_date=date(2020, 1, 6)))
        db.flush()
        db.add(PayrollRate(id=str(uuid.uuid4()), employee_id=eid,
                           reg_rate=D("20.00"), effective_date=date(2026, 1, 1)))
        db.commit()
        yield eid
    finally:
        db.execute(text("DELETE FROM payroll_vacation_payments WHERE vacation_id IN "
                        "(SELECT id FROM payroll_vacations WHERE employee_id=:e)"),
                   {"e": eid})
        db.execute(text("DELETE FROM payroll_vacations WHERE employee_id=:e"), {"e": eid})
        db.execute(text("DELETE FROM payroll_rates WHERE employee_id=:e"), {"e": eid})
        db.execute(text("DELETE FROM payroll_report_employees WHERE id=:e"), {"e": eid})
        db.commit()
        db.close()


def test_a_NON_UNION_vacation_pays_rate_times_hours_with_no_bonus(
        client, tokens, switch_on, non_union_member):
    """⚠️ **THE PATH THAT SHIPPED BROKEN IN #50.** `_regular_rate_for` queried
    `PayrollRate.tenant_id`, `.emp_id` and `.hourly_rate` — none of which
    exist — so opening a non-union person's vacation pay raised
    `AttributeError`. Every vacation test used a UNION member, so the branch
    was never driven: a guard reasoned from one caller.

    Found in the week-44 dress rehearsal, by reading `PayrollRate`'s actual
    columns for an unrelated reason. This is the test that would have caught
    it, and the golden is James's: 16 h at $20.00 → 320.00, no bonus."""
    made = client.post(f"{BASE}/employees/{non_union_member}/vacation",
                       data={"start_date": "2026-09-07", "end_date": "2026-09-08",
                             "hours": "16", "source": "approved request"},
                       headers=_auth(tokens["payroll"]))
    assert made.status_code == 201, made.text[:300]
    vid = made.json()["id"]

    r = client.get(f"{BASE}/vacations/{vid}/pay", params={"checks": 1},
                   headers=_auth(tokens["payroll"]))
    assert r.status_code == 200, r.text[:400]
    body = r.json()
    w = body["working"]
    assert w is not None, body["unavailable"]
    assert body["union"] is False
    # ⚠️ **`20.0000`, NOT `20.00` — COMPARE THE DECIMAL, NOT THE STRING.**
    # `reg_rate` is `Numeric(10,4)` and a rate genuinely carries four places
    # (the union rate is 22.5116). My first expectation encoded a formatting
    # assumption, which is the trap recorded on 2026-11-17: decimals for
    # hours and rates, strings for money.
    assert D(w["rate"]) == D("20"), w["rate"]
    assert w["parts"][0]["vac_pay"] == "320.00"
    assert w["parts"][0]["vac_bonus"] == "0.00"
    assert w["bonus_year_total"] is None


def test_a_non_union_person_with_NO_RATE_is_told_so(
        client, tokens, switch_on, member):
    """⚠️ The control for the above, and it uses the UNION fixture with its
    union flag flipped — so the refusal is reached through the same branch
    rather than through the union one."""
    from app.database import SessionLocal
    from app.models.payroll_report import PayrollReportEmployee

    db = SessionLocal()
    try:
        emp = db.query(PayrollReportEmployee).filter(
            PayrollReportEmployee.id == member).first()
        emp.is_union_member = False
        db.commit()
    finally:
        db.close()

    vid = client.post(f"{BASE}/employees/{member}/vacation",
                      data={"start_date": "2026-09-14", "end_date": "2026-09-15",
                            "hours": "16", "source": "approved request"},
                      headers=_auth(tokens["payroll"])).json()["id"]
    r = client.get(f"{BASE}/vacations/{vid}/pay",
                   headers=_auth(tokens["payroll"]))
    assert r.status_code == 200, r.text[:300]
    assert r.json()["working"] is None
    assert "No pay rate is on file" in r.json()["unavailable"]
