"""A town typed with a cemetery is part of it — James's ruling of 2026-10-29.

> towns typed with a cemetery are part of it, not held words. Sunnycrest serves several
> cemeteries that share a name, so people type the town.
> - A town word (any known cemetery town) typed right after a cemetery term, or right
>   before it ("skaneateles st marys"), belongs to that cemetery answer: matching town =
>   absorbed as confirmation; a shared name = picks that one; a town where no cemetery by
>   that name exists = ask with the choices.

⚠️ CASE 3 IS DEFERRED, BY A SECOND RULING THE SAME DAY, and that is asserted here rather
than left to be inferred from its absence. It collides with
`test_NO_PREFIX_EVER_LOSES_A_FIELD_IT_HAD`: a city conflict becomes a PICK, a pick
replaces the value, and the cemetery row goes from filled to a question as the next word
lands — the precise defect that test exists to catch. Clause 1 makes it safe, because a
term that has left the bar is a resolution and resolutions outrank the text.

⚠️ THE SHARED-NAME CASE NEEDS ITS OWN TENANT. James: "Test it with a fixture tenant that
has two St. Mary's in different towns (don't add a second cemetery to Sunnycrest; the
real ones come at onboarding)." Measured 2026-10-29: Sunnycrest has ONE cemetery, so the
case the feature is FOR cannot be exercised against it.
"""
from __future__ import annotations

import os
import uuid

import pytest

if not os.environ.get("DATABASE_URL") or not os.environ.get("SECRET_KEY"):
    pytest.skip(
        # ⚠️ THE MESSAGE NAMES BOTH, AND THE ONE IT REPLACES DID NOT. Ten files carry
        # this guard saying "DATABASE_URL is not set" while SECRET_KEY is just as able to
        # trip it — which is how ten gate files, 228 tests, skipped silently through
        # every local gate run on 2026-10-29. An instrument that names the wrong reason
        # sends the reader to check the variable that is already set.
        "needs DATABASE_URL and SECRET_KEY (CI sets both)",
        allow_module_level=True,
    )

from app.database import SessionLocal
from app.models.cemetery import Cemetery
from app.models.company import Company
from app.services.capture.typed_extraction import extract_text
from tests._cleanup import purge_companies_by_slug
from tests._ids import RUN_ID

SLUG = f"towns-{RUN_ID}"


@pytest.fixture
def two_st_marys():
    """A tenant with TWO St. Mary's, in different towns. Purged either side.

    ⚠️ CONSTRUCTED, AND SAID SO. No production tenant has two cemeteries of one name —
    the `(company_id, name)` unique constraint forbids an exact duplicate — so these
    differ by punctuation, which is what the name normalisation squeezes away. Without
    saying this a reader would take the feature for one that fires on real data.
    """
    db = SessionLocal()
    try:
        purge_companies_by_slug(db, f"{SLUG}%")
        db.commit()
        co = Company(id=str(uuid.uuid4()), name="Towns Vault Co", slug=SLUG,
                     vertical="manufacturing", is_active=True)
        db.add(co)
        db.flush()
        for name, city in (
            ("St. Mary's Cemetery", "Skaneateles"),
            ("St Marys Cemetery", "Auburn"),
            ("Oakwood Cemetery", "Syracuse"),
        ):
            db.add(Cemetery(id=str(uuid.uuid4()), company_id=co.id, name=name,
                            city=city, is_active=True))
        db.flush()
        yield db, co.id
    finally:
        db.rollback()
        try:
            purge_companies_by_slug(db, f"{SLUG}%")
            db.commit()
        except Exception:
            db.rollback()
        db.close()


def _ex(db, tid, text_in):
    return extract_text(db, tenant_id=tid, text=text_in)


# ── case 1: a matching town is absorbed ───────────────────────────────────────────

def test_a_matching_town_after_the_name_is_ABSORBED_not_held(two_st_marys):
    """⚠️ THE DEFECT JAMES WALKED. Before this, "…graveside st marys skaneateles"
    resolved the cemetery and then reported **'skaneateles'** as text the engine could
    not place — the town became a held word, which the ruling calls a defect."""
    db, tid = two_st_marys
    ex = _ex(db, tid, "going to st marys skaneateles")
    assert ex.values.get("cemetery") == "St. Mary's Cemetery", ex.values
    assert ex.values.get("cemetery_city") == "Skaneateles", ex.values
    assert "skaneateles" not in [u.lower() for u in ex.unrecognized], ex.unrecognized


def test_a_matching_town_BEFORE_the_name_is_absorbed_too(two_st_marys):
    """The ruling names both orderings: "or right before it ("skaneateles st marys")"."""
    db, tid = two_st_marys
    ex = _ex(db, tid, "skaneateles st marys")
    assert ex.values.get("cemetery") == "St. Mary's Cemetery", ex.values
    assert ex.values.get("cemetery_city") == "Skaneateles", ex.values
    assert ex.unrecognized == (), ex.unrecognized


def test_the_walk_sentence_leaves_NOTHING_unplaced(two_st_marys):
    """⚠️ JAMES'S OWN WALK SENTENCE, END TO END, which is the thing he reads on screen."""
    db, tid = two_st_marys
    ex = _ex(db, tid, "monti thursday 10am graveside st marys skaneateles")
    assert ex.values.get("cemetery") == "St. Mary's Cemetery", ex.values
    assert ex.unrecognized == (), ex.unrecognized


