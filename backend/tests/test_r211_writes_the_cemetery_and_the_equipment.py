"""Migration r211: James's D2 and D3, tested where the claim belongs.

⚠️ THE MIGRATION IS EXERCISED BY CALLING ITS `upgrade()`, NOT BY ASSUMING IT RAN.
Alembic refuses to run a migration twice, so "it is idempotent" could never be
exercised through alembic — and on a fresh CI database r211 legitimately writes
NOTHING, because the `sunnycrest` tenant it is guarded on is created by the seed
AFTER `alembic upgrade head`. The behavioural approve suites were written to assert
r211's rows and turned CI red for exactly that reason; the fix was to move the claim
here and let those suites ensure their own fixtures.

⚠️ EVERY TEST WORKS ON A THROWAWAY TENANT AND ROLLS BACK. Running the real migration
against the real `sunnycrest` row would write to whatever database this is pointed
at, which on a developer's machine is the tenant the browser walk uses.
"""

from __future__ import annotations

import importlib.util
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.database import SessionLocal


def _refuse_a_non_local_database() -> None:
    from urllib.parse import urlparse

    from app.config import settings

    host = (urlparse(settings.DATABASE_URL).hostname or "").lower()
    assert host in ("localhost", "127.0.0.1", "::1", "")


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "r211", "alembic/versions/r211_sunnycrest_cemetery_and_equipment.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def db():
    _refuse_a_non_local_database()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def run_upgrade(db):
    """Call the migration's own `upgrade()` against this session, inside a savepoint."""
    m = _load_migration()

    class FakeOp:
        @staticmethod
        def get_bind():
            return db.connection()

    m.op = FakeOp
    return m


@pytest.fixture
def throwaway_sunnycrest(db):
    """A tenant whose slug is what the migration looks for, rolled back after.

    ⚠️ THE REAL `sunnycrest` ROW IS RENAMED OUT OF THE WAY AND PUT BACK, because the
    migration finds its tenant by slug and there can only be one. All inside a
    savepoint, so a failure cannot leave the real tenant renamed.
    """
    sp = db.begin_nested()
    real = db.execute(
        text("SELECT id, slug FROM companies WHERE slug = 'sunnycrest'")
    ).first()
    if real:
        db.execute(
            text("UPDATE companies SET slug = 'sunnycrest-parked' WHERE id = :i"),
            {"i": real.id},
        )
    tid = str(uuid.uuid4())
    db.execute(
        # ⚠️ `created_at`/`updated_at` ARE NOT NULL WITH NO DEFAULT on this table, so
        # the ORM normally supplies them; a raw insert must say so itself.
        text("INSERT INTO companies (id, name, slug, is_active, created_at, updated_at) "
             "VALUES (:i, 'R211 Fixture', 'sunnycrest', true, now(), now())"),
        {"i": tid},
    )
    db.flush()
    try:
        yield tid
    finally:
        sp.rollback()


def _rows(db, tid):
    cems = [
        r.name
        for r in db.execute(
            text("SELECT name FROM cemeteries WHERE company_id = :t"), {"t": tid}
        )
    ]
    prods = {
        r.sku: (r.name, r.price)
        for r in db.execute(
            text("SELECT sku, name, price FROM products WHERE company_id = :t"),
            {"t": tid},
        )
    }
    return cems, prods


def test_it_writes_the_cemetery_and_the_four_products(db, run_upgrade, throwaway_sunnycrest):
    run_upgrade.upgrade()
    cems, prods = _rows(db, throwaway_sunnycrest)
    assert cems == ["St. Mary's Cemetery"], cems
    assert set(prods) == {"CE-PKG-FULL", "CE-PKG-TENT", "CE-PKG-LDG", "CE-PKG-LD"}, prods


