"""The weekly payroll Focus and its three panes — Payroll 5a.

⚠️ **THE READS TAKE `payroll.view`; THE TWO WRITES TAKE `payroll.approve`.**
James's ruling of 2026-11-13. Reading a week's dues is the job Susan was given.
Deciding a finding and correcting someone's hours change what payroll pays, so
they sit at the change level beside the week approval they feed.

⚠️ **EVERY ONE OF THE SIX IS BEHIND THE DATA SWITCH, READS INCLUDED.** A tenant
with the switch off holds no payroll data, so a Focus there could only report on
rows that should not exist — and a 200 with an empty Focus would make "the
switch is off" indistinguishable from "nothing happened this week".

⚠️ **A CORRECTION NEVER OVERWRITES THE IMPORT.** `payroll_hours_lines` holds
what Payentry printed. A correction is an appended, attributed delta, so the
arithmetic stays visible and a re-import cannot silently undo it.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.models.company import Company
from app.models.payroll_report import (
    PayrollHoursImport,
    PayrollHoursLine,
    PayrollRate,
    PayrollReportEmployee,
    PayrollRuleSet,
    PayrollWeek,
    PayrollWeekLine,
)
from app.models.user import User
from app.services.payroll.data_gate import PAYROLL_DATA_ENABLED
from tests._payroll_switch import read_switch, write_switch
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture
from tests._two_step import tenant_token

_canonical_tenant = make_canonical_tenant_fixture()

HEADERS = {"X-Company-Slug": "testco"}
BASE = "/api/v1/payroll-reports"

WEEK_END = date(2026, 10, 31)      # Saturday
CHECK_DATE = date(2026, 11, 5)
IN_WEEK = date(2026, 10, 28)       # Wednesday of that week
OUT_OF_WEEK = date(2026, 10, 20)

#: (file number, reg hours, ot hours, reg rate)
MEMBERS = [("9001", "40.00", "0.00", "22.50"),
           ("9002", "32.00", "6.00", "24.00")]

#: slug suffix -> (limited_to_areas, permissions)
ROLES = {
    "view":    (["payroll"], ["payroll.view"]),
    "approve": (["payroll"], ["payroll.view", "payroll.approve"]),
    # ⚠️ Holds the payroll permissions AND is limited to another area. Without
    # the permissions the refusal could be either guard; with them, only the
    # area guard can be refusing.
    "outside": (["scheduling"], ["payroll.view", "payroll.approve"]),
}


def H(token):
    return {**HEADERS, "Authorization": f"Bearer {token}"}


def _switch(db, value):
    co = db.query(Company).filter(Company.id == TESTCO_ID).first()
    co.set_setting(PAYROLL_DATA_ENABLED, value)
    db.commit()


@pytest.fixture(scope="module")
def seeded():
    """A calculated week with two union members, and three area-limited roles."""
    from app.database import SessionLocal
    from app.models.role import Role
    from app.models.role_permission import RolePermission
    from app.services.payroll import service as payroll_service

    db = SessionLocal()
    ids = {k: (f"area-probe-focus-{k}", f"area-probe-focus-role-{k}") for k in ROLES}

    def wipe():
        db.execute(text("DELETE FROM payroll_hour_corrections WHERE tenant_id=:t"),
                   {"t": TESTCO_ID})
        db.execute(text("DELETE FROM payroll_week_decisions WHERE tenant_id=:t"),
                   {"t": TESTCO_ID})
        db.execute(text(
            "DELETE FROM payroll_week_results WHERE week_id IN "
            "(SELECT id FROM payroll_weeks WHERE tenant_id=:t)"), {"t": TESTCO_ID})
        db.execute(text(
            "DELETE FROM payroll_week_lines WHERE week_id IN "
            "(SELECT id FROM payroll_weeks WHERE tenant_id=:t)"), {"t": TESTCO_ID})
        db.execute(text("DELETE FROM payroll_weeks WHERE tenant_id=:t"), {"t": TESTCO_ID})
        db.execute(text("DELETE FROM payroll_hours_lines WHERE tenant_id=:t"),
                   {"t": TESTCO_ID})
        db.execute(text("DELETE FROM payroll_hours_imports WHERE tenant_id=:t"),
                   {"t": TESTCO_ID})
        db.execute(text(
            "DELETE FROM payroll_rates WHERE employee_id IN "
            "(SELECT id FROM payroll_report_employees WHERE tenant_id=:t)"),
            {"t": TESTCO_ID})
        db.execute(text("DELETE FROM payroll_report_employees WHERE tenant_id=:t"),
                   {"t": TESTCO_ID})
        db.execute(text("DELETE FROM payroll_rule_sets WHERE tenant_id=:t"),
                   {"t": TESTCO_ID})
        for uid, rid in ids.values():
            db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
            db.execute(text("DELETE FROM role_permissions WHERE role_id=:r"), {"r": rid})
            db.execute(text("DELETE FROM roles WHERE id=:r"), {"r": rid})
        db.commit()

    try:
        wipe()
        # ⚠️ CAPTURED BEFORE THE WRITE. The teardown below used to write
        # `False`, which turns the switch off for a tenant that had it on —
        # see `tests/_payroll_switch.py`.
        _switch_as_found = read_switch(TESTCO_ID)
        _switch(db, True)

        db.add(PayrollRuleSet(id=str(uuid.uuid4()), tenant_id=TESTCO_ID,
                              effective_date=date(2026, 1, 1)))

        emp_ids = {}
        for fn, reg, ot, rate in MEMBERS:
            e = PayrollReportEmployee(
                id=str(uuid.uuid4()), tenant_id=TESTCO_ID,
                payentry_file_number=fn, display_name=f"Member {fn}",
                dept="PRECAST", is_union_member=True, active=True,
                initiation_fee_due=False,
            )
            db.add(e)
            db.flush()
            emp_ids[fn] = e.id
            db.add(PayrollRate(id=str(uuid.uuid4()), employee_id=e.id,
                               reg_rate=D(rate), ot_rate=D(rate) * D("1.5"),
                               effective_date=date(2026, 1, 1)))

        # ⚠️ `payroll_hours_lines.import_id` is a REAL foreign key to
        # `payroll_hours_imports`. A first draft generated a UUID for it and
        # the insert was refused — correctly: an hours line with no import is a
        # figure with no provenance, which is the thing this arc most forbids.
        hours_import = PayrollHoursImport(
            id=str(uuid.uuid4()), tenant_id=TESTCO_ID, source_kind="employee_hours",
            file_sha256="0" * 64, filename="fixture-employee-hours.pdf",
            week_end_date=WEEK_END, rows_parsed=len(MEMBERS), report={},
        )
        db.add(hours_import)
        db.flush()

        week = PayrollWeek(
            id=str(uuid.uuid4()), tenant_id=TESTCO_ID, week_number=44,
            week_end_date=WEEK_END,
            # ⚠️ NOT NULL and NOT derived here. Omitting it has broken a
            # fixture of mine before.
            check_date=CHECK_DATE, status="imported",
        )
        db.add(week)
        db.flush()
        for fn, reg, ot, _rate in MEMBERS:
            db.add(PayrollWeekLine(id=str(uuid.uuid4()), week_id=week.id,
                                   employee_id=emp_ids[fn],
                                   reg_hrs=D(reg), ot_hrs=D(ot)))
            # One parsed hours line so the timecard pane has something real to
            # show a correction next to.
            db.add(PayrollHoursLine(
                id=str(uuid.uuid4()), tenant_id=TESTCO_ID,
                import_id=hours_import.id, week_end_date=WEEK_END,
                emp_id=fn, name=f"Member {fn}", work_date=IN_WEEK,
                pay_type="REG", hours=D("8.00")))
        db.commit()

        payroll_service.calculate_week(db, week)
        db.commit()
        assert week.status == "calculated", f"fixture week is {week.status!r}"

        tokens = {}
        for key, (areas, perms) in ROLES.items():
            uid, rid = ids[key]
            db.add(Role(id=rid, company_id=TESTCO_ID, name=f"Focus {key}",
                        slug=f"area-probe-focus-{key}", is_system=False,
                        is_active=True, limited_to_areas=areas))
            db.flush()
            for p in perms:
                db.add(RolePermission(role_id=rid, permission_key=p))
            db.add(User(id=uid, email=f"{uid}@testco.example.com",
                        hashed_password="not-a-credential", first_name="Focus",
                        last_name=key.title(), role_id=rid, company_id=TESTCO_ID))
            tokens[key] = uid
        db.commit()

        # Controls: the roles must really hold what the tests assume.
        for key in ROLES:
            got = db.execute(text("SELECT limited_to_areas FROM roles WHERE id=:r"),
                             {"r": ids[key][1]}).scalar()
            assert got == ROLES[key][0], f"{key}: stored areas {got!r}"
        assert db.execute(text(
            "SELECT count(*) FROM role_permissions WHERE role_id=:r "
            "AND permission_key='payroll.approve'"
        ), {"r": ids["view"][1]}).scalar() == 0, "the view role must NOT hold approve"

        admin_id = db.execute(text(
            "SELECT u.id FROM users u JOIN roles r ON r.id=u.role_id "
            "WHERE u.company_id=:c AND r.slug='admin' "
            "AND r.limited_to_areas IS NULL LIMIT 1"), {"c": TESTCO_ID}).scalar()
        if admin_id is None:
            pytest.skip("testco has no unlimited admin — run the role seed")
        tokens["admin"] = admin_id

        yield {
            "week_id": week.id,
            "emp_ids": emp_ids,
            "tokens": {k: tenant_token(v, TESTCO_ID) for k, v in tokens.items()},
        }
    finally:
        wipe()
        # ⚠️ **AS FOUND, WHICH IS NOT THE SAME AS "OFF".** This read "a test
        # that leaves a safety switch ON disarms the next run" — right about
        # the DEFAULT, wrong about the TENANT. Writing `False` over a tenant
        # that had payroll on is this suite deciding what a shared database
        # holds, and it blanked a live note mid-walk-through on 2026-11-17.
        write_switch(TESTCO_ID, _switch_as_found)
        db.close()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def switch_on(seeded):
    """The fixture leaves the switch on; individual tests may turn it off."""
    from app.database import SessionLocal
    db = SessionLocal()
    _switch(db, True)
    yield
    _switch(db, True)
    db.close()


def _urls(week_id, emp_id):
    return {
        "focus":    f"{BASE}/weeks/{week_id}/focus",
        "dues":     f"{BASE}/weeks/{week_id}/panes/union-dues",
        "member":   f"{BASE}/weeks/{week_id}/panes/member/{emp_id}",
        "timecard": f"{BASE}/weeks/{week_id}/panes/timecard/{emp_id}",
    }


# ── the panes read ──────────────────────────────────────────────────────────


def test_the_dues_pane_totals_match_the_stored_report(client, seeded, switch_on):
    """⚠️ The pane must not be a SECOND computation of the dues.

    It reads `weekly_dues_detail`, the same report the deduction register and
    the monthly remittance read. Asserted by comparing the pane against that
    endpoint rather than against a number typed into this test — a literal here
    would agree with a pane that recomputed wrongly, as long as I typed the
    pane's answer.
    """
    w = seeded["week_id"]
    pane = client.get(_urls(w, "x")["dues"], headers=H(seeded["tokens"]["view"]))
    assert pane.status_code == 200, pane.text[:300]

    report = client.get(f"{BASE}/weeks/{w}/reports/weekly_dues_detail",
                        headers=H(seeded["tokens"]["view"]))
    assert report.status_code == 200, report.text[:300]

    assert pane.json()["total_dues"] == report.json()["totals"]["dues"]
    assert pane.json()["members_total"] == len(report.json()["rows"])
    assert pane.json()["members_total"] == len(MEMBERS)


def test_the_dues_pane_serves_the_formula_from_the_rule_set(client, seeded, switch_on):
    """The percentage is effective-dated, so the pane reports the rule set's
    own numbers rather than a sentence with 1.45% written into it."""
    r = client.get(_urls(seeded["week_id"], "x")["dues"],
                   headers=H(seeded["tokens"]["view"]))
    basis = r.json()["basis"]
    assert basis["percent"], basis
    assert basis["cap_multiplier"], basis
    assert basis["per_hour"], basis
    assert basis["rule_set_effective"] == "2026-01-01"


def test_the_member_pane_shows_the_working_and_the_ot_rate_used(
        client, seeded, switch_on):
    """⚠️ `ot_rate_used` and `ot_rate_derived` are the fields the week-44
    investigation turned on: the workbook's typed OT rates were stale and the
    difference was invisible until the rate used was shown next to the figure
    it produced."""
    emp = seeded["emp_ids"]["9002"]
    r = client.get(_urls(seeded["week_id"], emp)["member"],
                   headers=H(seeded["tokens"]["view"]))
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body["employee_id"] == emp
    assert body["dues"] is not None
    for k in ("component_a", "component_b", "component_c", "binds"):
        assert k in body["working"], body["working"]
    assert body["ot_rate_used"] is not None
    assert "ot_rate_derived" in body
    assert body["union_member"] is True


def test_the_member_pane_is_404_for_somebody_with_no_result(
        client, seeded, switch_on):
    r = client.get(_urls(seeded["week_id"], "no-such-employee")["member"],
                   headers=H(seeded["tokens"]["view"]))
    assert r.status_code == 404, r.status_code


def test_the_timecard_pane_says_whether_punch_data_exists_at_all(
        client, seeded, switch_on):
    """⚠️ Stated plainly, not implied by an empty list. No punch file for the
    week and a person who never punched look identical from outside, and only
    one of them is worth asking about.

    ⚠️ And never coordinates: `any_punch_has_location` is a boolean.
    """
    r = client.get(_urls(seeded["week_id"], "9001")["timecard"],
                   headers=H(seeded["tokens"]["view"]))
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body["punch_data_present"] is False
    assert body["days"], "the parsed hours line should appear as a day"
    for d in body["days"]:
        assert isinstance(d["any_punch_has_location"], bool)
        assert "latitude" not in d and "longitude" not in d


def test_no_pane_or_focus_response_carries_coordinates(client, seeded, switch_on):
    """Membership, not a spot check: a field added later is covered."""
    w, emp = seeded["week_id"], seeded["emp_ids"]["9001"]
    banned = ("latitude", "longitude", "lat", "lng", "coordinates", "gps")
    for name, url in {**_urls(w, emp), "timecard9001":
                      f"{BASE}/weeks/{w}/panes/timecard/9001"}.items():
        r = client.get(url, headers=H(seeded["tokens"]["view"]))
        if r.status_code != 200:
            continue
        blob = r.text.lower()
        for word in banned:
            assert f'"{word}"' not in blob, f"{name} carries {word!r}"


# ── payroll.approve on the two writes ───────────────────────────────────────


def _correct(client, token, week_id, **over):
    data = {"emp_id": "9001", "work_date": IN_WEEK.isoformat(),
            "pay_type": "REG", "hours": "1.50", "reason": "missed punch"}
    data.update(over)
    return client.post(f"{BASE}/weeks/{week_id}/corrections",
                       headers=H(token), data=data)


def _decide(client, token, week_id, **over):
    data = {"finding_key": "missed_punch:9001:2026-10-28",
            "outcome": "settled", "note": "checked with Tom"}
    data.update(over)
    return client.post(f"{BASE}/weeks/{week_id}/decisions",
                       headers=H(token), data=data)


def test_a_view_only_payroll_user_cannot_correct_or_decide(
        client, seeded, switch_on):
    """⚠️ The refusal must NAME the permission, so the person reading it can
    act. "You are not an admin" tells a payroll user nothing they can use."""
    w = seeded["week_id"]
    for call in (_correct, _decide):
        r = call(client, seeded["tokens"]["view"], w)
        assert r.status_code == 403, f"{call.__name__}: {r.status_code} {r.text[:200]}"
        assert "payroll.approve" in r.text, r.text[:200]


def test_the_approve_level_can_correct_and_decide(client, seeded, switch_on):
    """The positive control. Without it the refusals above are satisfied by
    endpoints that refuse everybody."""
    w = seeded["week_id"]
    assert _correct(client, seeded["tokens"]["approve"], w).status_code == 201
    assert _decide(client, seeded["tokens"]["approve"], w).status_code == 201


def test_a_view_only_payroll_user_can_still_read_every_pane(
        client, seeded, switch_on):
    w, emp = seeded["week_id"], seeded["emp_ids"]["9001"]
    for name, url in _urls(w, emp).items():
        r = client.get(url, headers=H(seeded["tokens"]["view"]))
        assert r.status_code == 200, f"{name}: {r.status_code} {r.text[:200]}"


# ── the switch ──────────────────────────────────────────────────────────────


def test_nothing_works_while_the_switch_is_off_not_even_for_admin(client, seeded):
    """⚠️ THE LOAD-BEARING TEST. Reads included, and the admin included.

    The switch is the control carrying "may this tenant hold payroll data at
    all". If this passed only for the limited roles, the switch would be a
    permission check wearing a different name.
    """
    from app.database import SessionLocal
    db = SessionLocal()
    _switch(db, False)
    try:
        w, emp = seeded["week_id"], seeded["emp_ids"]["9001"]

        # Every reader holds payroll.view, so the SWITCH is what refuses them.
        for who in ("admin", "approve", "view"):
            tok = seeded["tokens"][who]
            for name, url in _urls(w, emp).items():
                r = client.get(url, headers=H(tok))
                assert r.status_code == 403, f"{who} {name}: {r.status_code}"
                assert r.json()["detail"]["code"] == "payroll_data_disabled", r.text[:200]

        # ⚠️ ONLY THE CALLERS WHO HOLD `payroll.approve`. For a view-only user
        # the PERMISSION dependency answers before the handler runs at all, so
        # her refusal is "Permission required: payroll.approve" and never
        # reaches the switch. Asserting `payroll_data_disabled` for her would
        # be asserting the wrong guard, and it failed when I tried — which is
        # the ordering being real rather than assumed.
        for who in ("admin", "approve"):
            for call in (_correct, _decide):
                r = call(client, seeded["tokens"][who], w)
                assert r.status_code == 403, f"{who} {call.__name__}: {r.status_code}"
                assert r.json()["detail"]["code"] == "payroll_data_disabled", r.text[:200]
    finally:
        _switch(db, True)
        db.close()


# ── out of area ─────────────────────────────────────────────────────────────


def test_a_user_outside_the_payroll_area_is_refused_before_any_permission(
        client, seeded, switch_on):
    """⚠️ The probe HOLDS `payroll.view` and `payroll.approve` and is limited to
    `scheduling`. Because it holds the permissions, only the area guard can be
    the thing refusing — a probe holding neither would be refused either way
    and could not tell the two guards apart."""
    w, emp = seeded["week_id"], seeded["emp_ids"]["9001"]
    tok = seeded["tokens"]["outside"]
    checks = list(_urls(w, emp).items())
    for name, url in checks:
        r = client.get(url, headers=H(tok))
        assert r.status_code == 403, f"{name}: {r.status_code}"
        detail = r.json()["detail"]
        assert detail["code"] == "area_restricted", detail
        assert detail["requested_area"] == "payroll"
        assert detail["allowed_areas"] == ["scheduling"]
    for call in (_correct, _decide):
        r = call(client, tok, w)
        assert r.status_code == 403, f"{call.__name__}: {r.status_code}"
        assert r.json()["detail"]["code"] == "area_restricted", r.text[:200]


# ── corrections append, never overwrite ─────────────────────────────────────


def test_a_correction_leaves_the_parsed_hours_line_untouched(
        client, seeded, switch_on):
    """⚠️ THE RULE THIS TABLE EXISTS FOR. `payroll_hours_lines` holds what
    Payentry printed; a correction that overwrote it would destroy the only
    copy of the thing being corrected, and the next re-import would silently
    undo the correction."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        before = db.execute(text(
            "SELECT hours FROM payroll_hours_lines WHERE tenant_id=:t "
            "AND emp_id='9001' AND work_date=:d"),
            {"t": TESTCO_ID, "d": IN_WEEK}).scalar()
        assert before is not None, "fixture has no parsed line to protect"

        r = _correct(client, seeded["tokens"]["approve"], seeded["week_id"],
                     hours="2.25", reason="clocked in, never out")
        assert r.status_code == 201, r.text[:300]

        after = db.execute(text(
            "SELECT hours FROM payroll_hours_lines WHERE tenant_id=:t "
            "AND emp_id='9001' AND work_date=:d"),
            {"t": TESTCO_ID, "d": IN_WEEK}).scalar()
        assert after == before, f"the parsed line changed: {before} -> {after}"
    finally:
        db.close()


