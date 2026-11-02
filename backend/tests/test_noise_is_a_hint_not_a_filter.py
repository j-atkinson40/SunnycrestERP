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


@pytest.fixture(scope="module")
def vault_variant_names(db) -> list[str]:
    """The active variants that can BE a vault — the population the vault seam serves.

    ⚠️ ADDED 2026-11-02 (ruling A), AND THE SPLIT IS THE WHOLE CORRECTION TO THIS FILE.
    Its general test asserted that EVERY active variant is reachable by its own display
    name through the VAULT seam, and that claim was written before the vault slot had an
    acceptance rule. Eighteen of the fifty-two are not vaults — six `equipment` and
    twelve `urn` — and ruling A says the vault field must refuse them. So the claim
    narrows to the thirty-four it was always really about.

    ⚠️ AND THE NARROWING IS GUARDED FROM BOTH SIDES. `test_no_NON_vault_variant_puts_a_
    non_vault_in_the_slot` below is the other half: without it, "every vault variant is
    reachable" could be satisfied by a seam that had quietly started accepting
    everything again.
    """
    from app.services.capture.vault_form import is_vault_form

    rows = db.execute(text(
        "SELECT v.display_name, t.form FROM product_variant_templates v "
        "JOIN product_templates t ON t.id = v.product_template_id "
        "WHERE v.is_active IS TRUE"
    )).all()
    names = sorted({n for n, form in rows if is_vault_form(form)})
    # ⚠️ MEASURED 2026-11-02: 34 of 52. Asserted as a floor so this fixture cannot
    # silently shrink to a handful and take every claim below down with it.
    assert len(names) > 25, f"only {len(names)} vault-form variants"
    return names


@pytest.fixture(scope="module")
def non_vault_variant_names(db) -> list[str]:
    """The active variants that CANNOT be a vault — equipment and urns."""
    from app.services.capture.vault_form import is_vault_form

    rows = db.execute(text(
        "SELECT v.display_name, t.form FROM product_variant_templates v "
        "JOIN product_templates t ON t.id = v.product_template_id "
        "WHERE v.is_active IS TRUE"
    )).all()
    names = sorted({n for n, form in rows if not is_vault_form(form)})
    assert len(names) > 10, f"only {len(names)} non-vault variants — the control is void"
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

def test_every_VAULT_variant_is_reachable_by_its_own_display_name(
    db, tenant, vault_variant_names
):
    """⚠️ THE RULE AS ONE CLAIM OVER ALL 34 VAULT-FORM VARIANTS, not case by case.

    A director typing a vault's own name must reach it — resolved, or among the options
    of a pick when the name is genuinely shared. Before the 2026-10-07 fix this failed
    on the two `Cemetery Tent - ...` variants, because `cemetery` is in the noise list
    and is the first word of their names.

    ⚠️ RENAMED AND NARROWED 2026-11-02, AND THE TENTS ARE THE REASON BOTH TIMES. They
    were the ORIGINAL REPORT this file closed — and they are `form = 'equipment'`, so
    ruling A says the vault field must refuse them. The noise-word rule the file exists
    for is untouched and still has vault-form subjects: `burial` and `vault` are inside
    every burial-vault name, which is what lets "Continental Burial Vault" reach the
    family phrase, and all 34 are measured reachable. What changed is the POPULATION,
    not the rule.

    ⚠️ SO THE TENTS MOVED FROM THE EVIDENCE TO THE CONTROL. They are now asserted
    REFUSED, in `test_the_tents_are_REFUSED_by_the_vault_seam_now` below — the same
    phrasings, the opposite expectation, with the ruling naming why.
    """
    unreachable = []
    for name in vault_variant_names:
        got, opts, unrec = _vault(db, tenant, name)
        if got != name and name not in opts:
            unreachable.append((name, got, opts, unrec))
    assert not unreachable, (
        f"{len(unreachable)} vault variants are not reachable by their own display "
        f"name: {unreachable}"
    )


def test_no_NON_vault_variant_puts_a_non_vault_in_the_slot(
    db, tenant, non_vault_variant_names
):
    """⚠️ THE OTHER HALF OF THE NARROWING, AND IT IS WHAT STOPS THE TEST ABOVE FROM
    BEING SATISFIED BY A SEAM THAT ACCEPTS EVERYTHING AGAIN.

    ⚠️ THE CLAIM IS ABOUT THE PRODUCT REACHED, NOT ABOUT REACHING NOTHING, AND THAT
    DISTINCTION IS MEASURED. Two non-vault names legitimately reach the slot:
    `Cream & Gold` and `White & Silver` are URN names, and those exact words also sit
    inside `Universal Urn Vault (Cream & Gold)` and `(White & Silver)` — which are urn
    VAULTS. The phrase is genuinely shared between an urn and the urn vault it goes in,
    and the vault field taking the vault is correct. An assertion that no non-vault
    NAME may reach the slot would have been wrong, and would have forced a fix that
    made those two urn vaults untypeable.
    """
    from app.services.capture.vault_form import FormResolver, admits_name

    forms = FormResolver(db, tenant)
    bad = []
    for name in non_vault_variant_names:
        got, opts, _unrec = _vault(db, tenant, name)
        for reached in [got, *opts]:
            if reached and not admits_name(forms, reached):
                bad.append((name, reached))
    assert bad == [], bad


