"""Copies of documents that left Bridgeable — the general record, via the R-115.

⚠️ **THE RECORD IS GENERAL FROM THE FIRST PRODUCER, ON PURPOSE.** The R-115's
print and "mark as sent" are the first two things that put a document outside
the building. Built as R-115 columns they would be redone for every later
document, so they write to `outgoing_copies` with a `document_kind` and a
`subject` instead. These tests hold the general shape as much as the payroll
surface — in particular the area rule, which is the part a later document
kind will depend on and cannot discover for itself.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.models.user import User
from app.services.outgoing_copies import registry as copy_registry
from app.services.outgoing_copies import service as copy_service
from app.services.payroll.r115_schedule import check_dates_in
from tests._payroll_switch import payroll_switch
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture
from tests._two_step import tenant_token

_canonical_tenant = make_canonical_tenant_fixture()

HEADERS = {"X-Company-Slug": "testco"}
BASE = "/api/v1/payroll-reports"

_TODAY = date.today()
YEAR, MONTH = ((_TODAY.year - 1, 12) if _TODAY.month == 1
               else (_TODAY.year, _TODAY.month - 1))
SUBJECT = f"{YEAR}-{MONTH:02d}"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def tokens():
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
                pytest.skip(f"testco has no {slug} role")
            uid = f"copies-{slug}"
            if db.query(User).filter(User.id == uid).first() is None:
                db.add(User(id=uid, email=f"{uid}@testco.com",
                            hashed_password="x", first_name="Copy",
                            last_name=slug.title(), company_id=TESTCO_ID,
                            role_id=role.id, is_active=True))
                made.append(uid)
            out[slug] = uid
        db.commit()
        yield {k: tenant_token(v, TESTCO_ID) for k, v in out.items()}
    finally:
        for uid in made:
            db.execute(text("DELETE FROM outgoing_copies WHERE made_by_user_id=:u"),
                       {"u": uid})
            db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        db.commit()
        db.close()


def _auth(token):
    return {"Authorization": f"Bearer {token}", **HEADERS}


@pytest.fixture
def a_month_with_dues():
    """A register month, a rule set, and no copies to start from."""
    from app.database import SessionLocal
    from app.models.payroll_report import (
        PayrollCheck,
        PayrollCheckLine,
        PayrollRuleSet,
    )

    db = SessionLocal()
    made, rule_id = [], None
    try:
        if db.query(PayrollRuleSet).filter(
                PayrollRuleSet.tenant_id == TESTCO_ID).first() is None:
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
                   {"t": TESTCO_ID, "y": YEAR, "m": MONTH})
        db.execute(text("DELETE FROM payroll_checks WHERE tenant_id=:t "
                        "AND extract(year from check_date)=:y "
                        "AND extract(month from check_date)=:m"),
                   {"t": TESTCO_ID, "y": YEAR, "m": MONTH})
        for emp in ("C1", "C2"):
            for i, when in enumerate(check_dates_in(YEAR, MONTH)):
                cid = str(uuid.uuid4())
                made.append(cid)
                db.add(PayrollCheck(id=cid, tenant_id=TESTCO_ID, emp_id=emp,
                                    person=emp, check_number=f"CP-{emp}-{i}",
                                    check_date=when, source_page=0))
                db.add(PayrollCheckLine(
                    id=str(uuid.uuid4()), tenant_id=TESTCO_ID, check_id=cid,
                    kind="earning", code="Reg", hours=D("40.00"),
                    amount=D("1000.00")))
                db.add(PayrollCheckLine(
                    id=str(uuid.uuid4()), tenant_id=TESTCO_ID, check_id=cid,
                    kind="deduction", code="Union", amount=D("18.00")))
        db.execute(text("DELETE FROM outgoing_copies WHERE tenant_id=:t"),
                   {"t": TESTCO_ID})
        db.commit()
        yield db
    finally:
        db.execute(text("DELETE FROM outgoing_copies WHERE tenant_id=:t"),
                   {"t": TESTCO_ID})
        if made:
            db.execute(text("DELETE FROM payroll_check_lines "
                            "WHERE check_id = ANY(:i)"), {"i": made})
            db.execute(text("DELETE FROM payroll_checks WHERE id = ANY(:i)"),
                       {"i": made})
        if rule_id:
            db.execute(text("DELETE FROM payroll_rule_sets WHERE id=:i"),
                       {"i": rule_id})
        db.commit()
        db.close()


@pytest.fixture
def switch_on():
    with payroll_switch(TESTCO_ID, True):
        yield


# ── printing records a copy ──────────────────────────────────────────────


def test_printing_records_a_copy_that_FREEZES_the_figures(
        client, tokens, switch_on, a_month_with_dues):
    r = client.post(f"{BASE}/r115/copies",
                    data={"year": YEAR, "month": MONTH, "left_as": "printed"},
                    headers=_auth(tokens["payroll"]))
    assert r.status_code == 201, r.text[:300]
    body = r.json()
    assert body["left_as"] == "printed"
    assert body["document_kind"] == "r115"
    assert body["subject"] == SUBJECT
    assert body["made_by_name"], "a copy with no maker cannot be worded"
    assert body["renderer_version"], "a frozen copy must say what rendered it"
    # The copy is not a receipt: it carries the figures.
    stored = copy_service.copies_for(
        a_month_with_dues, tenant_id=TESTCO_ID, document_kind="r115",
        subject=SUBJECT)[0]
    by_key = {ln["key"]: ln["value"] for ln in stored.content["lines"]}
    assert by_key["total_remittance"] == "180.00", by_key
    assert by_key["total_earnings"] == "10000.00", by_key


def test_the_copy_appears_on_the_FORM_the_next_time_it_is_read(
        client, tokens, switch_on, a_month_with_dues):
    client.post(f"{BASE}/r115/copies",
                data={"year": YEAR, "month": MONTH, "left_as": "printed"},
                headers=_auth(tokens["payroll"]))
    body = client.get(f"{BASE}/r115", params={"year": YEAR, "month": MONTH},
                      headers=_auth(tokens["payroll"])).json()
    assert len(body["copies"]) == 1, body["copies"]
    assert body["copies"][0]["left_as"] == "printed"
    assert body["copies"][0]["differs_from_today"] is False


def test_copies_come_back_NEWEST_FIRST(client, tokens, switch_on,
                                       a_month_with_dues):
    for mode in ("printed", "printed"):
        client.post(f"{BASE}/r115/copies",
                    data={"year": YEAR, "month": MONTH, "left_as": mode},
                    headers=_auth(tokens["payroll"]))
    client.post(f"{BASE}/r115/copies",
                data={"year": YEAR, "month": MONTH, "left_as": "marked_sent",
                      "sent_how": "mailed with check 4521"},
                headers=_auth(tokens["admin"]))
    copies = client.get(f"{BASE}/r115", params={"year": YEAR, "month": MONTH},
                        headers=_auth(tokens["payroll"])).json()["copies"]
    assert len(copies) == 3
    assert copies[0]["left_as"] == "marked_sent", "the newest is first"
    assert [c["made_at"] for c in copies] == sorted(
        [c["made_at"] for c in copies], reverse=True)


# ── marking sent ─────────────────────────────────────────────────────────


def test_marking_sent_records_HOW(client, tokens, switch_on, a_month_with_dues):
    r = client.post(f"{BASE}/r115/copies",
                    data={"year": YEAR, "month": MONTH,
                          "left_as": "marked_sent",
                          "sent_how": "mailed with check 4521"},
                    headers=_auth(tokens["admin"]))
    assert r.status_code == 201, r.text[:300]
    assert r.json()["sent_how"] == "mailed with check 4521"


def test_marking_sent_WITHOUT_how_is_refused(client, tokens, switch_on,
                                             a_month_with_dues):
    """⚠️ "Sent" with no method is a claim nobody can follow up, which is the
    whole value of recording it."""
    r = client.post(f"{BASE}/r115/copies",
                    data={"year": YEAR, "month": MONTH,
                          "left_as": "marked_sent", "sent_how": "   "},
                    headers=_auth(tokens["admin"]))
    assert r.status_code == 400, r.text[:300]
    assert "how" in r.text.lower()


@pytest.fixture
def view_only_token():
    """A user with `payroll.view` and NOT `payroll.approve`.

    ⚠️ **THE SEEDED `payroll` ROLE HOLDS APPROVE, SO IT CANNOT TELL THESE
    APART.** The first version of the test below used it and got a 201 where
    it expected a 403 — which read as the permission check being absent and
    was the check working on a user who holds the permission. A test for a
    refusal needs an actor who should actually be refused.
    """
    import uuid as _uuid

    from app.database import SessionLocal
    from app.models.role import Role
    from app.models.role_permission import RolePermission

    db = SessionLocal()
    uid = "copies-view-only"
    rid = str(_uuid.uuid4())
    try:
        # ⚠️ AUDIT ROWS FIRST, IN SETUP AS WELL AS TEARDOWN. Marking a copy
        # sent writes an audit row keyed on this user, and `audit_logs.user_id`
        # has no cascade — so a run that ended badly leaves rows that make the
        # NEXT run fail at setup, which reads as a broken fixture rather than
        # as litter. Cleaning both ends makes the suite self-healing.
        db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
        db.execute(text("DELETE FROM outgoing_copies WHERE made_by_user_id=:u"),
                   {"u": uid})
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        # ⚠️ AND THE ROLE BY SLUG, NOT BY THE ID THIS RUN GENERATED. A
        # previous run's role survives with a different uuid and the same
        # slug, and `uq_roles_slug_company` then refuses the insert — which
        # fails at SETUP and reads as the fixture being broken. Clearing by
        # the natural key is what makes the suite survive its own bad days.
        for (old_rid,) in db.execute(text(
                "SELECT id FROM roles WHERE company_id=:c AND slug=:s"),
                {"c": TESTCO_ID, "s": "copies-view-only"}).fetchall():
            db.execute(text("DELETE FROM role_permissions WHERE role_id=:r"),
                       {"r": old_rid})
            db.execute(text("DELETE FROM roles WHERE id=:r"), {"r": old_rid})
        db.add(Role(id=rid, company_id=TESTCO_ID, name="copies-view-only",
                    slug="copies-view-only", is_system=False, is_active=True))
        db.flush()
        db.add(RolePermission(id=str(_uuid.uuid4()), role_id=rid,
                              permission_key="payroll.view"))
        db.add(User(id=uid, email=f"{uid}@testco.com",
                    hashed_password="not-a-credential", first_name="View",
                    last_name="Only", role_id=rid, company_id=TESTCO_ID,
                    is_active=True))
        db.commit()
        yield tenant_token(uid, TESTCO_ID)
    finally:
        db.execute(text("DELETE FROM outgoing_copies WHERE made_by_user_id=:u"),
                   {"u": uid})
        db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        db.execute(text("DELETE FROM role_permissions WHERE role_id=:r"), {"r": rid})
        db.execute(text("DELETE FROM roles WHERE id=:r"), {"r": rid})
        db.commit()
        db.close()


def test_marking_sent_needs_MORE_than_printing_does(
        client, tokens, switch_on, a_month_with_dues, view_only_token):
    """⚠️ Printing is reading. Saying a form reached the union is an
    assertion about the outside world, and needs `payroll.approve`."""
    printed = client.post(f"{BASE}/r115/copies",
                          data={"year": YEAR, "month": MONTH,
                                "left_as": "printed"},
                          headers=_auth(view_only_token))
    assert printed.status_code == 201, (
        f"a view-only reviewer may print: {printed.text[:200]}")

    sent = client.post(f"{BASE}/r115/copies",
                       data={"year": YEAR, "month": MONTH,
                             "left_as": "marked_sent", "sent_how": "mailed"},
                       headers=_auth(view_only_token))
    assert sent.status_code == 403, sent.text[:300]
    assert "payroll.approve" in sent.text

    # The control: the SAME request from someone who holds approve succeeds,
    # so the 403 above is about the permission and not about the request.
    ok = client.post(f"{BASE}/r115/copies",
                     data={"year": YEAR, "month": MONTH,
                           "left_as": "marked_sent", "sent_how": "mailed"},
                     headers=_auth(tokens["admin"]))
    assert ok.status_code == 201, ok.text[:300]


def test_an_unknown_way_of_leaving_is_refused(client, tokens, switch_on,
                                              a_month_with_dues):
    r = client.post(f"{BASE}/r115/copies",
                    data={"year": YEAR, "month": MONTH, "left_as": "faxed"},
                    headers=_auth(tokens["payroll"]))
    assert r.status_code == 400, r.text[:300]


# ── the point of the record: has it gone stale? ──────────────────────────


def test_a_copy_says_when_TODAYS_FIGURES_HAVE_MOVED(
        client, tokens, switch_on, a_month_with_dues):
    """⚠️ **THE REASON THE TABLE EXISTS.** "A form was printed in December" is
    an audit row. "The form printed in December no longer says what the data
    says" is the thing somebody needs to act on."""
    import uuid as _uuid

    from app.models.payroll_report import PayrollCheck, PayrollCheckLine

    client.post(f"{BASE}/r115/copies",
                data={"year": YEAR, "month": MONTH, "left_as": "printed"},
                headers=_auth(tokens["payroll"]))
    before = client.get(f"{BASE}/r115", params={"year": YEAR, "month": MONTH},
                        headers=_auth(tokens["payroll"])).json()
    assert before["copies"][0]["differs_from_today"] is False

    db = a_month_with_dues
    cid = str(_uuid.uuid4())
    db.add(PayrollCheck(id=cid, tenant_id=TESTCO_ID, emp_id="C3", person="C3",
                        check_number="CP-LATE", source_page=0,
                        check_date=check_dates_in(YEAR, MONTH)[-1]))
    db.add(PayrollCheckLine(id=str(_uuid.uuid4()), tenant_id=TESTCO_ID,
                            check_id=cid, kind="earning", code="Reg",
                            hours=D("40.00"), amount=D("1000.00")))
    db.add(PayrollCheckLine(id=str(_uuid.uuid4()), tenant_id=TESTCO_ID,
                            check_id=cid, kind="deduction", code="Union",
                            amount=D("18.00")))
    db.commit()
    try:
        after = client.get(f"{BASE}/r115", params={"year": YEAR, "month": MONTH},
                           headers=_auth(tokens["payroll"])).json()
        assert after["copies"][0]["differs_from_today"] is True
    finally:
        db.execute(text("DELETE FROM payroll_check_lines WHERE check_id=:c"),
                   {"c": cid})
        db.execute(text("DELETE FROM payroll_checks WHERE id=:c"), {"c": cid})
        db.commit()


