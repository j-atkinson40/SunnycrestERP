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

⚠️ MOVED ONTO THE SEEDED TENANT 2026-10-12, BY RULING — AND THE RULING'S STATED
REASON TURNED OUT TO BE WRONG, WHICH IS WORTH MORE THAN THE MOVE. The premise was
that a bare tenant made the availability layer unreachable. Measured afterwards: the
catalog, the 56 aliases and the availability config are all PLATFORM-level, so a bare
tenant inherits them, "Continental 34" resolves on one, and the conflict behind the
HTTP 500 arises there. Only the CEMETERIES are tenant-scoped.

What actually hid five defects from this file was that **none of its inputs ever
named a single vault**: `tent only`, `nameplate only`, `years only`, `full setup`,
and `Continental`, which is ambiguous and yields a pick rather than a resolution.
Every phrase stopped short of the same layer, and nothing in the file said so.

So the question to ask of a file like this one is not "what tenant does it run
against" but **"which layers do these inputs reach?"** The five tests at the bottom
exist to reach them; `seeded` is load-bearing for exactly one of the five (the
cemetery), and is kept for reasons stated in `tests/_seeded_tenant.py`.
`docs/investigations/2026-10-12-the-bare-tenant-gap.md` has the per-defect evidence,
run on both tenants.

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
def user(seeded):
    """⚠️ THE SEEDED TENANT, NOT A BARE ONE — see this module's docstring.

    Kept named `user` and yielding the same `(company_id, user_id)` pair so every
    test below is unchanged apart from the world it runs in. That is deliberate: the
    point of the move is that these assertions were always right and the ENVIRONMENT
    was what hid five defects, so changing the assertions at the same time would
    make it impossible to tell which of the two did the work.
    """
    return seeded.company_id, seeded.user_id


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

# ── the five live defects, each through the SESSION seam ────────────────
#
# ⚠️ THROUGH `session_service`, NOT THROUGH `evaluate_typed`. Sibling files already
# pin these at the function level; these exist because the PANE calls the session,
# and a defect fixed in the engine and not carried through the session's response
# would be invisible to the engine's own tests. Each one is break-tested in
# `docs/investigations/2026-10-12-the-bare-tenant-gap.md` with the edit that
# reintroduces the defect and the assertion it turns red.
#
# ⚠️ THIS COMMENT CLAIMED "NONE OF THESE FIVE COULD FAIL ON A BARE TENANT" AND THAT
# IS FALSE — I wrote it in the same session that measured the opposite. Run on a bare
# tenant, defects 1, 2, 3 and 5 each turn their test red exactly as they do here;
# only defect 4 needs a seeded cemetery, and on a bare tenant test 4 is red BEFORE
# anything is broken, so it is saturated there and reports the same result either
# way. Per-defect evidence on both tenants:
# `docs/investigations/2026-10-12-the-bare-tenant-gap.md`.

def test_1_AN_UNAVAILABLE_COMBINATION_DOES_NOT_500(db, user):
    """Defect 1. `UnpermittedAnswer` reached the route and the pane died."""
    from app.services.capture import session_service

    cid, uid = user
    row = _session(db, cid, uid)
    session_service.set_text(
        db, row.id, company_id=cid, user_id=uid,
        text="Continental 34, nameplate and vinyl",
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)

    assert state["conflicts"], (
        "no conflict reported for a combination this vault does not permit — either "
        "the engine raised (the original defect) or availability stopped narrowing"
    )
    c = state["conflicts"][0]
    assert c["field_id"] == "personalization"
    assert "nameplate_only" in c["permitted"], c


def test_2_THE_RESPONSE_DOES_NOT_CONTRADICT_ITSELF(db, user):
    """Defect 2. The withheld answer was still rendered, so one response called a
    value unavailable and showed it as done."""
    from app.services.capture import session_service

    cid, uid = user
    row = _session(db, cid, uid)
    session_service.set_text(
        db, row.id, company_id=cid, user_id=uid,
        text="Continental 34, nameplate and vinyl",
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)

    assert state["conflicts"], "precondition: there must be a conflict to contradict"
    pers = next(r for r in state["surface"]["rows"] if r["row_id"] == "personalization")
    assert pers["state"] != "done", (
        f"the Personalization row reads {pers['state']!r} showing {pers['value']!r} "
        f"in the same response that reports that value unavailable"
    )
    assert "personalization" not in state["answered"]


