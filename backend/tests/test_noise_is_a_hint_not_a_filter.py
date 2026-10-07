"""Noise-word removal is a HINT, not a filter — the rule, and the two reports it closes.

⚠️ THE RULE, STATED ONCE AND TESTED GENERALLY RATHER THAN CASE BY CASE.

    For each unclaimed fragment the vault pass resolves BOTH readings — the
    noise-stripped one and the fragment exactly as the director typed it — and keeps
    the stripped one only while it is at least as narrow. If the raw reading reaches
    FEWER candidates, the raw reading wins. Removing a noise word may never cost the
    director information they supplied.

    Separately: "and" is a spelling of "&". One-directionally, word -> symbol,
    because every ampersand-bearing name in the catalog stores the symbol.

⚠️ WHY A RULE RATHER THAN TWO FIXES. `_NOISE_WORDS` holds words a director says AROUND
a value, and three of them are also words INSIDE catalog names — `cemetery`, `burial`,
`vault`, measured 2026-10-07 across all 52 active variants. Stripping `burial` and
`vault` is load-bearing: it is what lets "Continental Burial Vault" reach the family
phrase. So the list is right and the removal is right; what was wrong was treating the
result as the only reading.

The two reports:

    "Loved and Cherished 24"  -> unrecognized.  "and" was stripped, and the catalog
                                spells the name with "&", so neither reading matched.
    "cemetery tent single"    -> unrecognized.  "cemetery" was stripped, and it is the
                                first word of the only two variants named
                                "Cemetery Tent - ...".

⚠️ AND THE GENERAL TEST IS THE ONE THAT MATTERS: every active variant is reachable by
its OWN DISPLAY NAME through the seam. Two cases would have been two patches; this is
the claim, and it fails by name if a future noise word eats a product name.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture.typed_extraction import (
    _NOISE_WORDS,
    _leftover_pairs,
    _narrower,
    EXTRACTOR,
)
from app.services.product_name_resolver import build_index, normalize, resolve


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
def variant_names(db) -> list[str]:
    names = [r[0] for r in db.execute(text(
        "SELECT display_name FROM product_variant_templates WHERE is_active IS TRUE"
    ))]
    assert len(names) > 40, f"only {len(names)} variants — every test here is void"
    return names


def _vault(db, tenant, line: str):
    ex = EXTRACTOR.extract_line(db, tenant_id=tenant, line=line, answers={})
    opts = [o[0] for p in ex.picks if p.field_id == "vault" for o in p.options]
    return ex.values.get("vault"), opts, list(ex.unrecognized)


# ── controls ────────────────────────────────────────────────────────────

def test_the_noise_list_really_does_contain_product_words(variant_names):
    """⚠️ THE PREMISE OF THIS WHOLE FILE, ASSERTED RATHER THAN ASSUMED. If no noise
    word were ever inside a product name there would be nothing to recover and every
    test below would pass for the wrong reason."""
    inside = {
        w for w in _NOISE_WORDS
        for n in variant_names
        if f" {w} " in f" {n.casefold()} "
    }
    assert inside, "no noise word appears inside any product name"
    # Measured 2026-10-07. Stated as a subset check, not equality, so adding a noise
    # word that happens to be a product word does not fail here — it fails in
    # `test_every_variant_is_reachable_by_its_own_display_name`, which is the test
    # that can say what broke.
    assert {"cemetery", "burial", "vault"} <= inside, sorted(inside)


# ── the rule, stated generally ──────────────────────────────────────────

def test_every_variant_is_reachable_by_its_own_display_name(db, tenant, variant_names):
    """⚠️ THE RULE AS ONE CLAIM OVER ALL 52 VARIANTS, not two cases.

    A director typing a product's own name must reach it — resolved, or among the
    options of a pick when the name is genuinely shared (`Cream & Gold` is both P300
    and P310). Before the fix this failed on the two `Cemetery Tent - ...` variants,
    because `cemetery` is in the noise list and is the first word of their names.
    """
    unreachable = []
    for name in variant_names:
        got, opts, unrec = _vault(db, tenant, name)
        if got != name and name not in opts:
            unreachable.append((name, got, opts, unrec))
    assert not unreachable, (
        f"{len(unreachable)} variants are not reachable by their own display name: "
        f"{unreachable}"
    )


# ── the two reports ─────────────────────────────────────────────────────

@pytest.mark.parametrize("line,expected", [
    ("Loved and Cherished 24", 'Loved & Cherished 24"'),
    ("Loved & Cherished 24", 'Loved & Cherished 24"'),
    ("loved and cherished 31", 'Loved & Cherished 31"'),
    ("cemetery tent single", "Cemetery Tent - Single"),
    ("Cemetery Tent - Double", "Cemetery Tent - Double"),
    ("cemetery tent double", "Cemetery Tent - Double"),
])
def test_the_reported_phrasings_resolve(db, tenant, line, expected):
    got, opts, unrec = _vault(db, tenant, line)
    assert got == expected, f"{line!r} -> value={got!r} picks={opts} unrec={unrec}"


def test_and_folds_to_the_ampersand_the_catalog_stores(db):
    assert normalize("Loved and Cherished 24") == normalize("Loved & Cherished 24")
    assert normalize("Cream and Gold") == "cream & gold"


@pytest.mark.parametrize("word", ["Highlands", "Sand Hill", "Anderson", "band", "Brandon"])
def test_the_and_fold_is_word_bounded(word):
    """⚠️ WITHOUT `\\b` THIS EATS THE "and" INSIDE "Highlands", and cemetery names in
    this region include one. Asserted on real-looking party names, because the fold is
    shared and a product-only test would not have caught it."""
    assert "&" not in normalize(word), normalize(word)


def test_the_fold_does_not_change_the_indexed_forms(db):
    """⚠️ THE BLAST RADIUS, MEASURED. `normalize` folds the catalog's own names as
    well as the query, so an over-eager rule would silently reshape the index. No
    indexed surface form contains the word "and" — every ampersand name stores the
    symbol — so the fold is a no-op on the index side and acts only on typed text."""
    idx = build_index(db)
    assert len(idx.by_form) > 100
    assert [k for k in idx.by_form if " and " in k] == []


# ── the raw reading is consulted on AMBIGUITY, not only on a miss ───────

def test_a_form_word_the_noise_filter_ate_is_recovered(db, tenant):
    """⚠️ THIS IS THE HALF THE FIRST FIX MISSED, AND IT ONLY APPEARED AFTER r207.

    "Veteran burial vault" strips to "Veteran", which reaches TWO candidates once the
    urn counterpart exists. A retry rule of "try the raw reading only when the stripped
    one matched NOTHING" never consults the raw form here — so the pane asked "burial
    or urn?" about a line that had already said burial. Fixed by making the test
    NARROWER, not NON-EMPTY.
    """
    got, opts, unrec = _vault(db, tenant, "Veteran burial vault")
    assert got == "Veteran Triune Burial Vault", (got, opts, unrec)
    got, opts, unrec = _vault(db, tenant, "Veteran urn vault")
    assert got == "Veteran Triune Urn Vault", (got, opts, unrec)
    # And the bare word still ASKS, because the director supplied no form.
    got, opts, _ = _vault(db, tenant, "Veteran")
    assert got is None
    assert set(opts) == {"Veteran Triune Burial Vault", "Veteran Triune Urn Vault"}, opts


def test_the_raw_reading_does_not_displace_a_good_stripped_hit(db, tenant):
    """⚠️ THE OTHER DIRECTION, AND THE REASON `_narrower` REFUSES AN EMPTY ALT. A raw
    fragment is usually a whole clause that matches nothing; if it could win, every
    phrase with a verb in it would stop resolving."""
    got, opts, unrec = _vault(db, tenant, "we need an oversized vault")
    assert got is None
    assert set(opts) == {'Continental 34"', 'Graveliner 34"', 'Graveliner 38"'}, opts
    assert not unrec, unrec


@pytest.mark.parametrize("line,expected", [
    ("34 inch Continental", 'Continental 34"'),
    ("an oversized Continental", 'Continental 34"'),
    ("Continental 34", 'Continental 34"'),
    ("Bronze Triune burial vault", "Bronze Triune Burial Vault"),
])
def test_what_already_resolved_still_resolves(db, tenant, line, expected):
    got, opts, unrec = _vault(db, tenant, line)
    assert got == expected, (got, opts, unrec)


@pytest.mark.parametrize("line,field,expected", [
    ("tent only", "cemetery_equipment", "Tent Only"),
    ("device and grass", "cemetery_equipment", "Lowering Device & Grass"),
])
def test_equipment_phrases_are_untouched(db, tenant, line, field, expected):
    """⚠️ "device and grass" IS THE ONE TO WATCH. The `and` fold and the raw-retry both
    touch text the equipment parser claims first; if ordering ever changed, this phrase
    would surface as an ambiguous VAULT pick, which is the exact confusion
    `test_a_restatement_is_SURFACED_not_silently_ignored` was written about."""
    ex = EXTRACTOR.extract_line(db, tenant_id=tenant, line=line, answers={})
    assert ex.values.get(field) == expected, ex.values
    assert not [p for p in ex.picks if p.field_id == "vault"], ex.picks


# ── the pieces ──────────────────────────────────────────────────────────

class _R:
    def __init__(self, n):
        self.candidates = tuple(range(n))


@pytest.mark.parametrize("alt,base,expected", [
    (0, 0, False),
    (0, 1, False),   # ⚠️ ZERO IS NEVER BETTER
    (0, 3, False),
    (1, 0, True),
    (1, 2, True),    # the ambiguity case
    (2, 3, True),
    (2, 2, False),   # not strictly narrower — the stripped reading stays primary
    (3, 2, False),
])
def test_narrower_prefers_fewer_candidates_and_never_zero(alt, base, expected):
    assert _narrower(_R(alt), _R(base)) is expected


def test_leftover_pairs_returns_the_raw_slice_and_the_stripped_rejoin(db):
    """⚠️ AND THE RAW ONE IS THE ONLY ONE WHOSE SPAN IS FINDABLE IN THE LINE. The
    stripped form is a rejoin of non-adjacent words, so `line.find(stripped)` returns
    -1 whenever a noise word sat in the middle. Asserted because the vault pass marks
    spans and a wrong span silently unclaims text."""
    line = "Loved and Cherished 24"
    pairs = _leftover_pairs(line, [])
    assert pairs == (("Loved Cherished 24", "Loved and Cherished 24"),), pairs
    stripped, raw = pairs[0]
    assert line.find(raw) == 0
    assert line.find(stripped) == -1, (
        "the stripped rejoin is findable in the line, so this hazard is gone and the "
        "comment above it is stale"
    )
