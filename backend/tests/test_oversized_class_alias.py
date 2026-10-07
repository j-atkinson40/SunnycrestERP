"""`oversized` as a class alias — r206, through the resolver and through the seam.

⚠️ THE RULING (James, 2026-10-07). `oversized | oversize | OS | O/S | OVS`, on word
boundaries only, narrow to BV-CON34, GL-34 and GL-38 and ASK. With a family name they
narrow within it ("oversized Continental" -> BV-CON34). A bare number after a family
name is accepted ("Continental 34").

⚠️ NO RESOLVER MECHANISM WAS ADDED. `platform_product_aliases` is UNIQUE on
`(variant_template_id, alias_text_normalized)` rather than on the text, so one alias
may carry several variants and `build_index` accumulates them. Every clause above is
rows. That is the whole of r206, and it is why these tests read the catalog rather
than a constructed index.

⚠️ CONTROLS FIRST, AND THE ONE THAT MATTERS IS THE WORD-BOUNDARY CONTROL. "`os` does
not fire inside `Boston`" is satisfied by an index that has never heard of `os` —
the same green a missing alias produces. So the boundary test asserts the alias IS
PRESENT in `by_form` before it asserts the non-match, and the number it reads first
is non-zero.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture.typed_extraction import EXTRACTOR
from app.services.product_name_resolver import (
    Discriminator,
    build_index,
    named_form,
    normalize,
    resolve,
)

#: The ruled forms. ⚠️ "O/S" folds to `o s`, not `os` — the slash becomes a space —
#: so it is a second key and not a spelling of the first.
CLASS_FORMS = ("oversized", "oversize", "OS", "O/S", "OVS")

#: The oversized class, as ruled.
CLASS_SKUS = {"BV-CON34", "GL-34", "GL-38"}


def _refuse_a_non_local_database() -> None:
    """Host only — never the credential. This file only reads, but the guard is
    cheap and a reader should not have to check."""
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
def idx(db):
    return build_index(db)


@pytest.fixture(scope="module")
def tenant(db) -> str:
    tid = db.execute(text("SELECT id FROM companies WHERE slug = 'testco'")).scalar()
    assert tid, "testco is not seeded — run scripts/seed_dev.sh"
    return tid


def _skus(idx, phrase: str) -> set[str]:
    return {c.sku for c in resolve(idx, phrase).candidates}


# ── controls ────────────────────────────────────────────────────────────

def test_the_index_and_the_alias_table_are_both_populated(idx):
    """⚠️ READ THESE TWO NUMBERS BEFORE ANY NON-MATCH BELOW IS ALLOWED TO MEAN
    ANYTHING. Over an empty catalog or an empty alias table every assertion in this
    file reports a correct-looking miss."""
    assert len(idx.by_form) > 100, f"only {len(idx.by_form)} surface forms indexed"
    assert idx.alias_count >= 53, (
        f"alias_count is {idx.alias_count}; r206 adds 48 to the 5 from r189, so a "
        f"lower number means the migration has not run and the class is unreachable"
    )


def test_every_oversized_variant_exists_in_the_catalog(idx):
    """The class is three SKUs. If one were absent the class alias would be
    narrower than the ruling and nothing else here would say so."""
    present = {c.sku for forms in idx.by_form.values() for c in forms}
    assert CLASS_SKUS <= present, CLASS_SKUS - present


# ── the class, bare ─────────────────────────────────────────────────────

@pytest.mark.parametrize("form", CLASS_FORMS)
def test_the_bare_class_reaches_exactly_the_three_and_asks(idx, form):
    r = resolve(idx, form)
    assert {c.sku for c in r.candidates} == CLASS_SKUS, sorted(
        c.sku for c in r.candidates
    )
    assert r.ambiguous and not r.resolved
    # ⚠️ `variant_template_id` MUST BE None. The whole point of the ruling is that
    # the pane asks; a resolver handing back the first of three would sell a
    # Continental to a caller who said "oversized" and meant a graveliner.
    assert r.variant_template_id is None
    # FORM first: burial vault or grave liner is the largest distinction and the one
    # the caller's own words usually settle.
    assert r.discriminator is Discriminator.FORM, r.discriminators


def test_the_two_abbreviation_spellings_are_distinct_keys(idx):
    """⚠️ RECORDED BECAUSE IT LOOKS LIKE A BUG AND IS NOT. `normalize` turns the
    slash into a space, so "O/S" is the key `o s`. Both were written as rows; a
    future fold that collapsed them would trip r206's unique constraint, which is
    asserted inside the migration."""
    assert normalize("OS") == "os"
    assert normalize("O/S") == "o s"
    assert _skus(idx, "OS") == _skus(idx, "O/S") == CLASS_SKUS


# ── the class with a family name ────────────────────────────────────────

@pytest.mark.parametrize("form", CLASS_FORMS)
def test_class_plus_continental_resolves_uniquely(idx, form):
    r = resolve(idx, f"{form} Continental")
    assert r.resolved, sorted(c.sku for c in r.candidates)
    assert r.candidates[0].sku == "BV-CON34"
    assert r.discriminators == ()


@pytest.mark.parametrize("form", CLASS_FORMS)
@pytest.mark.parametrize("family", ("Graveliner", "Grave Liner"))
def test_class_plus_graveliner_narrows_to_two_and_asks_the_size(idx, form, family):
    """⚠️ BOTH SPELLINGS, BECAUSE THE CATALOG ALREADY ACCEPTS BOTH. r189 confirmed
    "Grave Liner" (two words) against GL-STD, so leaving the two-word form dead
    here would be an inconsistency r206 introduced rather than inherited."""
    r = resolve(idx, f"{form} {family}")
    assert {c.sku for c in r.candidates} == {"GL-34", "GL-38"}, sorted(
        c.sku for c in r.candidates
    )
    assert r.variant_template_id is None
    assert r.discriminator is Discriminator.SIZE, r.discriminators


# ── a bare number after a family name ───────────────────────────────────

@pytest.mark.parametrize("phrase,sku", [
    ("Continental 34", "BV-CON34"),
    ("Graveliner 34", "GL-34"),
    ("Graveliner 38", "GL-38"),
    ("Grave Liner 38", "GL-38"),
    ("Loved & Cherished 19", "LC-19"),
    ("Loved & Cherished 24", "LC-24"),
    ("Loved & Cherished 31", "LC-31"),
])
def test_a_bare_number_after_a_family_name_resolves(idx, phrase, sku):
    r = resolve(idx, phrase)
    assert r.resolved, f"{phrase!r} -> {sorted(c.sku for c in r.candidates)}"
    assert r.candidates[0].sku == sku


def test_the_unit_bearing_form_still_resolves(idx):
    """⚠️ THE PRE-EXISTING PATH, PINNED. `option_label + product_name` already put
    `34" continental` in the index, so "34 inch Continental" worked before r206. If
    an alias row ever shadowed it this would be the test that noticed."""
    for phrase in ('Continental 34"', "Continental 34in", "34 inch Continental"):
        r = resolve(idx, phrase)
        assert r.resolved and r.candidates[0].sku == "BV-CON34", phrase


def test_every_size_bearing_variant_has_a_bare_number_alias(db, idx):
    """⚠️ A RATCHET OVER THE CLOSED SET r206 CLAIMS. The migration's whole argument
    for data over a mechanism is that size-bearing variants are a closed set of six.
    If a seventh is added, this fails and names it, rather than the new variant
    silently being unreachable by the form a person types."""
    sized = db.execute(text("""
        SELECT v.sku, v.option_label, t.display_name
        FROM product_variant_templates v
        JOIN product_templates t ON t.id = v.product_template_id
        WHERE v.is_active IS TRUE AND v.option_label ~ '^[0-9]'
    """)).all()
    assert sized, "no size-labelled variants found — this ratchet is measuring nothing"
    missing = []
    for sku, option_label, product_name in sized:
        number = normalize(option_label).rstrip('"')
        family = product_name
        for suffix in (" Burial Vault", " Urn Vault", " Vault"):
            if family.endswith(suffix):
                family = family[: -len(suffix)]
        bare = f"{family} {number}"
        if _skus(idx, bare) != {sku}:
            missing.append((sku, bare, sorted(_skus(idx, bare))))
    assert not missing, (
        f"these size-bearing variants are not reachable by a bare number: {missing}"
    )


# ── word boundaries ─────────────────────────────────────────────────────

@pytest.mark.parametrize("phrase", [
    "Boston", "cosmos", "Rosewood", "osprey", "Oscar", "overseas",
    "ovsomething", "boss", "oversize-ish",
])
def test_a_class_alias_does_not_fire_inside_another_word(idx, phrase):
    """⚠️ THE CONTROL IS THE FIRST ASSERTION AND IT IS LOAD-BEARING. An index with
    no `os` key passes the second assertion for the wrong reason, and that green is
    indistinguishable from this one. So: prove the key is there, THEN prove the
    longer word misses it.

    ⚠️ AND THE GUARANTEE IS THE EXACT LOOKUP, NOT A `\\b` ANYWHERE. `resolve` looks
    the whole normalised phrase up in `by_form`; there is no substring path for a
    short alias to fire through. Break-tested by replacing that lookup with a
    substring scan — see the commit body.
    """
    assert "os" in idx.by_form, "the `os` alias is absent; this test proves nothing"
    assert "ovs" in idx.by_form, "the `ovs` alias is absent; this test proves nothing"
    assert "oversize" in idx.by_form
    assert resolve(idx, phrase).candidates == (), (
        f"{phrase!r} reached {sorted(c.sku for c in resolve(idx, phrase).candidates)}"
    )


# ── through the seam ────────────────────────────────────────────────────

def test_a_director_typing_oversized_gets_a_numbered_pick(db, tenant):
    """⚠️ THROUGH `EXTRACTOR.extract_line`, NOT THE RESOLVER. The seam strips noise
    words from the leftover fragment, so "we need an oversized vault" arrives at the
    resolver as "oversized" — and that reduction is part of what is being asserted.
    Testing the resolver alone would leave it unmeasured."""
    ex = EXTRACTOR.extract_line(
        db, tenant_id=tenant, line="we need an oversized vault", answers={}
    )
    assert "vault" not in ex.values, "'oversized' was coerced to a single vault"
    picks = [p for p in ex.picks if p.field_id == "vault"]
    assert len(picks) == 1, ex.picks
    assert len(picks[0].options) == 3, picks[0].options
    assert {label.split(" — ")[0] for _, label in picks[0].options} == CLASS_SKUS
    assert picks[0].discriminator == Discriminator.FORM.value, picks[0].discriminator


def test_a_director_typing_oversized_continental_gets_the_vault(db, tenant):
    ex = EXTRACTOR.extract_line(
        db, tenant_id=tenant, line="an oversized Continental", answers={}
    )
    assert ex.values.get("vault") == 'Continental 34"', ex.values
    assert not ex.picks
    assert not ex.unrecognized, ex.unrecognized


def test_a_director_typing_a_bare_number_gets_the_vault(db, tenant):
    ex = EXTRACTOR.extract_line(
        db, tenant_id=tenant, line="Continental 34", answers={}
    )
    assert ex.values.get("vault") == 'Continental 34"', ex.values


# ── the stored normalised column is not what the resolver reads ─────────

def test_the_stored_normalised_column_agrees_with_normalize(db):
    """⚠️ A SEAM NOTHING ELSE WATCHES. `build_index` folds `alias_text` itself; the
    stored `alias_text_normalized` feeds only the unique constraint. So the two can
    disagree and no resolution changes — the column just stops being true. r206
    computes it with a local copy of the fold on purpose (a migration importing app
    code stops being reproducible when that code moves), and this is the check that
    holds them together. Covers the five r189 rows as well."""
    rows = db.execute(text(
        "SELECT alias_text, alias_text_normalized FROM platform_product_aliases"
    )).all()
    assert len(rows) >= 53, f"only {len(rows)} alias rows; r206 has not run"
    bad = [
        (t, stored, normalize(t)) for t, stored in rows if normalize(t) != stored
    ]
    assert not bad, f"stored normalisation disagrees with normalize(): {bad}"


# ── the defect r206 found, now fixed (ruled 2026-10-07) ─────────────────

@pytest.mark.parametrize("phrase,sku", [
    ("Veteran urn vault", "UV-VET"),
    ("SST urn vault", "UV-SSTRI"),
    ("Cameo Rose urn vault", "UV-CRTRI"),
])
def test_a_form_naming_query_reaches_that_form(idx, phrase, sku):
    """⚠️ THIS TEST USED TO ASSERT THE OPPOSITE, AND THE OLD WORDING IS THE POINT.

    Until 2026-10-07 it was `test_WRONGNESS_a_form_suffix_is_stripped_and_the_alias_
    ignores_form`, pinning that "Veteran urn vault" resolved — uniquely, with no
    discriminator — to BV-VTRI, the BURIAL vault, while UV-VET existed. Two things
    composed: `_strip_suffix` removed " urn vault" from the query so a family phrase
    could reach its variants, and the r189 alias `veteran` named only the burial
    variant. The strip deleted the single most important discriminator and the alias
    had nothing else to offer.

    James ruled the fix on 2026-10-07. It took BOTH halves, and the code half alone
    would have looked like a fix while being a downgrade: `named_form` in the resolver
    makes the wrong answer impossible, but turns it into NO MATCH, because nothing
    reaches UV-VET from the word "veteran". r207 adds the three counterpart rows.
    """
    r = resolve(idx, phrase)
    assert r.resolved, f"{phrase!r} -> {sorted(c.sku for c in r.candidates)}"
    assert r.candidates[0].sku == sku


@pytest.mark.parametrize("phrase,sku", [
    ("Veteran burial vault", "BV-VTRI"),
    ("SST burial vault", "BV-SSTRI"),
    ("Cameo Rose burial vault", "BV-CRTRI"),
    ("Bronze Triune burial vault", "BV-BTRI"),
])
def test_the_burial_side_of_the_same_phrase_still_reaches_the_burial_vault(idx, phrase, sku):
    """⚠️ THE OTHER DIRECTION, BECAUSE A FILTER THAT ONLY EVER NARROWS TOWARD URNS
    WOULD PASS EVERY TEST ABOVE. These were already correct before the fix, which is
    exactly why they are the control on it."""
    r = resolve(idx, phrase)
    assert r.resolved and r.candidates[0].sku == sku, sorted(
        c.sku for c in r.candidates
    )


@pytest.mark.parametrize("phrase", [
    "oversized urn vault",
    "Continental urn vault",
    "Basic Gray burial vault",
    "Grave Liner urn vault",
])
def test_a_form_with_no_member_is_NO_MATCH_never_the_other_form(idx, phrase):
    """⚠️ THE RULED GUARANTEE: "if none survive, NO MATCH, never the other form."

    There is no oversized urn vault and no Continental urn vault. Before the fix both
    returned burial vaults — three candidates and two respectively — so a director who
    said "urn vault" was offered burial vaults and the resolver called it an answer.
    """
    assert resolve(idx, phrase).candidates == (), sorted(
        c.sku for c in resolve(idx, phrase).candidates
    )


@pytest.mark.parametrize("phrase,skus", [
    ("Veteran", {"BV-VTRI", "UV-VET"}),
    ("SST", {"BV-SSTRI", "UV-SSTRI"}),
    ("Cameo Rose", {"BV-CRTRI", "UV-CRTRI"}),
])
def test_the_bare_alias_now_ASKS_instead_of_answering_silently(idx, phrase, skus):
    """⚠️ A DELIBERATE LOSS OF A UNIQUE ANSWER. Before r207 "Veteran" resolved to
    BV-VTRI alone — not because anything had decided the caller meant a burial vault,
    but because the alias only knew one. That is the module's own worked example
    ("Bronze Triune — burial or urn vault?") and it was going the wrong way."""
    r = resolve(idx, phrase)
    assert {c.sku for c in r.candidates} == skus, sorted(c.sku for c in r.candidates)
    assert r.variant_template_id is None
    assert r.discriminator is Discriminator.FORM


def test_a_bare_word_that_is_also_a_form_name_is_not_a_form_claim(idx):
    """"graveliner" alone is a FAMILY phrase spanning two forms, so it keeps
    returning all five — including UV-GL, the urn vault — and the discriminator asks.

    ⚠️ THE CAUSE IS THE LENGTH CHECK, NOT THE LEADING SPACE, AND THIS DOCSTRING SAID
    THE OPPOSITE UNTIL A BREAK TEST DISPROVED IT. Dropping the space from
    `(" graveliner", ...)` left this test GREEN — `len(n) > len(suf)` is false either
    way when the phrase IS the suffix. The two guards are separated into
    `test_named_form_*` below, each with its own firing break.
    """
    r = resolve(idx, "graveliner")
    skus = {c.sku for c in r.candidates}
    assert skus == {"GL-34", "GL-38", "GL-SS", "GL-STD", "UV-GL"}, sorted(skus)


@pytest.mark.parametrize("phrase", [
    # the phrase IS the suffix, with no preceding word
    "graveliner", "urn vault", "burial vault", "grave liner",
    # the suffix is the tail of a longer word, with no word boundary
    "pseudograveliner", "xgrave liner", "myurn vault",
])
def test_named_form_is_None_without_a_word_boundary_before_the_suffix(phrase):
    """⚠️ ONE GUARD, NOT TWO, AND TWO BREAK TESTS ARE WHY THIS IS ONE FUNCTION.

    These were split across two tests on the theory that `len(n) > len(suf)` covered
    the bare word and the leading space covered the longer word. Breaking the LENGTH
    CHECK left all 106 tests green: with the space in place, `endswith(suf)` and
    `len(n) == len(suf)` would require the phrase to BE " graveliner", and `normalize`
    never returns a leading space. The leading space is the single operative guard for
    both input classes, and it is break-tested — dropping the spaces turns the last
    three rows here red.

    The length check stays as insurance on that comment and is labelled DEFENSIVE in
    the source. ⚠️ Do not read this test as covering it; nothing does.
    """
    assert named_form(phrase) is None, named_form(phrase)


@pytest.mark.parametrize("phrase,form", [
    ("oversized graveliner", "grave_liner"),
    ("oversized grave liner", "grave_liner"),
    ("veteran urn vault", "urn_vault"),
    ("veteran burial vault", "burial_vault"),
    ("x burial liner", "grave_liner"),
])
def test_named_form_reads_a_real_form_claim(phrase, form):
    """⚠️ THE POSITIVE CONTROL ON BOTH GUARDS. Without this, a `named_form` that
    returned None for everything would satisfy the two tests above."""
    assert named_form(phrase) == form, named_form(phrase)


def test_vault_alone_names_no_form(idx):
    """⚠️ " vault" IS DELIBERATELY NOT IN `_FORM_SUFFIXES`. A vault may be burial or
    urn, so the word names nothing and must not filter. If it were added, "oversized
    vault" would quietly become a burial-vault query."""
    r = resolve(idx, "oversized vault")
    assert {c.sku for c in r.candidates} == CLASS_SKUS, sorted(
        c.sku for c in r.candidates
    )