# ── the two reports ─────────────────────────────────────────────────────

@pytest.mark.parametrize("line", [
    "cemetery tent single",
    "Cemetery Tent - Double",
    "cemetery tent double",
    "grass mats",
    "cremation table",
])
def test_the_tents_are_REFUSED_by_the_vault_seam_now(db, tenant, line):
    """⚠️ THE ORIGINAL REPORT, INVERTED BY RULING A — AND THAT INVERSION IS THE FINDING
    WORTH KEEPING.

    This file was written on 2026-10-07 because `"cemetery tent single"` came back as
    NOT UNDERSTOOD, and the fix made it resolve. It resolved into the VAULT field,
    because that was the only seam it went through — and a Cemetery Tent is
    `product_templates.form = 'equipment'`. So the 10-07 fix was right about the noise
    rule and wrong about the destination, and nothing said so for four weeks.

    ⚠️ "NOT UNDERSTOOD" IS NOW THE CORRECT ANSWER HERE, which is uncomfortable and is
    the honest state. The words reach no field: there is no equipment vocabulary for the
    catalogue's own equipment VARIANT names — only for the five `EQUIPMENT_PACKAGES`
    labels — so a director who types "lowering device" gets it reported as unplaced
    rather than silently filed as a vault.

    ⚠️ `"lowering device"` LEFT THIS LIST ON 2026-11-02, AND THAT IS RULING 2. When
    this test was written I reported that mapping it to a package was not an executor's
    call, because `Lowering Device Only` and `Lowering Device & Grass` are two prices
    and picking one would guess at a price. James ruled the third option: *"'lowering
    device' alone → Opas asks, two pills: 'Device only' / 'Device & grass'. Never map it
    to either price silently."* It now produces a PICK on `cemetery_equipment` — see
    `test_an_ambiguous_equipment_family_ASKS.py` — so it is no longer refused and no
    longer unplaced.

    ⚠️ THE FIVE THAT REMAIN ARE STILL REFUSED AND STILL UNPLACED, and that is still the
    honest state: no equipment vocabulary reaches a tent, grass mats or a cremation
    table, so the words land nowhere and the director sees them flagged.
    """
    got, opts, unrec = _vault(db, tenant, line)
    assert got is None, (line, got)
    assert opts == [], (line, opts)
    # ⚠️ AND IT IS HELD RATHER THAN SWALLOWED. A refused phrase that vanished from both
    # the value and the held list would be the worst of the three outcomes: the director
    # would see no row filled and no word flagged.
    assert unrec, (line, "refused AND swallowed — neither placed nor held")


@pytest.mark.parametrize("line,expected", [
    ("Loved and Cherished 24", 'Loved & Cherished 24"'),
    ("Loved & Cherished 24", 'Loved & Cherished 24"'),
    ("loved and cherished 31", 'Loved & Cherished 31"'),
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
    # ⚠️ AND THE BARE WORD NOW DEFAULTS, RULED 2026-10-13. Until then this read
    # "the bare word still ASKS, because the director supplied no form" and
    # asserted `got is None` with both options offered. James replaced that: a
    # form-only ambiguity takes the burial vault and offers a one-click switch.
    #
    # ⚠️ WHAT THIS TEST IS ACTUALLY ABOUT IS UNAFFECTED, which is why it keeps its
    # name. The claim is that the RAW reading is consulted on ambiguity and not only
    # on a miss — "Veteran burial vault" and "Veteran urn vault" above both resolve
    # to the form the director named. That is the half the first fix missed, and it
    # would still be missed if the raw reading were dropped: the default would make
    # "Veteran urn vault" resolve to the BURIAL vault, which is the live bug James
    # reported. The two assertions above are what catch that.
    got, opts, _ = _vault(db, tenant, "Veteran")
    assert got == "Veteran Triune Burial Vault", (got, opts)


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
    ("tent only", "cemetery_equipment", "tent_only"),
    ("device and grass", "cemetery_equipment", "lowering_device_and_grass"),
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
