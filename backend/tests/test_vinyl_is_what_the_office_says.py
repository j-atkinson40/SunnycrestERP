"""The office says "vinyl" — so "vinyl" works, and it carries the symbol with it.

⚠️ JAMES, 2026-10-12: "In the office, Life's Reflections is almost always called
'vinyl'." The labels stay as they are; what has to work is the word.

⚠️ TWO THIRDS OF THIS ALREADY WORKED, AND MEASURING FIRST IS WHY NOTHING WAS
REWRITTEN. `_PERSONALIZATION` already matched `life'?s\\s+reflections|vinyl` and
`nameplate\\s+(?:and|&|\\+)\\s+(?:a\\s+)?(?:life'?s\\s+reflections|vinyl)`, so "vinyl"
and "nameplate and vinyl" resolved before this file existed. They are pinned here
anyway, because nothing was asserting them and the next edit to that ordered table
could take them away silently.

⚠️ WHAT WAS ACTUALLY MISSING: `lifes_reflections_symbol` HAD NO EXTRACTOR AT ALL.
Grep count in `typed_extraction.py`: zero. The field was on the template, applicable
whenever a vinyl answer was chosen, and nothing could ever fill it — so "vinyl cross"
set the answer and dropped "cross" into `unrecognized`. Complete machinery behind an
unprovisioned entrance, CLAUDE.md §11.

⚠️ THE PASS IS GATED ON THE ANSWER, NOT ON THE WORD, and that is the whole safety
argument. Cross, Dove, Floral and Praying Hands are ordinary words and also Legacy
print names; a bare "cross" with no vinyl in the line must set nothing. Asserted
below in both directions.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture.typed_extraction import (
    EXTRACTOR,
    _VINYL_SYMBOLS,
    evaluate_typed,
)
from app.services.personalization.questions import VINYL_ANSWERS

#: ⚠️ A VAULT THAT PERMITS VINYL. Measured while writing this file: the Continental
#: 34" permits `nameplate_only` ALONE, so `evaluate_typed` raises `UnpermittedAnswer`
#: on it — correctly, that is availability doing its job. A test that reached for the
#: nearest vault would have read that refusal as a bug in the extractor.
VINYL_VAULT = "Bronze Triune Burial Vault"


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


def _type(db, tenant, lines):
    answers: dict = {}
    unrec: list[str] = []
    for line in lines:
        ex = EXTRACTOR.extract_line(db, tenant_id=tenant, line=line, answers=answers)
        answers.update(ex.values)
        unrec.extend(ex.unrecognized)
    return answers, unrec


# ── controls ────────────────────────────────────────────────────────────

def test_the_symbol_vocabulary_covers_seven_of_the_eight(db):
    """⚠️ SEVEN, AND `other` IS DELIBERATELY ABSENT. It means "a symbol not on the
    list, specified in notes", so there is no word a director says that should resolve
    TO it — an unlisted symbol must come back unrecognized and be asked about, never
    filed silently as `other`."""
    covered = {ident for _, ident in _VINYL_SYMBOLS}
    assert covered == set(VINYL_ANSWERS) - {"other"}, sorted(
        set(VINYL_ANSWERS) - covered
    )


def test_the_vinyl_vault_really_does_permit_vinyl(db, tenant):
    """⚠️ READ THIS BEFORE ANY ASSERTION BELOW. If the chosen vault did not permit
    `lifes_reflections`, `evaluate_typed` would raise and every "asks for the symbol"
    test would fail for a reason that has nothing to do with the word "vinyl"."""
    answers, _ = _type(db, tenant, [VINYL_VAULT, "vinyl"])
    assert answers["personalization"] == "lifes_reflections"
    evaluate_typed(db, tenant_id=tenant, answers=answers)  # must not raise


# ── the word itself ─────────────────────────────────────────────────────

@pytest.mark.parametrize("line,expected", [
    ("vinyl", "lifes_reflections"),
    ("vinyl emblem", "lifes_reflections"),
    ("life's reflections", "lifes_reflections"),
    ("lifes reflections", "lifes_reflections"),
    ("nameplate and vinyl", "nameplate_and_lifes_reflections"),
    ("nameplate & vinyl", "nameplate_and_lifes_reflections"),
    ("nameplate and life's reflections", "nameplate_and_lifes_reflections"),
])
def test_the_word_the_office_uses_reaches_the_answer(db, tenant, line, expected):
    answers, _ = _type(db, tenant, [line])
    assert answers.get("personalization") == expected, answers


# ── the symbol rides along ──────────────────────────────────────────────

@pytest.mark.parametrize("line,symbol", [
    ("vinyl cross", "cross"),
    ("a vinyl dove", "dove"),
    ("vinyl star of david", "star_of_david"),
    ("vinyl praying hands", "praying_hands"),
    ("vinyl patriotic", "patriotic_american_flag"),
    ("vinyl american flag", "patriotic_american_flag"),
    ("vinyl masonic", "masonic"),
    ("vinyl floral", "floral"),
    ("lifes reflections cross", "cross"),
    ("nameplate and vinyl with a cross", "cross"),
])
def test_the_symbol_is_captured_and_nothing_is_orphaned(db, tenant, line, symbol):
    """⚠️ `unrecognized` IS ASSERTED EMPTY, NOT JUST THE SYMBOL. Before this pass
    existed, "vinyl cross" set the answer and left "cross" in `unrecognized` — the
    word was visible but unplaced. A symbol captured while half the phrase still
    reports as unplaced is not the fix."""
    answers, unrec = _type(db, tenant, [line])
    assert answers.get("lifes_reflections_symbol") == symbol, answers
    assert not unrec, unrec


def test_star_of_david_needs_the_RAW_slice_to_survive(db, tenant):
    """⚠️ "of" IS A NOISE WORD. Scanning noise-stripped fragments reduces this to
    "star david", which no pattern matches — the same trap `service_location` fell
    into with "funeral home" the same day."""
    answers, unrec = _type(db, tenant, ["vinyl star of david"])
    assert answers["lifes_reflections_symbol"] == "star_of_david"
    assert not unrec, unrec


# ── "vinyl" alone ASKS for the symbol ───────────────────────────────────

def test_vinyl_alone_leaves_the_symbol_ASKED_but_not_demanded(db, tenant):
    """⚠️ `unanswered_optional`, NOT `missing`, AND THE DIFFERENCE IS THE RULING. The
    symbol is `required_when=Never()` — prompted, never required — so the pane shows
    the row and asks, and the done signal is not blocked on it. `missing` would stop a
    director completing an order over a detail the family may not have given yet."""
    answers, _ = _type(db, tenant, [VINYL_VAULT, "vinyl"])
    _, state = evaluate_typed(db, tenant_id=tenant, answers=answers)
    assert "lifes_reflections_symbol" in state.unanswered_optional, (
        f"symbol is not being asked. answered={sorted(state.answered)} "
        f"missing={sorted(state.missing)} optional={sorted(state.unanswered_optional)}"
    )
    assert "lifes_reflections_symbol" not in state.missing
    assert "lifes_reflections_symbol" not in state.not_applicable


def test_vinyl_with_a_symbol_moves_it_into_answered(db, tenant):
    answers, _ = _type(db, tenant, [VINYL_VAULT, "vinyl cross"])
    _, state = evaluate_typed(db, tenant_id=tenant, answers=answers)
    assert "lifes_reflections_symbol" in state.answered, sorted(state.answered)


# ── the gate: a symbol word with no vinyl sets nothing ──────────────────

@pytest.mark.parametrize("line", [
    "cross", "a dove", "floral", "praying hands", "masonic",
    "nameplate only and a cross",
])
def test_a_bare_symbol_word_sets_nothing_without_a_vinyl_answer(db, tenant, line):
    """⚠️ THE SAFETY ARGUMENT, ASSERTED. These are ordinary words and four of them are
    also Legacy print names. Ungated, "nameplate only and a cross" would file a
    Life's Reflections symbol on an order that chose a nameplate."""
    answers, _ = _type(db, tenant, [line])
    assert "lifes_reflections_symbol" not in answers, answers


