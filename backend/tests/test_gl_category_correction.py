"""LEDGER-1 A-1 — r174's 96 corrections, and the constraint that follows them.

⚠️ THE MIGRATION MIRRORS A VOCABULARY THAT LIVES IN CODE. `r174`'s
`ALLOWED_CATEGORIES` and `data_migration_service.PLATFORM_ACCOUNT_CATEGORIES`
must be identical — a value added to one and not the other means either a legal
category the database refuses, or a category the database accepts that nothing
produces. There is no mechanism keeping them in step, so this file is the
mechanism. That is the same shape as the four coexisting vocabularies A-1 exists
to collapse, and it would be careless to close that defect by opening a smaller
copy of it.

⚠️ THE REVERSE RESTORES WRONG VALUES ON PURPOSE. `test_reverse_restores_the_
prior_state` asserts that revenue accounts go back to `cogs`. That is what a
downgrade means: the prior state, not the state that should have been. Anyone
"fixing" this test has misread the migration.
"""
from __future__ import annotations

import importlib.util
import pathlib
import uuid

import pytest

from app.models.accounting_analysis import TenantGLMapping
from app.models.company import Company
from app.services.data_migration_service import PLATFORM_ACCOUNT_CATEGORIES
from tests._cleanup import purge_companies_by_slug