def test_a_RE_WORDED_LABEL_does_not_count_as_the_figures_moving():
    """⚠️ Comparison is on the FIGURES, not the payload. A copy carries the
    header too, and `completed_by` changing would otherwise make every past
    copy "differ from today" — false, and it would train the reader to
    ignore the notice."""
    from app.models.outgoing_copy import OutgoingCopy

    frozen = {"lines": [{"number": 4, "key": "total_earnings",
                         "label": "Total Earnings (excl. lump sum)",
                         "value": "100.00", "blank": False}],
              "header": {"completed_by": "Susan"}}
    today = {"lines": [{"number": 4, "key": "total_earnings",
                        "label": "Total earnings, excluding lump sum",
                        "value": "100.00", "blank": False}],
             "header": {"completed_by": "Someone Else"}}
    copy = OutgoingCopy(content=frozen)
    assert copy_service.differs_from(copy, today) is False
    # The control: a changed VALUE does count.
    today["lines"][0]["value"] = "101.00"
    assert copy_service.differs_from(copy, today) is True


def test_not_checked_is_NULL_and_not_false():
    """A caller that did not supply today's figures has not established that
    they match."""
    from app.models.outgoing_copy import OutgoingCopy

    copy = OutgoingCopy(content={"lines": [{"number": 1, "key": "a",
                                            "value": "1", "blank": False}]},
                        id="x", document_kind="r115", subject=SUBJECT,
                        left_as="printed", renderer="r", renderer_version="1")
    assert copy_service.shape(copy)["differs_from_today"] is None
    assert copy_service.shape(copy, current=copy.content)[
        "differs_from_today"] is False


