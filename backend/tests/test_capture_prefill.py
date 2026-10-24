"""A pane's choice survives re-extraction, and yields to a different name in the text.

James's bug of 2026-10-24: "'New order' in the Hopkins Customer Pane opens the capture,
shows Funeral Home = Hopkins for about a second, then Funeral Home goes back to blank."

⚠️ THE CAUSE, REPRODUCED THROUGH THE WHOLE CYCLE BEFORE ANYTHING WAS CHANGED, with three
of the dispatch's four hypotheses ruled out by measurement rather than by argument:

    bar text without the name    THE CAUSE. `start(opening_line=…)` writes the home into
                                 `values` and leaves `full_text` NULL. The client's next
                                 debounced `set_text` arrives with the BAR's text —
                                 empty, because the host opened the pane without putting
                                 the opening line in the bar — and `set_text` rebuilds
                                 `values` from "".
    a new session id             NO. One session throughout.
    stale-sequence handling      NO. The wipe is in the ACCEPTED response, not a dropped
                                 one.
    the generic-word ruling      NO. `set_text("order Johnson Funeral Home ")` resolves
                                 the home correctly — a full name is not a prefix, and
                                 the exact-match path takes it.

⚠️ AND THE CLIENT'S OWN GUARD COULD NOT HAVE SAVED IT. `CapturePane` skips the re-extract
when `state.full_text === text`; `full_text` is NULL after a prefilled start, so
`null === ""` is false and the request fired every time.

⚠️ WHY NOT `resolutions`, WHICH ALREADY SURVIVES RE-EXTRACTION. Measured before choosing:
seeding it does keep the home through `set_text("")` — and it also keeps returning
Johnson when the text says Riverside, because resolutions outrank the text by design.
That is the second half of the ruling broken ("replaced only if the person names a
different funeral home in the text").
"""
from __future__ import annotations

import os

import pytest

if not os.environ.get("DATABASE_URL") or not os.environ.get("SECRET_KEY"):
    pytest.skip("DATABASE_URL is not set", allow_module_level=True)

from sqlalchemy import text as sql

from app.database import SessionLocal
from app.services.capture import session_service as ss


def _refuse_a_non_local_database() -> None:
    """⚠️ COPIED FROM `test_whole_text_session.py` DELIBERATELY. These tests WRITE
    (sessions, values), and `DATABASE_URL` is an inherited premise — the one class
    CLAUDE.md says to re-derive rather than trust. A production host refuses loudly here
    instead of writing capture sessions into the real company's database.
    """
    from urllib.parse import urlparse

    from app.config import settings

    host = (urlparse(settings.DATABASE_URL).hostname or "").lower()
    assert host in ("localhost", "127.0.0.1", "::1", ""), (
        f"these tests write; refusing to run against host {host!r}"
    )


@pytest.fixture(scope="module")
def db():
    """⚠️ `seeded` DEPENDS ON THIS AND IT IS NOT GLOBAL. `seeded` comes from
    `tests/_seeded_tenant.py` via `pytest_plugins`, but the `db` it takes is supplied
    per module — so a file that uses `seeded` without defining `db` errors at setup
    with "fixture 'db' not found", which is how I found out.
    """
    _refuse_a_non_local_database()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()

HOME = "Johnson Funeral Home"
OTHER = "Riverside Funeral Home"
OPENING = f"order {HOME} "
PREFILL = {"funeral_home": HOME}


def _fh(row) -> str | None:
    return (row.values or {}).get("funeral_home")


@pytest.fixture()
def homes(db, seeded):
    """⚠️ THE TENANT'S REAL CUSTOMERS, ASSERTED PRESENT RATHER THAN CREATED. `seeded` is
    testco with its real catalog; both of these are `seed_staging` customers. A test that
    created its own would be asserting against names no extractor vocabulary knows, and
    would pass while the resolver was broken.
    """
    found = db.execute(
        sql("SELECT name FROM customers WHERE company_id = :c AND name IN (:a, :b)"),
        {"c": seeded.company_id, "a": HOME, "b": OTHER},
    ).scalars().all()
    missing = {HOME, OTHER} - set(found)
    assert not missing, (
        f"the seeded tenant is missing {sorted(missing)} — run seed_dev.sh. These tests "
        f"must not skip: a green run against a bare database is what this file's "
        f"docstring is about."
    )
    return seeded.company_id, seeded.user_id


