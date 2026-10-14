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

import uuid

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


def test_a_surname_INSIDE_a_funeral_home_name_is_accepted_behind_a_marker(
    db, tenant, the_records_exist
):
    """⚠️ THIS TEST ASSERTED THE OPPOSITE UNTIL 2026-10-14, and it recorded the cost
    of the rule it was pinning.

    It read: testco holds "Smith & Sons Funeral Home", so the guard refuses the
    commonest surname there — correct by the 10-13 ruling, and the reason James's
    sentence worked on sunnycrest and not on testco. He has now ruled the other way:
    **behind an explicit marker the surname is accepted even if it appears inside a
    multi-word FH or cemetery record.**

    ⚠️ THE MARKER IS THE EVIDENCE, WHICH IS WHY THE LIFT IS SAFE. A director who says
    "last name" has said in words that a surname follows; a one-word fragment of a
    four-word funeral-home name is weak evidence against that, and the funeral home
    itself is already captured from earlier in the same sentence.
    """
    ex = extract_text(db, tenant_id=tenant, text="order for riverside last name Smith")
    assert ex.values.get("deceased_name") == "Smith", ex.values
    assert ex.unrecognized == (), ex.unrecognized
    # ⚠️ AND THE FUNERAL HOME IS STILL THE FUNERAL HOME. The lift must not let the
    # surname steal a record the order already named.
    assert ex.values.get("funeral_home") == "Riverside Funeral Home", ex.values


@pytest.mark.parametrize("word", ["Smith", "hopkins", "oakwood", "riverside"])
def test_every_FH_and_cemetery_word_is_accepted_behind_a_marker(
    db, tenant, the_records_exist, word
):
    """⚠️ ALL FOUR COLLIDE ON THIS TENANT, measured 2026-10-14:
    `smith`→"Smith & Sons Funeral Home", `hopkins`→"Hopkins Funeral Home",
    `oakwood`→"Oakwood Cemetery"/"Oakwood Memorial", `riverside`→"Riverside Funeral
    Home". Every one is a plausible surname and every one used to be refused."""
    ex = extract_text(
        db, tenant_id=tenant, text=f"order for monticello last name {word}"
    )
    assert ex.values.get("deceased_name") == word, (word, ex.values)


def test_WITHOUT_A_MARKER_A_RECORD_NAME_IS_NOT_A_DECEDENT(db, tenant, the_records_exist):
    """The other half of the ruling, asserted as an OUTCOME — and the mechanism is
    not the one the ruling's wording implies.

    ⚠️ TWO BREAK TESTS ON THE MARKER-LESS LOOKUPS PRODUCED NO RED, and the reason is
    worth more than the guard. Removing the cemetery check, and then the
    funeral-home check, from the marker-less name pass changed nothing: a record's
    OWN pass claims its span first, so by the time the name scan runs over
    `_unclaimed_slices` there is nothing left of "Oakwood Cemetery" to take. The
    lookups are a backstop for a record name that no earlier pass claimed, not the
    thing doing the work.

    ⚠️ SO THIS TEST ASSERTS WHAT THE OFFICE SEES, not an internal check I cannot make
    fail. The claim is "a record name with no marker does not become a decedent",
    and it holds with those lookups removed — which is the honest statement of how
    strong it is.

    ⚠️ AND THE CEMETERY LOOKUP CANNOT BE ISOLATED ON THIS TENANT AT ALL. Measured
    2026-10-14: all three testco cemeteries are also `company_entities` rows
    (Lakeview Memorial Gardens, Oakwood Cemetery, St. Mary's Cemetery; none is
    cemetery-only), so the funeral-home check shadows it for every one of them.
    """
    # a bare single word is not a name candidate in the first place — the
    # marker-less passes require two or more capitalised words
    bare = extract_text(db, tenant_id=tenant, text="order for monticello Smith")
    assert bare.values.get("deceased_name") is None, bare.values

    # and a full record name, unmarked, is read as the record
    ex = extract_text(db, tenant_id=tenant, text="order for monticello Oakwood Cemetery")
    assert ex.values.get("deceased_name") is None, ex.values
    assert ex.values.get("cemetery") == "Oakwood Cemetery", ex.values


