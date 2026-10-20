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
    before anyone discovers it from a changed call-overlay result.

    ⚠️ IT COUNTS IMPORTS, NOT OCCURRENCES OF THE WORD, AND IT DID NOT UNTIL 2026-10-20.
    The old version read each file as TEXT and asked whether "typed_extraction" appeared
    anywhere in it — so a module that merely NAMED this one in a docstring was reported
    as an importer. Two did: `prefix_resolve` and `structured_parsers`, both explaining
    a defect whose whole point is which module it lived in, neither importing anything.

    The scan now parses. Same defect class as the `asdict` source check corrected
    earlier the same day, and as CLAUDE.md §11's "a count that measured the wrong unit":
    the instrument answered a question ADJACENT to the one asked, and its answer was
    well-formed. ⚠️ Naming a module in prose is how this codebase documents coupling;
    an instrument that punishes that would be read as a reason to stop writing it down.
    """
    import ast

    app_dir = pathlib.Path(__file__).resolve().parent.parent / "app"
    importers: list[str] = []
    for path in app_dir.rglob("*.py"):
        if path.name == "typed_extraction.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - a broken file is a different failure
            continue
        for node in ast.walk(tree):
            mods: list[str] = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [node.module or ""] + [
                    f"{node.module or ''}.{a.name}" for a in node.names
                ]
            if any("typed_extraction" in m for m in mods):
                importers.append(str(path.relative_to(app_dir)))
                break
    assert sorted(importers) == ["services/capture/session_service.py"], sorted(importers)


def test_the_importer_ratchet_can_actually_SEE_an_import():
    """⚠️ THE POSITIVE CONTROL, WITHOUT WHICH THE TEST ABOVE PASSES TRIVIALLY.

    An `ast` walk that matched nothing would satisfy `sorted([]) == [...]`? No — but an
    `ast` walk whose module-name test were subtly wrong would return `[]`, and `[] ==
    ["services/capture/session_service.py"]` is False, so that much is self-checking.
    What is NOT self-checking is the shape of the import it looks for: a scan that only
    understood `import x` and not `from x import y` would miss the real one and still
    have something to compare. So this asserts the known importer's own statement
    parses to a hit, and that a file naming the module in prose alone does not.

    CLAUDE.md §11: "require the control to be NON-ZERO, and read that number before the
    result it is vouching for."
    """
    import ast

    hits = []
    for src, label in (
        ("from app.services.capture.typed_extraction import extract_text", "from-import"),
        ("import app.services.capture.typed_extraction", "plain import"),
        ('"""typed_extraction has no way to know."""', "prose only"),
        ("# see typed_extraction for why", "comment only"),
    ):
        found = False
        for node in ast.walk(ast.parse(src)):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [node.module or ""] + [
                    f"{node.module or ''}.{a.name}" for a in node.names
                ]
            if any("typed_extraction" in m for m in mods):
                found = True
        hits.append((label, found))
    assert hits == [
        ("from-import", True), ("plain import", True),
        ("prose only", False), ("comment only", False),
    ], hits


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

def test_the_sample_order_captures_everything_and_asks_about_the_town(db, tenant):
    """⚠️ THIS ASSERTED NINE FIELDS AND TWO LOSSES UNTIL THE RULINGS OF 2026-10-12.

    It used to end with a `WRONGNESS` test pinning that `Mary Smith` and the cemetery
    were NOT captured, because both were marker-gated and relaxing either was a design
    decision. James ruled all three: a town that disagrees with the only matching
    record ASKS; a span matching an existing cemetery record resolves wherever it is
    typed; and one leftover person-like span is the decedent. So the sentence now
    places everything, and the only thing left is the question it should be asking.
    """
    ex = extract_text(db, tenant_id=tenant, text=SAMPLE)
    assert set(ex.values) == {
        "funeral_home", "deceased_name", "date_of_birth", "date_of_death", "vault",
        "service_location", "service_date", "service_time", "eta",
        "cemetery_equipment",
    }, sorted(ex.values)
    assert ex.values["deceased_name"] == "Mary Smith"
    assert ex.values["cemetery_equipment"] == "tent_only"   # the correction won
    assert ex.values["service_time"] == "10:00"
    assert ex.values["eta"] == "11:30"

    # ⚠️ THE TOWN CONFLICT IS THE POINT, NOT A LEFTOVER. The director said Auburn and
    # the only St Mary's on record is in Skaneateles, so the pane asks rather than
    # resolving silently or dropping "Auburn" into unplaced text.
    assert [p.field_id for p in ex.picks] == ["cemetery"], ex.picks
    assert ex.picks[0].discriminator == "city", ex.picks[0]
    assert "cemetery" not in ex.values, ex.values
    assert not ex.unrecognized, ex.unrecognized


@pytest.mark.parametrize("typed,expected", [
    ("St. Mary's Cemetery", "St. Mary's Cemetery"),
    ("Oakwood", "Oakwood Cemetery"),
    ("Oakwood Cemetery", "Oakwood Cemetery"),
    ("Lakeview Memorial Gardens", "Lakeview Memorial Gardens"),
    ("St Mary's in Skaneateles", "St. Mary's Cemetery"),
    ("to St Mary's", "St. Mary's Cemetery"),
])
def test_a_cemetery_on_record_resolves_with_or_without_a_marker(
    db, tenant, typed, expected
):
    """Ruling 2: matching a known name is a lookup, not a guess."""
    assert _vals(db, tenant, typed).get("cemetery") == expected


@pytest.mark.parametrize("typed", ["St Mary's in Auburn", "Oakwood in Syracuse",
                                   "to St Mary's in Auburn"])
def test_a_town_that_disagrees_with_the_record_ASKS(db, tenant, typed):
    """Ruling 1, both paths — with the marker and without it."""
    ex = extract_text(db, tenant_id=tenant, text=typed)
    assert "cemetery" not in ex.values, ex.values
    assert [p.field_id for p in ex.picks] == ["cemetery"], ex.picks
    assert ex.picks[0].discriminator == "city"
    assert not ex.unrecognized, ex.unrecognized


@pytest.mark.parametrize("typed,expected", [
    ("Mary Smith", "Mary Smith"),
    ("for Mary Smith", "Mary Smith"),
    ("decedent is Mary Smith", "Mary Smith"),
    ("the deceased Mary Smith", "Mary Smith"),
    ("order for Hopkins, Mary Smith", "Mary Smith"),
])
def test_one_leftover_person_like_span_is_the_decedent(db, tenant, typed, expected):
    assert _vals(db, tenant, typed).get("deceased_name") == expected


def test_two_leftover_names_do_NOT_guess(db, tenant):
    """Ruling 3: two or more and it takes none, both shown unplaced."""
    ex = extract_text(db, tenant_id=tenant, text="Mary Smith and John Albright")
    assert "deceased_name" not in ex.values, ex.values
    assert ex.unrecognized, "both names vanished instead of being shown"


@pytest.mark.parametrize("typed,protected_by", [
    # ⚠️ TWO DIFFERENT MECHANISMS, AND THIS COLUMN EXISTS BECAUSE I GOT IT WRONG.
    # The first version of this test claimed every row was "excluded by LOOKUP". A
    # break test that removed the funeral-home lookup left ALL 50 TESTS GREEN — and
    # the reason is that `Hopkins Funeral Home` was never reaching the decedent pass
    # at all: the location vocabulary was eating "Funeral Home" and leaving a single
    # word, which is not a candidate. The test was green for a mechanism it did not
    # name (CLAUDE.md §11 shape 9). Naming the mechanism per row is what makes the
    # break test meaningful.
    ("Hopkins", "one word is not a candidate"),
    ("Memorial Chapel", "lookup: funeral home"),
    ("Green Valley Memorial", "lookup: funeral home"),
    ("Smith & Sons Funeral Home", "lookup: funeral home"),
    ("Hopkins Funeral Home", "lookup: funeral home"),
    ("St. Mary's Cemetery", "lookup: cemetery"),
    ("Lakeview Memorial Gardens", "lookup: cemetery and funeral home"),
    ("Bronze Triune", "lookup: catalog"),
    ('Continental 34"', "lookup: catalog"),
    # ⚠️ THE ROWS THAT MAKE THE FUNERAL-HOME EXCLUSION TESTABLE, and the reason they
    # exist is that a break test refused to fire TWICE. Every exact record name is
    # claimed earlier by the marker-less lookup, so removing the exclusion inside the
    # decedent pass changed nothing — the guard looked dead. It is not: these are
    # PARTIAL names, which the exact-match lookup does not claim and which
    # `resolve_funeral_home` matches on significant tokens. Measured with the
    # exclusion removed: every one of them became the decedent.
    ("Hopkins Funeral", "lookup: funeral home, PARTIAL name"),
    ("Johnson Funeral", "lookup: funeral home, PARTIAL name"),
    ("Riverside Funeral", "lookup: funeral home, PARTIAL name"),
    ("Whitney Funeral", "lookup: funeral home, PARTIAL name"),
    ("Green Valley", "lookup: funeral home, PARTIAL name"),
])
def test_a_record_name_never_becomes_the_decedent(db, tenant, typed, protected_by):
    """⚠️ "Hopkins" NEVER BECOMES A DECEDENT, asserted by ruling."""
    assert "deceased_name" not in _vals(db, tenant, typed), protected_by


def test_a_funeral_home_whose_name_lacks_the_words_funeral_home(db, tenant):
    """⚠️ THE ROW THAT ACTUALLY EXERCISES THE FUNERAL-HOME LOOKUP, and the reason the
    break test now fires.

    `Green Valley Memorial` is a real funeral home on this tenant whose name contains
    neither "funeral" nor "home", so the location vocabulary cannot touch it and the
    only thing standing between it and the decedent field is the lookup. Paired with
    a genuine decedent in the same line, so the test also shows the two do not fight.
    """
    ex = extract_text(db, tenant_id=tenant, text="Green Valley Memorial, Mary Smith")
    assert ex.values.get("funeral_home") == "Green Valley Memorial", ex.values
    assert ex.values.get("deceased_name") == "Mary Smith", ex.values
    assert not ex.unrecognized, ex.unrecognized


@pytest.mark.parametrize("typed,fh,loc", [
    ("Hopkins Funeral Home", "Hopkins Funeral Home", None),
    ("Hopkins Funeral Home, service at the church", "Hopkins Funeral Home", "church"),
    ("the service is at the funeral home", None, "funeral_home"),
    ("order for Hopkins", "Hopkins Funeral Home", None),
])
def test_a_party_name_is_still_not_read_as_the_service_location(
    db, tenant, typed, fh, loc
):
    """⚠️ DEFECT 3a, REACHED BY THE PHRASING THE ORIGINAL FIX DID NOT COVER.

    3a was fixed by ORDER — the funeral-home pass claims the party's name before the
    location vocabulary sees it. But that pass is marker-gated, so "Hopkins Funeral
    Home" with no "for" got no claim and the vocabulary read "funeral home" out of the
    name again. Measured 2026-10-12: `service_location='funeral_home'` with "Hopkins"
    left unplaced. A marker-less record lookup for funeral homes closes it.

    ⚠️ The third row is the control: the location vocabulary must still work when no
    party is named, or the fix would be suppression rather than a fix.
    """
    vals = _vals(db, tenant, typed)
    assert vals.get("funeral_home") == fh, vals
    assert vals.get("service_location") == loc, vals


# ── performance ─────────────────────────────────────────────────────────

#: ⚠️ A CATASTROPHE CEILING, NOT THE RULED BUDGET. See the test below for why the
#: 150 ms figure is recorded rather than asserted here.
_CEILING_MS = 500.0


def test_one_re_extraction_of_a_full_order_is_not_catastrophically_slow(db, tenant):
    """⚠️ THIS ASSERTED `p50 < 150` AND TURNED CI RED, ON A COMMIT THAT HAD NOT MADE
    EXTRACTION SLOWER.

    CI measured **p50 152.4 ms** against the 150 ms line. Measured on this laptop
    across the same change:

        before the change (14820337)   p50 66.2 ms   max  74.7 ms
        with the n-gram vault scan     p50 65.8 ms   max 133.8 ms

    The p50 did not move. The CI runner is roughly 2.3x slower than the laptop —
    the same factor `ci.yml` records about its own seed step — so 66 ms becomes
    ~152 ms there and this assertion had been sitting ON the line, passing by luck,
    until it tipped.

    ⚠️ AND THIS IS THE SECOND COPY OF A FLAW FIXED YESTERDAY. The same
    absolute-wall-clock design was removed from `test_typed_capture_latency.py` on
    2026-10-12 — with a commit body explaining why a gate that is green on one
    machine and red on another cannot be read — and this assertion, in a different
    file, kept it. Third instance of "the fix landed on one copy" in two days, after
    the cemetery town pattern and the needed-count chip.

    ⚠️ THE RULED 150 ms BUDGET IS OWNED BY ONE FILE, and it is not this one.
    `test_typed_capture_latency.py` measures the curve — longest text over the same
    run's median, which is hardware-independent — and records the dev figures. Two
    gates on one budget is how they drift apart. What is left here is a ceiling loose
    enough to mean the same thing on any machine: 500 ms, about 3.3x the worst figure
    CI has produced for this sample.

    ⚠️ RECORDED, NOT GATED: on local dev 2026-10-13, p50 **65.8 ms** and max
    **133.8 ms** for this 164-character, 28-word order, against the ruled 150 ms. The
    max roughly doubled with the n-gram vault scan (74.7 -> 133.8) while the p50 held;
    the scan trades a little tail variance for reading run-on text at all.
    """
    extract_text(db, tenant_id=tenant, text=SAMPLE)   # warm the index
    times = []
    for _ in range(10):
        t0 = _time.perf_counter()
        extract_text(db, tenant_id=tenant, text=SAMPLE)
        times.append((_time.perf_counter() - t0) * 1000)
    times.sort()
    p50 = times[len(times) // 2]
    assert p50 < _CEILING_MS, (
        f"p50 {p50:.1f}ms exceeded the {_CEILING_MS}ms catastrophe ceiling "
        f"(the ruled budget is 150ms and is measured in "
        f"test_typed_capture_latency.py, which is hardware-independent): {times}"
    )