# ── the bug ───────────────────────────────────────────────────────────────────


def test_the_prefill_survives_the_whole_cycle(db, homes):
    """⚠️ THE WHOLE SEQUENCE, WHICH IS THE ONLY WAY TO SEE IT. The first state is correct
    — it was always correct. What broke it is the re-read that follows, so a test that
    starts a session and asserts passes against the bug.
    """
    cid, uid = homes
    row = ss.start(db, company_id=cid, user_id=uid, opening_line=OPENING, prefill=PREFILL)
    db.flush()
    assert _fh(row) == HOME, "the prefill must be there on the first state"
    assert row.prefill == PREFILL, "and stored, not merely applied"

    # the re-read the client makes ~400 ms later, with the BAR's text
    after = ss.set_text(db, row.id, company_id=cid, user_id=uid, text="")
    db.flush()
    assert _fh(after) == HOME, "re-extraction cleared the pane's choice"


@pytest.mark.parametrize("bar_text", [
    "",                                    # a fresh bar — the reproduction
    "monti thursday 10",                   # James's retest: the rest typed around it
    "order Johnson Funeral Home monti",    # the bar carrying the name too
    "   ",                                 # whitespace only
])
def test_re_extraction_never_clears_it(db, homes, bar_text):
    cid, uid = homes
    row = ss.start(db, company_id=cid, user_id=uid, opening_line=OPENING, prefill=PREFILL)
    db.flush()
    after = ss.set_text(db, row.id, company_id=cid, user_id=uid, text=bar_text)
    db.flush()
    assert _fh(after) == HOME, bar_text


def test_a_different_home_in_the_text_replaces_it(db, homes):
    """The other half of the ruling, and the half `resolutions` cannot do: "It's replaced
    only if the person names a different funeral home in the text."
    """
    cid, uid = homes
    row = ss.start(db, company_id=cid, user_id=uid, opening_line=OPENING, prefill=PREFILL)
    db.flush()
    after = ss.set_text(db, row.id, company_id=cid, user_id=uid,
                        text=f"order {OTHER} thursday 10am")
    db.flush()
    assert _fh(after) == OTHER, "the text must win over a prefill"

    # ⚠️ AND GOING BACK TO SILENCE RESTORES THE PANE'S CHOICE, which is what makes this a
    # precedence rule rather than a one-shot. The prefill is still stored; it simply lost
    # to a louder statement, and wins again when that statement is withdrawn.
    back = ss.set_text(db, row.id, company_id=cid, user_id=uid, text="thursday 10am")
    db.flush()
    assert _fh(back) == HOME


def test_the_rest_fills_in_around_it(db, homes):
    """James's retest: "Type 'monti thursday 10', and the rest should fill around it"."""
    cid, uid = homes
    row = ss.start(db, company_id=cid, user_id=uid, opening_line=OPENING, prefill=PREFILL)
    db.flush()
    after = ss.set_text(db, row.id, company_id=cid, user_id=uid,
                        text="order Johnson Funeral Home monti thursday 10")
    db.flush()
    values = after.values or {}
    assert values.get("funeral_home") == HOME
    assert "Monticello" in str(values.get("vault")), values
    assert values.get("service_date") is not None, values


def test_a_capture_with_no_prefill_is_untouched(db, homes):
    """⚠️ THE CONTROL. Every assertion above is about a session that HAS a prefill; if the
    new tier leaked into ordinary captures it would make a typed order keep a value the
    director had deleted — the exact failure the whole-text model exists to prevent.
    """
    cid, uid = homes
    row = ss.start(db, company_id=cid, user_id=uid, opening_line=OPENING)
    db.flush()
    assert row.prefill is None
    assert _fh(row) == HOME, "the opening line still extracts normally"
    after = ss.set_text(db, row.id, company_id=cid, user_id=uid, text="")
    db.flush()
    assert _fh(after) is None, "with no prefill, deleting the text still un-captures"


