"""S&O Session Two pins — the AR double-post dies (audit #2 D-2).

ONE POSTING MOMENT: the balance moves when the invoice becomes REAL
(approval / issuance), never at draft creation, and exactly once.
Flanks: double-invoice refused with the invoice named; draft orders
refuse invoicing; a voided draft never subtracts. The sweeper post-fix
finds nothing to launder.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.customer import Customer
from app.models.sales_order import SalesOrder
from app.services import sales_service
from app.services.draft_invoice_service import approve_invoice


@pytest.fixture(scope="module")
def world():
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User
    db = SessionLocal()
    co = Company(name="AR2", slug=f"ar2-{uuid.uuid4().hex[:6]}")
    db.add(co); db.flush()
    role = Role(company_id=co.id, name="AR2", slug=f"ar2-{uuid.uuid4().hex[:4]}")
    db.add(role); db.flush()
    usr = User(company_id=co.id, email=f"ar2-{uuid.uuid4().hex[:6]}@example.com",
               hashed_password="x", first_name="Pin", last_name="Two",
               role_id=role.id)
    db.add(usr); db.commit()
    ids = {"co": co.id, "user": usr.id}
    db.close()
    yield ids
    db = SessionLocal()
    for stmt in (
        "DELETE FROM invoice_lines WHERE invoice_id IN (SELECT id FROM invoices WHERE company_id = :c)",
        "DELETE FROM invoices WHERE company_id = :c",
        "DELETE FROM sales_order_lines WHERE sales_order_id IN (SELECT id FROM sales_orders WHERE company_id = :c)",
        "DELETE FROM sales_orders WHERE company_id = :c",
        "DELETE FROM vault_items WHERE company_id = :c",
        "DELETE FROM audit_logs WHERE company_id = :c",
        "DELETE FROM crm_activities WHERE company_id = :c",
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


def _mk_customer(db, world) -> Customer:
    c = Customer(company_id=world["co"], name=f"FH {uuid.uuid4().hex[:4]}",
                 account_number=f"AR-{uuid.uuid4().hex[:6]}",
                 current_balance=Decimal("0.00"))
    db.add(c); db.commit()
    return c


def _mk_order(db, world, customer, *, total="500.00", status="confirmed") -> SalesOrder:
    o = SalesOrder(
        id=str(uuid.uuid4()), company_id=world["co"],
        number=f"SO-PIN-{uuid.uuid4().hex[:6]}", customer_id=customer.id,
        status=status, subtotal=Decimal(total), tax_amount=Decimal("0.00"),
        total=Decimal(total),
        order_date=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc),
    )
    db.add(o); db.commit()
    return o


def _balance(db, customer_id) -> Decimal:
    return Decimal(str(db.execute(
        sql_text("SELECT current_balance FROM customers WHERE id = :i"),
        {"i": customer_id}).scalar()))


class TestOnePostingMoment:
    def test_draft_creation_moves_nothing(self, db, world):
        cust = _mk_customer(db, world)
        order = _mk_order(db, world, cust)
        inv = sales_service.create_invoice_from_order(
            db, world["co"], world["user"], order.id)
        assert inv.status == "draft"
        assert _balance(db, cust.id) == Decimal("0.00")

    def test_approval_posts_exactly_once(self, db, world):
        cust = _mk_customer(db, world)
        order = _mk_order(db, world, cust)
        inv = sales_service.create_invoice_from_order(
            db, world["co"], world["user"], order.id)
        approve_invoice(db, world["co"], inv.id, world["user"])
        # THE HAND MATH: one $500 invoice approved → balance $500, not $1,000.
        assert _balance(db, cust.id) == Decimal("500.00")

    def test_reapproval_refused_balance_untouched(self, db, world):
        cust = _mk_customer(db, world)
        order = _mk_order(db, world, cust)
        inv = sales_service.create_invoice_from_order(
            db, world["co"], world["user"], order.id)
        approve_invoice(db, world["co"], inv.id, world["user"])
        with pytest.raises(HTTPException) as e:
            approve_invoice(db, world["co"], inv.id, world["user"])
        assert e.value.status_code == 400
        assert _balance(db, cust.id) == Decimal("500.00")

    def test_manual_invoice_same_single_moment(self, db, world):
        cust = _mk_customer(db, world)

        class _Line:
            product_id = None; description = "Vault"; sort_order = 0
            quantity = Decimal("1"); unit_price = Decimal("250.00")

        class _Data:
            customer_id = cust.id; sales_order_id = None
            invoice_date = __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc)
            due_date = invoice_date; payment_terms = None
            tax_rate = Decimal("0.00"); notes = None
            lines = [_Line()]

        inv = sales_service.create_invoice(db, world["co"], world["user"], _Data())
        assert _balance(db, cust.id) == Decimal("0.00")  # draft: nothing
        approve_invoice(db, world["co"], inv.id, world["user"])
        assert _balance(db, cust.id) == Decimal("250.00")  # once

    def test_patch_out_of_draft_posts_and_back_refuses(self, db, world):
        cust = _mk_customer(db, world)
        order = _mk_order(db, world, cust)
        inv = sales_service.create_invoice_from_order(
            db, world["co"], world["user"], order.id)

        class _Patch:
            status = "sent"; notes = None
        sales_service.update_invoice(db, world["co"], world["user"], inv.id, _Patch())
        assert _balance(db, cust.id) == Decimal("500.00")

        class _Back:
            status = "draft"; notes = None
        with pytest.raises(HTTPException) as e:
            sales_service.update_invoice(db, world["co"], world["user"], inv.id, _Back())
        assert e.value.status_code == 400
        assert _balance(db, cust.id) == Decimal("500.00")


class TestFlankGuards:
    def test_double_invoice_refused_naming_existing(self, db, world):
        cust = _mk_customer(db, world)
        order = _mk_order(db, world, cust)
        inv = sales_service.create_invoice_from_order(
            db, world["co"], world["user"], order.id)
        with pytest.raises(HTTPException) as e:
            sales_service.create_invoice_from_order(
                db, world["co"], world["user"], order.id)
        assert e.value.status_code == 409
        assert inv.number in e.value.detail  # the existing invoice NAMED

    def test_draft_order_refuses_invoicing(self, db, world):
        cust = _mk_customer(db, world)
        order = _mk_order(db, world, cust, status="draft")
        with pytest.raises(HTTPException) as e:
            sales_service.create_invoice_from_order(
                db, world["co"], world["user"], order.id)
        assert e.value.status_code == 400
        assert "draft" in e.value.detail


class TestVoidHonesty:
    def test_void_draft_moves_nothing(self, db, world):
        cust = _mk_customer(db, world)
        order = _mk_order(db, world, cust)
        inv = sales_service.create_invoice_from_order(
            db, world["co"], world["user"], order.id)
        sales_service.void_invoice(db, world["co"], world["user"], inv.id)
        assert _balance(db, cust.id) == Decimal("0.00")  # never posted → no reversal

    def test_void_posted_reverses_once(self, db, world):
        cust = _mk_customer(db, world)
        order = _mk_order(db, world, cust)
        inv = sales_service.create_invoice_from_order(
            db, world["co"], world["user"], order.id)
        approve_invoice(db, world["co"], inv.id, world["user"])
        sales_service.void_invoice(db, world["co"], world["user"], inv.id)
        assert _balance(db, cust.id) == Decimal("0.00")  # +500 then -500


class TestSweeperPostFix:
    def test_full_lifecycle_leaves_sweeper_nothing(self, db, world):
        """The witness that matters: draft + approve + a standing draft →
        stored balances already equal calculated; the sweeper corrects 0."""
        from app.services.proactive_agents import run_ar_balance_reconciliation
        cust = _mk_customer(db, world)
        o1 = _mk_order(db, world, cust, total="300.00")
        o2 = _mk_order(db, world, cust, total="700.00")
        inv1 = sales_service.create_invoice_from_order(
            db, world["co"], world["user"], o1.id)
        approve_invoice(db, world["co"], inv1.id, world["user"])
        sales_service.create_invoice_from_order(  # stays draft — must not drift
            db, world["co"], world["user"], o2.id)
        assert _balance(db, cust.id) == Decimal("300.00")
        result = run_ar_balance_reconciliation(db, world["co"])
        assert result["balances_corrected"] == 0
        assert _balance(db, cust.id) == Decimal("300.00")
