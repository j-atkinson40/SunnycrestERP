"""A pass that needs context from elsewhere in the text gets it. Twice over.

⚠️ FOUND OVER HTTP ON DEV, NOT BY ANY TEST. Typing

    "… nameplate and vinyl, cross, …"

came back with the word **`cross` UNRECOGNIZED** and no symbol captured, while the
vinyl answer sat two segments earlier in the same sentence. `extract_text` reads each
segment in ISOLATION — which is what makes LAST_WINS possible, because a later
segment must be free to overwrite an earlier one — and isolation also hid the
personalization answer from the vinyl-symbol gate, which only fires when the chosen
personalization bears vinyl.

⚠️ THE FIX IS A SECOND PASS, AND THE TWO PARAMETERS ARE THE POINT. `extract_line` now
takes `gating` separately from `answers`:

    answers   what has been ANSWERED — drives FIRST_WINS re-statement reporting
    gating    context a GATED pass needs to fire at all, and nothing else

Passing the accumulated answers as `answers` would have fixed the gate and broken
LAST_WINS, because a later segment would then be reporting re-statements instead of
overwriting.

⚠️ AND MY FIRST VERSION OF THE SECOND PASS WAS ITSELF FIRST_WINS. It guarded with
`if field_id not in last`, so the first segment to produce a gated field blocked
every later one — "vinyl, cross, actually praying hands" captured `cross` and
discarded the correction. Guarding against a SNAPSHOT taken before the loop lets
pass-2 segments overwrite each other while never touching what pass 1 decided. Both
halves are tested below, because one without the other is a different bug.

⚠️ REQUIRES THE SEEDED `testco` TENANT — the vault has to resolve for availability to
permit vinyl at all.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture.typed_extraction import evaluate_typed, extract_text

#: ⚠️ A VAULT THAT PERMITS VINYL. The Continental 34" permits `nameplate_only` alone,
#: so vinyl on it produces a CONFLICT rather than a symbol question — measured, and
#: it would make every assertion here fail for an unrelated reason.
VINYL_VAULT = "Bronze Triune Burial Vault"
SYMBOL = "lifes_reflections_symbol"


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


# ── the control ─────────────────────────────────────────────────────────

def test_the_vault_permits_vinyl_so_the_symbol_is_reachable(db, tenant):
    """⚠️ READ FIRST. If this vault stopped permitting vinyl, the symbol would never
    be asked for and every test below would pass or fail about the wrong thing."""
    ex = extract_text(db, tenant_id=tenant, text=f"{VINYL_VAULT}, vinyl")
    assert ex.values.get("personalization") == "lifes_reflections"
    _, _, conflicts = evaluate_typed(db, tenant_id=tenant, answers=dict(ex.values))
    assert conflicts == (), conflicts


# ── the gate fires across segments ──────────────────────────────────────

def test_a_SYMBOL_IN_ITS_OWN_SEGMENT_is_captured(db, tenant):
    """The defect, stated as the fix. "cross" is its own segment and carries no word
    that says it is a vinyl symbol; the answer that makes it one is elsewhere."""
    ex = extract_text(db, tenant_id=tenant, text=f"{VINYL_VAULT}, vinyl, cross")
    assert ex.values.get(SYMBOL) == "cross", ex.values

def test_AND_THE_WORD_IS_NOT_REPORTED_AS_UNDERSTOOD_AND_UNPLACED_AT_ONCE(db, tenant):
    """⚠️ THE HALF THAT WAS VISIBLE ON JAMES'S SCREEN. Before the fix the response
    both failed to capture the symbol AND listed "cross" as not understood. A response
    that captures a word and reports it unplaced would be contradicting itself."""
    ex = extract_text(db, tenant_id=tenant, text=f"{VINYL_VAULT}, vinyl, cross")
    assert not any("cross" in u.lower() for u in ex.unrecognized), ex.unrecognized


def test_it_works_across_SEVERAL_segments_of_distance(db, tenant):
    """⚠️ NOT JUST THE ADJACENT SEGMENT. The sentence that exposed this had the vinyl
    answer and the symbol separated by nothing, but a director's real sentence puts
    the equipment, the dates and the cemetery in between."""
    ex = extract_text(
        db,
        tenant_id=tenant,
        text=f"{VINYL_VAULT}, nameplate and vinyl, tent only, years only, cross",
    )
    assert ex.values.get(SYMBOL) == "cross", ex.values
    assert ex.unrecognized == (), ex.unrecognized


def test_the_SYMBOL_BEFORE_THE_ANSWER_also_works(db, tenant):
    """⚠️ ORDER-INDEPENDENT, WHICH A SINGLE FORWARD PASS COULD NOT BE. A director may
    say the symbol first. Pass 1 reads the whole text before pass 2 gates anything,
    so "cross" is reachable whether it comes before or after "vinyl"."""
    ex = extract_text(db, tenant_id=tenant, text=f"{VINYL_VAULT}, cross, vinyl")
    assert ex.values.get(SYMBOL) == "cross", ex.values


# ── pass 2 is LAST_WINS within itself ───────────────────────────────────

def test_A_CORRECTED_SYMBOL_WINS(db, tenant):
    """⚠️ THE BUG MY OWN FIX INTRODUCED, PINNED. The first version of the second pass
    guarded `if field_id not in last`, so the first segment to produce the symbol
    blocked every later one and this returned `cross`."""
    ex = extract_text(
        db,
        tenant_id=tenant,
        text=f"{VINYL_VAULT}, vinyl, cross, actually praying hands",
    )
    assert ex.values.get(SYMBOL) == "praying_hands", ex.values


def test_pass_2_NEVER_OVERWRITES_WHAT_PASS_1_DECIDED(db, tenant):
    """⚠️ THE OTHER DIRECTION, AND WITHOUT IT THE FIX ABOVE WOULD BE A REGRESSION. A
    field pass 1 settled must survive the second read untouched, or the second pass
    becomes a second chance to reinterpret the whole sentence."""
    ex = extract_text(
        db, tenant_id=tenant, text=f"{VINYL_VAULT}, full setup, actually tent only"
    )
    assert ex.values.get("cemetery_equipment") == "tent_only", ex.values


def test_vinyl_WITHOUT_a_symbol_still_PROMPTS_and_does_not_BLOCK(db, tenant):
    """James's decision, 2026-10-12: vinyl without a symbol does not block
    completion; the symbol stays prompted.

    ⚠️ `unanswered_optional`, NOT `missing`, IS WHAT "PROMPTED BUT NOT BLOCKING"
    MEANS in this engine — `is_complete` ignores that set. Asserting only "not in
    missing" would also be true of a field nobody ever asks about.
    """
    ex = extract_text(db, tenant_id=tenant, text=f"{VINYL_VAULT}, vinyl")
    _, state, _ = evaluate_typed(db, tenant_id=tenant, answers=dict(ex.values))
    assert SYMBOL not in state.missing, "the symbol is blocking completion"
    assert SYMBOL in state.unanswered_optional, (
        "the symbol is not prompted at all — it should be asked for, just not "
        "required"
    )