def test_a_prefill_does_not_answer_a_question_the_director_was_asked(db, homes):
    """⚠️ A PENDING PICK IS NOT "THE TEXT SAYING NOTHING". If the text produced a question
    for the field, answering it from a prefill would settle the director's question for
    them without saying so. Asserted at the extractor, where the rule lives.
    """
    from app.services.capture.typed_extraction import extract_text

    cid, _ = homes
    # a vault phrase that is ambiguous on this tenant produces a pick, not a value
    ex = extract_text(db, tenant_id=cid, text="order continental",
                      prefill={"vault": "Monticello Burial Vault"})
    asked = {p.field_id for p in ex.picks}
    if "vault" in asked:
        assert "vault" not in ex.values, "a prefill silently answered a pending pick"
    else:
        pytest.skip("'continental' is unambiguous on this tenant — nothing to assert")


# ── the route, which the break harness found unwatched ────────────────────────


def test_the_route_stores_a_whitelisted_prefill(db, homes):
    """⚠️ A GAP A BREAK TEST FOUND. Deleting `prefill=body.prefill` from the route turned
    nothing red — every test above calls `session_service.start` directly, so the
    body-to-service wiring was uncovered. The route is what the browser talks to.
    """
    from app.api.routes.capture import StartRequest

    body = StartRequest(opening_line=OPENING, prefill={"funeral_home": HOME})
    assert body.prefill == {"funeral_home": HOME}

    cid, uid = homes
    row = ss.start(db, company_id=cid, user_id=uid,
                   opening_line=body.opening_line, prefill=body.prefill)
    db.flush()
    assert row.prefill == {"funeral_home": HOME}


@pytest.mark.parametrize("sent,kept", [
    ({"funeral_home": HOME}, {"funeral_home": HOME}),
    # ⚠️ WHITELISTED, NOT PASSED THROUGH. A client able to seed any field could write a
    # value no extractor produced and no director typed — and `total` or `service_date`
    # would be read by the office as measured.
    ({"total": "9999"}, None),
    ({"service_date": "2026-12-25"}, None),
    ({"funeral_home": HOME, "total": "9999"}, {"funeral_home": HOME}),
    # Empty and blank values are not a choice.
    ({"funeral_home": "   "}, None),
    ({}, None),
    (None, None),
])
def test_the_route_only_admits_fields_a_pane_may_seed(sent, kept):
    from app.api.routes.capture import StartRequest

    assert StartRequest(opening_line=None, prefill=sent).prefill == kept


def test_the_route_hands_the_prefill_to_the_service():
    """⚠️ STRUCTURAL, AND A BREAK TEST IS WHY IT EXISTS AT ALL. Deleting
    `prefill=body.prefill` from `start_session` turned nothing red: the test above
    constructs a `StartRequest` and then calls `session_service.start` itself, so the
    one line joining them was uncovered — the request shape was watched and the wiring
    was not.

    ⚠️ IT READS THE MODULE WITH `ast` RATHER THAN CALLING THE ROUTE, because
    `start_session` ends in `db.commit()` and the seeded fixture holds a savepoint that a
    commit would collapse — a behavioural test here would write into the tenant every
    later test reads. Structure is the honest alternative, and it is read with `ast`
    rather than grepped: five times in two days a prose match has been the wrong
    instrument in this repo.
    """
    import ast
    import pathlib

    import app.api.routes.capture as mod

    tree = ast.parse(pathlib.Path(mod.__file__).read_text())
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "start_session"
    )
    calls = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "start"
    ]
    assert calls, "start_session no longer calls session_service.start"
    passed = {kw.arg for call in calls for kw in call.keywords}
    assert "prefill" in passed, (
        "start_session does not pass `prefill` to the service — a pane's choice would "
        "reach the API and be dropped there"
    )
    # ⚠️ THE POSITIVE CONTROL. An empty `passed` would satisfy nothing above by accident,
    # but a renamed service call would make `calls` empty and the assertion vacuous.
    assert {"company_id", "user_id", "opening_line"} <= passed, passed
