"""One row per bar interpretation — the evidence the rulebook will come from.

James's dispatch of 2026-10-20, step 4. No "why?" line, no rulebook: this slice only
records what was typed, who interpreted it, what request came out, and what became of it.

⚠️ THE ONE HARD RULE IS THAT A LOGGING FAILURE NEVER COSTS AN ANSWER, and it has its own
test below. A log that can break the bar is worse than no log.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

if not os.environ.get("DATABASE_URL") or not os.environ.get("SECRET_KEY"):
    pytest.skip("DATABASE_URL is not set", allow_module_level=True)

from sqlalchemy import text as sql_text
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.company import Company
from app.models.customer import Customer
from app.models.opas_decision import OpasDecision
from app.models.sales_order import SalesOrder
from app.services.order_list import decision_log


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        s.execute(sql_text("SELECT 1"))
    except Exception as exc:
        s.close()
        pytest.skip(f"database unavailable: {exc}")
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def tenant(db):
    """⚠️ COMMITTED, BECAUSE `record_ask` COMMITS. A rolled-back fixture would make the
    log's own commit fail on a missing FK, which is a property of the test rather than of
    the code. The teardown purges by slug prefix.
    """
    company = Company(
        id=str(uuid.uuid4()), name="Log Co", slug=f"dlog-{uuid.uuid4().hex[:8]}",
        is_active=True, vertical="manufacturing",
    )
    db.add(company)
    db.commit()
    yield company
    db.rollback()
    db.execute(sql_text("DELETE FROM opas_decisions WHERE company_id = :c"), {"c": company.id})
    db.execute(sql_text("DELETE FROM companies WHERE id = :c"), {"c": company.id})
    db.commit()


def _rows(db, company_id):
    return (
        db.query(OpasDecision)
        .filter(OpasDecision.company_id == company_id)
        .order_by(OpasDecision.created_at)
        .all()
    )


# ───────────────────────────────────────────────────────────────────────────
# what a row records
# ───────────────────────────────────────────────────────────────────────────

def test_a_rules_hit_is_recorded_verbatim(db, tenant):
    body = {"kind": "question", "title": "Open orders",
            "question": {"is_default": True, "title": "Open orders"}}
    rid = decision_log.record_ask(
        db, company_id=tenant.id, user_id=None, phrase="  Orders, please ",
        body=body, surface="bar",
    )
    assert rid is not None
    row = _rows(db, tenant.id)[0]
    # ⚠️ VERBATIM, UNTRIMMED. A normalised copy would be the rules' view of the phrase
    # rather than the person's, and the rules' view is what we are trying to improve.
    assert row.input_text == "  Orders, please "
    assert row.proposed_by == "rules"
    assert row.outcome == "executed"
    assert row.proposed_request == {"question": {"is_default": True, "title": "Open orders"}}
    assert row.surface == "bar"
    assert row.model_accepted is None


def test_a_miss_is_recorded_as_refused_with_no_request(db, tenant):
    rid = decision_log.record_ask(
        db, company_id=tenant.id, user_id=None,
        phrase="anything going to st marys this week",
        body={"kind": "unrecognized", "hint": "Try: …"}, surface="bar",
    )
    assert rid is not None
    row = _rows(db, tenant.id)[0]
    assert row.outcome == "refused"
    assert row.proposed_request is None


def test_a_question_with_picks_is_recorded_as_asked(db, tenant):
    decision_log.record_ask(
        db, company_id=tenant.id, user_id=None, phrase="hopkins order",
        body={"kind": "picks", "picks": [
            {"n": 1, "label": "Smith · SO-2026-0001"},
            {"n": 2, "label": "Hart · SO-2026-0004"},
        ]},
        surface="bar",
    )
    row = _rows(db, tenant.id)[0]
    assert row.outcome == "asked"
    assert row.proposed_request == {"picks": ["Smith · SO-2026-0001", "Hart · SO-2026-0004"]}
    assert row.resolution is None, "an unanswered question must not claim a resolution"


def test_an_order_opened_by_name_is_recorded_with_the_id(db, tenant):
    decision_log.record_ask(
        db, company_id=tenant.id, user_id=None, phrase="riverside order",
        body={"kind": "open_order", "open_order_id": "o4"}, surface="bar",
    )
    row = _rows(db, tenant.id)[0]
    assert row.outcome == "executed"
    assert row.proposed_request == {"open_order_id": "o4"}


def test_a_model_answer_records_the_model_and_its_numbers(db, tenant):
    decision_log.record_ask(
        db, company_id=tenant.id, user_id=None,
        phrase="anything going to st marys this week",
        body={"kind": "question", "question": {"cemetery": "St. Mary's Cemetery"}},
        surface="bar", proposed_by="model", model_latency_ms=2898, model_accepted=True,
    )
    row = _rows(db, tenant.id)[0]
    assert row.proposed_by == "model"
    assert row.model_latency_ms == 2898
    assert row.model_accepted is True


# ───────────────────────────────────────────────────────────────────────────
# what is NOT recorded
# ───────────────────────────────────────────────────────────────────────────

def test_a_phrase_less_call_is_not_an_interpretation_and_is_not_logged(db, tenant):
    """⚠️ THE BAR RE-ASKS THE SAME QUESTION WITH NO PHRASE when a pill is removed and
    when a pick is chosen. Logging those would fill the evidence with rows nobody typed.
    """
    for phrase in (None, "", "   "):
        assert decision_log.record_ask(
            db, company_id=tenant.id, user_id=None, phrase=phrase,
            body={"kind": "question"}, surface="bar",
        ) is None
    assert _rows(db, tenant.id) == []
    # ⚠️ THE CONTROL: a real phrase DOES land, so the three Nones are about the guard.
    assert decision_log.record_ask(
        db, company_id=tenant.id, user_id=None, phrase="orders",
        body={"kind": "question"}, surface="bar",
    ) is not None


# ───────────────────────────────────────────────────────────────────────────
# the surface
# ───────────────────────────────────────────────────────────────────────────

def test_the_surface_is_derived_from_the_request_not_reported_by_the_client():
    """⚠️ A CLIENT THAT SAID "bar" WHILE SENDING AN OPEN QUESTION would put a wrong answer
    in the evidence, and the evidence is the one thing here that has to be right.
    """
    from app.services.order_list.question import default_question

    assert decision_log.surface_for(None, None) == "bar"
    assert decision_log.surface_for(default_question(), None) == "bar_with_list"
    assert decision_log.surface_for(None, "sales-order") == "bar_with_order"
    assert decision_log.surface_for(None, "catalog") == "catalog"
    # ⚠️ AND A CLIENT CLAIM CANNOT OVERRIDE A QUESTION IT ACTUALLY SENT: an open question
    # with a stale `front` still records that the list was open.
    assert decision_log.surface_for(default_question(), "sales-order") == "bar_with_order"


# ───────────────────────────────────────────────────────────────────────────
# the constraints
# ───────────────────────────────────────────────────────────────────────────

def test_a_model_row_without_a_verdict_is_refused_by_the_DATABASE(db, tenant):
    """⚠️ NOT BY PYTHON. `proposed_by = 'model'` with `model_accepted` NULL is a row that
    cannot say whether the door worked — the one question this table exists to answer
    about the model — so the CHECK constraint refuses it however it is constructed.
    """
    db.add(OpasDecision(
        company_id=tenant.id, input_text="x", surface="bar",
        proposed_by="model", outcome="executed", model_accepted=None,
    ))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_an_unknown_proposed_by_or_outcome_is_refused(db, tenant):
    for kwargs in (
        {"proposed_by": "vibes", "outcome": "executed"},
        {"proposed_by": "rules", "outcome": "maybe"},
        {"proposed_by": "rules", "outcome": "asked", "resolution": "shrugged"},
    ):
        db.add(OpasDecision(
            company_id=tenant.id, input_text="x", surface="bar", **kwargs,
        ))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
    # ⚠️ THE CONTROL: the legal combination is accepted, so the three refusals are about
    # the constraints rather than about a table that rejects everything.
    db.add(OpasDecision(
        company_id=tenant.id, input_text="x", surface="bar",
        proposed_by="rulebook", outcome="asked", resolution="answered",
        resolved_option=2,
    ))
    db.flush()
    db.rollback()


# ───────────────────────────────────────────────────────────────────────────
# ⚠️ the rule that matters most
# ───────────────────────────────────────────────────────────────────────────

def test_A_LOGGING_FAILURE_NEVER_COSTS_AN_ANSWER(db, tenant, monkeypatch):
    """⚠️ AND IT LEAVES THE SESSION USABLE, which is the half that is easy to miss.
    Without the rollback inside `record_ask`, a failed write leaves the caller's session
    in a failed transaction and the NEXT thing it does raises — a logging failure
    becoming a request failure one step later.
    """
    import app.models.opas_decision as mod

    class Exploding:
        def __init__(self, **_kw):
            raise RuntimeError("the log is on fire")

    monkeypatch.setattr(mod, "OpasDecision", Exploding)
    assert decision_log.record_ask(
        db, company_id=tenant.id, user_id=None, phrase="orders",
        body={"kind": "question"}, surface="bar",
    ) is None
    # the session still works
    assert db.execute(sql_text("SELECT 1")).scalar() == 1


def test_a_BAD_ROW_also_leaves_the_session_usable(db, tenant):
    """The other failure mode: the row is constructed fine and the DATABASE refuses it.
    A constraint violation must be rolled back here, not left for the next query.
    """
    rid = decision_log.record_ask(
        db, company_id=tenant.id, user_id=None, phrase="x",
        body={"kind": "question"}, surface="bar",
        # a verdict-less model row — the CHECK constraint refuses it
        proposed_by="model", model_accepted=None,
    )
    assert rid is None
    assert db.execute(sql_text("SELECT 1")).scalar() == 1
    assert _rows(db, tenant.id) == []


def test_the_catalog_resolve_outcome_follows_the_candidate_count(db, tenant):
    for n, expected in ((1, "executed"), (3, "asked"), (0, "refused")):
        rid = decision_log.record_resolve(
            db, company_id=tenant.id, user_id=None, phrase=f"phrase-{n}",
            candidate_count=n,
        )
        assert rid is not None
        row = db.query(OpasDecision).filter(OpasDecision.id == rid).one()
        assert row.outcome == expected, f"{n} candidates -> {row.outcome}"
        assert row.surface == "catalog"
        assert row.proposed_request == {"candidates": n}


# ───────────────────────────────────────────────────────────────────────────
# ⚠️ THE ROUTE'S OWN DECISION, WHICH THE SERVICE TESTS ABOVE CANNOT SEE
# ───────────────────────────────────────────────────────────────────────────

def test_the_route_records_NEVER_ASKED_as_null_not_as_refused(monkeypatch):
    """⚠️ ADDED AFTER A BREAK TEST FOUND NOTHING RED.

    Replacing the route's `seen.get("accepted") if seen.get("called") else None` with
    `bool(seen.get("accepted"))` turned nothing red across 33 tests — every one of them
    calls `record_ask` directly and none exercises the route's own mapping from the
    observer dict.

    The distinction is the whole value of the column. `False` says the model was
    consulted and its answer was refused; `None` says it was never consulted, which is
    what a rules hit looks like and is by far the common case. Collapsing them would
    make the refusal rate read as 100%.
    """
    import app.api.routes.order_list_pane as route

    # The observer dict as `propose` leaves it in each of the three real cases.
    cases = {
        "rules resolved it, the door was never opened": ({}, "rules", None),
        "no api key, so no call was attempted": (
            {"called": False, "reason": "no_api_key"}, "rules", None),
        "called and refused": (
            {"called": True, "accepted": False, "reason": "provider_error"},
            "rules", False),
        "called and accepted": (
            {"called": True, "accepted": True, "latency_ms": 2898}, "model", True),
    }
    for label, (seen, expect_by, expect_accepted) in cases.items():
        got_by = "model" if seen.get("accepted") else "rules"
        got_accepted = seen.get("accepted") if seen.get("called") else None
        assert got_by == expect_by, label
        assert got_accepted is expect_accepted, label

    # ⚠️ AND THE EXPRESSIONS ABOVE ARE THE ROUTE'S OWN, READ OUT OF ITS SOURCE — not a
    # copy that could drift away from it while staying green.
    import inspect
    src = inspect.getsource(route.ask_orders)
    assert 'seen.get("accepted") if seen.get("called") else None' in src
    assert '"model" if seen.get("accepted") else "rules"' in src


# ───────────────────────────────────────────────────────────────────────────
# ⚠️ THE ROUTE, OVER THE WIRE, WRITING A REAL ROW
# ───────────────────────────────────────────────────────────────────────────

def test_A_REAL_POST_TO_ask_LEAVES_A_ROW(db, tenant):
    """⚠️ EVERY TEST ABOVE CALLS `record_ask` DIRECTLY. None of them proves the route
    calls it at all.

    That is the gap that matters before handing James a walk: a decision log wired
    nowhere looks exactly like a decision log nobody has typed into yet — both are an
    empty table — and `record_ask` swallows its own failures, so a miswiring would be
    silent in both directions. This drives the real FastAPI route and then reads the
    table.

    ⚠️ IT ALSO PINS THE SURFACE DERIVATION AT THE BOUNDARY, which is the one fact the
    client supplies and the server could get wrong on its own.
    """
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_user, get_db
    from app.main import app
    from app.models.role import Role
    from app.models.user import User

    # ⚠️ `users.role_id` IS NOT NULL, and the bare tenant fixture seeds no roles — so the
    # role is created here rather than looked up with a `if role else None` fallback that
    # would have passed None into a non-null column.
    role = Role(
        id=str(uuid.uuid4()), company_id=tenant.id, name="Office", slug="office",
        is_active=True,
    )
    db.add(role)
    db.flush()
    user = User(
        id=str(uuid.uuid4()), company_id=tenant.id,
        email=f"dlog-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x", first_name="Log", last_name="Walker",
        is_active=True, role_id=role.id,
    )
    db.add(user)
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        client = TestClient(app)
        r = client.post("/api/v1/order-list/ask", json={"phrase": "orders this month"})
        assert r.status_code == 200, r.text
        r2 = client.post(
            "/api/v1/order-list/ask",
            json={"phrase": "only hopkins", "front": "sales-order"},
        )
        assert r2.status_code == 200, r2.text

        rows = _rows(db, tenant.id)
        assert len(rows) == 2, "the route did not write a row per phrase"
        first, second = rows
        assert first.input_text == "orders this month"
        assert first.surface == "bar"
        assert first.actor_user_id == user.id, "the actor is recorded"
        # ⚠️ `None`, NOT `False` — the model was never consulted on a rules hit, and
        # that is a different fact from consulted-and-refused.
        assert first.model_accepted is None
        assert first.proposed_by == "rules"
        assert first.outcome in ("executed", "asked", "refused")

        assert second.input_text == "only hopkins"
        # ⚠️ THE CLIENT'S `front` REACHED THE DERIVATION. Without the wiring this reads
        # "bar" and the two phrases become indistinguishable in the evidence.
        assert second.surface == "bar_with_order"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        db.execute(sql_text("DELETE FROM opas_decisions WHERE company_id = :c"), {"c": tenant.id})
        db.execute(sql_text("DELETE FROM users WHERE id = :u"), {"u": user.id})
        db.execute(sql_text("DELETE FROM roles WHERE id = :r"), {"r": role.id})
        db.commit()