# ── the general shape: areas and unknown kinds ───────────────────────────


def test_an_unregistered_document_kind_is_REFUSED_not_defaulted():
    """⚠️ Defaulting an unknown kind to a permissive area would leak the next
    document the day somebody forgot to register it; defaulting to a
    restrictive one would hide copies with no sign they existed."""
    with pytest.raises(copy_registry.UnknownDocumentKind):
        copy_registry.kind_for("invoice")
    # The control: a registered kind resolves.
    assert copy_registry.kind_for("r115").area == "payroll"


def test_copies_are_visible_only_to_callers_who_can_see_the_KINDS_AREA():
    """⚠️ **THE COMPOSED-SURFACE RULE, AND THE ONE A LATER DOCUMENT KIND WILL
    DEPEND ON.** `outgoing_copies` is one table holding documents from every
    area; the only thing that can keep a payroll-limited reader out of an
    invoice copy is the kind-to-area map applied on read."""
    from app.core.areas import allowed_area_grants

    unlimited = allowed_area_grants(None)
    payroll_only = allowed_area_grants(["payroll"])
    nothing = allowed_area_grants([])

    assert "r115" in copy_registry.readable_kinds(unlimited)
    assert "r115" in copy_registry.readable_kinds(payroll_only)
    assert "r115" not in copy_registry.readable_kinds(nothing), (
        "a role limited to no areas must see no copies")


