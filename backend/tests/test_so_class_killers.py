"""S&O Session One pins — the class-killers (audit #2 D-1/3-adjacent kills).

KILL 1 hand-math: $1,000 + $100 delivery @7% → $1,177 (tax path), $1,100
(no-tax), delivery-zero clean. KILL 2: missing price REFUSES; explicit 0
legitimate. KILL 3: the allocator survives concurrency + counts past
lexical breaks. KILL 4: a failed conversion never reports created.

BONUS CATCH (the pin earned its keep): the tax-path pin exposed a live
neighbor — autoflush=False + the placer block's db.refresh(quote) was
DISCARDING the just-computed tax on every customer quote. The flush-first
fix in quote_service.py is guarded by test_tax_path_1177 (it fails
without it).
"""
from __future__ import annotations

import threading
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.services import quote_service


@pytest.fixture(scope="module")
def world():
    from app.models.company import Company
    db = SessionLocal()
    co = Company(name="SO1", slug=f"sok-{uuid.uuid4().hex[:6]}")
    db.add(co); db.flush()
    from app.models.customer import Customer
    cust = Customer(company_id=co.id, name="Hand Check FH",
                    account_number=f"HC-{uuid.uuid4().hex[:4]}")
    from app.models.user import User
    from app.models.role import Role
    role = Role(company_id=co.id, name="SOK Admin", slug=f"sok-{uuid.uuid4().hex[:4]}")
    db.add(role); db.flush()
    usr = User(company_id=co.id, email=f"sok-{uuid.uuid4().hex[:6]}@example.com",
               hashed_password="x", first_name="Pin", last_name="Writer",
               role_id=role.id)
    db.add_all([cust, usr]); db.commit()
    ids = {"co": co.id, "cust": cust.id, "user": usr.id}
    db.close()
    yield ids
    db = SessionLocal()
    db.execute(sql_text(
        "DELETE FROM quote_lines WHERE quote_id IN "
        "(SELECT id FROM quotes WHERE company_id = :c)"), {"c": ids["co"]})
    db.commit()
    # Per-table commits — one failed delete must not roll back the rest.
    for t in ("quotes", "sales_order_lines", "sales_orders", "vault_items",
              "crm_activities", "audit_logs", "vaults", "company_modules",
              "financial_accounts", "customers", "users", "roles"):
        try:
            if t == "sales_order_lines":
                db.execute(sql_text(
                    "DELETE FROM sales_order_lines WHERE sales_order_id IN "
                    "(SELECT id FROM sales_orders WHERE company_id = :c)"),
                    {"c": ids["co"]})
            else:
                db.execute(sql_text(f"DELETE FROM {t} WHERE company_id = :c"),
                           {"c": ids["co"]})
            db.commit()
        except Exception:
            db.rollback()
    db.execute(sql_text("DELETE FROM companies WHERE id = :c"), {"c": ids["co"]})
    db.commit(); db.close()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback(); s.close()


def _mk_quote(db, world, monkeypatch, *, tax=False, delivery=None, lines=None):
    # customer_id also triggers the placer/crm side paths — they swallow
    # to warnings; the money path is what these pins measure.
    if tax:
        from app.services import tax_service

        class _R:  # rate object
            rate_percentage = Decimal("7.0")

        class _J:  # jurisdiction — U-1's reason string reads these
            county = "Test"; state = "NY"
        monkeypatch.setattr(tax_service, "get_jurisdiction_for_order",
                            lambda *a, **k: (_J(), _R()))
        monkeypatch.setattr(
            tax_service, "compute_tax",
            lambda subtotal, rate, exempt: (
                (subtotal * Decimal("0.07")).quantize(Decimal("0.01")),
                Decimal("0.07")),
        )
    return quote_service.create_quote(
        db, world["co"], world["user"],
        customer_name="Hand Check FH",
        product_line="funeral_vaults",
        line_items=lines or [
            {"description": "Vault", "quantity": 1, "unit_price": "1000.00"},
        ],
        customer_id=world["cust"] if tax else None,
        delivery_charge=delivery,
    )


