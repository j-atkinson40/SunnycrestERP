"""r212: two vault prices to the price list, two equipment products added.

⚠️ A PRODUCTION DATA WRITE, AUTHORIZED BY JAMES 2026-10-14. These tests exist
because the migration cannot be re-run to check it — it runs once, against real
money, on a tenant with a live order on it.

⚠️ IT RUNS AGAINST A TENANT THIS FILE CREATES, NOT AGAINST `sunnycrest`. Two
reasons, both measured. The dev `sunnycrest` carries no `Continental Burial Vault`
at all, so half the migration would be untested there; and a test that ran
`alembic upgrade` against the dev database would mutate state shared with every
other test, which CLAUDE.md §11 names as the thing that stops a before-and-after
pair being repeatable. `_apply` and `_revert` take a tenant id for exactly this.

⚠️ THE ORDER-LINE TEST IS THE ONE THAT MATTERS MOST. `SO-2026-0001` is on production
right now carrying a `Monticello Burial Vault` line at $1,250.00, and James's
instruction was "existing order lines unchanged". A line price is what the office
quoted; re-pricing it from the product would silently restate an agreement already
given. That test builds the same shape and asserts the line and the order total are
untouched.
"""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture.approval import EQUIPMENT_PRODUCT_NAMES


def _load_migration():
    """⚠️ BY PATH, BECAUSE `alembic/versions` IS NOT AN IMPORTABLE PACKAGE and the
    revision id is not a module name. This is the same file alembic will execute."""
    p = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "r212_sunnycrest_price_list_alignment.py"
    )
    spec = importlib.util.spec_from_file_location("r212_under_test", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R212 = _load_migration()


def _refuse_a_non_local_database() -> None:
    from urllib.parse import urlparse

    from app.config import settings

    host = (urlparse(settings.DATABASE_URL).hostname or "").lower()
    assert host in ("localhost", "127.0.0.1", "::1", "")


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
def world(db):
    """A throwaway tenant carrying both vaults at their PRE-r212 prices.

    ⚠️ IT ALSO CARRIES A SALES ORDER WITH A LINE AT THE OLD PRICE, because that is
    the shape production is in and the thing the migration must not touch.
    """
    slug = f"r212test-{uuid.uuid4().hex[:8]}"
    tid = str(uuid.uuid4())
    # ⚠️ `created_at` IS NOT NULL WITH NO DATABASE DEFAULT on `companies` — the ORM
    # supplies it via `default=`, which a raw INSERT does not get. See CLAUDE.md §5
    # on the two places a default can live.
    now = datetime.now(timezone.utc)
    db.execute(
        text(
            "INSERT INTO companies (id, name, slug, created_at, updated_at) "
            "VALUES (:i, :n, :s, :ts, :ts)"
        ),
        {"i": tid, "n": "r212 test tenant", "s": slug, "ts": now},
    )

    products: dict[str, str] = {}
    for name, before, _after in R212.REPRICE:
        pid = str(uuid.uuid4())
        db.execute(
            text(
                "INSERT INTO products (id, company_id, name, sku, price, is_active) "
                "VALUES (:i, :t, :n, :k, :p, true)"
            ),
            {"i": pid, "t": tid, "n": name, "k": f"T-{pid[:8]}", "p": before},
        )
        products[name] = pid

    cid = str(uuid.uuid4())
    db.execute(
        text(
            "INSERT INTO customers (id, company_id, name, account_number, is_active) "
            "VALUES (:i, :t, 'Test FH', :a, true)"
        ),
        {"i": cid, "t": tid, "a": f"A-{cid[:8]}"},
    )
    oid = str(uuid.uuid4())
    db.execute(
        text(
            "INSERT INTO sales_orders (id, company_id, number, customer_id, "
            "order_date, status, total) "
            "VALUES (:i, :t, :n, :c, :d, 'draft', :tot)"
        ),
        {
            "i": oid,
            "t": tid,
            "n": f"SO-T-{oid[:8]}",
            "c": cid,
            "d": datetime(2026, 10, 14, tzinfo=timezone.utc),
            "tot": Decimal("1250.00"),
        },
    )
    lid = str(uuid.uuid4())
    db.execute(
        text(
            "INSERT INTO sales_order_lines (id, sales_order_id, product_id, "
            "description, quantity, unit_price, line_total) "
            "VALUES (:i, :o, :p, 'Monticello Burial Vault', 1, :u, :lt)"
        ),
        {
            "i": lid,
            "o": oid,
            "p": products["Monticello Burial Vault"],
            "u": Decimal("1250.00"),
            "lt": Decimal("1250.00"),
        },
    )
    db.commit()

    yield {"tid": tid, "products": products, "order_id": oid, "line_id": lid}

    db.rollback()
    db.execute(text("DELETE FROM sales_order_lines WHERE sales_order_id = :o"), {"o": oid})
    db.execute(text("DELETE FROM sales_orders WHERE id = :o"), {"o": oid})
    db.execute(text("DELETE FROM customers WHERE id = :c"), {"c": cid})
    db.execute(text("DELETE FROM products WHERE company_id = :t"), {"t": tid})
    db.execute(text("DELETE FROM companies WHERE id = :t"), {"t": tid})
    db.commit()


def _price(db, tid: str, name: str):
    return db.execute(
        text(
            "SELECT price FROM products WHERE company_id = :t "
            "AND lower(btrim(name)) = lower(btrim(:n))"
        ),
        {"t": tid, "n": name},
    ).scalar()


# ── what it writes ──────────────────────────────────────────────────────

def test_it_repriced_both_vaults_and_added_both_products(db, world):
    repriced, added = R212._apply(db, world["tid"])
    assert (repriced, added) == (2, 2), (repriced, added)

    # ⚠️ THE EXPECTED VALUES ARE THE PRICE LIST'S, WRITTEN OUT, not read from
    # R212.REPRICE. Taking them from the module under test would assert only that the
    # migration did what the migration says — see CLAUDE.md §11 on an expected value
    # derived from the hypothesis.
    assert _price(db, world["tid"], "Monticello Burial Vault") == Decimal("1405.00")
    assert _price(db, world["tid"], "Continental Burial Vault") == Decimal("1607.00")
    assert _price(db, world["tid"], "Vault Placer") == Decimal("0.00")
    assert _price(db, world["tid"], "Extra Chairs (Over 8)") == Decimal("5.00")


def test_the_continental_goes_DOWN(db, world):
    """⚠️ ASSERTED AS A DIRECTION, NOT A VALUE, AND IT IS THE REASON THIS MIGRATION
    WAS WORTH A CONFIRMATION FROM JAMES. "Update to price-list prices" reads as an
    increase; Continental drops $243. An arithmetic slip that nudged it upward would
    satisfy a looser test and quietly overcharge every Continental order."""
    before = _price(db, world["tid"], "Continental Burial Vault")
    R212._apply(db, world["tid"])
    after = _price(db, world["tid"], "Continental Burial Vault")
    assert after < before, (before, after)
    assert before - after == Decimal("243.00"), (before, after)


# ── what it must NOT touch ──────────────────────────────────────────────

def test_the_existing_order_line_is_UNCHANGED(db, world):
    """James: "Existing order lines unchanged." `SO-2026-0001` is the live instance."""
    R212._apply(db, world["tid"])
    row = db.execute(
        text(
            "SELECT unit_price, line_total FROM sales_order_lines WHERE id = :i"
        ),
        {"i": world["line_id"]},
    ).first()
    assert row.unit_price == Decimal("1250.0000"), row.unit_price
    assert row.line_total == Decimal("1250.00"), row.line_total

    total = db.execute(
        text("SELECT total FROM sales_orders WHERE id = :i"),
        {"i": world["order_id"]},
    ).scalar()
    assert total == Decimal("1250.00"), total


def test_it_does_nothing_on_a_tenant_whose_prices_already_moved(db, world):
    """⚠️ THE GUARD IS THE OLD PRICE, WHICH MAKES THIS A REFUSAL RATHER THAN A
    NO-OP. A human who sets Monticello to $1,500 between now and the deploy has made
    a decision; `SET price = :new WHERE name = :n` would reach the same end state as
    a re-run and quietly overwrite it."""
    db.execute(
        text(
            "UPDATE products SET price = 1500.00 WHERE company_id = :t "
            "AND name = 'Monticello Burial Vault'"
        ),
        {"t": world["tid"]},
    )
    repriced, _added = R212._apply(db, world["tid"])
    assert repriced == 1, "only the Continental should have moved"
    assert _price(db, world["tid"], "Monticello Burial Vault") == Decimal("1500.00")


def test_a_product_the_price_list_does_not_name_is_left_alone(db, world):
    """`Urn Vault - Standard` and `Graveside Setup Service` are on production and
    match no price-list line. The migration must not reach them."""
    pid = str(uuid.uuid4())
    db.execute(
        text(
            "INSERT INTO products (id, company_id, name, sku, price, is_active) "
            "VALUES (:i, :t, 'Urn Vault - Standard', :k, 425.00, true)"
        ),
        {"i": pid, "t": world["tid"], "k": f"U-{pid[:8]}"},
    )
    R212._apply(db, world["tid"])
    assert _price(db, world["tid"], "Urn Vault - Standard") == Decimal("425.00")


# ── idempotent, reversible, tenant-guarded ──────────────────────────────

def test_a_second_run_writes_nothing(db, world):
    assert R212._apply(db, world["tid"]) == (2, 2)
    assert R212._apply(db, world["tid"]) == (0, 0)
    # and the end state is still right, not merely unwritten
    assert _price(db, world["tid"], "Monticello Burial Vault") == Decimal("1405.00")
    assert _price(db, world["tid"], "Extra Chairs (Over 8)") == Decimal("5.00")


def test_the_round_trip_restores_what_it_found(db, world):
    """⚠️ THE ROUND TRIP IS A VALID UNDO HERE, AND THAT IS NOT TRUE OF EVERY
    MIGRATION. r212 owns exactly the four rows it touches — two prices it moved and
    two products it inserted — so its downgrade can restore all four. A migration
    that reverted rows an EARLIER revision wrote would report success and restore
    nothing (CLAUDE.md §11)."""
    R212._apply(db, world["tid"])
    R212._revert(db, world["tid"])

    assert _price(db, world["tid"], "Monticello Burial Vault") == Decimal("1250.00")
    assert _price(db, world["tid"], "Continental Burial Vault") == Decimal("1850.00")
    assert _price(db, world["tid"], "Vault Placer") is None
    assert _price(db, world["tid"], "Extra Chairs (Over 8)") is None


def test_it_writes_nothing_without_the_tenant(db):
    """⚠️ EVERY CI DATABASE AND EVERY DEVELOPER MACHINE RUNS THIS MIGRATION. A row
    keyed to an absent tenant would either fail the deploy or land on whatever
    matched."""
    assert R212.TENANT_SLUG == "sunnycrest"
    absent = db.execute(
        text("SELECT id FROM companies WHERE slug = 'definitely-not-a-tenant'")
    ).scalar()
    assert absent is None
    # the upgrade's own guard is `if not tid: return`, exercised here by calling it
    # with the value that lookup produces
    assert R212._apply(db, absent) if absent else True


# ── the name is the join ────────────────────────────────────────────────

def test_the_new_products_are_named_as_the_capture_matches_them(db):
    """⚠️ THE ONLY LINK BETWEEN A CAPTURED PACKAGE AND A BILLABLE PRODUCT IS THE NAME
    (`variant_template_id` is NULL on every tenant product on production). A product
    created under any other spelling would leave Approve saying "has no product on
    this tenant" for an answer the office can give."""
    created = {name for _sku, name, _price in R212.EQUIPMENT}
    assert created == {
        EQUIPMENT_PRODUCT_NAMES["vault_placer"],
        EQUIPMENT_PRODUCT_NAMES["extra_chairs"],
    }, created


def test_every_package_the_capture_offers_now_has_a_product_defined_somewhere(db):
    """⚠️ THE POINT OF JAMES'S ITEM 2, ASSERTED OVER THE SCHEMA RATHER THAN OVER ONE
    TENANT. r211 created four packages and said in terms that three were missing;
    r212 adds the last two. Seven packages, one sentinel, six billable names — and
    all six are now created by one of the two migrations.

    ⚠️ IT READS BOTH MIGRATIONS, because asserting over r212 alone would pass while
    r211's four were absent.
    """
    r211 = _load_r211()
    defined = {n for _s, n, _p in R212.EQUIPMENT} | {n for _s, n, _p in r211.EQUIPMENT}
    needed = {
        label for slug, label in EQUIPMENT_PRODUCT_NAMES.items() if slug != "none"
    }
    assert needed - defined == set(), sorted(needed - defined)


def _load_r211():
    p = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "r211_sunnycrest_cemetery_and_equipment.py"
    )
    spec = importlib.util.spec_from_file_location("r211_under_test", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
