"""A name matches its record whether or not the director typed the apostrophe.

⚠️ `normalize`'s DOCSTRING CLAIMED THIS AND THE FUNCTION DID NOT DO IT. It read
'Apostrophes matter here: "St. Mary's" and "St Marys" must normalize together.'
Measured 2026-10-12:

    "St. Mary's Cemetery"  ->  'st mary s cemetery'
    "St Marys"             ->  'st marys'

because `[^a-z0-9]+ -> " "` turned the apostrophe into a separator. A stated reason
redirects a reader's question from "does this work" to "does the code match the
explanation", and the code matched an explanation that was backwards about its own
output (CLAUDE.md §11).

⚠️ WHAT IT COST, AND IT WAS NOT A MISSED MATCH. Measured over HTTP on dev, not in
any test: "to St Marys in Auburn" failed to match the seeded "St. Mary's Cemetery",
so no cemetery resolved — and the decedent-by-elimination pass then took "St Marys"
as the only person-like span in that segment and, under LAST_WINS, OVERWROTE the
real decedent "Mary Smith" captured from an earlier segment. One missing apostrophe
put a cemetery's name in the deceased's row.

⚠️ SO THE END-TO-END ASSERTION IS THE ONE THAT MATTERS. A unit test on `normalize`
alone would have gone green the moment the apostrophe was deleted while leaving the
decedent defect entirely unmeasured, because the two are separated by three passes.
Both are tested here, and the second is the reason the first is worth having.

⚠️ `normalize` IS SHARED WITH THE CALL PIPELINE, so this change reaches it too.
E6 requires those tests to pass UNMODIFIED, and they do —
`test_call_extraction_missing_set.py` and `test_piece4_conditionals.py`, 59 green,
neither file touched.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture.typed_extraction import extract_text
from app.services.party_resolver import normalize


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


# ── the normaliser ──────────────────────────────────────────────────────

@pytest.mark.parametrize("a,b", [
    ("St. Mary's Cemetery", "St Marys Cemetery"),
    ("St. Mary's", "St Marys"),
    ("St Mary's", "St Marys"),
    ("O'Brien Funeral Home", "OBrien Funeral Home"),
    # ⚠️ THE TYPOGRAPHIC APOSTROPHE TOO, because a pasted record and a typed line do
    # not agree about which character they produce. U+2019, not U+0027.
    ("St. Mary’s Cemetery", "St Marys Cemetery"),
])
def test_an_apostrophe_is_not_part_of_a_name_s_identity(a, b):
    assert normalize(a) == normalize(b), f"{normalize(a)!r} != {normalize(b)!r}"


def test_the_apostrophe_is_DELETED_not_turned_into_a_separator(a=None):
    """⚠️ THE MECHANISM, PINNED SEPARATELY FROM THE OUTCOME. Equality above would
    also hold if both sides gained a space; this asserts which way it went, because
    the separator form is what broke the match in the first place."""
    assert normalize("St. Mary's") == "st marys"
    assert "mary s" not in normalize("St. Mary's")


def test_it_still_distinguishes_names_that_really_differ():
    """⚠️ THE POSITIVE CONTROL. A normaliser that collapsed everything would satisfy
    every assertion above and match every cemetery to every other."""
    assert normalize("St. Mary's Cemetery") != normalize("Oakwood Cemetery")
    assert normalize("Lakeview Memorial Gardens") != normalize("Oakwood Cemetery")


# ── and what it cost end to end ─────────────────────────────────────────

def test_a_cemetery_resolves_WITHOUT_the_apostrophe(db, tenant):
    ex = extract_text(
        db, tenant_id=tenant, text="to St Marys in Skaneateles"
    )
    assert ex.values.get("cemetery") == "St. Mary's Cemetery", ex.values


def test_a_cemetery_resolves_WITH_the_apostrophe_too(db, tenant):
    """⚠️ BOTH SPELLINGS, because a fix that moved the failure from one to the other
    would look identical in a test of only one."""
    ex = extract_text(
        db, tenant_id=tenant, text="to St. Mary's in Skaneateles"
    )
    assert ex.values.get("cemetery") == "St. Mary's Cemetery", ex.values


def test_THE_CEMETERY_NAME_DOES_NOT_BECOME_THE_DECEASED(db, tenant):
    """The live defect, end to end, and the assertion that actually protects the
    director.

    ⚠️ BOTH HALVES ARE ASSERTED. The cemetery name must not land in
    `deceased_name`, AND the real decedent must survive — because the failure was
    not a missing capture, it was an OVERWRITE of a correct one.
    """
    ex = extract_text(
        db,
        tenant_id=tenant,
        text="Mary Smith, to St Marys in Skaneateles",
    )
    assert ex.values.get("deceased_name") == "Mary Smith", ex.values
    assert ex.values.get("cemetery") == "St. Mary's Cemetery", ex.values