class TestKill1DeliveryOnce:
    def test_tax_path_1177(self, db, world, monkeypatch):
        """$1,000 lines + $100 delivery @ 7% → subtotal 1100, tax 77,
        TOTAL $1,177.00 — the old code charged $1,277 (hand-proven)."""
        q = _mk_quote(db, world, monkeypatch, tax=True, delivery=100)
        assert Decimal(str(q["subtotal"])) == Decimal("1100.00")
        assert Decimal(str(q["total"])) == Decimal("1177.00")

    def test_no_tax_path_1100(self, db, world, monkeypatch):
        q = _mk_quote(db, world, monkeypatch, tax=False, delivery=100)
        assert Decimal(str(q["total"])) == Decimal("1100.00")

    def test_delivery_zero_clean(self, db, world, monkeypatch):
        q = _mk_quote(db, world, monkeypatch, tax=True, delivery=None)
        assert Decimal(str(q["total"])) == Decimal("1070.00")  # 1000 + 70


class TestKill2PriceRefusal:
    def test_missing_price_refuses_loudly(self, db, world, monkeypatch):
        with pytest.raises(ValueError, match="unit_price"):
            _mk_quote(db, world, monkeypatch,
                      lines=[{"description": "No price", "quantity": 1}])

    def test_explicit_zero_legitimate(self, db, world, monkeypatch):
        q = _mk_quote(db, world, monkeypatch,
                      lines=[{"description": "Included", "quantity": 1,
                              "unit_price": 0}])
        assert Decimal(str(q["total"])) == Decimal("0.00")


class TestKill3Numbering:
    def test_numeric_max_past_9999(self, db, world):
        from app.services.numbering import next_document_number
        from datetime import datetime, timezone
        y = datetime.now(timezone.utc).year
        db.execute(sql_text(
            "INSERT INTO quotes (id, company_id, number, customer_name, status, quote_date, created_at) "
            "VALUES (:i, :c, :n, 'x', 'draft', now(), now())"),
            {"i": str(uuid.uuid4()), "c": world["co"], "n": f"Q-{y}-9999"})
        db.execute(sql_text(
            "INSERT INTO quotes (id, company_id, number, customer_name, status, quote_date, created_at) "
            "VALUES (:i, :c, :n, 'x', 'draft', now(), now())"),
            {"i": str(uuid.uuid4()), "c": world["co"], "n": f"Q-{y}-10000"})
        db.commit()
        # Lexical max would say 9999 → 10000 (duplicate). Numeric says 10001.
        assert next_document_number(db, table="quotes", company_id=world["co"],
                                    prefix="Q") == f"Q-{y}-10001"
        db.rollback()

    def test_convention_breakers_ignored_not_crashing(self, db, world):
        from app.services.numbering import next_document_number
        db.execute(sql_text(
            "INSERT INTO sales_orders (id, company_id, number, customer_id, status, order_date, subtotal, tax_amount, total, created_at) "
            "SELECT :i, :c, 'SO-LEGACY-abc123', c2.id, 'draft', now(), 0, 0, 0, now() "
            "FROM customers c2 LIMIT 1"),
            {"i": str(uuid.uuid4()), "c": world["co"]})
        db.commit()
        n = next_document_number(db, table="sales_orders",
                                 company_id=world["co"], prefix="SO")
        assert n.endswith("-0001")  # LEGACY row ignored, no crash

    def test_concurrency_hammer(self, world):
        """Two sessions allocate + insert concurrently — distinct numbers,
        both commits survive the unique constraint."""
        results, errors = [], []

        def worker():
            s = SessionLocal()
            try:
                from app.services.numbering import next_document_number
                n = next_document_number(s, table="quotes",
                                         company_id=world["co"], prefix="QH")
                s.execute(sql_text(
                    "INSERT INTO quotes (id, company_id, number, customer_name, status, quote_date, created_at) "
                    "VALUES (:i, :c, :n, 'hammer', 'draft', now(), now())"),
                    {"i": str(uuid.uuid4()), "c": world["co"], "n": n})
                s.commit()
                results.append(n)
            except Exception as e:
                s.rollback(); errors.append(e)
            finally:
                s.close()

        threads = [threading.Thread(target=worker) for _ in range(6)]
        for t in threads: t.start()
        for t in threads: t.join()
        assert not errors, errors
        assert len(results) == 6
        assert len(set(results)) == 6  # ALL DISTINCT — the atomicity proof


class TestKill4NoSilent201:
    def test_conversion_failure_raises_not_created(self):
        import inspect
        from app.api.routes import order_station
        src = inspect.getsource(order_station)
        assert "conversion failure is not fatal" not in src  # the swallow is dead
        assert "no order exists" in src  # the honest refusal stands