def test_the_timecard_shows_parsed_and_corrected_apart(client, seeded, switch_on):
    """"Payentry said 8 and Susan added 2.25" is the fact a reviewer needs. A
    single merged 10.25 hides who decided it."""
    w = seeded["week_id"]
    assert _correct(client, seeded["tokens"]["approve"], w,
                    hours="2.25", reason="clocked in, never out").status_code == 201
    r = client.get(f"{BASE}/weeks/{w}/panes/timecard/9001",
                   headers=H(seeded["tokens"]["view"]))
    day = next(d for d in r.json()["days"] if d["work_date"] == IN_WEEK.isoformat())
    assert D(day["parsed_hours"]) == D("8.00"), day
    assert D(day["corrected_hours"]) > 0, day
    assert D(day["total_hours"]) == D(day["parsed_hours"]) + D(day["corrected_hours"])


def test_a_correction_outside_the_week_is_refused(client, seeded, switch_on):
    """A correction filed against the wrong week is invisible on both: it would
    not show on the week it was entered from, and would silently alter a week
    nobody was looking at."""
    r = _correct(client, seeded["tokens"]["approve"], seeded["week_id"],
                 work_date=OUT_OF_WEEK.isoformat())
    assert r.status_code == 422, r.status_code
    assert "outside the week" in r.text


