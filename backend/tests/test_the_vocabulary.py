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
