"""Shared tenant fixture — the canonical dev tenants, present on a BARE database.

⚠️ PASSING ON A BARE DATABASE IS NOT EVIDENCE A TEST IS INDEPENDENT OF SEEDED
STATE. It is evidence that THAT PATH did not need it. This module exists because
a partial pass concealed a hard dependency for two days:
`test_completeness_review.py` hardcoded `staging-test-001` and never created it.
Nine of its tests passed on CI's fresh Postgres and three failed —

    IntegrityError: ForeignKeyViolation
    completeness_nil_claims_tenant_id_fkey

— because `review()` against a nonexistent tenant happily returns all-`missing`
rows without touching a foreign key, while the three tests that INSERT a nil
claim do. So the file read ninety percent healthy and rested entirely on a row
nobody created. The nine greens were green for the wrong reason; the three reds
were the only evidence the dependency existed at all.

⚠️ TEARDOWN IS CREATE-SCOPED, AND THAT IS THE WHOLE SAFETY PROPERTY. The reflex
fix — create the tenant, purge it in teardown via `purge_companies_by_slug` — is
DESTRUCTIVE here. `staging-test-001` is the REAL testco row on any seeded
developer machine, so a blanket purge deletes their tenant along with everything
seeded under it. A test that eats a developer's tenant is worse than a red CI.

So: create only when absent, remove only what this fixture created. On CI the row
is made and unmade; on a seeded machine nothing is touched in either direction.
Net company count is unchanged on both, which keeps the conftest litter ratchet
satisfied without opting out of it.

Usage:

    from tests._tenant import canonical_tenant   # noqa: F401  (module fixture)

    TENANT = TESTCO_ID

`canonical_tenant` is module-scoped and autouse — importing the name into a test
module is enough to arm it.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

#: testco — the canonical MANUFACTURING dev tenant (`scripts/seed_staging.py`).
TESTCO_ID = "staging-test-001"
TESTCO_SLUG = "testco"
TESTCO_NAME = "Test Vault Co"

#: ⚠️ `created_at` IS SEMANTIC HERE, NOT BOILERPLATE — it is the tenant's START,
#: and several services bound their window by it. `completeness.review` reads it
#: via `_tenant_start` and refuses to owe anything for a period before the tenant
#: existed, which is correct behaviour and lethal to a fixture: a tenant born
#: `now()` owes nothing for any past date, so tests asserting on August periods
#: see an EMPTY window and fail with no rows rather than the rows they expect.
#:
#: This surfaced only on the bare axis, and it surfaced as TWO failures CI never
#: reported — on CI the row was absent entirely, `_tenant_start` returned None,
#: and the unbounded window happened to satisfy them. They were passing on a
#: tenant that did not exist. Creating the tenant is what made the bound real.
#:
#: Backdated to dev's own testco (2026-04-22) so both axes see the same history.
_BEGAN = datetime(2026, 4, 22, 15, 5, tzinfo=timezone.utc)


def ensure_company(db, *, company_id: str, slug: str, name: str) -> bool:
    """Create the companies row if absent. True when THIS call created it.

    Matched on ID, because the id is what every child row's FK points at. The
    slug is checked separately and only as a collision guard: a database holding
    that slug under a DIFFERENT id is somebody's real data, and inserting over it
    would trade a foreign-key error for a unique-constraint one while corrupting
    whatever was there. In that case we create nothing and report False, so
    teardown also removes nothing.
    """
    exists = db.execute(
        text("SELECT 1 FROM companies WHERE id = :i"), {"i": company_id}
    ).scalar()
    if exists:
        return False

    slug_taken = db.execute(
        text("SELECT 1 FROM companies WHERE slug = :s"), {"s": slug}
    ).scalar()
    if slug_taken:
        # Deliberately not an error. The suite's real requirement is "a company
        # row with this id"; a mismatched slug is a machine we should leave alone
        # rather than one we should fail on.
        return False

    # ⚠️ ORM INSERT, NOT RAW SQL, AND THAT IS LOAD-BEARING. `companies` has FIVE
    # NOT NULL columns with no database default — id, name, slug, created_at,
    # updated_at — and the last two are defaulted in PYTHON
    # (`default=lambda: datetime.now(timezone.utc)`). A raw INSERT naming only
    # the three obvious ones bypasses those defaults and dies on
    # NotNullViolation for created_at. That was the first version of this
    # function, and it is the same raw-SQL column-drift class that broke
    # seed_staging three times in R-1.6.4. The model already knows the shape;
    # asking it is cheaper than tracking the schema by hand.
    from app.models import Company

    db.add(Company(id=company_id, name=name, slug=slug, created_at=_BEGAN))
    db.commit()
    return True


def drop_company(db, *, company_id: str, child_tables: tuple[str, ...]) -> None:
    """Remove a company this fixture created, children first.

    Only ever called for a row `ensure_company` reported creating, so the child
    sweep cannot reach seeded data. Extra DELETEs over empty sets are harmless
    no-ops — the same reasoning `_cleanup.py` uses for its ordered list.
    """
    for table in child_tables:
        db.execute(
            text(f"DELETE FROM {table} WHERE tenant_id = :i"), {"i": company_id}
        )
    db.execute(text("DELETE FROM companies WHERE id = :i"), {"i": company_id})
    db.commit()


def make_canonical_tenant_fixture(*, child_tables: tuple[str, ...] = ()):
    """Build a module-scoped autouse fixture ensuring testco exists.

    A factory rather than one fixed fixture because the child tables to sweep are
    per-suite: the fixture cannot know which tables a given file writes, and
    guessing a union here would re-create `_cleanup.py`'s job in a second place.
    """

    @pytest.fixture(scope="module", autouse=True)
    def _canonical_tenant():
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            created = ensure_company(
                db, company_id=TESTCO_ID, slug=TESTCO_SLUG, name=TESTCO_NAME
            )
        finally:
            db.close()

        yield TESTCO_ID

        if not created:
            return  # seeded machine — this fixture made nothing, so it removes nothing
        db = SessionLocal()
        try:
            drop_company(db, company_id=TESTCO_ID, child_tables=child_tables)
        finally:
            db.close()

    return _canonical_tenant