@pytest.mark.parametrize(
    "word,what",
    [
        ("monticello", "a catalog product named exactly this"),
        ("continental", "a catalog product"),
    ],
)
def test_it_never_takes_a_CATALOG_word_as_a_surname(db, tenant, the_records_exist, word, what):
    """⚠️ THIS TEST ALSO COVERED `hopkins`, `Hopkins` AND `oakwood` UNTIL 2026-10-14.

    Those three are FH and cemetery words, and James ruled that behind an explicit
    marker a surname is accepted even when it appears inside a multi-word FH or
    cemetery record — so asserting they are refused would now be asserting the
    superseded rule. They are covered by
    `test_every_FH_and_cemetery_word_is_accepted_behind_a_marker`.

    ⚠️ THE CATALOG CASES SURVIVE UNCHANGED, because the ruling scopes the lift to
    "FH/cemetery" — and measured, that scope is also the better behaviour: testco
    holds a product named exactly `Monticello`, so the word there IS a product rather
    than a fragment of one.
    """
    ex = extract_text(db, tenant_id=tenant, text=f"order for riverside last name {word}")
    assert ex.values.get("deceased_name") is None, (word, what, ex.values)


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
    """sunnycrest, with the two records his sentence names.

    ⚠️ IT ENSURES THE RECORDS RATHER THAN ASSUMING THEM, AND CI TAUGHT ME THAT TWICE.
    Run 38445487845 failed here with `unrecognized == ('hopkins', "St Mary's")`:
    sunnycrest exists on a fresh CI database but its `company_entities` and
    `cemeteries` are EMPTY, so neither word resolved and the sentence failed for a
    reason that had nothing to do with surnames. A test must carry the world it needs.

    ⚠️ IT DOES NOT CREATE ANYTHING CALLED SMITH, which is the whole point of running
    this on sunnycrest: the claim is that "Smith" is free here, where it is a
    funeral-home word on testco. Adding Hopkins and St. Mary's cannot affect that.

    ⚠️ COMMITTED AND DELETED, NOT SAVEPOINTED, so the rows are visible to the
    extractor's own sessions and nothing is left behind.
    """
    tid = db.execute(
        text("SELECT id FROM companies WHERE slug = 'sunnycrest'")
    ).scalar()
    assert tid, "no sunnycrest tenant — this test must not skip"

    made: list[tuple[str, str]] = []

    def ensure(table: str, where: str, params: dict, insert: str) -> None:
        found = db.execute(text(f"SELECT id FROM {table} WHERE {where}"), params).scalar()
        if found:
            return
        rid = str(uuid.uuid4())
        db.execute(text(insert), {**params, "i": rid})
        made.append((table, rid))

    ensure(
        "company_entities", "company_id = :t AND name = :n",
        {"t": tid, "n": "Hopkins Funeral Home"},
        "INSERT INTO company_entities (id, company_id, name) VALUES (:i, :t, :n)",
    )
    ensure(
        "cemeteries", "company_id = :t AND name = :n",
        {"t": tid, "n": "St. Mary's Cemetery"},
        "INSERT INTO cemeteries (id, company_id, name, city, state, is_active) "
        "VALUES (:i, :t, :n, 'Skaneateles', 'NY', true)",
    )
    db.commit()

    # ⚠️ ASSERTED AFTER ENSURING, because "Smith" being free is the premise and a
    # tenant that had acquired a Smith record would make this test lie.
    from app.services.party_resolver import resolve_funeral_home

    assert not resolve_funeral_home(db, tid, "smith").candidates, (
        "sunnycrest has acquired a record matching 'smith'; this test's premise is gone"
    )

    yield tid

    for table, rid in made:
        db.execute(text(f"DELETE FROM {table} WHERE id = :i"), {"i": rid})
    db.commit()


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
