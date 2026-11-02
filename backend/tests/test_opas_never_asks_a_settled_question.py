"""Rulings a, b and c of 2026-11-02 — check 3 of James's walk, three separate causes.

He typed `"riverside 2 chairs"` and the screenshot showed three things wrong at once:

    a. Funeral Home captured with a green check, and Opas still asking *"Which funeral
       home?"* with Hopkins/Riverside pills.
    b. the equipment question never asked, though a chair count with no bundle cannot
       be priced at all (ruling D').
    c. the Equipment row reading *"Not mentioned yet"* with *"2 chairs"* underneath it.
       James: *"It can't be both."*

### Which cause was which, measured before anything was changed

⚠️ **(a) WAS NOT A STALE RESPONSE AND NOT A PICKER THAT FAILS TO SKIP SETTLED FIELDS.**
Both of James's candidates were wrong, and the real mechanism is a third thing:

    read_state(..., asking=None)              -> question_field_id = 'deceased_name'
    read_state(..., asking="funeral_home")    -> question_field_id = 'funeral_home'

The server was right either way — it was answering the question the CLIENT asked. The
pane passed `askedFieldId` into `setCaptureText`'s `?asking=` on every text PUT, and
`askedField` falls back to the server's own `guidedFieldId`, so each keystroke echoed
the PREVIOUS question back as a request to ask it again. The server honours `asking`
for an ANSWERED field deliberately — clicking a finished row to change it is ruled
behaviour — so the question pinned itself to the first field ever asked.

⚠️ **AND THE FIX IS CLIENT-SIDE FOR THAT REASON.** Refusing answered fields in the
server's `asking` validation would have broken click-to-change. The pane now sends
`focusedFieldId` — a real click and nothing else — which is what the service's own
comment always said the parameter was for.

⚠️ **(c) WAS NOT A SERVER STATE PROBLEM EITHER.** The row came back `state: "partial"`
with `secondary_value: "2 chairs"`, which is correct and has been since 2026-10-30.
`valueText` in `CapturePane` took only the state and the PRIMARY value, and `partial`
matched none of its branches, so it fell through to the last line. Defect 3c for the
third time, at the last layer that can still get it wrong.

So: **three causes, three layers — the client's `asking` echo, the server's question
ordering, and the client's row text.** None of them is the same bug as another.
"""

from __future__ import annotations

import os
import uuid
from urllib.parse import urlparse

import pytest
from sqlalchemy import text as sql

from app.database import SessionLocal
from app.services.capture import SALES_ORDER, session_service, template_for
from app.services.capture.schema import (
    CHAIRS_EXTRA_PENDING_FLAG,
    CHAIRS_WANTED_FLAG,
    EQUIPMENT_NONE_ANSWER,
    PLATFORM_DEFAULT_FIELDS,
    guided_field,
)
from app.services.capture.typed_extraction import evaluate_typed, extract_text


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


def _state(db, tid, uid, text_value, **kw):
    row = session_service.start(db, company_id=tid, user_id=uid)
    session_service.set_text(
        db, row.id, company_id=tid, user_id=uid, text=text_value or " "
    )
    return session_service.read_state(
        db, row.id, company_id=tid, user_id=uid, **kw
    ), row.id


# ── ruling a: never ask about a field that is settled ───────────────────────

#: One phrase that settles each field by TYPING, which is the ruling's own test
#: condition: *"for every field, settle it by typing and assert the next question isn't
#: it."*
#:
#: ⚠️ EVERY TEMPLATE FIELD IS ACCOUNTED FOR BELOW — the ones here and the ones in
#: `NOT_SETTLEABLE_BY_TYPING`, which is asserted exhaustive. A field added to the
#: template and to neither list fails `test_every_field_is_covered_by_this_file`, so
#: this sweep cannot silently stop covering one.
SETTLED_BY: tuple[tuple[str, str], ...] = (
    # ⚠️ THREE WORDS, NOT THE BARE "johnson", AND THE REASON IS AN OBSERVATION WORTH
    # RECORDING. A text that is EXACTLY one word captures no party at all — measured:
    # `"johnson"` -> `values={}`, `unrecognized=['johnson']`, while `"johnson "`,
    # `"order for johnson"`, `"johnson 2 chairs"` and `"johnson funeral home"` all
    # resolve it. A lone word is genuinely ambiguous between a party, a surname and a
    # product, so holding it is defensible — and it is exactly why James's check-3
    # screenshot opened on "Which funeral home?" with pills, which was CORRECT for text
    # that had captured nothing. The bug was that it kept asking after "2 chairs"
    # arrived. Not changed here; reported.
    ("funeral_home", "johnson funeral home"),
    ("vault", "monticello"),
    ("deceased_name", "decedent mary smith"),
    ("cemetery", "oakwood cemetery"),
    ("cemetery_city", "oakwood cemetery"),
    ("service_date", "service on march 2 2027"),
    ("service_time", "service at 10am"),
    ("service_location", "service at the church"),
    ("grave_location", "section A lot 2"),
    ("cemetery_equipment", "full equipment"),
    ("chairs_total", "12 chairs"),
    ("chairs_extra", "extra chairs 4"),
    ("date_of_birth", "1948 to 2026"),
    ("date_of_death", "1948 to 2026"),
    ("personalization", "nameplate only"),
    ("burial_date", "burial on march 3 2027"),
)

