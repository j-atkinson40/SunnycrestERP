"""Directors often give only a surname. "last name Smith" must fill the decedent row.

⚠️ WALK NOTE, James, production 2026-10-13 13:48: "last name Smith" went to Not
Understood. `_explicit_name` required `{1,2}` FURTHER capitalised words after its
marker — two words minimum — so a surname alone could never match it, and the
markers did not include "last name" or "family" at all.

⚠️ THE EXCLUSIONS ARE RECORD LOOKUPS, NOT A WORD LIST, and that matters more for a
single word than it did for two. "Hopkins", "Oakwood" and "Monticello" are all
plausible surnames AND all real records on this tenant; a one-word marker that
trusted its marker would turn "last name hopkins" into a decedent called after the
funeral home. A hand-written list of words-that-are-not-names would be wrong for
every tenant whose records nobody has seen.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture.typed_extraction import extract_text


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
def the_records_exist(db, tenant):
    """⚠️ THE EXCLUSION TESTS NEED REAL RECORDS TO EXCLUDE. Without them
    "last name hopkins" would be accepted and the test would pass for the wrong
    reason — the suite could not tell a working guard from an empty tenant."""
    ents = {
        r.name
        for r in db.execute(
            text("SELECT name FROM company_entities WHERE company_id = :t"),
            {"t": tenant},
        )
    }
    cems = {
        r.name
        for r in db.execute(
            text("SELECT name FROM cemeteries WHERE company_id = :t"), {"t": tenant}
        )
    }
    assert "Hopkins Funeral Home" in ents, sorted(ents)[:6]
    assert "Oakwood Cemetery" in cems, sorted(cems)
    return True


#: Every phrasing the dispatch names.
#:
#: ⚠️ "Keegan", NOT "Smith", AND THE REASON IS A MEASUREMENT RATHER THAN TASTE.
#: testco holds **Smith & Sons Funeral Home**, so `resolve_funeral_home(testco,
#: "smith")` returns a candidate and the record guard refuses the word — correctly,
#: by the ruling "never take a funeral-home, cemetery or catalog word". Using "Smith"
#: here would make these tests assert the guard is broken. The collision itself is
#: pinned in `test_a_surname_that_collides_with_a_record_is_refused`, and James's own
#: sentence is tested on HIS tenant, where "Smith" is free.
MARKERS = [
    "last name Keegan",
    "last name is Keegan",
    "the Keegan family",
    "Keegan family",
    "name is Keegan",
    "decedent Keegan",
]


@pytest.mark.parametrize("phrase", MARKERS)
def test_every_surname_marker_fills_the_decedent(db, tenant, phrase):
    ex = extract_text(db, tenant_id=tenant, text=f"order for riverside {phrase}")
    assert ex.values.get("deceased_name") == "Keegan", (phrase, ex.values)


@pytest.mark.parametrize("phrase", MARKERS)
def test_and_leaves_nothing_unplaced(db, tenant, phrase):
    # ⚠️ THE HALF THAT WAS BROKEN. "last name Smith" resolved to nothing AND was
    # reported as text the engine could not place — the whole clause, marker included.
    ex = extract_text(db, tenant_id=tenant, text=f"order for riverside {phrase}")
    assert ex.unrecognized == (), (phrase, ex.unrecognized)


def test_a_lowercase_surname_is_accepted_after_a_marker(db, tenant):
    # ⚠️ LOWERCASE IS ALLOWED ONLY BEHIND A MARKER, which is what makes it safe. A
    # bare lowercase word anywhere in the sentence is still not a name.
    ex = extract_text(db, tenant_id=tenant, text="order for riverside last name keegan")
    assert ex.values.get("deceased_name") == "keegan", ex.values


def test_it_is_displayed_AS_GIVEN_not_title_cased(db, tenant):
    # ⚠️ AS GIVEN, BY RULING. The office's own capitalisation is information —
    # "deSoto" and "MacLeod" are not what `.title()` would make of them.
    ex = extract_text(db, tenant_id=tenant, text="order for riverside last name deSoto")
    assert ex.values.get("deceased_name") == "deSoto", ex.values


@pytest.mark.parametrize(
    "word,what",
    [
        ("hopkins", "a funeral home on this tenant"),
        ("Hopkins", "a funeral home, capitalised"),
        ("oakwood", "a cemetery on this tenant"),
        ("monticello", "a catalog product"),
        ("continental", "a catalog product"),
    ],
)
def test_it_NEVER_takes_a_record_word_as_a_surname(db, tenant, the_records_exist, word, what):
    """⚠️ THE GUARD, AND EVERY ONE OF THESE IS A PLAUSIBLE SURNAME. The marker is not
    enough on its own; what decides is whether the word names something we hold."""
    ex = extract_text(db, tenant_id=tenant, text=f"order for riverside last name {word}")
    assert ex.values.get("deceased_name") is None, (word, what, ex.values)


def test_a_surname_that_collides_with_a_record_is_refused(db, tenant, the_records_exist):
    """⚠️ A REAL COST OF THE RULING, MEASURED AND RECORDED RATHER THAN HIDDEN.

    testco holds "Smith & Sons Funeral Home", so the commonest surname there is a
    funeral-home word and the guard refuses it. By the ruling that is correct; the
    consequence is that on such a tenant "last name Smith" still reads as text the
    engine could not place.

    ⚠️ IT IS TENANT-DEPENDENT, AND ON JAMES'S TENANT IT DOES NOT BITE. Measured
    2026-10-13: `resolve_funeral_home(sunnycrest, "smith")` returns nothing, because
    sunnycrest holds only Hopkins, Riverside Memorial Chapel and St. Mary's Cemetery.
    His walk sentence therefore works where he typed it.
    """
    ex = extract_text(db, tenant_id=tenant, text="order for riverside last name Smith")
    assert ex.values.get("deceased_name") is None, ex.values
    # and it is REPORTED rather than dropped — the office sees it was not taken
    assert any("Smith" in u for u in ex.unrecognized), ex.unrecognized


def test_the_two_word_name_still_works(db, tenant):
    # ⚠️ THE REGRESSION GUARD. The surname path is additional, not a replacement.
    ex = extract_text(
        db, tenant_id=tenant, text="order for riverside decedent Mary Smith"
    )
    assert ex.values.get("deceased_name") == "Mary Smith", ex.values


def test_a_surname_marker_does_not_eat_the_words_after_it(db, tenant):
    # ⚠️ ONE WORD, NOT A RUN. "last name Smith section 4" must not capture
    # "Smith section 4" — the marker-led span rule the cemetery and funeral-home
    # passes already follow.
    ex = extract_text(
        db,
        tenant_id=tenant,
        text="order for riverside last name Keegan section 4 lot 12",
    )
    assert ex.values.get("deceased_name") == "Keegan", ex.values
    assert ex.values.get("grave_location") == "Section 4, Lot 12", ex.values


@pytest.fixture(scope="module")
def james_tenant(db) -> str:
    tid = db.execute(
        text("SELECT id FROM companies WHERE slug = 'sunnycrest'")
    ).scalar()
    assert tid, "no sunnycrest tenant — this test must not skip"
    return tid


def test_JAMES_SENTENCE_from_the_walk(db, james_tenant):
    """His exact words, 2026-10-13 13:48, on the tenant he typed them on.

    ⚠️ ON `sunnycrest`, NOT `testco`, AND THAT IS THE POINT. "Smith" is a
    funeral-home word on testco and free on sunnycrest, so only his own tenant can
    answer whether his sentence works. Running it on testco would report a failure
    he will never see.
    """
    ex = extract_text(
        db,
        tenant_id=james_tenant,
        text=(
            "order for hopkins monticello with full equipment going to St. Mary's "
            "section 4 service Friday 11 am nameplate only last name Smith"
        ),
    )
    assert ex.values.get("deceased_name") == "Smith", ex.values
    assert ex.unrecognized == (), ex.unrecognized
    # and nothing else was disturbed
    assert ex.values.get("funeral_home") == "Hopkins Funeral Home"
    assert ex.values.get("vault") == "Monticello Burial Vault"
    assert ex.values.get("grave_location") == "Section 4"


def test_the_funeral_home_span_does_not_swallow_a_trailing_the(db, tenant, the_records_exist):
    """A defect the surname work exposed, fixed on its own terms.

    ⚠️ `resolve_funeral_home(testco, "riverside the")` RESOLVES, because
    `party_resolver.normalize` deletes separator words — so the funeral-home pass's
    longest-prefix loop claimed the trailing "the" along with the name. That was
    latent and harmless until something else wanted the word: with the surname clause
    claiming "the Keegan family" first, the overlapping funeral-home claim failed and
    the FUNERAL HOME was lost, reported as unplaced text.

    ⚠️ ASSERTED ON BOTH FIELDS AT ONCE, because the symptom appeared on the field
    that was NOT broken. A test that checked only the decedent would have passed
    while the funeral home quietly vanished.
    """
    ex = extract_text(
        db, tenant_id=tenant, text="order for riverside the Keegan family"
    )
    assert ex.values.get("funeral_home") == "Riverside Funeral Home", ex.values
    assert ex.values.get("deceased_name") == "Keegan", ex.values
    assert ex.unrecognized == (), ex.unrecognized