# ── case 2: a shared name is disambiguated by the town ───────────────────────────

def test_the_town_PICKS_the_right_one_of_two_cemeteries_sharing_a_name(two_st_marys):
    """⚠️ THE CASE THE WHOLE RULING IS FOR, and the only one that needs two records.

    Without the town, "st marys" matches both and must ask. With the town it resolves to
    exactly one — and which one depends on which town was typed, which is the assertion
    that a single-cemetery tenant cannot make.
    """
    db, tid = two_st_marys
    amb = _ex(db, tid, "going to st marys")
    assert amb.values.get("cemetery") is None, (
        f"control: two cemeteries share this name, so the bare name must NOT resolve; "
        f"got {amb.values.get('cemetery')!r}"
    )

    a = _ex(db, tid, "going to st marys skaneateles")
    assert a.values.get("cemetery") == "St. Mary's Cemetery", a.values
    assert a.values.get("cemetery_city") == "Skaneateles", a.values

    b = _ex(db, tid, "going to st marys auburn")
    assert b.values.get("cemetery") == "St Marys Cemetery", b.values
    assert b.values.get("cemetery_city") == "Auburn", b.values

    # ⚠️ AND THE TWO ANSWERS DIFFER, which is the whole point. A rule that returned the
    # same cemetery for both towns would satisfy each assertion above on its own.
    assert a.values["cemetery"] != b.values["cemetery"]


def test_the_town_before_the_name_disambiguates_too(two_st_marys):
    db, tid = two_st_marys
    assert _ex(db, tid, "auburn st marys").values.get("cemetery") == "St Marys Cemetery"
    assert (
        _ex(db, tid, "skaneateles st marys").values.get("cemetery")
        == "St. Mary's Cemetery"
    )


# ── what must NOT be read as a town ──────────────────────────────────────────────

def test_EQUIPMENT_after_a_cemetery_is_not_a_town(two_st_marys):
    """⚠️ THE REGRESSION THE BARE FORM INVITES, and the reason it narrows strictly. With
    no "in" there is nothing in the text saying a town follows — "st marys tent only"
    matches the bare pattern exactly as well as "st marys skaneateles" does. What tells
    them apart is that a bare word must BE a town we hold a cemetery in.
    """
    db, tid = two_st_marys
    ex = _ex(db, tid, "going to st marys skaneateles tent only")
    assert ex.values.get("cemetery") == "St. Mary's Cemetery", ex.values
    assert ex.values.get("cemetery_equipment") == "tent_only", ex.values


def test_a_FUNERAL_HOME_before_a_cemetery_is_not_a_town(two_st_marys):
    """⚠️ THE CONTROL FOR THE LEADING FORM. A forgiving read of the words before the name
    would take the last one as the town — "order for hopkins st marys" would make
    "hopkins" the town. The leading form is strict by construction for exactly this."""
    db, tid = two_st_marys
    ex = _ex(db, tid, "going to st marys skaneateles")
    assert ex.values.get("cemetery_city") == "Skaneateles"
    # a word that is not a town we hold is left alone entirely
    ex2 = _ex(db, tid, "nowhereville st marys skaneateles")
    assert ex2.values.get("cemetery_city") == "Skaneateles", ex2.values
    assert any("nowhereville" in u.lower() for u in ex2.unrecognized), ex2.unrecognized


# ── case 3, deferred: asserted as deferred rather than left ambiguous ───────────

def test_case_3_is_DEFERRED_and_the_word_surfaces_rather_than_un_answering_the_row(
    two_st_marys,
):
    """⚠️ A TOWN WHERE THAT CEMETERY ISN'T DOES **NOT** ASK YET, BY RULING.

    James deferred case 3 until clause 1 lands, because a city conflict becomes a PICK,
    a pick replaces the value, and the cemetery row would go from filled to a question as
    the next word lands — `test_NO_PREFIX_EVER_LOSES_A_FIELD_IT_HAD`'s whole subject.

    So the bare town is dropped and the WORD IS GIVEN BACK — it surfaces as unplaced,
    which is true and is what the held-word strip is for. Silently swallowing a word the
    engine did not use would be worse than either.

    ⚠️ AND THIS TEST IS THE THING TO DELETE WHEN CLAUSE 1 LANDS, which is why it says so.
    """
    db, tid = two_st_marys
    # Oakwood is in Syracuse; "skaneateles" is a town we hold, but no Oakwood is in it
    ex = _ex(db, tid, "going to oakwood skaneateles")
    assert ex.values.get("cemetery") == "Oakwood Cemetery", ex.values
    assert ex.values.get("cemetery_city") == "Syracuse", ex.values
    assert any("skaneateles" in u.lower() for u in ex.unrecognized), (
        f"the unused town should surface as unplaced, not vanish: {ex.unrecognized}"
    )


def test_the_EXPLICIT_in_form_still_raises_the_conflict(two_st_marys):
    """⚠️ UNTOUCHED BY THE DEFERRAL, AND THAT ASYMMETRY IS THE RULING. The word "in" is
    what says a town follows, so there the director wrote it and meant it — and a
    conflicting town has raised the pick since 2026-10-12."""
    db, tid = two_st_marys
    ex = _ex(db, tid, "going to oakwood in skaneateles")
    assert ex.values.get("cemetery") is None, ex.values
    assert [p.field_id for p in (getattr(ex, "picks", None) or ())] == ["cemetery"], (
        f"the explicit form must still ask: {ex.values}"
    )
