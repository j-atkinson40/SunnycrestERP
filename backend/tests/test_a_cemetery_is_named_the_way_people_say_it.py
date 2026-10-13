"""The cemetery clause: every marker James named, and every spelling of the name.

⚠️ WALK NOTE, James, 2026-10-13 11:24: "order for hopkins monticello going to
St. Mary's" left the cemetery empty and "St Mary's" under Not understood.

⚠️ THE FIELD BEING RIGHT HID THE SPAN BEING WRONG. On the seeded tenant the
cemetery VALUE resolved correctly for every spelling before this file existed — so
`values["cemetery"]` was a green light over two real defects. What was broken was
what the clause CLAIMED:

    "going to St. Mary's"   name='St'          span='going to St'   -> "Mary's" unplaced
    "headed to Oakwood"     name='Oakwood'     span='to Oakwood'    -> "headed" unplaced
    "out to Oakwood"        name='Oakwood'     span='to Oakwood'    -> "out"    unplaced

So these tests assert the UNRECOGNIZED SET as well as the value. A test that
checked only the value passes against the defect James reported.

⚠️ AND THE PERIOD WAS THE SAME BUG, IN THE SAME FILE, ONE STEP OVER. `_CEM_TOWN`
gained `.` in its charset on 2026-10-12 for "St. Albans"; `_CEM_NAME` did not, so an
abbreviated CEMETERY stopped at the period while an abbreviated TOWN read fine. With
`name='St'` the town step never ran either — "going to St. Mary's Cemetery in
Skaneateles" returned `town=None`.

⚠️ COMMA-FREE THROUGHOUT, because that is how a director types and because commas
were what held three earlier defects apart.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture.typed_extraction import (
    extract_text,
    parse_cemetery_clause,
)

#: Every marker the dispatch names.
MARKERS = ["going to", "to", "at", "headed to", "out to"]

#: Spellings of the seeded "St. Mary's Cemetery" that must all reach it.
#: ⚠️ "saint marys" IS DELIBERATELY ABSENT — see
#: `test_saint_spelled_out_is_not_matched_and_that_is_recorded`.
SPELLINGS = [
    "St. Mary's Cemetery",
    "St. Mary's",
    "St Mary's",
    "St Marys",
    "st marys",
    "ST MARYS",
]


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


@pytest.fixture(scope="module")
def the_world_has_the_records(db, tenant):
    """⚠️ THE POSITIVE CONTROL ON THE FIXTURE ITSELF, and it is not ceremony.

    James's miss on production was NOT a matching failure — his tenant has ZERO rows
    in `cemeteries`, so there was nothing for any pattern to match. A suite that
    cannot tell "the matcher is broken" from "the table is empty" would have called
    that a parser bug, which is exactly what happened. This fails loudly instead.
    """
    names = {
        r.name
        for r in db.execute(
            text("SELECT name FROM cemeteries WHERE company_id = :t"), {"t": tenant}
        )
    }
    assert "St. Mary's Cemetery" in names, (
        f"the seeded tenant has no St. Mary's Cemetery row; it has {sorted(names)}. "
        f"Every assertion below would fail for the wrong reason."
    )
    return names


# ── the markers ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("marker", MARKERS)
def test_every_marker_reaches_the_cemetery(
    db, tenant, the_world_has_the_records, marker
):
    ex = extract_text(
        db, tenant_id=tenant, text=f"order for hopkins monticello {marker} st marys"
    )
    assert ex.values.get("cemetery") == "St. Mary's Cemetery", (marker, ex.values)


@pytest.mark.parametrize("marker", MARKERS)
def test_every_marker_LEAVES_NOTHING_UNPLACED(
    db, tenant, the_world_has_the_records, marker
):
    """⚠️ THE HALF THAT WAS BROKEN. The value above resolved for all five markers
    before the fix; "headed" and "out" were reported as text the engine could not
    place, because the marker pattern matched only the bare "to" inside them."""
    ex = extract_text(
        db, tenant_id=tenant, text=f"order for hopkins monticello {marker} st marys"
    )
    assert ex.unrecognized == (), (marker, ex.unrecognized)


@pytest.mark.parametrize("marker", MARKERS)
def test_every_marker_CLAIMS_ITS_OWN_WORDS(marker):
    # ⚠️ ASSERTED ON THE CLAUSE, NOT THE SENTENCE, so the claim is pinned at the step
    # that makes it rather than inferred from what survived downstream.
    line = f"order for hopkins monticello {marker} st marys"
    cl = parse_cemetery_clause(line)
    assert cl is not None, marker
    claimed = line[cl.start : cl.end]
    assert claimed == f"{marker} st marys", (marker, claimed)


# ── the spellings ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("spelling", SPELLINGS)
def test_every_spelling_reaches_the_record(
    db, tenant, the_world_has_the_records, spelling
):
    ex = extract_text(
        db, tenant_id=tenant, text=f"order for hopkins monticello going to {spelling}"
    )
    assert ex.values.get("cemetery") == "St. Mary's Cemetery", (spelling, ex.values)


@pytest.mark.parametrize("spelling", SPELLINGS)
def test_every_spelling_LEAVES_NOTHING_UNPLACED(
    db, tenant, the_world_has_the_records, spelling
):
    """⚠️ THIS IS THE TEST THAT WOULD HAVE CAUGHT JAMES'S REPORT. "St. Mary's"
    resolved and still put "Mary's" under Not understood, because `_CEM_NAME` had no
    period in its charset and the name ended at "St"."""
    ex = extract_text(
        db, tenant_id=tenant, text=f"order for hopkins monticello going to {spelling}"
    )
    assert ex.unrecognized == (), (spelling, ex.unrecognized)


@pytest.mark.parametrize("spelling", SPELLINGS)
def test_the_whole_name_is_claimed_not_just_its_first_word(spelling):
    line = f"order for hopkins monticello going to {spelling}"
    cl = parse_cemetery_clause(line)
    assert cl is not None, spelling
    assert line[cl.start : cl.end] == f"going to {spelling}", (
        spelling,
        line[cl.start : cl.end],
    )


def test_the_trailing_word_cemetery_is_optional_both_ways(
    db, tenant, the_world_has_the_records
):
    # ⚠️ BOTH DIRECTIONS IN ONE TEST, because the rule is an equivalence: the typed
    # name matches the record with OR without its trailing "Cemetery".
    with_it = extract_text(
        db, tenant_id=tenant, text="order for hopkins going to oakwood cemetery"
    )
    without = extract_text(
        db, tenant_id=tenant, text="order for hopkins going to oakwood"
    )
    assert with_it.values.get("cemetery") == "Oakwood Cemetery", with_it.values
    assert without.values.get("cemetery") == "Oakwood Cemetery", without.values
    assert with_it.unrecognized == () and without.unrecognized == ()


def test_a_name_with_no_cemetery_suffix_in_the_record_still_matches(
    db, tenant, the_world_has_the_records
):
    # ⚠️ THE NEGATIVE CONTROL ON THE SUFFIX RULE. "Lakeview Memorial Gardens" has no
    # trailing "Cemetery" at all; a rule implemented as "strip Cemetery and compare"
    # must not require one to be there.
    ex = extract_text(
        db, tenant_id=tenant, text="order for hopkins going to lakeview memorial gardens"
    )
    assert ex.values.get("cemetery") == "Lakeview Memorial Gardens", ex.values
    assert ex.unrecognized == ()


# ── the town rides along, which it did not while the name ended early ───────

def test_the_town_is_read_from_an_abbreviated_name(
    db, tenant, the_world_has_the_records
):
    """⚠️ A CONSEQUENCE OF THE PERIOD BUG, AND A SEPARATE SYMPTOM. With `name='St'`
    the suffix and town steps ran against the wrong offset, so
    "going to St. Mary's Cemetery in Skaneateles" returned `town=None` — the town was
    not merely wrong, it was never read."""
    line = "order for hopkins going to St. Mary's Cemetery in Skaneateles"
    cl = parse_cemetery_clause(line)
    assert cl is not None
    assert cl.town == "Skaneateles", cl.town
    ex = extract_text(db, tenant_id=tenant, text=line)
    assert ex.values.get("cemetery") == "St. Mary's Cemetery", ex.values
    assert ex.values.get("cemetery_city") == "Skaneateles", ex.values
    assert ex.unrecognized == ()


# ── what is NOT claimed, stated rather than assumed ─────────────────────────

def test_saint_spelled_out_is_not_matched_and_that_is_recorded(
    db, tenant, the_world_has_the_records
):
    """"saint marys" does NOT reach "St. Mary's Cemetery", and nothing here pretends
    otherwise.

    ⚠️ THE DISPATCH SAID "saint marys" IF AN ALIAS EXISTS, AND NO ALIAS TABLE EXISTS
    FOR CEMETERIES. `resolve_cemetery` reads `SELECT id, name, city FROM cemeteries`
    (`party_resolver.py:255`) and nothing else; the alias table that exists,
    `platform_product_aliases`, is for products. Expanding "saint" to "st" inside the
    normalizer was considered and NOT done: the normalizer folds the catalog's own
    names as well as the query, and a word-substitution rule there reshapes every
    index built on it. That is a decision with a blast radius, so it is James's, not
    a quiet widening here.

    ⚠️ IT ASSERTS THE WORDS ARE REPORTED, not merely that the match failed. A
    director who types "saint marys" must SEE that it was not understood rather than
    have it silently dropped.
    """
    ex = extract_text(
        db, tenant_id=tenant, text="order for hopkins monticello going to saint marys"
    )
    assert ex.values.get("cemetery") is None, ex.values
    assert "saint marys" in " ".join(ex.unrecognized).lower(), ex.unrecognized


def test_a_marker_does_not_invent_a_cemetery_from_any_following_words(
    db, tenant, the_world_has_the_records
):
    # ⚠️ THE GUARD ON THE WIDENED MARKER SET. "at" and "to" are common words; adding
    # "headed to"/"out to" must not make the clause claim text that resolves to
    # nothing. A span is only claimed when the resolver returns a record.
    ex = extract_text(
        db, tenant_id=tenant, text="order for hopkins monticello going to the shop"
    )
    assert ex.values.get("cemetery") is None, ex.values
