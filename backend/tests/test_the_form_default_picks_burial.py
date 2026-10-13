"""The vault form default: ambiguous ONLY by form resolves to the burial vault.

⚠️ RULED BY JAMES 2026-10-13, and the ruling is narrow in a way that matters. A vault
phrase that is ambiguous *only* because two records differ by FORM (burial vs urn)
resolves to the burial vault and captures it, with a one-click switch offered. Any
OTHER discriminator — size, or form AND size together — still raises a pick. The
office's own words were that a burial vault is what they mean nine times in ten, and
that being asked is worse than being wrong once with a visible way back.

⚠️ THE CONDITION IS `discriminators == ("form",)` EXACTLY, not "form is among the
discriminators". Measured on the seeded catalog 2026-10-13:

    veteran        → ('form',)          → default + switch
    monticello     → ('form',)          → default + switch
    bronze triune  → ('form',)          → default + switch
    continental    → ('size',)          → still asks
    graveliner     → ('form', 'size')   → still asks (but see below)
    triune         → ('form', 'option') → still asks   <-- the load-bearing case
    venetian       → ('form', 'option') → still asks
    oversize       → ('form','line','size') → still asks

A `"form" in discs` version silently resolves `triune`, `venetian` and `oversize`,
each of which has a `burial_vault` candidate plus a second discriminator — so the
loose check would pick an OPTION or a SIZE for the office. It does NOT mis-resolve
`graveliner`, which has no `burial_vault` candidate at all and asks either way; I
reached for graveliner first, and a break test with the loose check left the whole
suite green until the three phrases above replaced it.

⚠️ "urn" ANYWHERE IN THE VAULT PHRASE SELECTS THE URN VAULT. My first version read
the word from the n-gram that matched the catalog record rather than from the phrase
the director typed, so "monticello urn" matched the record "monticello" — no "urn" in
it — and took the BURIAL vault, which is precisely the live bug James reported for
"Veteran urn vault". The fix reads the unclaimed slice. The tests below type the word
on both sides of the name because that is how the two code paths differ.
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


def _ex(db, tenant, phrase):
    return extract_text(db, tenant_id=tenant, text=f"order for hopkins {phrase}")


# ── the default fires, and says so ──────────────────────────────────────────

@pytest.mark.parametrize("phrase", ["monticello", "veteran", "bronze triune"])
def test_a_form_only_ambiguity_takes_the_burial_vault(db, tenant, phrase):
    ex = _ex(db, tenant, phrase)
    assert not ex.picks, f"{phrase!r} should not ask; it got {ex.picks}"
    captured = ex.values.get("vault")
    assert captured, f"{phrase!r} captured no vault at all"
    assert "urn" not in captured.casefold(), (
        f"{phrase!r} defaulted to {captured!r}, which is not the burial vault"
    )


@pytest.mark.parametrize("phrase", ["monticello", "veteran", "bronze triune"])
def test_and_offers_a_one_CLICK_WAY_BACK(db, tenant, phrase):
    # ⚠️ THE SWITCH IS WHAT MAKES THE DEFAULT ACCEPTABLE. A default with no visible
    # alternative is a guess the director cannot see or undo, and that is the version
    # James rejected. Asserting the capture without asserting the switch would pass
    # for exactly that version.
    ex = _ex(db, tenant, phrase)
    offers = [s for s in ex.switches if s.field_id == "vault"]
    assert len(offers) == 1, f"{phrase!r} offered {offers}"
    assert "urn" in offers[0].to_value.casefold(), (
        f"the switch should lead to the urn vault, not {offers[0].to_value!r}"
    )
    assert offers[0].from_label == ex.values["vault"]


# ── "urn" in the phrase wins, from either side of the name ──────────────────

@pytest.mark.parametrize(
    "phrase",
    ["monticello urn", "urn monticello", "veteran urn", "monticello urn vault"],
)
def test_the_word_urn_selects_the_urn_vault(db, tenant, phrase):
    ex = _ex(db, tenant, phrase)
    assert not ex.picks, f"{phrase!r} should not ask"
    captured = ex.values.get("vault", "")
    assert "urn" in captured.casefold(), (
        f"{phrase!r} took {captured!r} — this is the live bug James reported"
    )


def test_and_the_switch_then_points_BACK_to_the_burial_vault(db, tenant):
    # ⚠️ THE SWITCH IS SYMMETRIC. If it only ever pointed at the urn vault, a director
    # who said "urn" and meant it would be offered a switch to the vault they already
    # have, and the one who mistyped would have no way back.
    ex = _ex(db, tenant, "monticello urn")
    offers = [s for s in ex.switches if s.field_id == "vault"]
    assert len(offers) == 1
    assert "urn" not in offers[0].to_value.casefold()


# ── every other ambiguity still asks ───────────────────────────────────────

def test_a_SIZE_ambiguity_still_asks(db, tenant):
    ex = _ex(db, tenant, "continental")
    assert [p for p in ex.picks if p.field_id == "vault"], (
        "continental differs by SIZE; defaulting it would pick a size for the office"
    )
    assert "vault" not in ex.values


@pytest.mark.parametrize(
    "phrase,discs",
    [
        ("triune", "('form', 'option')"),
        ("venetian", "('form', 'option')"),
        ("oversize", "('form', 'line', 'size')"),
    ],
)
def test_form_PLUS_something_else_still_asks(db, tenant, phrase, discs):
    """The cases that make `== ("form",)` load-bearing rather than decorative.

    ⚠️ I WROTE THE WRONG TEST FIRST AND THE BREAK TEST CAUGHT IT. My original version
    used `graveliner` and asserted it still asks. It does — but for a reason that has
    nothing to do with this condition: graveliner's forms are `grave_liner` and
    `urn_vault`, with NO `burial_vault` among them, so a loosened check falls through
    on `mine is None` and asks anyway. Loosening the condition to "form is among the
    discriminators" left all sixteen tests green.

    ⚠️ THESE THREE PHRASES ARE THE REAL ONES, found by scanning all 207 indexed
    phrases: each is ambiguous by form AND something else, and each HAS a
    `burial_vault` candidate for a loose check to seize on. `triune` and `venetian`
    differ by form and OPTION; `oversize` by form, line and size. Resolving any of
    them to "the burial vault" picks an option or a size on the office's behalf,
    which is the thing the ruling does not authorise.
    """
    ex = _ex(db, tenant, phrase)
    picks = [p for p in ex.picks if p.field_id == "vault"]
    assert picks, (
        f"{phrase!r} is ambiguous by {discs} — more than form — so it must still ask"
    )
    assert "vault" not in ex.values
    assert not ex.switches


def test_graveliner_asks_too_but_NOT_because_of_this_condition(db, tenant):
    """Five records must not collapse to one — and this is not the form guard.

    ⚠️ ITS REASON IS STATED SO IT IS NOT MISTAKEN FOR THE GUARD. Graveliner is the
    phrase I reached for first; no candidate of it has form `burial_vault`, so the
    form default never applies and it asks whatever the condition says. The claim
    worth keeping is only that it asks.
    """
    from app.services.product_name_resolver import build_index
    from app.services.product_name_resolver import resolve as resolve_vault

    vr = resolve_vault(build_index(db), "graveliner")
    # ⚠️ ASSERTED, NOT ASSUMED. If the catalog ever gains a Graveliner burial vault,
    # this phrase DOES start exercising the form check and this test's reasoning is
    # stale — so it fails here rather than going quietly wrong.
    assert "burial_vault" not in {c.form for c in vr.candidates}

    ex = _ex(db, tenant, "graveliner")
    picks = [p for p in ex.picks if p.field_id == "vault"]
    assert picks and len(picks[0].options) > 2
    assert "vault" not in ex.values


@pytest.mark.parametrize("phrase", ["continental 34", "monticello burial vault"])
def test_an_UNAMBIGUOUS_phrase_resolves_with_NO_switch(db, tenant, phrase):
    # ⚠️ THE NEGATIVE CONTROL FOR THE SWITCH. A build that offered a switch on every
    # vault it captured would pass every test above. A director who named the form
    # explicitly is not guessing and must not be offered a correction.
    ex = _ex(db, tenant, phrase)
    assert not ex.picks, f"{phrase!r} should not ask"
    assert ex.values.get("vault"), f"{phrase!r} captured nothing"
    assert not [s for s in ex.switches if s.field_id == "vault"], (
        f"{phrase!r} was explicit; it should not be offered a switch"
    )


def test_no_vault_phrase_at_all_offers_no_switch(db, tenant):
    ex = extract_text(db, tenant_id=tenant, text="order for hopkins tent only")
    assert not ex.switches
