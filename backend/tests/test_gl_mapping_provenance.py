"""LEDGER-1 A-1 — the importer records HOW it classified, not just what.

⚠️ `parse_sage_coa` HAS ALWAYS RETURNED A CONFIDENCE AND THE IMPORTER THREW IT
AWAY. 1.0 for an exact hit on `SAGE_CATEGORY_MAP`, 0.7 for a fuzzy substring
hit, 0.0 for the fallback — computed on every account, returned on every
account, persisted on none. A 0.7 guess was stored indistinguishably from a 1.0
exact match.

That is the reason four misclassifications sat in production undetected. Every
wrong row looked exactly like a confident, deliberate classification, because
the only thing stored was the answer.

The raw Sage label went the same way, which is worse: without it the
misclassification could not be recomputed from the stored data at all.
Diagnosing it meant going back to the source CSV.

These tests pin both writes.

⚠️ `import_gl_accounts` COMMITS (`data_migration_service.py`, the `db.commit()`
at the end of the loop), so a rollback-scoped fixture does NOT clean up after
it. The first version of this file assumed savepoints all the way down and
leaked four companies; the conftest litter ratchet caught it, which is the
ratchet doing exactly its job. Teardown purges by slug prefix via
`tests/_cleanup.py::purge_companies_by_slug`, per CLAUDE.md §11.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.models.accounting_analysis import TenantGLMapping
from app.models.company import Company
from app.services.data_migration_service import import_gl_accounts
from tests._cleanup import purge_companies_by_slug


@pytest.fixture
def db():
    from app.database import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


#: Every tenant this module creates carries this prefix so teardown can find
#: them by LIKE, including any left behind by a test that failed mid-import.
_SLUG_PREFIX = "ledger1-probe-"


@pytest.fixture
def tenant(db):
    """A throwaway tenant, purged in teardown.

    NOT rollback-scoped: `import_gl_accounts` commits, so the rows survive the
    session's rollback and must be deleted explicitly.
    """
    company = Company(
        id=str(uuid.uuid4()),
        name="LEDGER-1 provenance probe",
        slug=f"{_SLUG_PREFIX}{uuid.uuid4().hex[:8]}",
    )
    db.add(company)
    db.commit()
    try:
        yield company
    finally:
        purge_companies_by_slug(db, f"{_SLUG_PREFIX}%")
        db.commit()


def _acct(number: str, description: str, sage_category: str, account_type: str, confidence: float) -> dict:
    return {
        "account_number": number,
        "description": description,
        "status": "active",
        "sage_category": sage_category,
        "bridgeable_account_type": account_type,
        "confidence": confidence,
    }


class TestProvenanceIsPersisted:

    def test_exact_match_stores_the_label_and_confidence_1(self, db, tenant):
        import_gl_accounts(
            db, tenant.id,
            [_acct("5010", "PRECAST SALES", "SALES", "revenue", 1.0)],
            {},
        )
        row = db.query(TenantGLMapping).filter(
            TenantGLMapping.tenant_id == tenant.id,
            TenantGLMapping.account_number == "5010",
        ).one()
        assert row.platform_category == "revenue"
        assert row.sage_category == "SALES"
        assert row.confidence == Decimal("1.00")

    def test_fuzzy_match_is_distinguishable_from_an_exact_one(self, db, tenant):
        # The whole point: 0.7 must not look like 1.0 in the stored row.
        import_gl_accounts(
            db, tenant.id,
            [_acct("1500", "TOTAL FIXED ASSETS", "TOTAL FIXED ASSETS", "fixed_asset", 0.7)],
            {},
        )
        row = db.query(TenantGLMapping).filter(
            TenantGLMapping.tenant_id == tenant.id,
            TenantGLMapping.account_number == "1500",
        ).one()
        assert row.confidence == Decimal("0.70")
        assert row.confidence < Decimal("1.00")

    def test_unmapped_stores_confidence_0_and_the_label_that_failed(self, db, tenant):
        # An unmapped row must carry the label nobody could map, so the next
        # person can fix the mapping rather than re-deriving it from a CSV.
        import_gl_accounts(
            db, tenant.id,
            [_acct("9999", "MYSTERY", "SOMETHING SAGE INVENTED", "unclassified", 0.0)],
            {},
        )
        row = db.query(TenantGLMapping).filter(
            TenantGLMapping.tenant_id == tenant.id,
            TenantGLMapping.account_number == "9999",
        ).one()
        assert row.platform_category == "unclassified"
        assert row.sage_category == "SOMETHING SAGE INVENTED"
        assert row.confidence == Decimal("0.00")

    def test_overwrite_refreshes_provenance_too(self, db, tenant):
        # A re-import must not leave stale provenance describing the PREVIOUS
        # classification — that would be worse than none.
        import_gl_accounts(
            db, tenant.id,
            [_acct("5010", "PRECAST SALES", "SALES", "cogs", 0.7)],
            {},
        )
        import_gl_accounts(
            db, tenant.id,
            [_acct("5010", "PRECAST SALES", "SALES", "revenue", 1.0)],
            {"overwrite_existing": True},
        )
        row = db.query(TenantGLMapping).filter(
            TenantGLMapping.tenant_id == tenant.id,
            TenantGLMapping.account_number == "5010",
        ).one()
        assert row.platform_category == "revenue"
        assert row.confidence == Decimal("1.00")


class TestPreExistingRowsAreHonest:

    def test_a_row_written_without_provenance_reads_null_not_zero(self, db, tenant):
        # r173 does NOT backfill. NULL is the true statement about a row
        # imported before provenance was recorded; a fabricated 0.0 would say
        # "we measured this and it was unmappable", which is a different and
        # false claim.
        row = TenantGLMapping(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            platform_category="other",
            account_number="1010",
            account_name="LEGACY ROW",
        )
        db.add(row)
        db.flush()
        fetched = db.query(TenantGLMapping).filter(
            TenantGLMapping.tenant_id == tenant.id,
            TenantGLMapping.account_number == "1010",
        ).one()
        assert fetched.sage_category is None
        assert fetched.confidence is None
