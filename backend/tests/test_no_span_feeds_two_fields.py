"""No span feeds two fields — the rule, the defect that forced it, and the near misses.

⚠️ THE DEFECT, FROM PRODUCTION. James typed "start an order for Hopkins Funeral Home"
into the live pane and the Service row said `funeral_home`. He had not said where the
service was. The words "Funeral Home" were read TWICE: once as part of the party's
name, once as the place. One phrase, two fields.

⚠️ THE FIX IS AN ORDER CHANGE AS MUCH AS A GUARD, and the guard alone would have made
it worse. `service_location` ran eighth, scanning the whole line with `low.find`;
`funeral_home` runs nineteenth. Adding an overlap check without moving the pass would
have let `service_location` WIN the span and blocked the funeral home instead — the
same bug with the fields swapped. The specific entity has to claim its own name before
a bare vocabulary scan is allowed to look at the text.

⚠️ AND THE PASS SCANS RAW UNCLAIMED SLICES, NOT `_leftovers`. `funeral`, `home` and
`service` are all in `_NOISE_WORDS`, so a noise-stripped fragment can never contain
the phrase "funeral home" and "the service is at the funeral home" would resolve to
nothing. That near miss is asserted below, because the obvious implementation breaks
it and the breakage looks like a different feature.

⚠️ WHAT THIS FILE CANNOT YET ASSERT, STATED SO NOBODY READS MORE INTO IT. The general
property — "for any line, no two fields were set from overlapping text" — needs the
claimed spans exposed on `LineExtraction`, which the live-extraction work adds for its
own reasons (unrecognized text has to be attributed to its span in the pane). Until
then this file covers the defect, the near misses, and a corpus of adversarial pairs:
narrower than the property, and honest about it.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture.typed_extraction import EXTRACTOR, _claim, _free


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


def _ex(db, tenant, line: str):
    return EXTRACTOR.extract_line(db, tenant_id=tenant, line=line, answers={})


# ── control ─────────────────────────────────────────────────────────────

def test_the_funeral_home_resolver_can_see_something(db, tenant):
    """⚠️ READ THIS FIRST. Every assertion below turns on "Hopkins" resolving to a
    real party. Against an unseeded tenant the funeral home would be None and the
    defect test would pass for the wrong reason — the absence of a double read and
    the absence of any read look identical."""
    ex = _ex(db, tenant, "order for Hopkins")
    assert ex.values.get("funeral_home") == "Hopkins Funeral Home", ex.values


# ── the span algebra ────────────────────────────────────────────────────

@pytest.mark.parametrize("a,b,expected", [
    (0, 5, False),    # identical
    (2, 4, False),    # contained
    (4, 9, False),    # straddles the end
    (0, 1, False),    # straddles the start
    (5, 9, True),     # ⚠️ ABUTTING IS NOT OVERLAPPING — half-open intervals
    (9, 12, True),
])
def test_free_is_half_open(a, b, expected):
    """⚠️ `(0,5)` AND `(5,9)` MUST BOTH BE LEGAL. Treating the boundary as a clash
    would refuse every pair of adjacent words and silently drop the second field."""
    assert _free([(0, 5)], a, b) is expected


def test_claim_refuses_and_leaves_the_list_alone():
    spans = [(0, 5)]
    assert _claim(spans, 3, 8) is False
    assert spans == [(0, 5)], "a refused claim still mutated the span list"
    assert _claim(spans, 5, 8) is True
    assert spans == [(0, 5), (5, 8)]


# ── the defect ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("line", [
    "start an order for Hopkins Funeral Home",
    "new order for Hopkins Funeral Home",
    "order for Hopkins Funeral Home",
    "take an order for Hopkins Funeral Home please",
])
def test_the_party_name_is_not_also_read_as_the_service_location(db, tenant, line):
    """⚠️ THE REPORTED DEFECT. The funeral home resolves AND the Service row stays
    silent, because the director said nothing about where the service is."""
    ex = _ex(db, tenant, line)
    assert ex.values.get("funeral_home") == "Hopkins Funeral Home", ex.values
    assert "service_location" not in ex.values, (
        f"{line!r} answered service_location = "
        f"{ex.values.get('service_location')!r} from the party's own name"
    )


# ── the near misses the fix must not create ─────────────────────────────

@pytest.mark.parametrize("line,expected", [
    ("the service is at the funeral home", "funeral_home"),
    ("service at the funeral home", "funeral_home"),
    ("service at the church", "church"),
    ("service at the graveside", "graveside"),
    ("service at the grave", "graveside"),
    ("we'll do it grave side", "graveside"),
])
def test_a_service_location_with_no_party_still_resolves(db, tenant, line, expected):
    """⚠️ THE OBVIOUS IMPLEMENTATION BREAKS EVERY ROW HERE. Scanning `_leftovers`
    instead of the raw unclaimed slices strips `funeral`, `home` and `service` as
    noise words, so the phrase can never be found."""
    ex = _ex(db, tenant, line)
    assert ex.values.get("service_location") == expected, ex.values


@pytest.mark.parametrize("line,loc", [
    ("order for Hopkins, service at the funeral home", "funeral_home"),
    ("order for Hopkins Funeral Home, service at the church", "church"),
    ("order for Hopkins Funeral Home, service at the graveside", "graveside"),
])
def test_both_fields_resolve_when_the_director_said_both(db, tenant, line, loc):
    """⚠️ THE CASE THAT PROVES THE FIX IS NOT JUST SUPPRESSION. Two fields from two
    DIFFERENT pieces of text is exactly what should happen; a fix that merely stopped
    `service_location` from ever firing after a funeral home would pass every test
    above and fail these."""
    ex = _ex(db, tenant, line)
    assert ex.values.get("funeral_home") == "Hopkins Funeral Home", ex.values
    assert ex.values.get("service_location") == loc, ex.values


def test_the_longest_location_phrase_wins_so_no_fragment_is_orphaned(db, tenant):
    """⚠️ A REGRESSION I INTRODUCED AND A PROBE CAUGHT, PINNED HERE.

    My first version took the EARLIEST match in the slice. "service at the graveside"
    then matched `at the grave` (8-20) before `graveside` (15-24), claimed the shorter
    span, and left "side" sitting in `unrecognized` — a word the director typed,
    reported as unplaced, because two vocabulary entries overlapped. The rule is now
    "the match that consumes the most text wins".
    """
    ex = _ex(db, tenant, "service at the graveside")
    assert ex.values.get("service_location") == "graveside"
    assert not ex.unrecognized, ex.unrecognized
