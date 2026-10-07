"""The print resolver returns candidates, never a pick, and never coerces.

⚠️ THE RULING THESE TEST (2026-10-07): resolve typed print names against
Bridgeable's 64; an unmatched name is kept VERBATIM and FLAGGED, never dropped or
coerced. Each half is a separate failure mode and each has its own test — dropping
loses what the director said, coercing invents a different print.

No database. Pure functions over the committed print list.
"""
from __future__ import annotations

import pytest

from app.services.legacy_print_resolver import (
    PrintDiscriminator,
    normalize,
    print_count,
    resolve,
)


def test_the_instrument_sees_the_list():
    """⚠️ THE POSITIVE CONTROL, FIRST. A resolver over an empty list returns "no
    match" for every input, which is exactly what a correct no-match looks like.
    Every absence assertion below is void without this."""
    assert print_count() == 64, f"expected 64 prints, saw {print_count()}"
    assert resolve("Cross — Gold").matched


# ── exact ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("spoken,expected", [
    ("Cross — Gold", "Cross — Gold"),
    ("cross gold", "Cross — Gold"),          # as a director would type it
    ("CROSS  GOLD", "Cross — Gold"),         # casing and doubled space
    ("Irish Blessing", "Irish Blessing"),
    ("Going Home", "Going Home"),
    ("Whitetail Buck", "Whitetail Buck"),
])
def test_an_exact_name_resolves_to_one_print(spoken, expected):
    r = resolve(spoken)
    assert r.print_name == expected
    assert r.phrase == spoken, "the input must survive unchanged"


def test_the_ampersand_name_resolves_from_either_spelling():
    """`Green Field & Barn` — the portal calls it `Field and Barn`, so both the
    symbol and the word have to reach it."""
    assert resolve("Green Field & Barn").print_name == "Green Field & Barn"
    assert resolve("green field and barn").print_name == "Green Field & Barn"


# ── ambiguity is a question, not a failure ──────────────────────────────

def test_a_shared_base_name_returns_the_SET_and_names_the_finish_question():
    """⚠️ THE CENTRAL CONTRACT. Three crosses exist. Returning one of them would
    put a print on a vault nobody chose."""
    r = resolve("Cross")

    assert len(r.candidates) == 3, [c.name for c in r.candidates]
    assert r.print_name is None, "the resolver picked when it should have asked"
    assert PrintDiscriminator.FINISH in r.discriminators


def test_numbered_variants_are_named_as_a_variant_question():
    r = resolve("Jewish")
    assert {c.name for c in r.candidates} == {"Jewish 1", "Jewish 2"}
    assert r.discriminators == (PrintDiscriminator.VARIANT,)


def test_a_word_shared_by_unrelated_prints_is_classified_as_unrelated():
    """⚠️ THE DISCRIMINATOR MUST DISCRIMINATE. If every multi-candidate result said
    FINISH, the caller would ask "which finish?" about two different pictures.

    ⚠️ I PICKED THE WRONG EXAMPLE TWICE AND BOTH TIMES THE RESOLVER WAS RIGHT.
    `blessing` returns `Irish Blessing` / `— No Poem`, which share a base and are a
    finish pair. `marble` returns only `Marble — Gold` / `— White`, because the
    prefix pass catches it and stops — also a finish pair. An unrelated case needs a
    word that appears MID-NAME across different pictures, which only the third pass
    reaches. `gold` is that: a cross, a marble, a stained glass and a star of David.
    """
    r = resolve("stained glass")
    assert len(r.candidates) == 2
    assert PrintDiscriminator.FINISH in r.discriminators

    r2 = resolve("gold")
    assert len(r2.candidates) == 4, [c.name for c in r2.candidates]
    assert r2.discriminators == (PrintDiscriminator.UNRELATED,), (
        f"{[c.name for c in r2.candidates]} classified as {r2.discriminators}"
    )


# ── unmatched: kept verbatim, flagged, never coerced ────────────────────

@pytest.mark.parametrize("spoken", [
    "U.S. Flag",                 # the portal's urn-list name for American Flag
    "Crucifix on Bible",         # the portal's urn-list name for Crucifix — Bible
    "Tropical Island",           # the portal's urn-list name for Tropical
    "Sunrise-Sunset 1",          # the portal's urn-list numbering
    "something nobody printed",
])
def test_an_unmatched_name_is_KEPT_and_FLAGGED_not_coerced(spoken):
    """⚠️ EVERY CASE HERE IS A REAL PORTAL NAME EXCEPT THE LAST. These are not
    hypothetical typos: the portal's two lists and Bridgeable's disagree by 14 names
    each way, so until the Wilbert poster arrives these ARRIVE on calls and must
    survive. Coercing `U.S. Flag` to `American Flag` would be a guess recorded as a
    fact; dropping it would lose what the director said.
    """
    r = resolve(spoken)

    assert r.matched is False, (
        f"{spoken!r} matched {[c.name for c in r.candidates]} — the resolver "
        f"coerced a name the list does not contain"
    )
    assert r.print_name is None
    assert r.phrase == spoken, "the unmatched phrase was not kept verbatim"


def test_the_near_miss_pair_is_the_control_on_coercion():
    """⚠️ THE DISCRIMINATING PAIR. `American Flag` IS on the list and `U.S. Flag` is
    not, and they are the same picture. A resolver with any fuzzy distance would
    match both and this test is what fails."""
    assert resolve("American Flag").print_name == "American Flag"
    assert resolve("U.S. Flag").matched is False


def test_sibling_prints_one_edit_apart_are_never_conflated():
    """`Bridge 1` and `Bridge 2` differ by one character and are different prints.
    The reason this resolver has no edit distance."""
    assert resolve("Bridge 1").print_name == "Bridge 1"
    assert resolve("Bridge 2").print_name == "Bridge 2"
    assert len(resolve("Bridge").candidates) == 2


# ── degenerate input ────────────────────────────────────────────────────

@pytest.mark.parametrize("spoken", [None, "", "   ", "!!!"])
def test_empty_input_matches_nothing_and_does_not_raise(spoken):
    r = resolve(spoken)
    assert r.matched is False
    assert r.print_name is None


def test_normalize_trims_before_stripping_punctuation():
    """⚠️ ORDER-OF-OPERATIONS REGRESSION GUARD. Stripping punctuation first leaves a
    separator behind on trailing whitespace — measured in `normalizeRequest`
    2026-10-03. `Cross — Gold ` must normalize identically to `Cross — Gold`."""
    assert normalize("Cross — Gold ") == normalize("Cross — Gold")
    assert normalize("  Jesus at Dawn  ") == normalize("Jesus at Dawn")
