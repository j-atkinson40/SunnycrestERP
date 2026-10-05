"""Resolving a spoken product phrase to catalog variants.

⚠️ THE CLAIM UNDER TEST IS THAT IT NEVER PICKS. Eight of fifty-two variants are
not uniquely reachable by their own display name, and the measured consequence of
a best match is specific: `"cream and gold"` matches P300 (Regal) and P310
(Tribute urn), P300 sorts first, so a picking resolver sells the Regal silently on
every funeral order.

⚠️ AND REPORTING THE RIGHT KIND OF AMBIGUITY IS A SEPARATE CLAIM FROM REPORTING
ONE. A resolver that called every ambiguity `OPTION` would satisfy any test that
only checked "is it ambiguous" — and only the kind makes the question usable.
`TestEachDiscriminatorKind` gives each kind a case that fires on it alone.

⚠️ COLD PATH. Nothing calls this; the vault phrase arrives from an overlay with no
production entrance. Constructed phrases against the REAL catalog — so the
candidate skus are facts, not fixtures.
"""
from __future__ import annotations

import pytest

from app.database import SessionLocal
from app.services.product_name_resolver import (
    Discriminator,
    build_index,
    normalize,
    resolve,
)


@pytest.fixture(scope="module")
def index():
    db = SessionLocal()
    try:
        return build_index(db)
    finally:
        db.close()


class TestTheIndexIsReal:
    def test_it_indexed_something(self, index):
        """⚠️ POSITIVE CONTROL. Every NO-MATCH assertion below is vacuous against
        an empty index, and an empty index is what a broken query returns."""
        assert len(index.by_form) > 100, len(index.by_form)

    def test_the_alias_table_contributed(self, index):
        """⚠️ A CORRECTNESS REQUIREMENT, NOT AN OPTIMISATION. Three variants are
        reachable ONLY through alias rows; a zero here means they are
        unresolvable and the three assertions below would fail for that reason
        rather than a matching one."""
        assert index.alias_count > 0


class TestItNeverPicks:
    def test_an_ambiguous_phrase_returns_the_whole_set(self, index):
        r = resolve(index, "Cream & Gold")
        assert r.ambiguous
        assert {c.sku for c in r.candidates} == {"P300", "P310"}

    def test_variant_template_id_is_None_when_ambiguous(self, index):
        """⚠️ THE DISCRIMINATING ASSERTION OF THE WHOLE MODULE. Returning the
        first candidate here is exactly the defect: P300 sorts before P310, so a
        caller reaching for an id would get the Regal every time and never know a
        choice existed."""
        r = resolve(index, "Cream & Gold")
        assert r.variant_template_id is None

    def test_variant_template_id_is_the_id_when_resolved(self, index):
        """⚠️ THE CONTROL. A property that always returned None would satisfy the
        test above."""
        r = resolve(index, "Monarch")
        assert r.resolved
        assert r.variant_template_id == r.candidates[0].variant_template_id

    def test_an_unmatched_phrase_is_empty_and_asks_nothing(self, index):
        r = resolve(index, "a vault nobody sells")
        assert r.unmatched
        assert r.discriminator is None
        assert r.variant_template_id is None


class TestEachDiscriminatorKind:
    """⚠️ ONE CASE PER KIND, EACH FIRING ON THAT KIND ALONE. A resolver reporting
    a single kind for everything is indistinguishable from a correct one unless
    the kinds are pinned separately."""

    @pytest.mark.parametrize("phrase,kind,skus", [
        # burial vs urn — same family, same option
        ("Bronze Triune", Discriminator.FORM, {"BV-BTRI", "UV-BTRI"}),
        # the same finish in two product lines
        ("Cream & Gold", Discriminator.LINE, {"P300", "P310"}),
        # Standard vs 34 inch — a size question wearing an option column
        ("Continental", Discriminator.SIZE, {"BV-CON", "BV-CON34"}),
        # finishes within one product, no size among them
        ("Tent", Discriminator.OPTION, {"CE-TD", "CE-TS"}),
    ])
    def test_the_kind_is_classified_from_what_differs(self, index, phrase, kind, skus):
        r = resolve(index, phrase)
        assert r.ambiguous, phrase
        assert {c.sku for c in r.candidates} == skus
        assert r.discriminator is kind, (
            f"{phrase!r} reported {r.discriminator} — the question an operator "
            f"would ask is {kind.value}"
        )

    def test_a_size_pair_whose_labels_are_all_numeric_is_also_SIZE(self, index):
        """Loved & Cherished is 19"/24"/31" — every label a size, where
        Continental mixes `Standard` with `34 inch`. Both must read SIZE."""
        r = resolve(index, "Loved & Cherished")
        assert {c.sku for c in r.candidates} == {"LC-19", "LC-24", "LC-31"}
        assert r.discriminator is Discriminator.SIZE

    def test_precedence_puts_FORM_first_when_several_attributes_differ(self, index):
        """Graveliner spans grave_liner and urn_vault AND several sizes. Both
        differ, so `discriminators` holds both and FORM is asked first."""
        r = resolve(index, "Graveliner")
        assert len(r.candidates) > 2
        assert r.discriminator is Discriminator.FORM
        assert Discriminator.FORM in r.discriminators
        assert len(r.discriminators) > 1, (
            "only one attribute differs — this case no longer tests precedence"
        )