#: ⚠️ FIELDS NO TYPED PHRASE CAN SETTLE, NAMED RATHER THAN OMITTED. Each has a reason
#: that is already recorded elsewhere in the suite:
#:
#:   service_location_other    `not_typeable` on the FieldDefinition — the extractor's
#:                             vocabulary cannot produce `service_location == "other"`,
#:                             which is its precondition.
#:   eta                       conditional on a non-graveside service AND typeable, but
#:                             "eta 11:30" needs a service location in the same breath;
#:                             covered by `test_any_field_in_any_order.py`.
#:   nameplate_date_format     applies only under personalization and is asked, never
#:                             typed as a standalone phrase.
#:   legacy_series             ditto, behind the Legacy answer.
#:   legacy_print_name         ditto.
#:   lifes_reflections_symbol  ditto.
NOT_SETTLEABLE_BY_TYPING: frozenset[str] = frozenset({
    "service_location_other",
    "eta",
    "nameplate_date_format",
    "legacy_series",
    "legacy_print_name",
    "lifes_reflections_symbol",
})


def test_every_field_is_covered_by_this_file():
    """⚠️ THE EXHAUSTIVENESS RATCHET, AND IT IS WHAT MAKES THE SWEEP A SWEEP. James's
    ruling says "for EVERY field"; a hand-written list silently stops being every field
    on the next schema change. This fails by name the moment one is added."""
    declared = {f.field_id for f in PLATFORM_DEFAULT_FIELDS}
    covered = {f for f, _p in SETTLED_BY} | NOT_SETTLEABLE_BY_TYPING
    assert declared - covered == set(), sorted(declared - covered)
    # ⚠️ AND NOTHING IS LISTED THAT THE TEMPLATE NO LONGER HAS, which is the direction
    # that would make a row of this sweep silently test nothing.
    assert covered - declared == set(), sorted(covered - declared)


@pytest.mark.parametrize("field_id,phrase", SETTLED_BY)
def test_opas_never_asks_about_a_field_it_has_just_been_given(
    world, db, field_id, phrase
):
    """⚠️ RULING a: *"Opas never asks about a field that is settled."*

    ⚠️ THE PREMISE IS ASSERTED FIRST, because the interesting failure is the phrase
    not landing at all — a question about an unsettled field is correct behaviour, and
    without this line the test would pass for that reason.
    """
    tid, uid = world
    sp = db.begin_nested()
    try:
        st, _sid = _state(db, tid, uid, phrase)
        assert st["values"].get(field_id) is not None, (
            f"{phrase!r} did not settle {field_id} — this row tests nothing",
            st["values"],
        )
        assert st["question_field_id"] != field_id, (
            field_id, st["question_field_id"], st.get("question"),
        )
        # ⚠️ AND THE SENTENCE TOO, not only the field id. They are composed from the
        # same `field_id` today; asserting both means a future divergence fails here
        # rather than putting a settled question back on screen.
        from app.services.capture.schema import question_for

        assert st.get("question") != question_for(field_id), st.get("question")
    finally:
        sp.rollback()


