"""Setting an employee's payroll status — the entrance r234 never had.

⚠️ **THE FIELD SHIPPED ELEVEN DAYS BEFORE ANYTHING COULD WRITE IT.** `r234`
added `payroll_status` / `payroll_status_since`; measured on production
2026-11-21, **0 of 30** employees carried a value while two readers depended
on them — the R-115's line 1 (which fell back to counting checks) and
`roster_coverage`'s excused branch, which had therefore **never once been
taken**. CLAUDE.md §11: complete machinery behind an unprovisioned entrance.

These tests hold the entrance, and in particular the three things that make
the record worth keeping: the reason, the before-and-after, and the
distinction between the day a status BEGAN and the day somebody typed it.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.models.user import User
from tests._payroll_switch import payroll_switch
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture
from tests._two_step import tenant_token

_canonical_tenant = make_canonical_tenant_fixture()

HEADERS = {"X-Company-Slug": "testco"}
BASE = "/api/v1/payroll-reports"


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
        for slug in ("admin", "payroll"):
            role = (db.query(Role)
                    .filter(Role.company_id == TESTCO_ID, Role.slug == slug).first())
            if role is None:
                pytest.skip(f"testco has no {slug} role")
            uid = f"empstatus-{slug}"
            db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
            db.add(User(id=uid, email=f"{uid}@testco.com", hashed_password="x",
                        first_name="Status", last_name=slug.title(),
                        company_id=TESTCO_ID, role_id=role.id, is_active=True))
            made.append(uid)
            out[slug] = uid

        # ⚠️ A VIEW-ONLY ACTOR, because the seeded `payroll` role HOLDS
        # `payroll.approve` — a refusal test using it would get a 201 and read
        # as a missing check. That exact mistake cost a debugging cycle on the
        # copies endpoint.
        rid = str(uuid.uuid4())
        for (old,) in db.execute(text(
                "SELECT id FROM roles WHERE company_id=:c AND slug='empstatus-view'"),
                {"c": TESTCO_ID}).fetchall():
            db.execute(text("DELETE FROM role_permissions WHERE role_id=:r"), {"r": old})
            db.execute(text("DELETE FROM roles WHERE id=:r"), {"r": old})
        db.add(Role(id=rid, company_id=TESTCO_ID, name="empstatus-view",
                    slug="empstatus-view", is_system=False, is_active=True))
        db.flush()
        db.add(RolePermission(id=str(uuid.uuid4()), role_id=rid,
                              permission_key="payroll.view"))
        uid = "empstatus-viewonly"
        db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        db.add(User(id=uid, email=f"{uid}@testco.com", hashed_password="x",
                    first_name="View", last_name="Only", company_id=TESTCO_ID,
                    role_id=rid, is_active=True))
        made.append(uid)
        roles.append(rid)
        out["viewonly"] = uid
        db.commit()
        yield {k: tenant_token(v, TESTCO_ID) for k, v in out.items()}
    finally:
        for uid in made:
            db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        for rid in roles:
            db.execute(text("DELETE FROM role_permissions WHERE role_id=:r"), {"r": rid})
            db.execute(text("DELETE FROM roles WHERE id=:r"), {"r": rid})
        db.commit()
        db.close()


def _auth(tok):
    return {"Authorization": f"Bearer {tok}", **HEADERS}


@pytest.fixture
def employee():
    from app.database import SessionLocal
    from app.models.payroll_report import PayrollReportEmployee

    db = SessionLocal()
    eid = str(uuid.uuid4())
    try:
        db.add(PayrollReportEmployee(
            id=eid, tenant_id=TESTCO_ID, payentry_file_number="ST-01",
            display_name="Status, Test T", is_union_member=True))
        db.commit()
        yield eid
    finally:
        db.execute(text("DELETE FROM payroll_employee_status_changes "
                        "WHERE employee_id=:e"), {"e": eid})
        db.execute(text("DELETE FROM payroll_report_employees WHERE id=:e"), {"e": eid})
        db.commit()
        db.close()


@pytest.fixture
def switch_on():
    with payroll_switch(TESTCO_ID, True):
        yield


# ── the absence this closes ──────────────────────────────────────────────


def test_an_employee_starts_with_NO_STATUS_and_that_is_not_active(
        client, tokens, switch_on, employee):
    """⚠️ NULL IS NOT `active`. NULL means nobody has said; `active` means
    somebody looked. The R-115's line-1 fallback turns on exactly this —
    a tenant with no statuses counts by checks AND SAYS SO."""
    r = client.get(f"{BASE}/employees/{employee}/status",
                   headers=_auth(tokens["payroll"]))
    assert r.status_code == 200, r.text[:300]
    assert r.json()["status"] is None
    assert r.json()["since"] is None
    assert r.json()["history"] == []


def test_setting_a_status_records_it_AND_moves_the_current_value(
        client, tokens, switch_on, employee):
    r = client.put(f"{BASE}/employees/{employee}/status",
                   data={"status": "left", "since": "2026-06-25",
                         "reason": "Payentry termination date"},
                   headers=_auth(tokens["payroll"]))
    assert r.status_code == 201, r.text[:300]

    got = client.get(f"{BASE}/employees/{employee}/status",
                     headers=_auth(tokens["payroll"])).json()
    assert got["status"] == "left"
    assert got["since"] == "2026-06-25"
    assert len(got["history"]) == 1
    assert got["history"][0]["reason"] == "Payentry termination date"
    assert got["history"][0]["changed_by_name"], "a change with no author"

    # The denormalised column moved too — every existing reader uses it.
    from app.database import SessionLocal
    from app.models.payroll_report import PayrollReportEmployee
    db = SessionLocal()
    try:
        e = db.query(PayrollReportEmployee).filter(
            PayrollReportEmployee.id == employee).first()
        assert e.payroll_status == "left"
        assert e.payroll_status_since == date(2026, 6, 25)
    finally:
        db.close()


def test_a_second_change_APPENDS_and_carries_what_it_replaced(
        client, tokens, switch_on, employee):
    """⚠️ **NEVER AN OVERWRITE** (James, 2026-11-21). A status decides whether
    somebody appears on a form filed with a union; who said what, and when,
    has to survive the next edit."""
    client.put(f"{BASE}/employees/{employee}/status",
               data={"status": "workers_comp", "since": "2026-10-01",
                     "reason": "out on comp"}, headers=_auth(tokens["payroll"]))
    client.put(f"{BASE}/employees/{employee}/status",
               data={"status": "left", "since": "2026-11-03",
                     "reason": "did not return"}, headers=_auth(tokens["payroll"]))

    h = client.get(f"{BASE}/employees/{employee}/status",
                   headers=_auth(tokens["payroll"])).json()["history"]
    assert len(h) == 2, h
    assert h[0]["status"] == "left", "newest first"
    assert h[0]["previous_status"] == "workers_comp"
    assert h[0]["previous_since"] == "2026-10-01"
    assert h[1]["previous_status"] is None, "the first change replaced nothing"


# ── the three things that make the record worth keeping ──────────────────


def test_a_change_with_NO_REASON_is_refused(client, tokens, switch_on, employee):
    """The field somebody reads a year later when the union asks why a member
    was not on a form. "left" with no reason cannot answer them."""
    for blank in ("", "   "):
        r = client.put(f"{BASE}/employees/{employee}/status",
                       data={"status": "left", "since": "2026-06-25",
                             "reason": blank},
                       headers=_auth(tokens["payroll"]))
        assert r.status_code in (400, 422), f"{blank!r}: {r.status_code}"


def test_SINCE_and_CHANGED_AT_are_different_dates(
        client, tokens, switch_on, employee):
    """⚠️ Routinely months apart — a June leaver recorded in November. The
    R-115's line-1 rule compares `since` against the month, so conflating
    them would put a leaver back into a month they had already left."""
    client.put(f"{BASE}/employees/{employee}/status",
               data={"status": "left", "since": "2026-06-25",
                     "reason": "Payentry termination date"},
               headers=_auth(tokens["payroll"]))
    h = client.get(f"{BASE}/employees/{employee}/status",
                   headers=_auth(tokens["payroll"])).json()["history"][0]
    assert h["since"] == "2026-06-25"
    assert h["changed_at"][:4] >= "2026"
    assert h["changed_at"][:10] != h["since"], (
        "the day it began and the day it was typed are not the same field")


def test_a_FUTURE_since_is_refused(client, tokens, switch_on, employee):
    """⚠️ "Left as of next March" would drop the member from every month
    until then — including months already filed — because the line-1 rule
    only asks whether the status began before the month."""
    soon = (date.today() + timedelta(days=30)).isoformat()
    r = client.put(f"{BASE}/employees/{employee}/status",
                   data={"status": "left", "since": soon, "reason": "planned"},
                   headers=_auth(tokens["payroll"]))
    assert r.status_code == 400, r.text[:200]
    assert "future" in r.text.lower()


def test_an_unknown_status_is_refused(client, tokens, switch_on, employee):
    r = client.put(f"{BASE}/employees/{employee}/status",
                   data={"status": "furloughed", "since": "2026-06-25",
                         "reason": "x"}, headers=_auth(tokens["payroll"]))
    assert r.status_code == 400, r.text[:200]


def test_a_NO_OP_change_is_refused_rather_than_recorded(
        client, tokens, switch_on, employee):
    """A no-op row is noise in the one place that has to stay readable."""
    body = {"status": "left", "since": "2026-06-25", "reason": "first"}
    assert client.put(f"{BASE}/employees/{employee}/status", data=body,
                      headers=_auth(tokens["payroll"])).status_code == 201
    again = client.put(f"{BASE}/employees/{employee}/status",
                       data={**body, "reason": "second"},
                       headers=_auth(tokens["payroll"]))
    assert again.status_code == 400, again.text[:200]
    assert len(client.get(f"{BASE}/employees/{employee}/status",
                          headers=_auth(tokens["payroll"])).json()["history"]) == 1


# ── who may ──────────────────────────────────────────────────────────────


def test_setting_needs_payroll_approve_and_READING_does_not(
        client, tokens, switch_on, employee):
    """⚠️ `payroll.approve`, NOT admin. Susan knows somebody left — she
    reconciles the roster weekly. If only an admin could record it, the fact
    would be known by one person and recordable by another, which is how it
    stays unrecorded."""
    assert client.get(f"{BASE}/employees/{employee}/status",
                      headers=_auth(tokens["viewonly"])).status_code == 200

    denied = client.put(f"{BASE}/employees/{employee}/status",
                        data={"status": "left", "since": "2026-06-25",
                              "reason": "x"}, headers=_auth(tokens["viewonly"]))
    assert denied.status_code == 403, denied.text[:200]

    # The control: the same request from somebody who holds it succeeds.
    assert client.put(f"{BASE}/employees/{employee}/status",
                      data={"status": "left", "since": "2026-06-25",
                            "reason": "x"},
                      headers=_auth(tokens["payroll"])).status_code == 201


def test_another_tenants_employee_is_a_404_not_a_403(client, tokens, switch_on):
    """A 403 would confirm the id exists."""
    r = client.get(f"{BASE}/employees/{uuid.uuid4()}/status",
                   headers=_auth(tokens["payroll"]))
    assert r.status_code == 404, r.status_code


def test_the_data_switch_still_gates_the_whole_surface(client, tokens, employee):
    with payroll_switch(TESTCO_ID, False):
        r = client.get(f"{BASE}/employees/{employee}/status",
                       headers=_auth(tokens["payroll"]))
        assert r.status_code == 403, r.text[:200]


# ── what it unblocks ─────────────────────────────────────────────────────


def test_setting_statuses_flips_line_1_off_the_CHECK_FALLBACK(
        client, tokens, switch_on, employee):
    """⚠️ **THE REASON THIS EXISTS.** With no status recorded anywhere, the
    R-115 counts line 1 by checks and warns that it is doing so. One recorded
    status is enough to switch it to counting membership — which is what
    makes Susan's lookup in Payentry worth doing."""
    from datetime import date as _d

    from app.database import SessionLocal
    from app.services.payroll import r115_form
    from app.services.payroll.rules import DEFAULT_RULES

    db = SessionLocal()
    try:
        before = r115_form.build_lines(db, tenant_id=TESTCO_ID, year=2026,
                                       month=10, rules=DEFAULT_RULES)
        assert before["unit"]["basis"] == "checks_in_month", before["unit"]
    finally:
        db.close()

    client.put(f"{BASE}/employees/{employee}/status",
               data={"status": "left", "since": "2026-06-25",
                     "reason": "Payentry termination date"},
               headers=_auth(tokens["payroll"]))

    db = SessionLocal()
    try:
        after = r115_form.build_lines(db, tenant_id=TESTCO_ID, year=2026,
                                      month=10, rules=DEFAULT_RULES)
        assert after["unit"]["basis"] == "payroll_status", after["unit"]
        assert not any("payroll_status" in w for w in after["warnings"]), \
            after["warnings"]
    finally:
        db.close()
