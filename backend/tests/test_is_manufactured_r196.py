"""`is_manufactured` asserts nothing until somebody establishes it.

⚠️ READ-ONLY. Creates no rows.

⚠️ SUBJECT: the database `DATABASE_URL` points at. Asserts r196 is applied there.

WHAT IT PINS, and the two tables are pinned in OPPOSITE directions on purpose:

1. **`products` holds NULL everywhere.** The column carried
   `server_default=false` on an already-populated table, so every product asserted
   "we do not make this" without anyone deciding it. Production measured 33 rows
   and ZERO true.

2. **`product_catalog_templates` keeps its values.** Its literals VARY — vaults
   `true`, cemetery equipment `false` — so they are per-row decisions, not a fill.
   Nulling them would destroy a real finding to satisfy a rule aimed at fills.

3. **Neither column has a default, of either kind.** The database default AND the
   SQLAlchemy-level `default=True` are both gone. A migration that dropped only
   the first would leave every ORM-created row still asserting `True`.

⚠️ The two directions are what makes this suite worth having. A test that only
checked "everything is NULL" would pass on a migration that nulled both tables —
which would be wrong, and wrong in a way nothing downstream would contradict.
"""
from __future__ import annotations

import pytest
from sqlalchemy import inspect, text

from app.database import SessionLocal, engine


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(scope="module", autouse=True)
def _require_r196(db):
    """⚠️ PRECONDITION. Without r196 the no-default assertions below describe a
    different schema, and the NULL assertion would be asserting the migration's
    own absence."""
    for table in ("products", "product_catalog_templates"):
        d = db.execute(
            text(
                "SELECT column_default FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = 'is_manufactured'"
            ),
            {"t": table},
        ).scalar_one()
        assert d is None, (
            f"{table}.is_manufactured still carries default {d!r} — r196 is not "
            f"applied to this database"
        )


class TestProductsAssertNothing:
    def test_no_product_carries_a_value(self, db):
        n = db.execute(
            text("SELECT count(*) FROM products WHERE is_manufactured IS NOT NULL")
        ).scalar_one()
        assert n == 0, f"{n} products assert a manufacture fact nobody established"

    def test_the_column_is_nullable(self, db):
        v = db.execute(
            text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name='products' AND column_name='is_manufactured'"
            )
        ).scalar_one()
        assert v == "YES"

    def test_the_orm_finally_declares_it(self):
        """⚠️ It had NO ORM attribute before r196 — structurally unreachable, not
        merely unread, which is why `assert_no_schema_drift` could never have
        caught it (model→DB only, DB-extra treated as noise)."""
        from app.models.product import Product

        col = Product.__table__.c.get("is_manufactured")
        assert col is not None, "Product still does not declare the column"
        assert col.nullable is True
        assert col.default is None, "a Python-side default would re-assert on insert"
        assert col.server_default is None


class TestTemplatesKeepTheirDecisions:
    def test_the_values_are_preserved_not_nulled(self, db):
        n = db.execute(
            text(
                "SELECT count(*) FROM product_catalog_templates "
                "WHERE is_manufactured IS NOT NULL"
            )
        ).scalar_one()
        assert n > 0, (
            "product_catalog_templates was nulled. Its literals VARY — vaults true, "
            "cemetery equipment false — so they are decisions, not a fill, and the "
            "rule that nulls fills does not reach them."
        )

    def test_the_values_actually_vary(self, db):
        """⚠️ THE POSITIVE CONTROL, AND IT IS THE WHOLE JUSTIFICATION. The
        preserve-don't-null ruling rests on these being per-row decisions. If they
        ever became uniform, that premise is gone and the ruling should be
        revisited rather than inherited."""
        vals = {
            r[0]
            for r in db.execute(
                text(
                    "SELECT DISTINCT is_manufactured FROM product_catalog_templates "
                    "WHERE is_manufactured IS NOT NULL"
                )
            )
        }
        assert vals == {True, False}, (
            f"expected both true and false; got {vals}. Uniform values would make "
            f"this the r188 fill shape after all."
        )

    def test_the_python_side_default_is_gone(self):
        """Dropping the server default alone would have fixed nothing for the path
        that actually inserts — the seeder goes through the ORM."""
        from app.models.product_catalog_template import ProductCatalogTemplate

        col = ProductCatalogTemplate.__table__.c.is_manufactured
        assert col.default is None, "SQLAlchemy-level default=True still present"
        assert col.server_default is None
        assert col.nullable is True


class TestTheSeedersWritesAreUnchanged:
    def test_the_three_writes_still_vary(self):
        """⚠️ Reads the SOURCE, not the database — the ruling to keep these was
        made from the literals, so the literals are what must not drift. Three
        loops, three categories, one of them different."""
        from pathlib import Path

        src = (
            Path(__file__).resolve().parents[1]
            / "app" / "services" / "catalog_template_seeder.py"
        ).read_text()
        writes = [
            ln.strip() for ln in src.splitlines() if "is_manufactured=" in ln
        ]
        assert len(writes) == 3, f"expected 3 writes, found {len(writes)}: {writes}"
        assert writes.count("is_manufactured=True,") == 2
        assert writes.count("is_manufactured=False,") == 1


class TestTheTwoTablesDisagreeOnPurpose:
    def test_one_is_null_and_the_other_is_not(self, db):
        """⚠️ THE SHAPE OF THE WHOLE MIGRATION IN ONE ASSERTION. A test that only
        checked "everything is NULL" would pass on a migration that nulled both,
        which would be wrong and which nothing downstream would contradict."""
        products_nonnull = db.execute(
            text("SELECT count(*) FROM products WHERE is_manufactured IS NOT NULL")
        ).scalar_one()
        templates_nonnull = db.execute(
            text(
                "SELECT count(*) FROM product_catalog_templates "
                "WHERE is_manufactured IS NOT NULL"
            )
        ).scalar_one()
        assert products_nonnull == 0
        assert templates_nonnull > 0

    def test_neither_column_can_acquire_a_default_again(self, db):
        insp = inspect(engine)
        for table in ("products", "product_catalog_templates"):
            col = next(
                c for c in insp.get_columns(table) if c["name"] == "is_manufactured"
            )
            assert col["default"] is None, f"{table} regained a default"