def test_a_correction_without_a_reason_is_refused(client, seeded, switch_on):
    r = _correct(client, seeded["tokens"]["approve"], seeded["week_id"],
                 reason="   ")
    assert r.status_code == 422, r.status_code
    assert "reason" in r.text


# ── decisions supersede ─────────────────────────────────────────────────────


def test_a_second_decision_supersedes_the_first_and_only_one_is_live(
        client, seeded, switch_on):
    """⚠️ A change of mind is not an integrity error. The partial unique index
    allows any number of superseded decisions behind one live one, and the
    history is what makes "who decided this, and what did it replace?"
    answerable six weeks later."""
    from app.database import SessionLocal
    w = seeded["week_id"]
    key = "dues_difference:9002:"
    assert _decide(client, seeded["tokens"]["approve"], w,
                   finding_key=key, outcome="asked").status_code == 201
    assert _decide(client, seeded["tokens"]["approve"], w,
                   finding_key=key, outcome="settled").status_code == 201

    db = SessionLocal()
    try:
        live = db.execute(text(
            "SELECT outcome FROM payroll_week_decisions WHERE tenant_id=:t "
            "AND finding_key=:k AND superseded_by IS NULL"),
            {"t": TESTCO_ID, "k": key}).fetchall()
        assert [r[0] for r in live] == ["settled"], live
        total = db.execute(text(
            "SELECT count(*) FROM payroll_week_decisions WHERE tenant_id=:t "
            "AND finding_key=:k"), {"t": TESTCO_ID, "k": key}).scalar()
        assert total == 2, f"the superseded decision was deleted, not kept: {total}"
    finally:
        db.close()


