"""D-11 U-2+U-3 pins — one lifecycle, one converter (parameterized).

U-2: one vocabulary (rejected survives; declined is an inbound alias that
never stores), one transition rule set (converted terminal), the expiry
clock honoring the unified set.
U-3: ONE conversion path, both faces calling it — draft-vs-confirmed as
THE PARAMETER. THE PARITY PIN: identical quotes through both faces →
identical orders modulo the status parameter, field-compared.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.customer import Customer
from app.models.quote import QUOTE_STATUS_ALIASES, QUOTE_STATUSES
from app.models.tax import TaxJurisdiction, TaxRate
from app.services import quote_service, sales_service


@pytest.fixture(scope="module")
def world():
    from app.models.company import Company
    from app.models.delivery_settings import DeliverySettings
    from app.models.role import Role
    from app.models.user import User
    db = SessionLocal()
    co = Company(name="U23", slug=f"u23-{uuid.uuid4().hex[:6]}")
    db.add(co); db.flush()
    role = Role(company_id=co.id, name="U23", slug=f"u23-{uuid.uuid4().hex[:4]}")
    db.add(role); db.flush()
    usr = User(company_id=co.id, email=f"u23-{uuid.uuid4().hex[:6]}@example.com",
               hashed_password="x", first_name="Pin", last_name="U23",
               role_id=role.id)
    rate = TaxRate(tenant_id=co.id, rate_name="Cayuga 7",
                   rate_percentage=Decimal("7.0"))
    db.add_all([usr, rate]); db.flush()
    jur = TaxJurisdiction(tenant_id=co.id, jurisdiction_name="Cayuga NY",
                          state="NY", county="Cayuga", tax_rate_id=rate.id)
    cust = Customer(company_id=co.id, name="U23 FH",
                    account_number=f"U23-{uuid.uuid4().hex[:5]}",
                    zip_code="13021")
    settings = DeliverySettings(company_id=co.id,
                                auto_create_delivery_from_order=True)
    db.add_all([jur, cust, settings]); db.commit()
    ids = {"co": co.id, "user": usr.id, "cust": cust.id}
    db.close()
    yield ids
    db = SessionLocal()
    for stmt in (
        "DELETE FROM deliveries WHERE company_id = :c",
        "DELETE FROM sales_order_lines WHERE sales_order_id IN (SELECT id FROM sales_orders WHERE company_id = :c)",
        "DELETE FROM sales_orders WHERE company_id = :c",
        "DELETE FROM quote_lines WHERE quote_id IN (SELECT id FROM quotes WHERE company_id = :c)",
        "DELETE FROM quotes WHERE company_id = :c",
        "DELETE FROM vault_items WHERE company_id = :c",
        "DELETE FROM audit_logs WHERE company_id = :c",
        "DELETE FROM crm_activities WHERE company_id = :c",
        "DELETE FROM tax_jurisdictions WHERE tenant_id = :c",
        "DELETE FROM tax_rates WHERE tenant_id = :c",
        "DELETE FROM delivery_settings WHERE company_id = :c",
        "DELETE FROM vaults WHERE company_id = :c",
        "DELETE FROM company_modules WHERE company_id = :c",
        "DELETE FROM financial_accounts WHERE company_id = :c",
        "DELETE FROM customers WHERE company_id = :c",
        "DELETE FROM users WHERE company_id = :c",
        "DELETE FROM roles WHERE company_id = :c",
        "DELETE FROM companies WHERE id = :c",
    ):
        try:
            db.execute(sql_text(stmt), {"c": ids["co"]})
            db.commit()
        except Exception:
            db.rollback()
    db.close()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback(); s.close()


def _mk_quote(db, world):
    """One canonical quote shape used by every parity comparison."""
    return quote_service.create_quote(
        db, world["co"], world["user"],
        customer_name="U23 FH", product_line="funeral_vaults",
        line_items=[{"description": "Vault", "quantity": 1,
                     "unit_price": "1000.00"}],
        customer_id=world["cust"], delivery_charge=100,
        contact_name="Pat Contact", installation_address="1 Elm St",
        deceased_name="John Doe", notes="parity",
    )


class TestOneVocabulary:
    def test_the_set_and_the_alias(self):
        assert QUOTE_STATUSES == {"draft", "sent", "accepted", "rejected",
                                  "expired", "converted"}
        assert QUOTE_STATUS_ALIASES == {"declined": "rejected"}

    def test_declined_normalizes_via_q_face(self, db, world):
        q = _mk_quote(db, world)
        out = quote_service.update_quote_status(
            db, world["co"], world["user"], q["id"], "declined")
        assert out["status"] == "rejected"  # the row speaks canon

    def test_declined_normalizes_via_qte_face(self, db, world):
        q = _mk_quote(db, world)
        quote = sales_service.set_quote_status(
            db, world["co"], world["user"], q["id"], "declined")
        assert quote.status == "rejected"

    def test_converted_is_terminal_and_unsettable(self, db, world):
        q = _mk_quote(db, world)
        with pytest.raises(HTTPException) as e:
            sales_service.set_quote_status(
                db, world["co"], world["user"], q["id"], "converted")
        assert e.value.status_code == 400
        quote_service.convert_quote_to_order(
            db, world["co"], world["user"], q["id"])
        with pytest.raises(HTTPException) as e2:
            quote_service.update_quote_status(
                db, world["co"], world["user"], q["id"], "sent")
        assert e2.value.status_code == 400


class TestExpiryHonorsTheSet:
    def test_draft_sent_flip_others_untouched(self, db, world):
        from app.models.quote import Quote
        past = datetime.now(timezone.utc) - timedelta(days=1)
        rows = {}
        for st in ("draft", "sent", "accepted", "rejected"):
            q = _mk_quote(db, world)
            row = db.query(Quote).filter(Quote.id == q["id"]).one()
            row.status = st
            row.expiry_date = past
            rows[st] = row.id
        db.commit()
        sales_service.expire_stale_quotes(db, world["co"])
        db.expire_all()
        got = {st: db.query(Quote).get(qid).status for st, qid in rows.items()}
        assert got["draft"] == "expired"
        assert got["sent"] == "expired"
        assert got["accepted"] == "accepted"   # untouched
        assert got["rejected"] == "rejected"   # untouched


class TestOneConverter:
    def test_parity_modulo_the_parameter(self, db, world):
        """THE PARITY PIN OF THIS PHASE: identical quotes through both
        faces → identical orders MODULO status. Every money field, every
        line, terms, ship-to, deceased — field-compared."""
        from app.models.sales_order import SalesOrder
        q1 = _mk_quote(db, world)
        q2 = _mk_quote(db, world)

        r1 = quote_service.convert_quote_to_order(
            db, world["co"], world["user"], q1["id"])       # confirmed face
        o1 = db.query(SalesOrder).filter(SalesOrder.id == r1["id"]).one()
        o2 = sales_service.convert_quote_to_order(
            db, world["co"], world["user"], q2["id"])       # draft face

        assert o1.status == "confirmed" and o2.status == "draft"  # THE parameter
        for f in ("subtotal", "tax_rate", "tax_amount", "total",
                  "payment_terms", "ship_to_name", "ship_to_address",
                  "deceased_name", "notes", "customer_id"):
            assert getattr(o1, f) == getattr(o2, f), f
        l1 = [(ln.description, ln.quantity, ln.unit_price, ln.line_total,
               ln.is_auto_added) for ln in sorted(o1.lines, key=lambda x: x.sort_order)]
        l2 = [(ln.description, ln.quantity, ln.unit_price, ln.line_total,
               ln.is_auto_added) for ln in sorted(o2.lines, key=lambda x: x.sort_order)]
        assert l1 == l2

    def test_the_parameters_truth_delivery(self, db, world):
        """confirmed → delivery auto-created NOW; draft → not yet."""
        q1 = _mk_quote(db, world)
        q2 = _mk_quote(db, world)
        r1 = quote_service.convert_quote_to_order(
            db, world["co"], world["user"], q1["id"])
        o2 = sales_service.convert_quote_to_order(
            db, world["co"], world["user"], q2["id"])

        def deliveries(oid):
            return db.execute(sql_text(
                "SELECT count(*) FROM deliveries WHERE order_id = :o"),
                {"o": oid}).scalar()
        assert deliveries(r1["id"]) == 1
        assert deliveries(o2.id) == 0

    def test_u1_tax_truth_carries(self, db, world):
        """The resolved 7% travels quote → order on the fields the order
        HAS (tax_rate/tax_amount); the REASON stays on the quote,
        reachable via order.quote_id — no invented fields."""
        from app.models.quote import Quote
        from app.models.sales_order import SalesOrder
        q = _mk_quote(db, world)
        assert Decimal(str(q["total"])) == Decimal("1177.00")  # U-1's law
        r = quote_service.convert_quote_to_order(
            db, world["co"], world["user"], q["id"])
        order = db.query(SalesOrder).filter(SalesOrder.id == r["id"]).one()
        assert order.tax_amount == Decimal("77.00")
        assert order.total == Decimal("1177.00")
        src = db.query(Quote).filter(Quote.id == order.quote_id).one()
        assert "resolved: 7%" in src.tax_reason

    def test_unified_source_guard_both_faces(self, db, world):
        """A rejected quote refuses conversion on BOTH faces (the unified
        rule — the Q- face previously allowed any non-converted source)."""
        for face in ("q", "qte"):
            q = _mk_quote(db, world)
            sales_service.set_quote_status(
                db, world["co"], world["user"], q["id"], "rejected")
            with pytest.raises(HTTPException) as e:
                if face == "q":
                    quote_service.convert_quote_to_order(
                        db, world["co"], world["user"], q["id"])
                else:
                    sales_service.convert_quote_to_order(
                        db, world["co"], world["user"], q["id"])
            assert e.value.status_code == 400