class TestTheSuffixStrip:
    @pytest.mark.parametrize("phrase,skus", [
        ("Bronze Triune Urn Vault", {"UV-BTRI"}),
        ("Bronze Triune Burial Vault", {"BV-BTRI"}),
    ])
    def test_the_full_name_still_resolves_uniquely(self, index, phrase, skus):
        """⚠️ THE CONTROL ON THE STRIP. Stripping suffixes must not make the FULL
        names ambiguous — they are the forms that already worked."""
        r = resolve(index, phrase)
        assert r.resolved, (phrase, [c.sku for c in r.candidates])
        assert {c.sku for c in r.candidates} == skus

    def test_the_bare_family_phrase_reaches_candidates(self, index):
        """Before the strip this matched nothing. Two candidates is a question;
        no match is a dead end."""
        assert resolve(index, "Monticello").candidates


class TestNormalisation:
    @pytest.mark.parametrize("phrase", [
        'Continental 34"', "Continental 34 inch", "continental 34in",
        "CONTINENTAL 34 INCHES", "Continental  34  inch",
    ])
    def test_size_spellings_all_reach_the_same_variant(self, index, phrase):
        r = resolve(index, phrase)
        assert {c.sku for c in r.candidates} == {"BV-CON34"}, (
            phrase, [c.sku for c in r.candidates])

    def test_ampersands_and_inch_marks_survive_normalisation(self):
        """⚠️ They DISTINGUISH real entries — `Cream & Gold`, `Continental 34"` —
        so stripping them would merge variants."""
        assert normalize("Cream & Gold") == "cream & gold"
        assert normalize('Continental 34"') == 'continental 34"'

    def test_trademark_marks_and_smart_quotes_fold_away(self):
        assert normalize("Legacy Series™ Print") == "legacy series print"
        assert normalize('Graveliner 34”') == 'graveliner 34"'

    def test_an_empty_or_none_phrase_matches_nothing(self, index):
        for p in ("", "   ", None):
            r = resolve(index, p)
            assert r.unmatched and r.discriminator is None


class TestTheAliasTableIsTheOnlyRoute:
    @pytest.mark.parametrize("phrase,sku", [
        ("Veteran", "BV-VTRI"),
        ("SST", "BV-SSTRI"),
        ("Basic Gray", "UV-SAL"),
    ])
    def test_three_variants_resolve_only_via_aliases(self, index, phrase, sku):
        """⚠️ NOTHING IN THESE VARIANTS' OWN NAMES REACHES THEM. `Basic Gray` is
        the clearest: the variant is `Salute Urn Vault`, and the two strings share
        no word. Drop the alias read and these three become unresolvable."""
        r = resolve(index, phrase)
        assert r.resolved, (phrase, [c.sku for c in r.candidates])
        assert r.candidates[0].sku == sku

    def test_a_phrase_the_catalog_does_not_name_is_a_clean_no_match(self, index):
        """⚠️ WORKING AS DESIGNED, NOT A BUG. "Cemetery Tent" is a PREFIX of
        `Cemetery Tent - Single`/`- Double`, and prefix matching would make "Tent"
        match everything containing the word with the nearest hit winning. The
        remedy is an alias row, confirmed once by a human."""
        r = resolve(index, "Cemetery Tent")
        assert r.unmatched