def test_an_unknown_outcome_is_refused_rather_than_stored(client, seeded, switch_on):
    """An unrecognised outcome renders as nothing, so it is refused at the edge
    rather than stored and discovered on screen."""
    r = _decide(client, seeded["tokens"]["approve"], seeded["week_id"],
                outcome="probably_fine")
    assert r.status_code == 422, r.status_code
    assert "probably_fine" in r.text


def test_the_focus_reports_the_live_decision_and_the_correction(
        client, seeded, switch_on):
    w = seeded["week_id"]
    assert _decide(client, seeded["tokens"]["approve"], w,
                   finding_key="no_hours:9001:", outcome="not_an_issue").status_code == 201
    assert _correct(client, seeded["tokens"]["approve"], w,
                    reason="missed punch").status_code == 201

    r = client.get(f"{BASE}/weeks/{w}/focus", headers=H(seeded["tokens"]["view"]))
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert "no_hours:9001:" in {d["finding_key"] for d in body["decisions"]}
    assert any(c["emp_id"] == "9001" for c in body["corrections"])
    assert body["dues"]["members_total"] == len(MEMBERS)
    # The outcomes are served, so the client renders the declared set rather
    # than a list of its own that drifts from the one the server validates.
    assert "settled" in body["decision_outcomes"]


