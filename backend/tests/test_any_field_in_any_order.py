"""Whatever you type, about anything, in any order, lands where it belongs.

James, 2026-11-02: *"Opas asking a question is a suggestion, not a form. Whatever you
type, about anything, in any order, should land where it belongs."* And, as two ruled
items from the same walk:

    4. *"The open question must never narrow what a line can fill. While Opas asks X,
       text about Y fills Y; only text that fits nothing else answers X. Test with the
       question set to each field in turn and equipment/chairs/date/cemetery text typed
       — all must land on their own fields."*
    2. *"A word is placed OR held, never both; add that as an invariant test."*

### Item 4 was already true, and this file is why that is now checkable

⚠️ MEASURED BEFORE ANYTHING WAS CHANGED: `extract_text` takes `(text, resolutions,
prefill)` and has NO question argument, so the open question cannot narrow anything —
typing goes through `PUT /sessions/{id}/text`, and `POST /sessions/{id}/answer` is the
separate pill path that names its field explicitly. The walk made it LOOK otherwise
because Opas was asking "Deceased" when `" chairs"` went to the vault, and the real
causes were a missing form filter and a missing chairs phrasing.

⚠️ SO THIS IS A REGRESSION TEST OVER A PROPERTY, NOT A FIX, and it is worth having for
exactly that reason: the property holds by the SHAPE of the call today, and a future
"use the open question as a hint" change would be an easy and plausible thing to add.

### The placed-or-held invariant

⚠️ THE CLASS IS REAL AND WAS GUARDED IN ONE PLACE. `typed_extraction` already carries a
hand-written fix for it — *"THE WORD MUST STOP BEING HELD, OR THE PANE SHOWS IT IN BOTH
PLACES — filled on the Deceased row AND in 'not placed yet'"* — for `deceased_name`
and nothing else. One case fixed, no general guard, which is the shape that let the
Vault Placer ruling reach one door out of six.

⚠️ AND THE 2026-11-02 SCREENSHOT WAS NOT AN INSTANCE OF IT, which is recorded here so
the test is not mistaken for a repair. Read from production, that session's stored
`unrecognized` was EMPTY and its single span was `('captured', ('vault',), 'chairs')` —
so the word was tinted as understood in the bar, which sits at the bottom of the
overlay, rather than being listed as unplaced. The invariant is added because it is
right, not because it was breached.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

import pytest
from sqlalchemy import text as sql

from app.database import SessionLocal
from app.services.capture import session_service
from app.services.capture.typed_extraction import extract_text


def _local_only() -> None:
    host = (urlparse(os.environ.get("DATABASE_URL", "")).hostname or "").lower()
    assert host in ("localhost", "127.0.0.1", "::1", ""), host


@pytest.fixture(scope="module")
def db():
    _local_only()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(scope="module")
def world(db):
    tid = db.execute(sql("SELECT id FROM companies WHERE slug = 'testco'")).scalar()
    if not tid:
        pytest.skip("no testco tenant")
    uid = db.execute(
        sql("SELECT id FROM users WHERE company_id = :t LIMIT 1"), {"t": tid}
    ).scalar()
    if not uid:
        pytest.skip("no user on testco")
    return tid, uid


# ── item 4: the open question never narrows what a line can fill ────────────

#: Prefixes that leave DIFFERENT questions open, each with the question it produces.
#:
#: ⚠️ THE QUESTION EACH ONE OPENS IS ASSERTED, NOT ASSUMED. A prefix list that silently
#: produced the same question four times would make the matrix below four copies of one
#: case — the "test passes because the setup collapsed" shape, which is how a 61% score
#: once came from a test set rather than from the world.
PREFIXES: tuple[tuple[str, str], ...] = (
    ("", "funeral home"),
    ("johnson ", "funeral home"),
    ("johnson monticello ", "deceased"),
    ("johnson monticello decedent mary smith ", "service"),
)

#: Text about four DIFFERENT fields, none of which is the field being asked about in
#: any row above. Each must land on its own field regardless.
TAILS: tuple[tuple[str, str, object], ...] = (
    ("12 chairs", "chairs_total", "12"),
    ("full equipment", "cemetery_equipment", "full_equipment"),
    ("oakwood cemetery", "cemetery", "Oakwood Cemetery"),
    # ⚠️ NO COMMA IN THIS ONE, DELIBERATELY, AND THE REASON IS A SEPARATE DEFECT
    # PINNED BELOW. `"section A, lot 2"` — the way a director actually writes it —
    # extracts as `"Section A"` and loses the lot. That is nothing to do with which
    # question is open (it fails identically in all four rows, which is itself evidence
    # for item 4) and it is pre-existing: measured at `426ab5b6`, same result. Using
    # the comma here would make this matrix fail for a reason it is not about.
    ("section A lot 2", "grave_location", "Section A, Lot 2"),
)


def _ask(db, tenant, uid, text_value):
    row = session_service.start(db, company_id=tenant, user_id=uid)
    session_service.set_text(
        db, row.id, company_id=tenant, user_id=uid, text=text_value or " "
    )
    return session_service.read_state(db, row.id, company_id=tenant, user_id=uid)


def test_the_prefixes_really_do_open_different_questions(world, db):
    """⚠️ THE CONTROL ON THE MATRIX. Without it the four rows below could all be the
    same state wearing four different strings."""
    tenant, uid = world
    sp = db.begin_nested()
    try:
        asked = []
        for prefix, expected in PREFIXES:
            q = (_ask(db, tenant, uid, prefix)["next_question"] or "").lower()
            asked.append(q)
            assert expected in q, (prefix, q)
        assert len(set(asked)) >= 3, asked
    finally:
        sp.rollback()


def test_text_about_Y_fills_Y_whatever_question_is_open(world, db):
    """⚠️ THE MATRIX JAMES ASKED FOR: four open questions × four kinds of text. Every
    cell must land on its own field, and the cell's value is asserted rather than just
    its presence — a field set to the wrong value is the defect, not an absent one."""
    tenant, uid = world
    sp = db.begin_nested()
    try:
        failures: list[tuple] = []
        for prefix, question in PREFIXES:
            for tail, field_id, want in TAILS:
                st = _ask(db, tenant, uid, prefix + tail)
                got = st["values"].get(field_id)
                if got != want:
                    failures.append((question, tail, field_id, want, got))
        assert failures == [], failures
    finally:
        sp.rollback()


def test_the_open_question_is_not_even_an_INPUT_to_extraction():
    """⚠️ THE STRUCTURAL HALF, AND IT IS THE STRONGER CLAIM. The matrix above shows the
    question does not narrow anything TODAY; this shows it CANNOT, because extraction is
    never told what is being asked. A future change that threaded the open question in
    as a hint would turn this red before anybody had to notice a cell in the matrix.
    """
    import inspect

    params = set(inspect.signature(extract_text).parameters)
    for forbidden in ("asking", "question", "next_question", "field_id", "guided_field"):
        assert forbidden not in params, (forbidden, sorted(params))


# ── item 2: a word is PLACED or HELD, never both ─────────────────────────────

#: ⚠️ ONE SENTENCE PER FIELD FAMILY, AND THE LIST IS THE TEST'S REACH. A phrasing not
#: here is not covered; these are chosen to put a word of every kind through the
#: extractor at once, including two that were unreachable before 2026-11-02.
PHRASES: tuple[str, ...] = (
    "order for johnson monticello decedent mary smith thursday 10am",
    "order for johnson st marys cemetery section A lot 2",
    "order for johnson full equipment, 12 chairs",
    "order for johnson chairs",
    "order for johnson extra chairs",
    "order for johnson continental 34 nameplate only",
    "order for johnson 1948 to 2026",
    "order for johnson blargle",
    " chairs",
)


def test_no_word_is_both_PLACED_and_HELD(world, db):
    """⚠️ THE INVARIANT. `unrecognized` is the held list and the spans say what was
    placed; a word in both would be shown as understood in the bar AND listed as not
    placed in the pane. `typed_extraction` fixes exactly this for `deceased_name` by
    hand; this asserts it for every phrasing above.

    ⚠️ COMPARED ON THE WORD, NOT THE SPAN, BECAUSE THE TWO LISTS ARE BUILT DIFFERENTLY.
    The held list is noise-stripped text and a span is a pair of offsets into the raw
    sentence, so the only thing they can be compared on is the words themselves — which
    is the same comparison the `deceased_name` fix makes (`u.casefold() != _nf`).
    """
    tenant, _uid = world
    overlaps: list[tuple] = []
    for phrase in PHRASES:
        ex = extract_text(db, tenant_id=tenant, text=phrase)
        placed_words = {
            w.casefold().strip(".,;:")
            for sp in ex.spans
            if sp.state == "captured"
            for w in phrase[sp.start:sp.end].split()
        }
        for held in ex.unrecognized:
            for w in str(held).split():
                if w.casefold().strip(".,;:") in placed_words:
                    overlaps.append((phrase, held, w))
    assert overlaps == [], overlaps


def test_a_HELD_word_is_really_reachable(world, db):
    """⚠️ THE CONTROL, AND THE INVARIANT ABOVE IS WORTHLESS WITHOUT IT. "No word is in
    both lists" is trivially true when the held list is always empty — which is the
    state of eight of the nine phrases above, and would be the state of all nine if the
    leftover rule ever stopped reporting anything."""
    tenant, _uid = world
    ex = extract_text(db, tenant_id=tenant, text="order for johnson blargle")
    assert "blargle" in [str(u).casefold() for u in ex.unrecognized], ex.unrecognized


def test_the_WALK_PHRASE_is_placed_and_not_held(world, db):
    """⚠️ JAMES'S OWN TEXT, VERBATIM FROM PRODUCTION — `" chairs"`, leading space and
    all, read out of capture session `5cce14dc` on 2026-11-02.

    ⚠️ IT IS PINNED AS A SENTENCE RATHER THAN AS A UNIT CASE because that is what was
    typed, and because three separate defects met in it: the vault slot had no form
    filter, the chairs vocabulary had no bare "chairs", and the ghost was completing
    toward a price-list name. The first two are visible here.
    """
    tenant, _uid = world
    ex = extract_text(db, tenant_id=tenant, text=" chairs")
    values = dict(ex.values)
    # ⚠️ NOT THE VAULT. This is the row James watched fill with "Graveside Chairs".
    assert values.get("vault") is None, values
    # ⚠️ AND IT REACHED CHAIRS, which is the other half — before ruling B the word
    # matched no chairs pattern at all, which is why it was free for the vault to take.
    from app.services.capture.schema import CHAIRS_WANTED_FLAG

    assert values.get(CHAIRS_WANTED_FLAG) == "1", values
    # placed, so not held
    assert list(ex.unrecognized) == [], ex.unrecognized
    assert [(sp.state, sp.field_ids) for sp in ex.spans] == [
        ("captured", ("chairs_total",))
    ], [(sp.state, sp.field_ids) for sp in ex.spans]


# ── ruling 3: anything said about the grave is never dropped ────────────────


@pytest.mark.parametrize("typed,expected", [
    # ⚠️ THE COMMA FORM FIRST, BECAUSE IT IS THE ONE THAT WAS BROKEN and it is how the
    # office actually writes a grave.
    ("section A, lot 2", "Section A, Lot 2"),
    ("section A lot 2", "Section A, Lot 2"),
    # ⚠️ AND THE TWO FORMS MUST AGREE, which is asserted as its own test below rather
    # than left to a reader comparing two rows of this table.
    ("section A, lot 2, space 3", "Section A, Lot 2, Space 3"),
    ("section A, row 7", "Section A, Row 7"),
    # ⚠️ `lot` ALONE, which matched NOTHING before ruling 3. The old pattern opened on
    # `section` and treated the lot as an optional tail, so "lot 2" was reported as text
    # the engine could not place — a thing the director said about the grave, dropped.
    # James: *"Lot is never required (standing ruling), but anything said about the
    # grave is never dropped."*
    ("lot 2", "Lot 2"),
    ("row 7", "Row 7"),
    ("space 3", "Space 3"),
    # ⚠️ CANONICAL ORDER, NOT TYPED ORDER. Two spellings of one place across two orders
    # is what makes a cemetery map unsearchable.
    ("lot 2, section A", "Section A, Lot 2"),
])
def test_everything_said_about_the_grave_is_kept(world, db, typed, expected):
    """⚠️ RULING 3 (James, 2026-11-02): *"'section A, lot 2' must keep the lot. Grave
    location takes section and lot (and 'row', 'grave', 'space') together across a
    comma; 'lot' joins the grave vocabulary."*

    ⚠️ THIS FILE PINNED THE DEFECT AS A KNOWN GAP UNTIL TODAY, in a test that asserted
    the wrong behaviour on purpose and said the day its assertion failed was the day the
    gap closed. It failed on ruling 3 and is replaced by this.
    """
    tenant, _uid = world
    ex = extract_text(db, tenant_id=tenant, text=f"order for johnson {typed}")
    assert dict(ex.values).get("grave_location") == expected, dict(ex.values)
    # ⚠️ AND NOTHING IS HELD. The old failure left a bare "2" in the unplaced list and
    # the word "lot" in neither list; a fix that kept the value but still reported a
    # stray token would be half a fix.
    assert list(ex.unrecognized) == [], ex.unrecognized


def test_the_comma_and_the_space_forms_AGREE(world, db):
    """⚠️ ASSERTED AS EQUALITY, NOT AS TWO LITERALS. Two expected strings could both be
    edited to agree on a wrong answer; this cannot be satisfied unless the comma
    genuinely stops mattering."""
    tenant, _uid = world
    with_comma = extract_text(
        db, tenant_id=tenant, text="order for johnson section A, lot 2"
    )
    without = extract_text(
        db, tenant_id=tenant, text="order for johnson section A lot 2"
    )
    assert (
        dict(with_comma.values).get("grave_location")
        == dict(without.values).get("grave_location")
        == "Section A, Lot 2"
    )


def test_the_grave_vocabulary_STILL_DOES_NOT_EAT_GRAVESIDE(world, db):
    r"""⚠️ THE 2026-10-13 DEFECT, AND RULING 3 RE-OPENED IT FOR ONE RUN. The old pattern
    could only open on `section`, so "we'll do it grave side" matched nothing. Letting
    `grave` open a location made `\bgrave\b\s*([A-Za-z0-9]+)` match "grave side" —
    `grave_location = "Space side"`, with the word that makes the service GRAVESIDE
    eaten. That is the 10-13 defect arrived at from the opposite direction, and
    `test_no_span_feeds_two_fields.py` is what caught it.

    ⚠️ THE REPAIR IS A VALUE SHAPE, NOT A STOPLIST: a grave component's value must carry
    a digit or be one or two letters, because a plot identifier does and an English word
    does not. The cost is named where it is declared — a section called "North" is not
    typeable — and that is the safe direction of the trade.
    """
    tenant, _uid = world
    ex = extract_text(db, tenant_id=tenant, text="we'll do it grave side")
    values = dict(ex.values)
    assert values.get("service_location") == "graveside", values
    assert values.get("grave_location") is None, values
    # and the same sentence that the 10-13 ruling was about keeps BOTH
    both = extract_text(
        db, tenant_id=tenant, text="order for johnson section 4 graveside friday 11am"
    )
    bv = dict(both.values)
    assert bv.get("grave_location") == "Section 4", bv
    assert bv.get("service_location") == "graveside", bv
