"""A party name resolves whether or not the director reached for the shift key.

⚠️ FOUND BY REPRODUCING JAMES'S PRODUCTION WALK NOTE, 2026-10-12. He typed
"order for hopkins" — lowercase, no punctuation — and `hopkins` came back
UNRECOGNIZED while "order for Hopkins" resolved to `Hopkins Funeral Home`. A
director typing fast on a call does not capitalise, and this is the one input the
walk instruction actually named.

⚠️ TWO INDEPENDENT GAPS CONSPIRED, AND NEITHER ALONE EXPLAINS IT — which is why
there are two groups of tests below and why the fix is in one place but had to be
reasoned about in two:

    the MARKER path          `\\b(?:for|from|with)\\s+([A-Z]...)` — required a
                             CAPITAL, so lowercase matched nothing. FIXED: the
                             pattern is case-insensitive.

    the MARKER-LESS path     a record-name scan that IS case-insensitive but tries
                             n-gram sizes (5, 4, 3, 2) — minimum TWO words. The
                             single word "hopkins" could not match there either, so
                             it could not cover for the marker path. NOT CHANGED;
                             tested here so the next reader does not "fix" the
                             wrong one.

⚠️ WIDENING THE CASE CANNOT INVENT A FUNERAL HOME, and that is the argument for the
fix being safe rather than merely small. The span is claimed only when
`resolve_funeral_home` returns a party or a candidate set; a span resolving to
nothing claims nothing and falls through every later pass unchanged. The cost of a
wrong match is bounded by the resolver, not by the regex.

⚠️ THE DECEDENT PASS STILL REQUIRES CAPITALS AND IS DELIBERATELY NOT CHANGED HERE —
measured and pinned below so the gap is visible rather than discovered twice. Its
pattern is `\\b[A-Z][A-Za-z'\\-]+(?:\\s+[A-Z][A-Za-z'\\-]+){1,2}\\b`, so lowercase
"mary smith" comes back unrecognized. Unlike a funeral home, a decedent's name has
NO RECORD to check against — it is free text — so making that pass
case-insensitive is a real loosening with no backstop, and whether to do it is a
behaviour decision rather than a defect fix.

⚠️ REQUIRES THE SEEDED `testco` TENANT, and fails loudly rather than skipping.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture.typed_extraction import extract_text

#: ⚠️ A ONE-WORD PREFIX OF A REAL RECORD NAME, which is what makes it the hard case:
#: it is not the record's full name, so the exact-name scan cannot match it — only
#: the marker path's resolver can.
TYPED = "hopkins"
RECORD = "Hopkins Funeral Home"


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

def test_the_record_this_file_depends_on_exists(db, tenant):
    """⚠️ READ FIRST. Without the record, every assertion below would be measuring a
    missing row rather than a capitalisation rule."""
    names = [
        r[0] for r in db.execute(
            text("select name from company_entities where company_id = :t"),
            {"t": tenant},
        )
    ]
    assert RECORD in names, names


# ── the phrase James actually typed ─────────────────────────────────────

def test_THE_EXACT_PHRASE_FROM_THE_WALK_NOTE(db, tenant):
    """`order for hopkins` — lowercase, no punctuation, no trailing anything."""
    ex = extract_text(db, tenant_id=tenant, text="order for hopkins")
    assert ex.values.get("funeral_home") == RECORD, ex.values
    assert ex.unrecognized == (), ex.unrecognized


@pytest.mark.parametrize("phrase", [
    "order for hopkins",
    "order for Hopkins",
    "order for HOPKINS",
    "ORDER FOR HOPKINS",
    "order for hopkins funeral home",
    "order for Hopkins Funeral Home",
])
def test_case_does_not_decide_whether_a_party_resolves(db, tenant, phrase):
    ex = extract_text(db, tenant_id=tenant, text=phrase)
    assert ex.values.get("funeral_home") == RECORD, (phrase, ex.values)


@pytest.mark.parametrize("marker", ["for", "from", "with"])
def test_every_marker_is_case_insensitive_not_just_for(db, tenant, marker):
    """⚠️ ALL THREE, because the pattern names three and a fix applied to the one in
    the bug report is a fix to a sample (CLAUDE.md §11)."""
    ex = extract_text(db, tenant_id=tenant, text=f"order {marker} hopkins")
    assert ex.values.get("funeral_home") == RECORD, (marker, ex.values)


# ── the other gap, pinned so nobody fixes the wrong one ─────────────────

def test_the_MARKER_LESS_scan_still_needs_two_words(db, tenant):
    """⚠️ THE SECOND GAP, MEASURED AND LEFT ALONE. The record-name scan is
    case-insensitive already but tries sizes (5, 4, 3, 2) — two words minimum — so
    a bare one-word name with NO MARKER in front of it resolves nowhere.

    This is not the defect James hit (his phrase had "for"), and extending the scan
    to single words would make every lone capitalised word a candidate party. Pinned
    so the next reader can see that the marker path is where the fix belongs.
    """
    ex = extract_text(db, tenant_id=tenant, text="hopkins")
    assert ex.values.get("funeral_home") is None, ex.values
    # ⚠️ AND IT IS REPORTED, NOT SWALLOWED — E1's never-dropped rule. The director
    # sees the word they typed sitting in "Not understood".
    assert any("hopkins" in u.lower() for u in ex.unrecognized), ex.unrecognized


def test_the_marker_less_scan_DOES_match_a_full_name_lowercase(db, tenant):
    """⚠️ THE POSITIVE CONTROL ON THAT GAP'S BOUNDARY. Two-plus words DO match
    without a marker and already did, case-insensitively — so the gap is about
    LENGTH, not about case, and the test above is not evidence of a case problem."""
    ex = extract_text(db, tenant_id=tenant, text="burial at hopkins funeral home")
    assert ex.values.get("funeral_home") == RECORD, ex.values


# ── the decedent gap, reported not fixed ────────────────────────────────

def test_a_LOWERCASE_DECEDENT_is_still_not_recognised(db, tenant):
    """⚠️ A GAP RECORDED AS ONE, NOT A PASSING TEST PRETENDING TO BE A FEATURE.

    The decedent pass requires capitals, so "mary smith" is unrecognized while
    "Mary Smith" is captured. Unlike a funeral home, a decedent's name has no record
    to check against, so making that pass case-insensitive loosens it with no
    backstop — nearly every two-word phrase becomes person-like. That is a behaviour
    decision, not a defect fix.

    ⚠️ IF THIS GOES RED THE GAP WAS CLOSED, which is good news and means deleting
    this test — not loosening it.
    """
    ex = extract_text(db, tenant_id=tenant, text="order for hopkins, mary smith")
    assert ex.values.get("deceased_name") is None, (
        "the decedent pass now reads lowercase names — close this gap in STATE and "
        "delete this test"
    )
    assert any("mary smith" in u.lower() for u in ex.unrecognized), ex.unrecognized

    # and the capitalised form still works, so the gap is about CASE and nothing else
    ex2 = extract_text(db, tenant_id=tenant, text="order for hopkins, Mary Smith")
    assert ex2.values.get("deceased_name") == "Mary Smith", ex2.values


# ── nothing else moved ──────────────────────────────────────────────────

def test_a_NON_PARTY_phrase_after_a_marker_claims_nothing(db, tenant):
    """⚠️ THE REGRESSION THE WIDER CASE COULD HAVE CAUSED. With `re.I` the marker
    pattern now matches lowercase runs like "for the church", so the resolver is
    asked about spans it was never asked about before. It must answer "no" and the
    span must stay available to the passes that actually want it."""
    ex = extract_text(
        db, tenant_id=tenant, text="service at the church thursday 10am"
    )
    assert ex.values.get("funeral_home") is None, ex.values
    assert ex.values.get("service_location") == "church", ex.values
    assert ex.values.get("service_time") == "10:00", ex.values