# ── the finding key ─────────────────────────────────────────────────────────


def test_the_finding_key_keeps_its_separators_when_a_part_is_absent():
    """⚠️ Fixed positions, so a kind with no date cannot collide with a
    different kind that has one."""
    from app.services.payroll.week_focus import finding_key

    assert finding_key("no_hours", emp_id="12008") == "no_hours:12008:"
    assert finding_key("saturday", emp_id="1", on_date=date(2026, 10, 31)) == \
        "saturday:1:2026-10-31"
    assert finding_key("a", emp_id="b") != finding_key("a:b", emp_id="")


def test_the_permission_gate_answers_before_the_switch_for_a_view_only_user(
        client, seeded):
    """⚠️ WHICH guard refuses, not merely that something does.

    The dependency runs before the handler body, so a view-only user is
    refused for lacking `payroll.approve` even with the switch off. This is the
    companion to the switch test above: between them, neither refusal can
    quietly stop firing while the other covers for it.
    """
    from app.database import SessionLocal
    db = SessionLocal()
    _switch(db, False)
    try:
        for call in (_correct, _decide):
            r = call(client, seeded["tokens"]["view"], seeded["week_id"])
            assert r.status_code == 403, f"{call.__name__}: {r.status_code}"
            assert "payroll.approve" in r.text, r.text[:200]
            assert "payroll_data_disabled" not in r.text, (
                "the switch answered before the permission check — the gate "
                "order changed"
            )
    finally:
        _switch(db, True)
        db.close()