def test_the_SERVER_honours_asking_for_a_settled_field_ON_PURPOSE(world, db):
    """⚠️ THE OTHER HALF OF RULING a, AND IT IS WHY THE FIX IS CLIENT-SIDE.

    `read_state`'s `asking` parameter validates against
    `missing | unanswered_optional | answered` — ANSWERED included — because clicking a
    finished row to change it is ruled behaviour. So the server will ask about a settled
    field when asked to, and that is correct.

    ⚠️ THIS TEST PINS THE BEHAVIOUR THE BUG RODE IN ON, which is the point. The defect
    was the pane echoing the last question back as `?asking=` on every keystroke; the
    repair is that the pane now sends only a real click. If someone "fixes" this end
    instead, click-to-change breaks and this test says so.
    """
    tid, uid = world
    sp = db.begin_nested()
    try:
        st, _sid = _state(db, tid, uid, "johnson 2 chairs")
        assert st["values"].get("funeral_home") is not None, st["values"]
        assert "funeral_home" in st["answered"], st["answered"]
        # unasked, the question has moved on
        assert st["question_field_id"] != "funeral_home", st["question_field_id"]

        row2 = session_service.start(db, company_id=tid, user_id=uid)
        session_service.set_text(db, row2.id, company_id=tid, user_id=uid,
                                 text="johnson 2 chairs")
        asked = session_service.read_state(
            db, row2.id, company_id=tid, user_id=uid, asking="funeral_home"
        )
        assert asked["question_field_id"] == "funeral_home", asked["question_field_id"]
    finally:
        sp.rollback()


# ── ruling b: chairs with no bundle ask the equipment question next ─────────

@pytest.mark.parametrize("phrase", [
    "johnson 2 chairs",
    "johnson 12 chairs",
    "johnson extra chairs 4",
    "johnson chairs",
    "johnson extra chairs",
])
def test_a_chair_count_with_NO_BUNDLE_asks_the_equipment_question_next(
    world, db, phrase
):
    """⚠️ RULING b: *"When a chair count is present and no bundle is set, the equipment
    question is asked next (ahead of other open fields) with the count carried, per
    D'."*

    ⚠️ ALL FOUR WAYS CHAIRS CAN BE PRESENT, because reading only the two COUNT fields
    would miss `"chairs"` and `"extra chairs"` — the numberless mentions, which are
    exactly the phrasings that cannot be priced without the bundle.

    ⚠️ AND IT JUMPS AHEAD OF REQUIRED FIELDS, WHICH BREAKS THE "REQUIRED FIRST" RULE
    DELIBERATELY. `guided_field`'s own docstring says a director who has not named the
    cemetery should be asked for the cemetery before being asked about chairs — true
    when chairs are merely unmentioned. Once a count is typed the director has raised
    the subject, and ruling D' means the order cannot be priced at all until the bundle
    is known.
    """
    tid, uid = world
    sp = db.begin_nested()
    try:
        st, _sid = _state(db, tid, uid, phrase)
        assert st["question_field_id"] == "cemetery_equipment", (
            st["question_field_id"], st.get("question"), st["values"],
        )
        # ⚠️ THE COUNT IS CARRIED, not cleared by the question being asked.
        said = any(
            st["values"].get(k)
            for k in ("chairs_total", "chairs_extra",
                      CHAIRS_WANTED_FLAG, CHAIRS_EXTRA_PENDING_FLAG)
        )
        assert said, st["values"]
    finally:
        sp.rollback()


@pytest.mark.parametrize("phrase,why", [
    ("johnson full equipment 2 chairs", "the bundle is set"),
    ("johnson no equipment 2 chairs", "'none' is an ANSWER, not an open question"),
    ("johnson", "nothing was said about chairs"),
])
def test_the_equipment_question_does_NOT_jump_the_queue_otherwise(
    world, db, phrase, why
):
    """⚠️ THE CONTROL, AND WITHOUT IT RULING b WOULD BE SATISFIED BY A RULE THAT ASKS
    ABOUT EQUIPMENT ALWAYS. The third row is the one that matters most: on an order
    where chairs were never mentioned, the required fields come first as they always
    did."""
    tid, uid = world
    sp = db.begin_nested()
    try:
        st, _sid = _state(db, tid, uid, phrase)
        assert st["question_field_id"] != "cemetery_equipment", (why, st.get("question"))
    finally:
        sp.rollback()


