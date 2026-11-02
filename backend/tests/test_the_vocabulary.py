"""What the bar may complete, for this tenant. James 2026-10-16, step 3.

⚠️ THE SCOPE IS THE DESIGN. Measured: the platform catalog holds BOTH
`Monticello Burial Vault` and `Monticello Urn Vault`, so "monti" is ambiguous across
the catalog. Scoping to what the tenant CARRIES is what makes the ruling's own verify
line work on sunnycrest — and it is also the more correct scope, because completing to
a vault the tenant does not sell produces an order Approve then refuses.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture.vocabulary import build_vocabulary


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
        s.rollback(); s.close()


@pytest.fixture(scope="module")
def sunnycrest(db) -> str:
    tid = db.execute(text("SELECT id FROM companies WHERE slug='sunnycrest'")).scalar()
    assert tid, "no sunnycrest tenant — this test must not skip"
    return tid


def test_it_is_not_empty(db, sunnycrest):
    """⚠️ THE CONTROL. Every assertion below is vacuous over an empty list, and an
    empty vocabulary is also exactly what a broken query returns."""
    assert len(build_vocabulary(db, sunnycrest)) > 20


def test_every_vault_term_carries_its_FORM(db, sunnycrest):
    """⚠️ THE FORM DEFAULT CANNOT WORK WITHOUT IT. James ruled that matches differing
    only by form resolve to the burial vault; the display name alone cannot tell the
    client which word IS the form, so it travels as its own field."""
    vaults = [t for t in build_vocabulary(db, sunnycrest) if t.kind == "vault"]
    assert vaults, "no vault terms at all"
    missing = [t.text for t in vaults if not t.form]
    assert missing == [], missing


def test_both_monticello_forms_are_present_and_distinguishable(db, sunnycrest):
    """The case the ruling is about, asserted on real data rather than a fixture."""
    monti = [
        t for t in build_vocabulary(db, sunnycrest)
        if t.text.lower().startswith("monticello")
    ]
    forms = {t.form for t in monti}
    assert "burial_vault" in forms and "urn_vault" in forms, [(t.text, t.form) for t in monti]


def test_what_the_tenant_carries_is_marked(db, sunnycrest):
    """⚠️ `carried` IS THE TIE-BREAK'S INPUT, so a vocabulary that marked nothing
    would silently disable step 5 of the rule while still looking complete."""
    v = build_vocabulary(db, sunnycrest)
    assert any(t.carried for t in v), "nothing marked as carried"
    assert any(not t.carried for t in v), "everything marked carried — the flag is inert"


def test_the_parties_are_there(db, sunnycrest):
    kinds = {t.kind for t in build_vocabulary(db, sunnycrest)}
    for k in ("funeral_home", "cemetery", "vault", "equipment", "personalization"):
        assert k in kinds, (k, sorted(kinds))


# ── ruling A/C: the bar offers words a person types, not billing lines ───────


def test_the_vault_FILLING_KINDS_carry_no_non_vault(db, sunnycrest):
    """⚠️ RULING A/C (James, 2026-11-02): *"Ghost vocabulary excludes product names
    that are billing lines."* Measured before the fix on this very tenant: the catalogue
    half emitted `Graveside Chairs` (form `equipment`) as kind `vault`, and the tenant
    half emitted `Extra Chairs (Over 8)` as kind `product` — both of which
    `prefix_resolve.KINDS_VAULT` treats as vault candidates. Typing "chairs" therefore
    ghost-completed to `" (Over 8)"`, a price-list overage name, and resolved into the
    VAULT row.

    ⚠️ ASKED THROUGH THE RAW RESOLVER RATHER THAN THROUGH `form`, because an alias
    carries none. `test_the_vault_slot_only_takes_vaults.py` makes the same check the
    hub of its door matrix; this one keeps it beside the builder that has to satisfy it.
    """
    from app.services.capture.prefix_resolve import KINDS_VAULT
    from app.services.capture.vault_form import is_vault_form
    from app.services.product_name_resolver import build_index, resolve

    idx = build_index(db)
    terms = [t for t in build_vocabulary(db, sunnycrest) if t.kind in KINDS_VAULT]
    assert terms, "no vault-filling terms — this test is measuring nothing"
    bad = [
        (t.text, t.kind)
        for t in terms
        if any(not is_vault_form(c.form) for c in resolve(idx, t.text).candidates)
    ]
    assert bad == [], bad


def test_the_CHAIRS_WORDS_are_offered_and_the_PRICE_LIST_NAME_IS_NOT(db, sunnycrest):
    """⚠️ BOTH HALVES OF THE RULING, AND THE SECOND HALF IS WHY THE FIRST IS NEEDED.
    James: *"chairs words come from the chairs vocabulary, not the Extra Chairs
    product."* Excluding the product name without adding the words would have left a
    director typing "chai" with no completion at all."""
    terms = build_vocabulary(db, sunnycrest)
    chairs = {t.text for t in terms if t.kind == "chairs"}
    assert chairs == {"chairs", "extra chairs"}, sorted(chairs)
    # ⚠️ THE BILLING LINE IS GONE FROM EVERY KIND, not merely demoted to another one.
    assert not [t for t in terms if "(Over 8)" in t.text], [
        (t.text, t.kind) for t in terms if "(Over 8)" in t.text
    ]


def test_the_CHAIRS_KIND_IS_NOT_A_VAULT_FILLING_KIND(db, sunnycrest):
    """⚠️ IF IT WERE, THE FIX WOULD HAVE REOPENED THE DOOR IT CLOSED. `KINDS_VAULT`
    decides which vocabulary kinds the prefix pass resolves as products; adding
    "chairs" to the bar while leaving it in that set would send the word straight back
    to the product resolver."""
    from app.services.capture.prefix_resolve import KINDS_VAULT

    assert "chairs" not in KINDS_VAULT, KINDS_VAULT


def test_EVERY_OFFERED_CHAIRS_PHRASE_IS_ONE_THE_EXTRACTOR_UNDERSTANDS(db, sunnycrest):
    """⚠️ THE TWO SIDES HELD TOGETHER, which is what the vocabulary module's own comment
    promises. A phrase the bar completes to and the engine cannot read would be a
    completion that produces "not understood" the moment it is accepted — the exact
    shape of `startsCaptureWithParty`'s dead end."""
    from app.services.capture.typed_extraction import _chairs
    from app.services.capture.vocabulary import CHAIRS_PHRASES

    for phrase in CHAIRS_PHRASES:
        got = _chairs(phrase)
        assert got is not None, phrase
        sense, count, _span = got
        assert count is None, (phrase, got)
        assert sense in ("wanted", "extra_pending"), (phrase, got)
    # ⚠️ AND THE TWO PHRASES MEAN DIFFERENT THINGS, which is ruling B. If both mapped to
    # one sense the bar would be offering a distinction the engine does not make.
    senses = {p: _chairs(p)[0] for p in CHAIRS_PHRASES}
    assert len(set(senses.values())) == 2, senses