# ── findings on the Focus ───────────────────────────────────────────────────


def test_the_focus_serves_findings_recomputed_read_only(client, seeded, switch_on):
    """⚠️ READ-ONLY. The Focus runs `calculate_week(persist=False)` so the
    findings Susan answers are the ones the import reported, not a second set
    computed for display. A GET that wrote results would also silently
    re-approve arithmetic nobody asked it to re-run.
    """
    from app.database import SessionLocal

    w = seeded["week_id"]
    db = SessionLocal()
    try:
        before = db.execute(text(
            "SELECT count(*), max(id) FROM payroll_week_results WHERE week_id=:w"),
            {"w": w}).first()
        status_before = db.execute(text(
            "SELECT status FROM payroll_weeks WHERE id=:w"), {"w": w}).scalar()
    finally:
        db.close()

    r = client.get(f"{BASE}/weeks/{w}/focus", headers=H(seeded["tokens"]["view"]))
    assert r.status_code == 200, r.text[:300]
    assert isinstance(r.json()["findings"], list)
    # Every finding carries a key the decision endpoint will accept, or the
    # answer cannot be recorded against it.
    for f in r.json()["findings"]:
        assert f["key"], f
        assert f["code"], f

    db = SessionLocal()
    try:
        after = db.execute(text(
            "SELECT count(*), max(id) FROM payroll_week_results WHERE week_id=:w"),
            {"w": w}).first()
        status_after = db.execute(text(
            "SELECT status FROM payroll_weeks WHERE id=:w"), {"w": w}).scalar()
    finally:
        db.close()
    assert after == before, f"the Focus GET wrote results: {before} -> {after}"
    assert status_after == status_before, "the Focus GET changed the week status"