def test_the_jump_reads_the_FLAGS_which_the_partition_cannot_see(world, db):
    """⚠️ THE MECHANISM, PINNED, BECAUSE MY FIRST VERSION WAS DEAD ON ARRIVAL. It read
    `getattr(state, "answers", None)` — and `CaptureState` has no `answers` field, so
    the rule compiled, ran, and never once fired. `guided_field` takes the answers
    explicitly now, and an explicit argument cannot be silently absent.

    ⚠️ THE FLAGS ARE THE REASON THE ANSWERS ARE NEEDED AT ALL. `chairs_wanted` and
    `chairs_extra_pending` are keys the TEMPLATE does not declare, so none of
    `CaptureState`'s five sets contains them — that invisibility is the whole point of
    their being flags, and it is also why a state-only rule could not see them.
    """
    tid, uid = world
    sp = db.begin_nested()
    try:
        ex = extract_text(db, tenant_id=tid, text="johnson chairs")
        answers = dict(ex.values)
        assert answers.get(CHAIRS_WANTED_FLAG) == "1", answers
        _r, state, _c = evaluate_typed(db, tenant_id=tid, answers=answers)
        for bucket in (state.missing, state.answered, state.unanswered_optional,
                       state.not_applicable, state.indeterminate):
            assert CHAIRS_WANTED_FLAG not in bucket, bucket

        # with the answers, the rule fires; without them it cannot
        assert guided_field(state, answers) == "cemetery_equipment"
        assert guided_field(state) != "cemetery_equipment", (
            "the rule fired without being given the answers — it is reading something "
            "it should not be able to see"
        )
    finally:
        sp.rollback()


# ── ruling c: a row holding anything said is never "Not mentioned" ──────────

def test_the_equipment_row_says_the_count_AND_asks_for_the_bundle(world, db):
    """⚠️ RULING c: *"Equipment row with chairs but no bundle reads '2 chairs · which
    equipment?' in the partial style — never 'Not mentioned yet' alongside a value."*"""
    tid, uid = world
    sp = db.begin_nested()
    try:
        st, _sid = _state(db, tid, uid, "johnson 2 chairs")
        eq = next(r for r in st["surface"]["rows"]
                  if r["row_id"] == "cemetery_equipment")
        assert eq["state"] == "partial", eq
        assert eq["secondary_value"] == "2 chairs · which equipment?", eq
        # ⚠️ AND THE PRIMARY IS EMPTY, which is the state the frontend has to render
        # without saying "Not mentioned yet". `capture-pane.test.tsx` holds that half —
        # the server's job is to make sure the words exist.
        assert eq["value"] is None, eq
    finally:
        sp.rollback()


def test_a_bundle_whose_included_count_is_NULL_is_not_asked_for_again(world, db):
    """⚠️ THE DISTINCTION RULING c TURNS ON, AND CONFLATING IT WOULD BE WRONG ON EVERY
    NEW TENANT. `included_chairs_for` returns None for four reasons and only one is "no
    bundle"; the others are the `none` sentinel, an unlisted value, and a bundle whose
    `included_chairs` column is NULL. That last is the onboarding-checklist state —
    the bundle IS chosen, so the row must not go on asking for one.

    ⚠️ TESTCO IS EXACTLY THAT TENANT, which is why this test lives here rather than in
    the seeded-bundle file: its products carry no `included_chairs`, so a bundle set
    here always produces `included is None` with `bundle_set` true.
    """
    tid, uid = world
    sp = db.begin_nested()
    try:
        st, _sid = _state(db, tid, uid, "johnson full equipment 2 chairs")
        eq = next(r for r in st["surface"]["rows"]
                  if r["row_id"] == "cemetery_equipment")
        assert eq["value"] == "Full Equipment", eq
        assert eq["secondary_value"] == "2 chairs", eq
        assert "which equipment" not in (eq["secondary_value"] or ""), eq
    finally:
        sp.rollback()


def test_NO_ROW_EVER_HAS_A_VALUE_AND_A_NOT_MENTIONED_STATE(world, db):
    """⚠️ THE GENERAL RULE, SWEPT OVER REAL ORDERS: *"a row holding anything said is
    never 'Not mentioned'."* Asserted over the SERVER's states — the frontend's half of
    the same rule is `valueText`, tested in `capture-pane.test.tsx`.

    ⚠️ AND THE SWEEP INCLUDES THE SECONDARY, which is the half that was broken. A row
    with no primary and a rendered secondary is a row holding something said.
    """
    tid, uid = world
    sp = db.begin_nested()
    try:
        offenders = []
        for phrase in (
            "johnson 2 chairs",
            "johnson chairs",
            "johnson extra chairs",
            "johnson full equipment 12 chairs",
            "johnson monticello decedent mary smith oakwood cemetery",
            "johnson 1948 to 2026",
            "johnson section A lot 2",
        ):
            st, _sid = _state(db, tid, uid, phrase)
            for r in st["surface"]["rows"]:
                holds = r["value"] is not None or r["secondary_value"] is not None
                if holds and r["state"] == "not_mentioned":
                    offenders.append((phrase, r["row_id"], r["value"],
                                      r["secondary_value"]))
        assert offenders == [], offenders
    finally:
        sp.rollback()
