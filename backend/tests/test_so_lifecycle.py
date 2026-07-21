"""S&O Session Three pins — lifecycle (audit #2 D-3 net / D-6 vocabulary /
D-7-partial convert bypass / shipment-policy face).

FIX 1: `completed` joins the 18:00 batch net — a completed-uninvoiced
order drafts; an invoiced one doesn't (double protection).
FIX 2: batch invoices state the bill-in-full-at-shipment policy on their
face (Operator Decision 2, pre-staged option b).
FIX 3: one canonical cancel spelling — both legacy spellings excluded
everywhere; PATCH input normalizes.
FIX 4: the Order-Station convert path fires delivery auto-creation
(the confirmed-on-INSERT hook bypass closed) + money-field parity
between the two converters.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.customer import Customer
from app.models.sales_order import CANCEL_SPELLINGS, STATUS_CANCELLED, SalesOrder
from app.services import sales_service


@pytest.fixture(scope="module")
def world():
    from app.models.company import Company
    from app.models.delivery_settings import DeliverySettings
    from app.models.role import Role
    from app.models.user import User
    db = SessionLocal()
    co = Company(name="LC3", slug=f"lc3-{uuid.uuid4().hex[:6]}")
    db.add(co); db.flush()
    role = Role(company_id=co.id, name="LC3", slug=f"lc3-{uuid.uuid4().hex[:4]}")
    db.add(role); db.flush()
    usr = User(company_id=co.id, email=f"lc3-{uuid.uuid4().hex[:6]}@example.com",
               hashed_password="x", first_name="Pin", last_name="Three",
               role_id=role.id)
    settings = DeliverySettings(
        company_id=co.id,
        invoice_generation_mode="end_of_day",
        auto_create_delivery_from_order=True,
    )
    db.add_all([usr, settings]); db.commit()
    ids = {"co": co.id, "user": usr.id}
    db.close()
    yield ids
    db = SessionLocal()
    for stmt in (
        "DELETE FROM invoice_lines WHERE invoice_id IN (SELECT id FROM invoices WHERE company_id = :c)",
        "DELETE FROM invoices WHERE company_id = :c",
        "DELETE FROM deliveries WHERE company_id = :c",
        "DELETE FROM sales_order_lines WHERE sales_order_id IN (SELECT id FROM sales_orders WHERE company_id = :c)",
        "DELETE FROM sales_orders WHERE company_id = :c",
        "DELETE FROM quote_lines WHERE quote_id IN (SELECT id FROM quotes WHERE company_id = :c)",
        "DELETE FROM quotes WHERE company_id = :c",
        "DELETE FROM vault_items WHERE company_id = :c",
        "DELETE FROM audit_logs WHERE company_id = :c",
        "DELETE FROM crm_activities WHERE company_id = :c",
        "DELETE FROM agent_alerts WHERE tenant_id = :c",
        # agent_activity_log rows are written by the sweeper path;
        # without this the companies DELETE fails silently and the
        # fixture litters one LC3 company per run (tripwire catch,
        # Suite Session 2).
        "DELETE FROM agent_activity_log WHERE tenant_id = :c",
        "DELETE FROM delivery_settings WHERE company_id = :c",
        "DELETE FROM vaults WHERE company_id = :c",
        "DELETE FROM company_modules WHERE company_id = :c",
        "DELETE FROM financial_accounts WHERE tenant_id = :c",
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


def _mk_customer(db, world) -> Customer:
    c = Customer(company_id=world["co"], name=f"FH {uuid.uuid4().hex[:4]}",
                 account_number=f"LC-{uuid.uuid4().hex[:6]}",
                 current_balance=Decimal("0.00"))
    db.add(c); db.commit()
    return c


def _mk_order(db, world, customer, *, status, total="400.00",
              scheduled_yesterday=True) -> SalesOrder:
    o = SalesOrder(
        id=str(uuid.uuid4()), company_id=world["co"],
        number=f"SO-LC3-{uuid.uuid4().hex[:6]}", customer_id=customer.id,
        status=status, subtotal=Decimal(total), tax_amount=Decimal("0.00"),
        total=Decimal(total),
        order_date=datetime.now(timezone.utc),
        scheduled_date=(datetime.now(timezone.utc) - timedelta(days=1)).date()
        if scheduled_yesterday else None,
    )
    db.add(o); db.commit()
    return o


def _run_batch(db, world):
    from app.services.draft_invoice_service import generate_draft_invoices
    generate_draft_invoices(db, world["co"])


def _invoices_for(db, order_id):
    return db.execute(sql_text(
        "SELECT id, status, notes FROM invoices WHERE sales_order_id = :o"),
        {"o": order_id}).fetchall()


class TestCompletedJoinsTheNet:
    def test_completed_uninvoiced_order_drafts(self, db, world):
        cust = _mk_customer(db, world)
        order = _mk_order(db, world, cust, status="completed")
        _run_batch(db, world)
        invs = _invoices_for(db, order.id)
        assert len(invs) == 1
        assert invs[0][1] == "draft"          # inert until approval (Session Two)
        assert _balance(db, cust.id) == Decimal("0.00")  # draft moves nothing

    def test_invoiced_completed_order_does_not_double(self, db, world):
        cust = _mk_customer(db, world)
        order = _mk_order(db, world, cust, status="completed")
        _run_batch(db, world)
        _run_batch(db, world)  # second sweep — the net must not re-catch
        assert len(_invoices_for(db, order.id)) == 1

    def test_cancelled_stays_out_both_spellings(self, db, world):
        cust = _mk_customer(db, world)
        for sp in CANCEL_SPELLINGS:
            order = _mk_order(db, world, cust, status=sp)
            _run_batch(db, world)
            assert _invoices_for(db, order.id) == []


def _balance(db, customer_id) -> Decimal:
    return Decimal(str(db.execute(
        sql_text("SELECT current_balance FROM customers WHERE id = :i"),
        {"i": customer_id}).scalar()))


class TestPolicyOnTheFace:
    def test_batch_invoice_states_the_policy(self, db, world):
        from app.services.draft_invoice_service import _POLICY_NOTE
        cust = _mk_customer(db, world)
        order = _mk_order(db, world, cust, status="delivered")
        _run_batch(db, world)
        invs = _invoices_for(db, order.id)
        assert len(invs) == 1
        assert _POLICY_NOTE in (invs[0][2] or "")


class TestVocabularyHeal:
    def test_patch_normalizes_legacy_spelling(self, db, world):
        cust = _mk_customer(db, world)
        order = _mk_order(db, world, cust, status="confirmed",
                          scheduled_yesterday=False)

        class _Patch:
            status = "canceled"  # the legacy single-L
            required_date = None; shipped_date = None; notes = None
            deceased_name = None; service_location = None
            service_location_other = None; service_time = None; eta = None
        updated = sales_service.update_sales_order(
            db, world["co"], world["user"], order.id, _Patch())
        assert updated.status == STATUS_CANCELLED  # canonical double-L stored

    def test_cancelled_order_refuses_invoicing_canonical(self, db, world):
        from fastapi import HTTPException
        cust = _mk_customer(db, world)
        order = _mk_order(db, world, cust, status=STATUS_CANCELLED,
                          scheduled_yesterday=False)
        with pytest.raises(HTTPException) as e:
            sales_service.create_invoice_from_order(
                db, world["co"], world["user"], order.id)
        assert e.value.status_code == 400


class TestConvertBypassClosed:
    def _mk_quote(self, db, world, cust):
        from app.services import quote_service
        return quote_service.create_quote(
            db, world["co"], world["user"],
            customer_name=cust.name, product_line="funeral_vaults",
            line_items=[{"description": "Vault", "quantity": 1,
                         "unit_price": "900.00"}],
            customer_id=cust.id,
        )

    def test_order_station_convert_creates_delivery(self, db, world):
        from app.services import quote_service
        cust = _mk_customer(db, world)
        q = self._mk_quote(db, world, cust)
        result = quote_service.convert_quote_to_order(
            db, world["co"], world["user"], q["id"])
        deliveries = db.execute(sql_text(
            "SELECT id FROM deliveries WHERE order_id = :o"),
            {"o": result["id"]}).fetchall()
        assert len(deliveries) == 1  # the bypass is closed

    def test_converter_money_parity(self, db, world):
        """Identical quote through BOTH converters → identical money shape
        (subtotal / tax / total / lines / payment_terms). Status divergence
        (draft vs confirmed) is the documented D-11 seam, not asserted."""
        from app.services import quote_service
        cust = _mk_customer(db, world)
        q1 = self._mk_quote(db, world, cust)
        q2 = self._mk_quote(db, world, cust)

        r1 = quote_service.convert_quote_to_order(
            db, world["co"], world["user"], q1["id"])
        o1 = db.query(SalesOrder).filter(SalesOrder.id == r1["id"]).one()
        o2 = sales_service.convert_quote_to_order(
            db, world["co"], world["user"], q2["id"])

        for f in ("subtotal", "tax_amount", "total", "payment_terms"):
            assert getattr(o1, f) == getattr(o2, f), f
        l1 = [(ln.description, ln.quantity, ln.unit_price, ln.line_total)
              for ln in o1.lines]
        l2 = [(ln.description, ln.quantity, ln.unit_price, ln.line_total)
              for ln in o2.lines]
        assert l1 == l2