def test_3_A_ROW_WITH_A_VALUE_DOES_NOT_CLAIM_THE_LICENSEE_CONFIGURED_NOTHING(db, user):
    """Defect 3. The Cemetery row read "Not configured for this licensee" above a
    time, and after the first fix the Personalization row did the same above a
    captured symbol."""
    from app.services.capture import session_service

    cid, uid = user
    row = _session(db, cid, uid)
    session_service.set_text(
        db, row.id, company_id=cid, user_id=uid,
        text="Bronze Triune Burial Vault, nameplate and vinyl, cross, years only, "
             "eta 11:30",
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)

    offenders = [
        (r["row_id"], r["value"])
        for r in state["surface"]["rows"]
        if r["state"] == "not_configured" and r["value"] is not None
    ]
    assert offenders == [], (
        f"these rows report the licensee's setup as missing while displaying a "
        f"captured value: {offenders}"
    )
    # ⚠️ AND THE TWO SPECIFIC ROWS ARE NAMED, because "no offenders" is also true of
    # a response where nothing was captured at all.
    cem = next(r for r in state["surface"]["rows"] if r["row_id"] == "cemetery")
    assert cem["value"] is not None, "the ETA did not render; nothing was measured"
    pers = next(r for r in state["surface"]["rows"] if r["row_id"] == "personalization")
    assert pers["value"] is not None, "the symbol did not render; nothing was measured"


def test_4_A_CEMETERY_NAME_DOES_NOT_BECOME_THE_DECEASED(db, user):
    """Defect 4. The apostrophe made the lookup miss, and the unmatched name was then
    taken as the decedent and OVERWROTE the real one."""
    from app.services.capture import session_service

    cid, uid = user
    row = _session(db, cid, uid)
    session_service.set_text(
        db, row.id, company_id=cid, user_id=uid,
        text="Mary Smith, to St Marys in Skaneateles",
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)

    assert state["values"].get("deceased_name") == "Mary Smith", state["values"]
    assert state["values"].get("cemetery") == "St. Mary's Cemetery", state["values"]


def test_5_A_SYMBOL_IN_ITS_OWN_SEGMENT_IS_CAPTURED_AND_NOT_CALLED_UNREADABLE(db, user):
    """Defect 5. "cross" was captured as nothing AND listed as not understood."""
    from app.services.capture import session_service

    cid, uid = user
    row = _session(db, cid, uid)
    session_service.set_text(
        db, row.id, company_id=cid, user_id=uid,
        text="Bronze Triune Burial Vault, nameplate and vinyl, cross",
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)

    assert state["values"].get("lifes_reflections_symbol") == "cross", state["values"]
    assert not any("cross" in u.lower() for u in state["unrecognized"]), (
        f"the symbol was captured AND reported unplaced: {state['unrecognized']}"
    )


def test_the_whole_sentence_James_walks(db, user):
    """The sentence from the walk doc, end to end through the session.

    ⚠️ ONE TEST OVER THE WHOLE SENTENCE, because the five above are each a single
    defect and a director types all of it at once. Three things this asserts that no
    single-defect test does: that the correction wins over the earlier equipment
    answer, that the ambiguous cemetery raises EXACTLY ONE question, and that nothing
    is left unplaced.
    """
    from app.services.capture import session_service

    cid, uid = user
    row = _session(db, cid, uid)
    session_service.set_text(
        db, row.id, company_id=cid, user_id=uid,
        text=(
            "order for Hopkins, Mary Smith, 1948 to 2026, 34 inch Continental, "
            "St Mary's in Auburn, service at the church Thursday 10am, eta 11:30, "
            "full setup actually tent only"
        ),
    )
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)

    assert state["values"].get("deceased_name") == "Mary Smith", state["values"]
    assert state["values"].get("funeral_home") == "Hopkins Funeral Home", state["values"]
    # ⚠️ THE CORRECTION WINS. This is LAST_WINS at the session seam on the phrasing
    # James actually types — "full setup actually tent only", no comma.
    assert state["values"].get("cemetery_equipment") == "tent_only", state["values"]
    # exactly one question, and it is the cemetery
    assert [p["field_id"] for p in state["pending_picks"]] == ["cemetery"], (
        state["pending_picks"]
    )
    assert state["unrecognized"] == [], state["unrecognized"]
