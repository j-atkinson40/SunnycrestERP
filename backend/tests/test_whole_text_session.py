"""The typed session when the WHOLE TEXT is the source, not a list of lines.

⚠️ THIS FILE EXISTS BECAUSE `test_whole_text_extraction.py` TESTS THE FUNCTION AND
NOTHING TESTED THE WIRING. `extract_text` was complete, correct, and reachable from
no endpoint and no service for three days — complete machinery behind an
unprovisioned entrance (CLAUDE.md §11). Every test here goes through
`session_service`, which is what the route layer calls, so a function that stops
being called fails here.

⚠️ THE CLAIM THESE TESTS MAKE, stated so a reader can check it against them:

    set_text REPLACES.    Deleting a word un-captures what it said and stops
                          reporting what it failed to place.
    choose PERSISTS.      A settled pick survives every later re-read of text
                          that is still ambiguous.
    status is DERIVED.    "that's it" then deleted leaves the session capturing.
    add_line is UNTOUCHED (E6). Its policy, its accumulation, and the call
                          pipeline's behaviour are unchanged.

⚠️ THE `add_line` ASSERTIONS ARE NOT DECORATION. E6 requires the call pipeline's
behaviour not to change, and the only mechanism by which this work could have
changed it is the shared `EXTRACTOR`. `test_call_extraction_missing_set.py` and
`test_piece4_conditionals.py` pass unmodified; these pin the line path's OWN
policy at the seam, where a well-meaning "unify the two paths" refactor would
first break it.
"""
from __future__ import annotations

import uuid

import pytest

from app.database import SessionLocal


def _refuse_a_non_local_database() -> None:
    from urllib.parse import urlparse

    from app.config import settings

    host = (urlparse(settings.DATABASE_URL).hostname or "").lower()
    assert host in ("localhost", "127.0.0.1", "::1", ""), (
        f"these tests write; refusing to run against host {host!r}"
    )


@pytest.fixture(scope="module")
def db():
    _refuse_a_non_local_database()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def user(db):
    """One tenant, one user, in a savepoint that rolls back."""
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    sp = db.begin_nested()
    cid = str(uuid.uuid4())
    db.add(Company(id=cid, name="Whole Text Co", slug=f"wtc-{cid[:8]}"))
    db.flush()
    rid = str(uuid.uuid4())
    db.add(Role(id=rid, company_id=cid, name="Admin", slug="admin"))
    db.flush()
    uid = str(uuid.uuid4())
    db.add(User(
        id=uid, company_id=cid, email=f"{uid[:8]}@wtc.example.com",
        hashed_password="x", first_name="Whole", last_name="Text",
        role_id=rid, is_active=True,
    ))
    db.flush()
    try:
        yield cid, uid
    finally:
        sp.rollback()


def _session(db, cid, uid):
    from app.services.capture import session_service
    return session_service.start(db, company_id=cid, user_id=uid)


# ── the text is the source ───────────────────────────────────────────────

def test_the_text_is_stored_and_read_back(db, user):
    from app.services.capture import session_service

    cid, uid = user
    row = _session(db, cid, uid)
    session_service.set_text(
        db, row.id, company_id=cid, user_id=uid, text="tent only"
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)

    assert state["full_text"] == "tent only"
    assert state["values"]["cemetery_equipment"] == "tent_only"


def test_a_fresh_session_has_NO_whole_text_record_and_that_is_not_empty_string(db, user):
    """⚠️ NULL vs "" IS A REAL DISTINCTION AND THE PANE BRANCHES ON IT. A session with
    no text record falls back to its lines; a session whose text is "" has been
    cleared by the director. Collapsing them would make a cleared bar re-render the
    old lines."""
    from app.services.capture import session_service

    cid, uid = user
    row = _session(db, cid, uid)
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    assert state["full_text"] is None

    session_service.set_text(db, row.id, company_id=cid, user_id=uid, text="")
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    assert state["full_text"] == ""
    assert state["full_text"] is not None