_MIGRATION = (
    pathlib.Path(__file__).resolve().parents[1]
    / "alembic" / "versions" / "r174_gl_category_correction.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("r174_probe", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


r174 = _load_migration()

_SLUG_PREFIX = "ledger1-corr-"


@pytest.fixture
def db():
    from app.database import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def tenant(db):
    company = Company(
        id=str(uuid.uuid4()),
        name="LEDGER-1 correction probe",
        slug=f"{_SLUG_PREFIX}{uuid.uuid4().hex[:8]}",
    )
    db.add(company)
    db.commit()
    try:
        yield company
    finally:
        purge_companies_by_slug(db, f"{_SLUG_PREFIX}%")
        db.commit()


def _apply(db, tenant_id, forward=True):
    """Replay the migration's UPDATE logic against one tenant."""
    from sqlalchemy import text

    for acct, from_cat, to_cat, _name, _sage in r174.CORRECTIONS:
        a, b = (from_cat, to_cat) if forward else (to_cat, from_cat)
        db.execute(
            text(
                "UPDATE tenant_gl_mappings SET platform_category = :b "
                "WHERE tenant_id = :t AND account_number = :acct "
                "AND platform_category = :a"
            ),
            {"b": b, "t": tenant_id, "acct": acct, "a": a},
        )
    db.commit()


class TestTheCorrectionTableIsCoherent:

    def test_there_are_ninety_six(self):
        assert len(r174.CORRECTIONS) == 96

    def test_no_account_appears_twice(self):
        numbers = [c[0] for c in r174.CORRECTIONS]
        assert len(numbers) == len(set(numbers))

    def test_no_correction_is_a_no_op(self):
        for acct, from_cat, to_cat, _n, _s in r174.CORRECTIONS:
            assert from_cat != to_cat, f"{acct} corrects to itself"

    def test_every_value_on_both_sides_is_a_real_category(self):
        for acct, from_cat, to_cat, _n, _s in r174.CORRECTIONS:
            assert from_cat in PLATFORM_ACCOUNT_CATEGORIES, f"{acct} from={from_cat}"
            assert to_cat in PLATFORM_ACCOUNT_CATEGORIES, f"{acct} to={to_cat}"

    def test_the_transitions_are_the_six_expected(self):
        from collections import Counter

        got = Counter((c[1], c[2]) for c in r174.CORRECTIONS)
        assert got == {
            ("other", "cogs"): 47,
            ("other", "delivery_cost"): 26,
            ("current_liability", "long_term_liability"): 8,
            ("cogs", "revenue"): 8,
            ("cogs", "contra_revenue"): 5,
            ("other_income", "other_expense"): 2,
        }

    def test_the_five_contra_revenue_accounts_are_the_ruled_ones(self):
        contra = {c[0] for c in r174.CORRECTIONS if c[2] == "contra_revenue"}
        assert contra == {"5150", "5160", "5165", "5170", "5410"}

    def test_freight_billed_out_is_revenue_not_a_cost(self):
        # 5210 sits in Sage's SALES; 7500 FREIGHT IN sits in COST OF GOODS SOLD.
        freight = {c[0]: c[2] for c in r174.CORRECTIONS if c[0] in ("5210", "7500")}
        assert freight["5210"] == "revenue"
        assert freight["7500"] == "cogs"

    def test_nothing_is_corrected_INTO_the_unknown_buckets(self):
        # The whole point is emptying `other`; landing anything back in `other`
        # or `unclassified` would defeat the migration.
        targets = {c[2] for c in r174.CORRECTIONS}
        assert "other" not in targets
        assert "unclassified" not in targets


class TestTheVocabularyMirrorMatches:

    def test_migration_and_service_agree_exactly(self):
        assert set(r174.ALLOWED_CATEGORIES) == set(PLATFORM_ACCOUNT_CATEGORIES), (
            "r174.ALLOWED_CATEGORIES has drifted from "
            "data_migration_service.PLATFORM_ACCOUNT_CATEGORIES"
        )

    def test_other_expense_is_permitted(self):
        # Added after the set was committed as complete; the constraint must
        # know about it or every INTEREST EXPENSE row is refused on write.
        assert "other_expense" in r174.ALLOWED_CATEGORIES

    def test_other_and_unclassified_are_both_permitted_and_distinct(self):
        assert "other" in r174.ALLOWED_CATEGORIES
        assert "unclassified" in r174.ALLOWED_CATEGORIES


class TestApplyingItToRealRows:

    def _seed(self, db, tenant_id):
        for acct, from_cat, _to, name, sage in r174.CORRECTIONS:
            db.add(
                TenantGLMapping(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    platform_category=from_cat,
                    account_number=acct,
                    account_name=name,
                    sage_category=sage,
                )
            )
        db.commit()

    def _categories(self, db, tenant_id):
        return {
            r.account_number: r.platform_category
            for r in db.query(TenantGLMapping).filter(
                TenantGLMapping.tenant_id == tenant_id
            )
        }

    def test_every_one_of_the_ninety_six_moves(self, db, tenant):
        self._seed(db, tenant.id)
        _apply(db, tenant.id)
        got = self._categories(db, tenant.id)
        for acct, _from, to_cat, _n, _s in r174.CORRECTIONS:
            assert got[acct] == to_cat, f"{acct} did not move"

    def test_applying_twice_changes_nothing_further(self, db, tenant):
        self._seed(db, tenant.id)
        _apply(db, tenant.id)
        once = self._categories(db, tenant.id)
        _apply(db, tenant.id)
        assert self._categories(db, tenant.id) == once

    def test_reverse_restores_the_prior_state(self, db, tenant):
        # ⚠️ Restores values that are WRONG. That is what a downgrade means.
        self._seed(db, tenant.id)
        before = self._categories(db, tenant.id)
        _apply(db, tenant.id)
        _apply(db, tenant.id, forward=False)
        assert self._categories(db, tenant.id) == before

    def test_the_other_bucket_empties_completely(self, db, tenant):
        self._seed(db, tenant.id)
        _apply(db, tenant.id)
        got = self._categories(db, tenant.id)
        assert "other" not in got.values()

    def test_a_row_already_correct_is_left_alone(self, db, tenant):
        # Scoped by (account_number, current value), so a tenant whose chart is
        # already right is untouched — this is what makes it safe to run
        # against every database rather than one.
        db.add(
            TenantGLMapping(
                id=str(uuid.uuid4()),
                tenant_id=tenant.id,
                platform_category="revenue",
                account_number="5010",
                account_name="PRECAST SALES",
            )
        )
        db.commit()
        _apply(db, tenant.id)
        assert self._categories(db, tenant.id)["5010"] == "revenue"
