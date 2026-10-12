"""The whole typed text is the source, re-read on every pause. Last mention wins.

⚠️ THE MODEL CHANGE. The line-append model treated each Enter as a separate event and
`once()` meant "this field is not yet answered", so the FIRST mention won and a later
one was reported as a re-statement. Under whole-text re-extraction the director can see
every word on screen, "full setup ... actually tent only" is ONE statement containing a
correction, and the later mention is simply the answer.

⚠️ THE POLICY IS EXPLICIT PER SOURCE, BY RULING, because the two sources genuinely
disagree — see `MentionPolicy`. `extract_line` keeps FIRST_WINS and is unchanged;
`extract_text` declares LAST_WINS.

⚠️ AND E6 IS SAFE BY CONSTRUCTION RATHER THAN BY CARE, which this file asserts by
ENUMERATION rather than by reading: `typed_extraction` is imported by exactly one
module in `app/`. The call pipeline cannot reach a line extractor, so no policy here
can change its behaviour.

⚠️ `extract_text` COMPOSES `extract_line` rather than replacing it, so the span rule,
every vocabulary, the party resolvers and claim-before-write all still apply. That is
the reason this file is short: it tests the composition, not the passes.
"""
from __future__ import annotations

import pathlib
import time as _time

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture.typed_extraction import (
    MentionPolicy,
    extract_text,
    segments,
)

#: James's own sample order from the dispatch, verbatim.
SAMPLE = (
    "order for Hopkins, Mary Smith, 1948 to 2026, 34 inch Continental, "
    "St Mary's in Auburn, service at the church Thursday 10am, eta 11:30, "
    "full setup actually tent only"
)


def _refuse_a_non_local_database() -> None:
    from urllib.parse import urlparse

    from app.config import settings

    host = (urlparse(settings.DATABASE_URL).hostname or "").lower()
    assert host in ("localhost", "127.0.0.1", "::1", "")


@pytest.fixture(scope="module")
def db():
    _refuse_a_non_local_database()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(scope="module")
def tenant(db) -> str:
    tid = db.execute(text("SELECT id FROM companies WHERE slug = 'testco'")).scalar()
    assert tid, "testco is not seeded — run scripts/seed_dev.sh"
    return tid


def _vals(db, tenant, t, **kw):
    return extract_text(db, tenant_id=tenant, text=t, **kw).values


# ── E6, asserted by enumeration ─────────────────────────────────────────

def test_only_the_typed_path_imports_the_extractor():
    """⚠️ THE E6 GUARANTEE, MEASURED NOT READ. If a second module ever imports this,
    the mention policy stops being isolated to the typed path and this test says so
    before anyone discovers it from a changed call-overlay result."""
    app_dir = pathlib.Path(__file__).resolve().parent.parent / "app"
    importers = sorted(
        str(p.relative_to(app_dir))
        for p in app_dir.rglob("*.py")
        if "typed_extraction" in p.read_text(encoding="utf-8")
        and p.name != "typed_extraction.py"
    )
    assert importers == ["services/capture/session_service.py"], importers


def test_the_two_policies_are_named_and_distinct():
    assert MentionPolicy.FIRST_WINS != MentionPolicy.LAST_WINS
    assert extract_text.__doc__ and "Last mention wins" in extract_text.__doc__


# ── segmentation ────────────────────────────────────────────────────────

def test_segments_split_on_separators_and_corrections():
    assert segments("a, b; c\nd actually e") == ("a", "b", "c", "d", "e")


@pytest.mark.parametrize("phrase", [
    "device and grass",
    "Loved and Cherished 24",
    "nameplate and vinyl",
])
def test_segments_do_NOT_split_on_bare_and(phrase):
    """⚠️ THE WHOLE DIFFICULTY OF THE SEPARATOR SET. Three real phrases contain "and"
    as part of their meaning; splitting there cuts each in half and leaves both halves
    unrecognized."""
    assert segments(phrase) == (phrase,)