def test_the_focus_reports_a_member_absent_from_the_hours_export(
        client, seeded, switch_on):
    """⚠️ **THE FINDING THAT MATTERS MOST, AND `calculate_week` DOES NOT RAISE IT.**

    `calculate_week` flags things about LINES it can see. A union member with no
    line has nothing to flag, so a week recalculated from stored rows says
    nothing about them. The roster mismatch is raised at IMPORT and then gone —
    which means the week Susan opens on Tuesday would have shown her nothing
    about a member who was never paid.

    That is how Stevenson went unpaid. The Focus re-runs `reconcile_roster`
    from stored rows, through the same function the import uses.
    """
    from app.database import SessionLocal
    from app.models.payroll_report import PayrollReportEmployee

    db = SessionLocal()
    try:
        # A fourth member: configured, active, union — and NO week line.
        absent = PayrollReportEmployee(
            id=str(uuid.uuid4()), tenant_id=TESTCO_ID,
            payentry_file_number="9404", display_name="Absent, Member",
            dept="PRECAST", is_union_member=True, active=True,
            initiation_fee_due=False,
        )
        db.add(absent)
        db.commit()

        r = client.get(f"{BASE}/weeks/{seeded['week_id']}/focus",
                       headers=H(seeded["tokens"]["view"]))
        assert r.status_code == 200, r.text[:300]
        codes = {f["code"] for f in r.json()["findings"]}
        assert "configured_member_missing_from_export" in codes, (
            f"a union member with no hours produced no finding; got {codes}"
        )
        mine = next(f for f in r.json()["findings"]
                    if f["code"] == "configured_member_missing_from_export")
        assert mine["file_number"] == "9404", mine
        # The key must be one the decision endpoint accepts, or the answer
        # cannot be recorded against the finding.
        assert mine["key"] == "configured_member_missing_from_export:9404:", mine
        assert client.post(
            f"{BASE}/weeks/{seeded['week_id']}/decisions",
            headers=H(seeded["tokens"]["approve"]),
            data={"finding_key": mine["key"], "outcome": "asked", "note": "x"},
        ).status_code == 201
    finally:
        db.execute(text("DELETE FROM payroll_report_employees WHERE id=:i"),
                   {"i": absent.id})
        db.commit()
        db.close()