def test_the_alias_form_exposure_list_is_exactly_what_was_ruled(db):
    """⚠️ A RATCHET OVER THE ENUMERATION, so a new alias cannot reintroduce the shape.

    An alias is EXPOSED when it reaches a variant whose counterpart — same
    `family_slug`, same `option_label`, a different `form` — it does not reach. That
    relation is the one that matters; grouping by family alone reports 24 false
    positives, because `triune` holds ten variants and `graveliner` five.

    Measured 2026-10-07 over all confirmed rows: four exposed, three fixed by r207.
    `Basic Gray` is the fourth and is NOT a defect — its r189 note records that
    Wilbert lists one product as "Basic Gray/Salute Urn Vault" and the owner confirmed
    ONE product on 2026-10-02, so the phrase names the urn vault specifically. Adding
    BV-SAL would make a settled name ambiguous on the strength of a shape match.
    """
    from collections import defaultdict

    variants = db.execute(text("""
        SELECT v.id, v.sku, v.option_label, t.family_slug, t.form
        FROM product_variant_templates v
        JOIN product_templates t ON t.id = v.product_template_id
        WHERE v.is_active IS TRUE
    """)).all()
    assert len(variants) > 40, f"only {len(variants)} variants — this ratchet is blind"
    by_key = defaultdict(list)
    for v in variants:
        by_key[(v.family_slug, (v.option_label or "").casefold())].append(v)
    vid = {v.id: v for v in variants}

    rows = db.execute(text(
        "SELECT alias_text, alias_text_normalized, variant_template_id "
        "FROM platform_product_aliases WHERE is_confirmed IS TRUE"
    )).all()
    assert len(rows) >= 56, f"only {len(rows)} alias rows; r206+r207 have not both run"
    reached = defaultdict(set)
    texts = {}
    for atext, anorm, v_id in rows:
        reached[anorm].add(v_id)
        texts[anorm] = atext

    exposed = {}
    for anorm, vids in reached.items():
        missing = {
            sib.sku
            for v_id in vids
            for sib in by_key[(vid[v_id].family_slug,
                               (vid[v_id].option_label or "").casefold())]
            if sib.form != vid[v_id].form and sib.id not in vids
        }
        if missing:
            exposed[texts[anorm]] = sorted(missing)

    assert exposed == {"Basic Gray": ["BV-SAL"]}, (
        f"the alias form-exposure list changed. Expected only the ruled exception "
        f"(Basic Gray, deliberate). Got: {exposed}"
    )