# ── last mention wins ───────────────────────────────────────────────────

@pytest.mark.parametrize("typed,field,expected", [
    ("full setup, actually tent only", "cemetery_equipment", "tent_only"),
    ("tent only, actually full setup", "cemetery_equipment", "full_equipment"),
    ("full setup actually tent only", "cemetery_equipment", "tent_only"),
    ("service at the church, actually at the graveside", "service_location", "graveside"),
])
def test_the_later_mention_is_the_answer(db, tenant, typed, field, expected):
    """⚠️ BOTH DIRECTIONS. A fix that always preferred the shorter phrase, or the
    alphabetically later value, would pass one row and fail its mirror."""
    assert _vals(db, tenant, typed).get(field) == expected


def test_a_later_mention_replaces_an_ANSWER_WITH_A_QUESTION(db, tenant):
    """⚠️ THE CASE A `values.update()` MERGE CANNOT EXPRESS. "34 inch Continental,
    actually Continental" must end with the PICK and no value — the director has
    become less specific, and the pane must ask again rather than keep the old
    answer."""
    ex = extract_text(db, tenant_id=tenant,
                      text="34 inch Continental, actually Continental")
    assert "vault" not in ex.values, ex.values
    assert [p.field_id for p in ex.picks] == ["vault"], ex.picks


def test_a_later_mention_replaces_a_QUESTION_WITH_AN_ANSWER(db, tenant):
    ex = extract_text(db, tenant_id=tenant,
                      text="Continental, actually 34 inch Continental")
    assert ex.values.get("vault") == 'Continental 34"', ex.values
    assert not ex.picks, ex.picks


# ── partial words ───────────────────────────────────────────────────────

@pytest.mark.parametrize("typed", ["Contin", "Continenta", "34 inch Contin", "Hopk"])
def test_a_partial_word_resolves_to_nothing(db, tenant, typed):
    """⚠️ THE PROPERTY LIVE TYPING DEPENDS ON. Every keystroke re-reads the text, so a
    half-typed word is seen on almost every pass; if "Contin" guessed Continental the
    pane would fill in answers the director had not finished giving."""
    ex = extract_text(db, tenant_id=tenant, text=typed)
    assert not ex.values, ex.values
    assert not ex.picks, ex.picks
    assert ex.unrecognized, "the half-typed word vanished instead of being shown"


# ── resolutions outrank re-extraction ───────────────────────────────────

def test_a_clicked_pick_survives_re_reading_the_same_text(db, tenant):
    """⚠️ WITHOUT THIS THE PANE IS UNUSABLE. The text is still ambiguous and still on
    screen, so re-reading it raises the same question on the very next keystroke."""
    ex = extract_text(db, tenant_id=tenant, text="Continental",
                      resolutions={"vault": 'Continental 34"'})
    assert ex.values["vault"] == 'Continental 34"'
    assert not ex.picks, ex.picks


def test_a_resolution_outranks_a_value_the_text_would_have_produced(db, tenant):
    ex = extract_text(db, tenant_id=tenant, text="34 inch Continental",
                      resolutions={"vault": "Graveliner 38\""})
    assert ex.values["vault"] == "Graveliner 38\""


# ── the text is the only source ─────────────────────────────────────────

def test_nothing_accumulates_so_deleting_a_word_removes_its_answer(db, tenant):
    """⚠️ THE LINE-APPEND MODEL ACCUMULATED `unrecognized`, which was right when each
    line was an event and is wrong now. If the director deletes a word the pane must
    stop reporting it."""
    with_it = extract_text(db, tenant_id=tenant, text="tent only, zzzqqq")
    without = extract_text(db, tenant_id=tenant, text="tent only")
    assert any("zzzqqq" in u for u in with_it.unrecognized), with_it.unrecognized
    assert not any("zzzqqq" in u for u in without.unrecognized), without.unrecognized