def test_a_cemetery_named_for_a_symbol_keeps_its_own_name(db, tenant):
    """⚠️ THE REASON THE PASS RUNS AFTER THE CEMETERY, MEASURED WITH A REAL ROW.

    "vinyl, to Holy Cross Cemetery" — the cemetery claims its name first, so the
    symbol pass never sees "Cross". This is the identical defect James found in the
    Service row ("Hopkins Funeral Home" read as the service location), one field over,
    and it is prevented by the same ordering rather than by a special case.

    ⚠️ AND THE SECOND LINE IS THE ONE THAT MATTERS: with the symbol said explicitly,
    BOTH resolve, from different text. A fix that merely suppressed the symbol near a
    cemetery would pass the first assertion and fail this one.
    """
    sp = db.begin_nested()
    try:
        db.execute(text(
            "INSERT INTO cemeteries (id, company_id, name, city, is_active, created_at) "
            "VALUES (:i, :c, 'Holy Cross Cemetery', 'Syracuse', TRUE, now())"
        ), {"i": str(uuid.uuid4()), "c": tenant})
        db.flush()

        answers, unrec = _type(db, tenant, ["vinyl, to Holy Cross Cemetery"])
        assert answers.get("cemetery") == "Holy Cross Cemetery", answers
        assert "lifes_reflections_symbol" not in answers, answers
        assert not unrec, unrec

        answers, unrec = _type(db, tenant, ["vinyl cross, to Holy Cross Cemetery"])
        assert answers.get("cemetery") == "Holy Cross Cemetery", answers
        assert answers.get("lifes_reflections_symbol") == "cross", answers
        assert not unrec, unrec
    finally:
        sp.rollback()
