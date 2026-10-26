"""The record, the rulebook, and the route that writes them.

James's dispatch of 2026-10-26, clauses 2–4. The rules themselves are in
`test_opas_why.py`, which has no database guard.

⚠️ ONE TEST HERE DRIVES THE REAL FastAPI ROUTE, and the reason is the 2026-10-20 lesson
recorded on the decision log: "every service test can pass while the route logs nothing".
A reason that the service stores and the endpoint never calls is an empty column, and so
is a reason nobody has typed.

⚠️ AND ONE TEST READS A TYPESCRIPT FILE. `opens_rulebook`'s phrase list is mirrored in
`order-list-routing.ts` because the bar needs the predicate locally — it has to tell a
REASON from a NEW REQUEST without asking a server that does not know a question is
outstanding. Two copies that nothing compares will drift, so this compares them, the
same arrangement `GENERIC_WORDS` has with `ghost.ts`.
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import date
from pathlib import Path

import pytest

if not os.environ.get("DATABASE_URL") or not os.environ.get("SECRET_KEY"):
    pytest.skip("DATABASE_URL is not set", allow_module_level=True)

from sqlalchemy import text

from app.database import SessionLocal
from app.models.company import Company
from app.models.opas_decision import OpasDecision
from app.models.opas_rule import OpasRule
from app.services.order_list import rulebook
from tests._cleanup import purge_companies_by_slug

SLUG = "rb1-rulebook"


@pytest.fixture()
def tenant():
    db = SessionLocal()
    try:
        purge_companies_by_slug(db, f"{SLUG}%")
        db.commit()
        company = Company(id=str(uuid.uuid4()), name="RB1 Vault Co", slug=SLUG,
                          vertical="manufacturing", is_active=True)
        db.add(company)
        db.flush()
        yield db, company.id
    finally:
        db.rollback()
        try:
            purge_companies_by_slug(db, f"{SLUG}%")
            db.commit()
        except Exception:
            db.rollback()
        db.close()


def _decision(db, tid, **kw) -> OpasDecision:
    row = OpasDecision(
        company_id=tid, input_text=kw.pop("input_text", "order hopkins monticello"),
        surface="capture", proposed_by="rules",
        proposed_request={"opened": "capture"}, outcome="executed", **kw,
    )
    db.add(row)
    db.flush()
    return row


CHANGE = {"field": "vault", "was": "Monticello Burial Vault",
          "now": "Continental Burial Vault", "label": "Vault"}


# ── the record ────────────────────────────────────────────────────────────────


def test_a_reason_and_its_scope_land_on_the_decision_row(tenant):
    db, tid = tenant
    d = _decision(db, tid)
    assert rulebook.record_answer(
        db, decision_id=d.id, company_id=tid,
        reason="they always take the continental for a veteran",
        scope="always", change=CHANGE,
    ) is True
    db.refresh(d)
    assert d.reason == "they always take the continental for a veteran"
    assert d.reason_scope == "always"
    assert (d.changed_field, d.changed_from, d.changed_to) == (
        "vault", "Monticello Burial Vault", "Continental Burial Vault",
    )
    assert d.resolved_at is not None


def test_a_skip_has_a_scope_and_no_reason(tenant):
    """⚠️ WHICH IS WHY THE CHECK IS ONE-DIRECTIONAL. A reason with no scope is a
    half-answered question; a scope with no reason is exactly what a skip is."""
    db, tid = tenant
    d = _decision(db, tid)
    assert rulebook.record_answer(
        db, decision_id=d.id, company_id=tid, reason=None, scope="skipped", change=None,
    ) is True
    db.refresh(d)
    assert d.reason is None and d.reason_scope == "skipped"


def test_the_second_answer_is_refused(tenant):
    """"never asks twice for one order" — enforced at the RECORD, not only where the
    question is drawn. A retry, a second tab or a double ⌘1 must not replace the first."""
    db, tid = tenant
    d = _decision(db, tid)
    assert rulebook.record_answer(db, decision_id=d.id, company_id=tid,
                                 reason="first", scope="today", change=CHANGE) is True
    assert rulebook.record_answer(db, decision_id=d.id, company_id=tid,
                                 reason="second", scope="always", change=CHANGE) is False
    db.refresh(d)
    assert d.reason == "first" and d.reason_scope == "today"


def test_another_tenants_decision_row_cannot_be_answered(tenant):
    db, tid = tenant
    other = Company(id=str(uuid.uuid4()), name="RB1 Other", slug=f"{SLUG}-other",
                    vertical="manufacturing", is_active=True)
    db.add(other)
    db.flush()
    theirs = _decision(db, other.id)
    assert rulebook.record_answer(db, decision_id=theirs.id, company_id=tid,
                                 reason="x", scope="today", change=CHANGE) is False
    db.refresh(theirs)
    assert theirs.reason_scope is None
    # The control: their own tenant can.
    assert rulebook.record_answer(db, decision_id=theirs.id, company_id=other.id,
                                 reason="x", scope="today", change=CHANGE) is True


def test_the_database_refuses_a_reason_with_no_scope(tenant):
    """⚠️ THE CHECK CONSTRAINT, EXERCISED. A row holding a reason and no scope would read
    as a deliberate record of a half-answered question, and the service cannot write one
    — but the column could, which is what a constraint is for."""
    db, tid = tenant
    d = _decision(db, tid)
    # ⚠️ THE `raises` GOES ROUND THE UPDATE, not round a later flush. Postgres evaluates
    # a CHECK on the statement, so my first version of this test raised OUTSIDE the
    # block and failed while the constraint was working perfectly — the test's
    # mechanics, not the schema's.
    with pytest.raises(Exception) as caught:
        db.execute(text("UPDATE opas_decisions SET reason = :r WHERE id = :i"),
                   {"r": "orphaned", "i": d.id})
    assert "ck_opas_decisions_reason_has_scope" in str(caught.value)
    db.rollback()


# ── the rulebook ──────────────────────────────────────────────────────────────


def test_a_confirmed_rule_appears_with_where_it_came_from(tenant):
    db, tid = tenant
    d = _decision(db, tid)
    rulebook.record_answer(db, decision_id=d.id, company_id=tid,
                           reason="they always take the continental for a veteran",
                           scope="always", change=CHANGE)
    rid = rulebook.add_rule(
        db, company_id=tid, user_id=None,
        rule_text="Veterans take the Continental rather than the Monticello.",
        source_decision_id=d.id,
    )
    assert rid is not None
    book = rulebook.rulebook(db, tid)
    assert len(book["rules"]) == 1
    entry = book["rules"][0]
    assert entry["text"] == "Veterans take the Continental rather than the Monticello."
    assert entry["change"] == "vault · Monticello Burial Vault → Continental Burial Vault"
    assert entry["reason"] == "they always take the continental for a veteran"
    assert entry["decision_id"] == d.id


def test_the_footer_says_nothing_uses_these_yet(tenant):
    """⚠️ THE MOST IMPORTANT LINE ON THE PANE. "nothing uses the rulebook in this slice.
    It records and shows" (James) — a reader who sees a rule they confirmed would
    otherwise reasonably assume it is in force.

    ⚠️ AND IT IS PRESENT WITH NO RULES TOO, which is the likeliest moment for somebody
    to wonder what it would do if it had any."""
    db, tid = tenant
    empty = rulebook.rulebook(db, tid)
    assert empty["rules"] == []
    assert empty["empty"] == "No rules yet"
    assert empty["footer"] == rulebook.FOOTER
    assert "doesn" in empty["footer"] and "use these yet" in empty["footer"]

    rulebook.add_rule(db, company_id=tid, user_id=None, rule_text="A rule.")
    full = rulebook.rulebook(db, tid)
    assert full["footer"] == rulebook.FOOTER
    assert "empty" not in full


def test_an_empty_sentence_is_not_a_rule(tenant):
    db, tid = tenant
    assert rulebook.add_rule(db, company_id=tid, user_id=None, rule_text="   ") is None
    assert rulebook.add_rule(db, company_id=tid, user_id=None, rule_text="") is None
    assert rulebook.rulebook(db, tid)["rules"] == []


def test_a_rule_can_be_edited_or_switched_off(tenant):
    db, tid = tenant
    rid = rulebook.add_rule(db, company_id=tid, user_id=None, rule_text="First wording.")
    got = rulebook.update_rule(db, company_id=tid, rule_id=rid, rule_text="Better wording.")
    assert got["text"] == "Better wording."
    assert rulebook.rulebook(db, tid)["rules"][0]["text"] == "Better wording."

    rulebook.update_rule(db, company_id=tid, rule_id=rid, is_active=False)
    assert rulebook.rulebook(db, tid)["rules"] == []
    # ⚠️ SWITCHED OFF, NOT DELETED. The row survives so the pane can one day say a rule
    # was withdrawn, and so a mis-click is recoverable.
    assert db.query(OpasRule).filter(OpasRule.id == rid).one().is_active is False


def test_another_tenants_rule_cannot_be_read_or_edited(tenant):
    db, tid = tenant
    other = Company(id=str(uuid.uuid4()), name="RB1 Other2", slug=f"{SLUG}-other2",
                    vertical="manufacturing", is_active=True)
    db.add(other)
    db.flush()
    theirs = rulebook.add_rule(db, company_id=other.id, user_id=None, rule_text="Theirs.")
    assert rulebook.rulebook(db, tid)["rules"] == []
    assert rulebook.update_rule(db, company_id=tid, rule_id=theirs, rule_text="mine") is None
    # The control, and it proves the id was good.
    assert rulebook.update_rule(db, company_id=other.id, rule_id=theirs,
                                rule_text="still theirs") is not None


def test_a_rule_outlives_the_decision_it_came_from(tenant):
    """⚠️ `SET NULL`, NOT `CASCADE`. A rule whose log row was purged is still a rule the
    office wrote; deleting it because the log was tidied would let the log decide what
    the rulebook says."""
    db, tid = tenant
    d = _decision(db, tid)
    rid = rulebook.add_rule(db, company_id=tid, user_id=None, rule_text="Survives.",
                            source_decision_id=d.id)
    db.execute(text("DELETE FROM opas_decisions WHERE id = :i"), {"i": d.id})
    db.flush()
    row = db.query(OpasRule).filter(OpasRule.id == rid).one()
    assert row.source_decision_id is None
    assert rulebook.rulebook(db, tid)["rules"][0]["text"] == "Survives."


# ── the bar phrase ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("phrase,expected", [
    ("rules", True), ("the rules", True), ("rulebook", True), ("the rulebook", True),
    ("Show me the rulebook", True), ("  RULES  ", True),
    ("rule", False), ("ruled", False), ("rule out", False),
    ("the rules of thumb", False), ("", False),
])
def test_opens_rulebook(phrase, expected):
    assert rulebook.opens_rulebook(phrase) is expected


def test_the_two_opener_lists_agree():
    """⚠️ THE CLIENT MIRRORS THIS LIST AND NOTHING ELSE COMPARES THEM.

    The bar needs the predicate locally: in the reason stage of Opas's "why?" it has to
    tell a REASON from a NEW REQUEST, and the server has not been told a question is
    outstanding. Two copies that nothing compares will drift — the arrangement
    `GENERIC_WORDS` has with `ghost.ts`, for the same reason.
    """
    ts = (
        Path(__file__).resolve().parents[2]
        / "frontend/src/components/opas/order-list/order-list-routing.ts"
    )
    source = ts.read_text()
    block = re.search(
        r"const RULEBOOK_OPENERS:[^=]*=\s*\[(.*?)\]", source, re.S,
    )
    assert block is not None, "RULEBOOK_OPENERS not found in order-list-routing.ts"
    # ⚠️ THE STRINGS, NOT THE WHOLE BLOCK. A comment inside the literal must not be
    # read as a phrase — the prose-vs-code trap CLAUDE.md records five instances of.
    mirrored = set(re.findall(r'"([^"]+)"', block.group(1)))
    assert mirrored == set(rulebook._OPENERS), (
        f"only on the client: {sorted(mirrored - set(rulebook._OPENERS))}; "
        f"only on the server: {sorted(set(rulebook._OPENERS) - mirrored)}"
    )


# ── the route ─────────────────────────────────────────────────────────────────


def test_A_REAL_POST_TO_why_WRITES_THE_REASON_AND_THE_RULE():
    """⚠️ IT DRIVES THE REAL ROUTE, because every service test above can pass while the
    endpoint never calls them — the 2026-10-20 lesson from the decision log, where a log
    wired nowhere and a log nobody had typed into were the same empty table.

    The whole of clause 2 and 3 in one pass: approve, be asked, answer with "always",
    get a draft back, confirm it, and find it in the rulebook.
    """
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_user, get_db
    from app.main import app
    from app.models.user import User

    db = SessionLocal()
    try:
        # ⚠️ SUNNYCREST, NOT TESTCO, AND MEASURING IS WHY. This test skipped on testco
        # because APPROVE is blocked there for every vault: the extractor resolves
        # "monticello" to "Monticello Burial Vault" and `_product_by_exact_name` finds no
        # such product — testco's are named "Monticello", "Monarch", "Continental". So
        # the capture could never become an order and the route under test was never
        # reached. A skipped route test is documentation (CLAUDE.md §11).
        #
        # ⚠️ SUNNYCREST HAS THE REAL CATALOGUE — "Monticello Burial Vault" and
        # "Continental Burial Vault" both exist as products, courtesy of
        # `seed_sunnycrest_demo_catalog.py` — so a capture there reaches `ready=True`
        # with no blockers. Measured before switching, not assumed.
        tid = db.execute(text("SELECT id FROM companies WHERE slug='sunnycrest'")).scalar()
        if tid is None:
            pytest.skip("sunnycrest is not seeded in this database")
        user = db.query(User).filter(User.company_id == tid).first()
        if user is None:
            pytest.skip("sunnycrest has no users")

        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: user
        client = TestClient(app)

        # the capture, with a change: Opas reads monticello, the person retypes
        started = client.post("/api/v1/capture/sessions", json={})
        assert started.status_code == 200, started.text
        sid = started.json()["session_id"]
        # ⚠️ A COMPLETE ORDER, OR APPROVE REFUSES AND THE TEST PROVES NOTHING. The
        # cemetery, the deceased and the service location are all blockers; measured
        # from `assess_approval` rather than guessed.
        for body in (
            "order hopkins monticello thursday 10am st marys graveside "
            "for the smith family",
            "order hopkins continental thursday 10am st marys graveside "
            "for the smith family",
        ):
            r = client.put(f"/api/v1/capture/sessions/{sid}/text", json={"text": body})
            assert r.status_code == 200, r.text
        r = client.post(f"/api/v1/capture/sessions/{sid}/choose",
                        json={"field_id": "vault", "index": 1})
        assert r.status_code == 200, r.text

        # ⚠️ THE DECISION ROW WAS LINKED BY THE ROUTE, which is the id the whole flow
        # hangs on and which used to be thrown away.
        linked = db.execute(
            text("SELECT decision_id FROM capture_sessions WHERE id = :s"), {"s": sid},
        ).scalar()
        assert linked is not None, "the first text must link the session to its log row"

        approved = client.post(f"/api/v1/capture/sessions/{sid}/approve")
        if approved.status_code != 200:
            pytest.skip(f"approve blocked in this database: {approved.text[:200]}")
        ask = approved.json().get("ask_why")
        assert ask is not None, "an approve after a change must carry the question"
        assert ask["field"] == "vault"
        assert ask["prompt"].startswith("You changed the vault from")

        # answer it: always
        r = client.post(f"/api/v1/capture/sessions/{sid}/why",
                        json={"reason": "veterans always take the continental",
                              "scope": "always"})
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["stored"] is True
        # ⚠️ A DRAFT COMES BACK EITHER WAY, AND WITH NO KEY IT IS THEIR OWN WORDS.
        # "If the model is down, your own words become the draft" (James), which is
        # clause 5's "Model key off -> own words drafted".
        #
        # ⚠️ THE EQUALITY IS THE POINT AND `assert out["draft"]` WAS NOT ENOUGH. A break
        # test made `rule_draft.draft` return a canned model sentence and NOTHING went
        # red — truthy is true of either answer, so the test could not tell the
        # fallback from the model. Asserted against the configuration rather than
        # hard-coded: with a key present the model's sentence is the right answer.
        from app.config import settings

        assert out["draft"], "there is always something to confirm"
        if not settings.ANTHROPIC_API_KEY:
            assert out["draft"] == "veterans always take the continental", (
                "with no key the draft must be the person's own words, verbatim"
            )

        # confirm it
        r = client.post(f"/api/v1/capture/sessions/{sid}/why",
                        json={"reason": "veterans always take the continental",
                              "scope": "always",
                              "rule_text": "Veterans take the Continental."})
        assert r.status_code == 200, r.text
        assert r.json()["rule_id"]

        # it is in the rulebook, with its provenance
        book = client.get("/api/v1/order-list/rulebook")
        assert book.status_code == 200, book.text
        payload = book.json()
        texts = [x["text"] for x in payload["rules"]]
        assert "Veterans take the Continental." in texts
        assert payload["footer"] == rulebook.FOOTER

        # ⚠️ AND IT IS NOT ASKED AGAIN. A re-read of the same session must not carry the
        # question — "never asks twice for one order".
        again = client.get(f"/api/v1/capture/sessions/{sid}")
        assert "ask_why" not in again.json()
    finally:
        app.dependency_overrides.clear()
        db.rollback()
        try:
            db.execute(text(
                "DELETE FROM opas_rules WHERE text = 'Veterans take the Continental.'"))
            db.commit()
        except Exception:
            db.rollback()
        db.close()