def test_re_reading_the_same_text_gives_the_same_answer(db, tenant):
    """Idempotence. Live typing re-reads constantly; a pass that drifted would make
    the rows flicker."""
    a = extract_text(db, tenant_id=tenant, text=SAMPLE)
    b = extract_text(db, tenant_id=tenant, text=SAMPLE)
    assert a.values == b.values
    assert a.unrecognized == b.unrecognized
    assert [p.field_id for p in a.picks] == [p.field_id for p in b.picks]


# ── the sample order, and what it still loses ───────────────────────────

def test_the_sample_order_captures_these_nine_fields(db, tenant):
    ex = extract_text(db, tenant_id=tenant, text=SAMPLE)
    assert set(ex.values) == {
        "funeral_home", "date_of_birth", "date_of_death", "vault",
        "service_location", "service_date", "service_time", "eta",
        "cemetery_equipment",
    }, sorted(ex.values)
    assert ex.values["cemetery_equipment"] == "tent_only"   # the correction won
    assert ex.values["service_time"] == "10:00"
    assert ex.values["eta"] == "11:30"


def test_WRONGNESS_the_sample_order_still_loses_two_fields(db, tenant):
    """⚠️ WRONGNESS. PINNED, NOT ENDORSED, AND AWAITING A RULING.

    `Mary Smith` and the cemetery are not captured, and both are DELIBERATE
    marker-gating rather than bugs:

      * `deceased_name` fires only behind a marker — "decedent is Mary Smith" works.
        A bare capitalised pair could be the funeral home, the decedent, a cemetery or
        a street, and the extractor refuses to guess.
      * the cemetery clause needs its marker too — "to St Mary's in Auburn" resolves.
        ⚠️ Even the EXACT name "St. Mary's Cemetery" does not resolve without one.

    Relaxing either is a design decision with real downside, so it is reported rather
    than taken. Asserted as-is so that changing it is a visible edit to this file.
    """
    ex = extract_text(db, tenant_id=tenant, text=SAMPLE)
    assert "deceased_name" not in ex.values
    assert "cemetery" not in ex.values
    assert any("Mary Smith" in u for u in ex.unrecognized), ex.unrecognized
    # ⚠️ "in" is a noise word, so the fragment arrives as "St Mary's Auburn".
    assert any("Mary" in u and "Auburn" in u for u in ex.unrecognized), ex.unrecognized


def test_the_markers_DO_work_so_the_gap_is_the_marker_and_not_the_resolver(db, tenant):
    """⚠️ THE CONTROL ON THE WRONGNESS ABOVE. Without this, "the cemetery is not
    captured" could equally mean the cemetery resolver is broken."""
    ex = extract_text(
        db, tenant_id=tenant,
        text="decedent is Mary Smith, to St Mary's in Auburn",
    )
    assert ex.values.get("deceased_name") == "Mary Smith", ex.values
    assert ex.values.get("cemetery") == "St. Mary's Cemetery", ex.values


# ── performance ─────────────────────────────────────────────────────────

def test_one_re_extraction_of_a_full_order_is_well_under_the_budget(db, tenant):
    """⚠️ THE RULED BUDGET IS 150 ms PER EXTRACTION, and it is a budget because live
    typing re-reads on every pause. Measured on local dev; the first call is excluded
    because it builds the catalog index."""
    extract_text(db, tenant_id=tenant, text=SAMPLE)   # warm the index
    times = []
    for _ in range(10):
        t0 = _time.perf_counter()
        extract_text(db, tenant_id=tenant, text=SAMPLE)
        times.append((_time.perf_counter() - t0) * 1000)
    times.sort()
    assert times[len(times) // 2] < 150, f"p50 {times[len(times)//2]:.1f}ms: {times}"
    assert times[-1] < 300, f"max {times[-1]:.1f}ms: {times}"