def test_a_reader_limited_to_ANOTHER_area_sees_no_r115_copies():
    """The discriminating case: a real area that is not payroll."""
    from app.core.areas import KNOWN_AREAS, allowed_area_grants

    others = [a for a in KNOWN_AREAS if a != "payroll"]
    assert others, "the test needs a second area to be meaningful"
    grants = allowed_area_grants([others[0]])
    assert "r115" not in copy_registry.readable_kinds(grants), others[0]


def test_every_registered_kind_names_an_area_that_EXISTS():
    """⚠️ A kind pointing at a misspelled area would be invisible to
    everyone, and would look exactly like a permissions problem."""
    from app.core.areas import KNOWN_AREAS

    for kind, spec in copy_registry.KINDS.items():
        assert spec.area in KNOWN_AREAS, (kind, spec.area)
        assert spec.renderer and spec.renderer_version, kind


def test_the_two_modes_with_no_producer_are_NAMED_as_such():
    """⚠️ **AN EMPTY `emailed` SET DOES NOT MEAN NO EMAILS WERE SENT** — it
    means Bridgeable has never been able to send one. Anything reporting on
    these modes has to say so, so the distinction is recorded in code rather
    than in a comment somebody can read past."""
    from app.models.outgoing_copy import LEFT_AS, LEFT_AS_WITH_PRODUCERS

    assert set(LEFT_AS_WITH_PRODUCERS) < set(LEFT_AS)
    assert set(LEFT_AS) - set(LEFT_AS_WITH_PRODUCERS) == {"downloaded",
                                                          "emailed"}


def test_a_copy_with_no_content_is_refused():
    """Recording that something left while losing what it said is worse than
    not recording it."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        with pytest.raises(copy_service.OutgoingCopyError):
            copy_service.record_copy(
                db, tenant_id=TESTCO_ID, document_kind="r115",
                subject=SUBJECT, content={}, left_as="printed",
                made_by_user_id=None)
    finally:
        db.rollback()
        db.close()