def test_DELETING_A_WORD_UN_CAPTURES_WHAT_IT_SAID(db, user):
    """⚠️ THE WHOLE REASON THE MODEL CHANGED. Under `add_line` this was impossible:
    the value was written once and nothing could take it back, so a director who
    mistyped had no way to correct it except by saying the opposite out loud."""
    from app.services.capture import session_service

    cid, uid = user
    row = _session(db, cid, uid)

    session_service.set_text(
        db, row.id, company_id=cid, user_id=uid, text="tent only, nameplate only"
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    assert state["values"]["cemetery_equipment"] == "tent_only"
    assert state["values"]["personalization"] == "nameplate_only"

    # the director deletes the equipment phrase
    session_service.set_text(
        db, row.id, company_id=cid, user_id=uid, text="nameplate only"
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    assert "cemetery_equipment" not in state["values"], (
        "deleting the phrase left its value behind — the text is not the source"
    )
    assert state["values"]["personalization"] == "nameplate_only"


def test_UNRECOGNIZED_DOES_NOT_ACCUMULATE_UNDER_WHOLE_TEXT(db, user):
    """⚠️ THE OPPOSITE OF `add_line`'S RULE, DELIBERATELY. Accumulating was right when
    each line was an event that happened; it is wrong when the text is editable,
    because the pane would keep reporting words that are no longer on screen."""
    from app.services.capture import session_service

    cid, uid = user
    row = _session(db, cid, uid)

    session_service.set_text(
        db, row.id, company_id=cid, user_id=uid, text="zzqqwx tent only"
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    assert any("zzqqwx" in u for u in state["unrecognized"]), state["unrecognized"]

    session_service.set_text(
        db, row.id, company_id=cid, user_id=uid, text="tent only"
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    assert not any("zzqqwx" in u for u in state["unrecognized"]), (
        f"the deleted word is still reported: {state['unrecognized']}"
    )


def test_setting_the_SAME_text_twice_changes_nothing(db, user):
    """⚠️ THE `PUT` CONTRACT. The pane re-sends on every pause, including pauses where
    nothing changed, so a second identical call must be a no-op."""
    from app.services.capture import session_service

    cid, uid = user
    row = _session(db, cid, uid)
    t = "tent only, nameplate only, years only"

    session_service.set_text(db, row.id, company_id=cid, user_id=uid, text=t)
    first = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    session_service.set_text(db, row.id, company_id=cid, user_id=uid, text=t)
    second = session_service.read_state(db, row.id, company_id=cid, user_id=uid)

    assert first == second


# ── resolutions outrank re-extraction ───────────────────────────────────

def test_a_SETTLED_PICK_SURVIVES_RE_EXTRACTION_OF_STILL_AMBIGUOUS_TEXT(db, user):
    """⚠️ THE DEFECT THIS COLUMN EXISTS FOR, PINNED AT THE SEAM. The text that raised
    the question is still on screen and still ambiguous. Without a durable
    resolution, the next keystroke re-reads it, the same pick comes back, and the
    pane is unusable — the director cannot answer a question that re-asks itself."""
    from app.services.capture import session_service

    cid, uid = user
    row = _session(db, cid, uid)

    # ⚠️ A PHRASE THAT GENUINELY PRODUCES A PICK, measured rather than assumed — the
    # test asserts that below before relying on it. A phrase that resolved cleanly
    # would make every assertion after it vacuous.
    session_service.set_text(
        db, row.id, company_id=cid, user_id=uid, text="Continental"
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    picks = state["pending_picks"]
    assert picks, "no pick was raised, so this test cannot measure what it claims"
    field_id = picks[0]["field_id"]
    chosen = picks[0]["options"][0][0]

    session_service.choose(
        db, row.id, company_id=cid, user_id=uid, field_id=field_id, index=1
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    assert state["values"][field_id] == chosen
    assert not [p for p in state["pending_picks"] if p["field_id"] == field_id]

    # the director keeps typing; the ambiguous phrase is STILL in the text
    session_service.set_text(
        db, row.id, company_id=cid, user_id=uid, text="Continental, tent only"
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    assert state["values"][field_id] == chosen, (
        "re-extraction erased the settled pick"
    )
    assert not [p for p in state["pending_picks"] if p["field_id"] == field_id], (
        "the settled question was asked again"
    )
    assert state["values"]["cemetery_equipment"] == "tent_only"


def test_resolutions_are_returned_so_a_RELOAD_restores_them(db, user):
    """⚠️ RETURNED, NOT JUST STORED. A pane that re-reads the text without the
    resolutions would re-raise every settled question on reopen, which is exactly
    the tuck-survival case the GET endpoint exists for."""
    from app.services.capture import session_service

    cid, uid = user
    row = _session(db, cid, uid)
    session_service.set_text(
        db, row.id, company_id=cid, user_id=uid, text="Continental"
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    assert state["pending_picks"]
    field_id = state["pending_picks"][0]["field_id"]

    session_service.choose(
        db, row.id, company_id=cid, user_id=uid, field_id=field_id, index=1
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    assert field_id in state["resolutions"], state["resolutions"]


# ── status is derived from the text, never latched ───────────────────────

def test_the_done_signal_in_the_TEXT_reaches_the_rows(db, user):
    """⚠️ READ FROM THE TEXT, NOT FROM THE LINES. A typed-pane session has no lines,
    so a done signal read only from `typed_lines` would work in the call path and
    silently not in the pane — which is how `RowState.NEEDED` was dead state before."""
    from app.services.capture import session_service

    cid, uid = user
    row = _session(db, cid, uid)
    session_service.set_text(
        db, row.id, company_id=cid, user_id=uid, text="tent only, that's it"
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    assert any(r["state"] == "needed" for r in state["surface"]["rows"]), (
        "no row reported NEEDED after a done signal in the text"
    )


def test_DELETING_the_done_signal_stops_the_rows_reporting_NEEDED(db, user):
    """⚠️ NOT LATCHED. Latching would make the done signal the one thing on screen
    that editing could not take back."""
    from app.services.capture import session_service

    cid, uid = user
    row = _session(db, cid, uid)
    session_service.set_text(
        db, row.id, company_id=cid, user_id=uid, text="tent only, that's it"
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    assert any(r["state"] == "needed" for r in state["surface"]["rows"])

    session_service.set_text(
        db, row.id, company_id=cid, user_id=uid, text="tent only"
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    assert not any(r["state"] == "needed" for r in state["surface"]["rows"]), (
        "the done signal latched — deleting it did not take it back"
    )


def test_a_session_IN_REVIEW_returns_to_capturing_when_the_text_stops_saying_done(
    db, user
):
    """The `else` branch of the status re-derivation, pinned at the seam.

    ⚠️ THE PRECONDITION IS SET DIRECTLY, AND HERE IS WHY RATHER THAN A SHRUG. A
    session only reaches `review` when NOTHING is required-and-missing, and on a
    bare tenant nine fields are — vault, funeral_home, deceased_name, cemetery,
    burial_date, service_date, service_time, grave_location, service_location
    (measured, not recalled). Reaching review through the text needs a tenant with
    a resolvable vault, a real funeral home and a real cemetery, which is the
    seeded-tenant fixture, not this one.

    ⚠️ SO THIS TEST PINS THE BRANCH AND NOT THE ROUTE TO IT, and says so. Without
    it the `else` is UNREACHABLE FROM ANY TEST IN THIS FILE: my first attempt
    asserted `status == "capturing"` after deleting a done signal and passed with
    the branch deleted, because `_signal_done` had already set `capturing` on the
    way in — a check whose success condition is invariant under the failure it
    catches (CLAUDE.md §11, shape 7). Found by break-testing, not by reading.
    """
    from app.models.capture_session import STATUS_REVIEW
    from app.services.capture import session_service

    cid, uid = user
    row = _session(db, cid, uid)
    session_service.set_text(
        db, row.id, company_id=cid, user_id=uid, text="tent only"
    )
    row.status = STATUS_REVIEW
    db.flush()

    session_service.set_text(
        db, row.id, company_id=cid, user_id=uid, text="tent only"
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    assert state["status"] == "capturing", (
        "a session in review stayed there while its text says nothing about being "
        "done — the status is latched, not derived"
    )


# ── E6: the line path is not touched ────────────────────────────────────

def test_add_line_STILL_ACCUMULATES_and_still_wins_FIRST(db, user):
    """⚠️ E6 AT THE SEAM. Two sources, two policies, and this pins the one that must
    not have moved: a line re-stating a field does NOT overwrite the earlier answer.
    If someone 'unifies' the two paths onto LAST_WINS, this goes red here rather
    than in the call pipeline's own suite three weeks later."""
    from app.services.capture import session_service

    cid, uid = user
    row = _session(db, cid, uid)
    session_service.add_line(db, row.id, company_id=cid, user_id=uid, line="full setup")
    session_service.add_line(db, row.id, company_id=cid, user_id=uid, line="tent only")

    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    assert state["values"]["cemetery_equipment"] == "full_equipment", (
        "the second line overwrote the first — add_line's FIRST_WINS policy moved"
    )
    assert state["typed_lines"] == ["full setup", "tent only"]
    assert state["full_text"] is None, (
        "add_line wrote a whole-text record; the two paths are no longer distinct"
    )


def test_whole_text_LAST_WINS_where_the_line_path_FIRST_WINS(db, user):
    """⚠️ THE SAME TWO PHRASES, THE OPPOSITE OUTCOME, BY RULING. This is the pair that
    makes the policy difference visible: identical input, different source, different
    answer. A test of either one alone would pass under a single unified policy."""
    from app.services.capture import session_service

    cid, uid = user
    row = _session(db, cid, uid)
    session_service.set_text(
        db, row.id, company_id=cid, user_id=uid, text="full setup, actually tent only"
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    assert state["values"]["cemetery_equipment"] == "tent_only", (
        "the correction did not win — whole text is not LAST_WINS"
    )


def test_choose_on_a_LINE_captured_session_does_not_re_extract(db, user):
    """⚠️ THE BRANCH IN `choose`, EXERCISED FROM THE LINE SIDE. A session with no
    whole-text record must take the old path verbatim; re-extracting it would mean
    re-reading lines that were never meant to be re-read."""
    from app.services.capture import session_service

    cid, uid = user
    row = _session(db, cid, uid)
    session_service.add_line(
        db, row.id, company_id=cid, user_id=uid, line="Continental"
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    assert state["pending_picks"], "no pick on the line path either"
    field_id = state["pending_picks"][0]["field_id"]
    chosen = state["pending_picks"][0]["options"][0][0]

    session_service.choose(
        db, row.id, company_id=cid, user_id=uid, field_id=field_id, index=1
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    assert state["values"][field_id] == chosen
    assert state["full_text"] is None, "choose invented a whole-text record"


# ── isolation still holds on the new path ───────────────────────────────

def test_set_text_refuses_another_users_session(db, user):
    """⚠️ THE NEW ENDPOINT IS SCOPED LIKE THE OTHERS, and this is asserted rather than
    assumed because `set_text` is a new `_load` caller and a new caller is where a
    scoping argument gets dropped."""
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User
    from app.services.capture import session_service

    cid, uid = user
    row = _session(db, cid, uid)

    sp = db.begin_nested()
    try:
        other_c = str(uuid.uuid4())
        db.add(Company(id=other_c, name="Other Co", slug=f"oc-{other_c[:8]}"))
        db.flush()
        other_r = str(uuid.uuid4())
        db.add(Role(id=other_r, company_id=other_c, name="Admin", slug="admin"))
        db.flush()
        other_u = str(uuid.uuid4())
        db.add(User(
            id=other_u, company_id=other_c, email=f"{other_u[:8]}@oc.example.com",
            hashed_password="x", first_name="Other", last_name="User",
            role_id=other_r, is_active=True,
        ))
        db.flush()

        with pytest.raises(session_service.SessionNotFound):
            session_service.set_text(
                db, row.id, company_id=other_c, user_id=other_u, text="tent only"
            )
    finally:
        sp.rollback()