def test_a_whole_week_of_hours_can_be_corrected_in_one_entry(
        client, seeded, switch_on):
    """⚠️ **40 HOURS. THE COMMONEST REAL CORRECTION IS A WEEK, NOT A DAY.**

    The first version bounded this at ±24 on the reasoning that no single day
    is more than a day — true of a day and false of the job. Stevenson's week
    never reached Payentry at all; Susan enters 40 REG against one date. At ±24
    that insert raised a CheckViolation and the screen got a 500.

    Every test I had written used small numbers, because I wrote them against
    the constraint rather than against the work.
    """
    r = _correct(client, seeded["tokens"]["approve"], seeded["week_id"],
                 hours="40.00", reason="whole week never reached Payentry")
    assert r.status_code == 201, r.text[:300]
    assert D(r.json()["hours"]) == D("40.00")


def test_an_implausible_correction_is_refused_with_a_message_not_a_500(
        client, seeded, switch_on):
    """⚠️ The DATABASE is the backstop; the EDGE is the error surface.

    Hitting the CHECK constraint produces an IntegrityError and a 500, which
    tells the person at the screen nothing. The service refuses first and names
    both the figure and the bound.
    """
    r = _correct(client, seeded["tokens"]["approve"], seeded["week_id"],
                 hours="400", reason="decimal slip")
    assert r.status_code == 422, f"{r.status_code}: {r.text[:200]}"
    assert "400" in r.text and "168" in r.text, r.text[:300]


def test_the_correction_bound_matches_the_database_constraint():
    """The two are one number in two places; a drift makes the edge check
    useless in one direction and the 500 return in the other."""
    from app.services.payroll.week_focus import _MAX_CORRECTION_HOURS
    import re as _re
    src = open("app/models/payroll_report.py").read()
    m = _re.search(r'hours >= -(\d+) AND hours <= (\d+)', src)
    assert m, "could not find the CHECK constraint in the model"
    assert int(m.group(1)) == int(m.group(2)) == int(_MAX_CORRECTION_HOURS), (
        f"edge bound {_MAX_CORRECTION_HOURS} != constraint {m.groups()}"
    )