def test_the_prices_are_the_price_list_prices(db, run_upgrade, throwaway_sunnycrest):
    """⚠️ THE FOUR FIGURES JAMES NAMED, read from the 2026-02-01 price list PDF's own
    GRAVESIDE SERVICE table, "With Our Product" column."""
    run_upgrade.upgrade()
    _cems, prods = _rows(db, throwaway_sunnycrest)
    assert prods["CE-PKG-FULL"] == ("Full Equipment", Decimal("300.00"))
    assert prods["CE-PKG-TENT"] == ("Tent Only", Decimal("225.00"))
    assert prods["CE-PKG-LDG"] == ("Lowering Device & Grass", Decimal("185.00"))
    assert prods["CE-PKG-LD"] == ("Lowering Device Only", Decimal("140.00"))


def test_the_product_names_are_what_APPROVE_MATCHES_ON(db, run_upgrade, throwaway_sunnycrest):
    """⚠️ THE NAMES ARE THE INTERFACE, NOT THE SKUS. Approve matches a captured
    equipment package to a product by its exact NAME, built from the schema's own
    `EQUIPMENT_PACKAGES` labels. A product written here under a prettier name would
    leave the package unbillable and Approve would block — so the two are asserted
    against each other rather than against a retyped list."""
    from app.services.capture.approval import EQUIPMENT_PRODUCT_NAMES

    run_upgrade.upgrade()
    _cems, prods = _rows(db, throwaway_sunnycrest)
    written = {name for name, _price in prods.values()}
    for slug in ("full_equipment", "tent_only", "lowering_device_and_grass",
                 "lowering_device_only"):
        assert EQUIPMENT_PRODUCT_NAMES[slug] in written, (slug, written)


def test_it_is_IDEMPOTENT(db, run_upgrade, throwaway_sunnycrest):
    # ⚠️ ONLY REACHABLE BY CALLING `upgrade()` TWICE DIRECTLY. Alembic would refuse
    # the second run, so going through alembic could never test this.
    run_upgrade.upgrade()
    run_upgrade.upgrade()
    run_upgrade.upgrade()
    cems, prods = _rows(db, throwaway_sunnycrest)
    assert len(cems) == 1, cems
    assert len(prods) == 4, prods


def test_the_DOWNGRADE_removes_exactly_what_it_wrote(db, run_upgrade, throwaway_sunnycrest):
    tid = throwaway_sunnycrest
    # a row a human added, which the downgrade must not touch
    db.execute(
        text("INSERT INTO cemeteries (id, company_id, name, is_active) "
             "VALUES (:i, :t, 'Hand Added Memorial', true)"),
        {"i": str(uuid.uuid4()), "t": tid},
    )
    run_upgrade.upgrade()
    run_upgrade.downgrade()
    cems, prods = _rows(db, tid)
    assert cems == ["Hand Added Memorial"], cems
    assert prods == {}, prods


def test_it_WRITES_NOTHING_without_a_sunnycrest_tenant(db, run_upgrade):
    """⚠️ THE INSTRUCTION, AND THE BEHAVIOUR CI ACTUALLY EXERCISES. On a fresh
    database the tenant arrives after migrations, so this is the path that runs
    there — and it must write nothing rather than fail or land rows on some other
    tenant."""
    sp = db.begin_nested()
    real = db.execute(
        text("SELECT id FROM companies WHERE slug = 'sunnycrest'")
    ).scalar()
    if real:
        db.execute(
            text("UPDATE companies SET slug = 'sunnycrest-parked' WHERE id = :i"),
            {"i": real},
        )
        db.flush()
    before_c = db.execute(text("SELECT count(*) FROM cemeteries")).scalar()
    before_p = db.execute(
        text("SELECT count(*) FROM products WHERE sku LIKE 'CE-PKG-%'")
    ).scalar()
    try:
        run_upgrade.upgrade()
        assert db.execute(text("SELECT count(*) FROM cemeteries")).scalar() == before_c
        assert db.execute(
            text("SELECT count(*) FROM products WHERE sku LIKE 'CE-PKG-%'")
        ).scalar() == before_p
    finally:
        sp.rollback()
