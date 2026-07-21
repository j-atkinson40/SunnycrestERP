"""The exceptions arc pins — credit memos, the write-off verb, the
credit pocket's doors. Every money move hand-proven through the
Session-Two chokepoint; the balance law (current_balance = Σ open
invoice remainders; the pocket separate) holds at every step, proven by
the sweeper's zero-run after a full exceptions exercise.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.company import Company
from app.models.credit_memo import CreditMemo, CustomerCreditEntry
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.services import sales_service as ss


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _cleanup(db, company_ids):
    for cid in company_ids:
        for stmt in (
            "DELETE FROM customer_credit_entries WHERE company_id = :c",
            "DELETE FROM credit_memos WHERE company_id = :c",
            "DELETE FROM customer_payment_applications WHERE payment_id IN (SELECT id FROM customer_payments WHERE company_id = :c)",
            "DELETE FROM customer_payments WHERE company_id = :c",
            "DELETE FROM agent_alerts WHERE tenant_id = :c",
            "DELETE FROM behavioral_insights WHERE tenant_id = :c",
            "DELETE FROM behavioral_profiles WHERE tenant_id = :c",
            "DELETE FROM audit_logs WHERE company_id = :c",
            "DELETE FROM invoices WHERE company_id = :c",
            "DELETE FROM customers WHERE company_id = :c",
            "DELETE FROM users WHERE company_id = :c",
            "DELETE FROM vaults WHERE company_id = :c",
            "DELETE FROM company_modules WHERE company_id = :c",
            "DELETE FROM companies WHERE id = :c",
        ):
            try:
                db.execute(sql_text(stmt), {"c": cid})
                db.commit()
            except Exception:
                db.rollback()


def _world(db, tag: str):
    from app.models.role import Role
    from app.models.user import User
    co = Company(name=f"EXC {tag}", slug=f"exc-{tag}-{uuid.uuid4().hex[:6]}")
    db.add(co)
    db.flush()
    role = db.query(Role).first()
    user = User(company_id=co.id, email=f"exc-{uuid.uuid4().hex[:6]}@t.internal",
                hashed_password="x", first_name="Exc", last_name="Pin",
                role_id=role.id if role else None)
    cust = Customer(company_id=co.id, name="Hopkins FH",
                    current_balance=Decimal("0.00"),
                    credit_balance=Decimal("0.00"))
    db.add_all([user, cust])
    db.commit()
    # module-level shim: tests call verbs with U1 — patch to the real id
    globals()["U1"] = user.id
    return co, cust


def _posted_invoice(db, co, cust, total="1000.00", status="sent") -> Invoice:
    """A posted invoice, AR moved through the chokepoint (the one law)."""
    inv = Invoice(
        company_id=co.id, customer_id=cust.id,
        number=f"INV-X-{uuid.uuid4().hex[:6]}",
        invoice_date=datetime.now(timezone.utc) - timedelta(days=30),
        due_date=datetime.now(timezone.utc) - timedelta(days=1),
        status=status, total=Decimal(total), amount_paid=Decimal("0.00"),
    )
    db.add(inv)
    db.flush()
    ss.post_invoice_to_ar(db, co.id, inv)
    db.commit()
    return inv


def _fresh(db, obj):
    db.expire_all()
    return db.get(type(obj), obj.id)


class TestMemoHandProven:
    def test_memo_300_on_1000(self, db):
        """Invoice $1,000 → memo $300 → balance $700, AR moved −$300 ONCE."""
        co, cust = _world(db, "m1")
        try:
            inv = _posted_invoice(db, co, cust)
            assert _fresh(db, cust).current_balance == Decimal("1000.00")
            memo = ss.create_credit_memo(
                db, co.id, U1, inv.id, Decimal("300.00"),
                "damaged liner on delivery")
            assert memo.number.startswith("CM-")
            assert memo.status == "posted"
            assert memo.reason == "damaged liner on delivery"
            inv2 = _fresh(db, inv)
            assert inv2.balance_remaining == Decimal("700.00")
            assert inv2.amount_credited == Decimal("300.00")
            assert inv2.status == "partial"  # partially settled, honestly
            assert _fresh(db, cust).current_balance == Decimal("700.00")
        finally:
            _cleanup(db, [co.id])

    def test_reason_required(self, db):
        co, cust = _world(db, "m2")
        try:
            inv = _posted_invoice(db, co, cust)
            with pytest.raises(HTTPException) as e:
                ss.create_credit_memo(db, co.id, U1, inv.id,
                                      Decimal("100.00"), "   ")
            assert "reason" in e.value.detail.lower()
        finally:
            _cleanup(db, [co.id])

    def test_over_memo_refuses_toward_the_pocket(self, db):
        """A memo can't make an invoice negative — the excess is the
        pocket's business, explicitly."""
        co, cust = _world(db, "m3")
        try:
            inv = _posted_invoice(db, co, cust)
            ss.create_credit_memo(db, co.id, U1, inv.id,
                                  Decimal("300.00"), "partial credit")
            with pytest.raises(HTTPException) as e:
                ss.create_credit_memo(db, co.id, U1, inv.id,
                                      Decimal("800.00"), "too much")
            assert "pocket" in e.value.detail
            # nothing moved on the refusal
            assert _fresh(db, inv).balance_remaining == Decimal("700.00")
            assert _fresh(db, cust).current_balance == Decimal("700.00")
        finally:
            _cleanup(db, [co.id])

    def test_full_memo_settles(self, db):
        """Settlement by memo counts as settlement — balance zero,
        status paid, the memo as the settling document."""
        co, cust = _world(db, "m4")
        try:
            inv = _posted_invoice(db, co, cust)
            ss.create_credit_memo(db, co.id, U1, inv.id,
                                  Decimal("1000.00"), "order cancelled after billing")
            inv2 = _fresh(db, inv)
            assert inv2.balance_remaining == Decimal("0.00")
            assert inv2.status == "paid"
            assert inv2.paid_at is not None
            assert _fresh(db, cust).current_balance == Decimal("0.00")
        finally:
            _cleanup(db, [co.id])

    def test_memo_draft_invoice_refuses(self, db):
        co, cust = _world(db, "m5")
        try:
            inv = Invoice(
                company_id=co.id, customer_id=cust.id,
                number=f"INV-X-{uuid.uuid4().hex[:6]}",
                invoice_date=datetime.now(timezone.utc),
                due_date=datetime.now(timezone.utc),
                status="draft", total=Decimal("500.00"),
            )
            db.add(inv)
            db.commit()
            with pytest.raises(HTTPException) as e:
                ss.create_credit_memo(db, co.id, U1, inv.id,
                                      Decimal("100.00"), "x")
            assert "draft" in e.value.detail.lower()
        finally:
            _cleanup(db, [co.id])


class TestMemoVoidSymmetry:
    def test_void_reverses_whole(self, db):
        """S2's void honesty on the negative: the memo always posted, so
        voiding always reverses — balance and AR walk back exactly."""
        co, cust = _world(db, "v1")
        try:
            inv = _posted_invoice(db, co, cust)
            memo = ss.create_credit_memo(db, co.id, U1, inv.id,
                                         Decimal("300.00"), "mistake")
            memo = ss.void_credit_memo(db, co.id, U1, memo.id, "wrong invoice")
            assert memo.status == "void"
            assert memo.void_reason == "wrong invoice"
            inv2 = _fresh(db, inv)
            assert inv2.balance_remaining == Decimal("1000.00")
            assert inv2.amount_credited == Decimal("0.00")
            assert inv2.status == "sent"  # nothing settled anymore
            assert _fresh(db, cust).current_balance == Decimal("1000.00")
            with pytest.raises(HTTPException):
                ss.void_credit_memo(db, co.id, U1, memo.id)  # already void
        finally:
            _cleanup(db, [co.id])

    def test_void_walks_back_settlement(self, db):
        co, cust = _world(db, "v2")
        try:
            inv = _posted_invoice(db, co, cust)
            memo = ss.create_credit_memo(db, co.id, U1, inv.id,
                                         Decimal("1000.00"), "full credit")
            assert _fresh(db, inv).status == "paid"
            ss.void_credit_memo(db, co.id, U1, memo.id)
            inv2 = _fresh(db, inv)
            assert inv2.status == "sent"
            assert inv2.paid_at is None
        finally:
            _cleanup(db, [co.id])

    def test_void_refused_behind_a_write_off(self, db):
        co, cust = _world(db, "v3")
        try:
            inv = _posted_invoice(db, co, cust)
            memo = ss.create_credit_memo(db, co.id, U1, inv.id,
                                         Decimal("300.00"), "credit")
            ss.write_off_invoice(db, co.id, U1, inv.id, "uncollectable")
            with pytest.raises(HTTPException) as e:
                ss.void_credit_memo(db, co.id, U1, memo.id)
            assert "reinstate" in e.value.detail.lower()
        finally:
            _cleanup(db, [co.id])


class TestWriteOffVerb:
    def test_partial_paid_writes_off_the_remainder(self, db):
        """$1,000 invoice, $400 paid → write-off moves the $600
        REMAINDER off AR; the paid part stays paid."""
        co, cust = _world(db, "w1")
        try:
            inv = _posted_invoice(db, co, cust)
            inv.amount_paid = Decimal("400.00")
            inv.status = "partial"
            cust.current_balance = Decimal("600.00")  # after the payment
            db.commit()
            inv = ss.write_off_invoice(db, co.id, U1, inv.id,
                                       "customer closed — uncollectable")
            assert inv.status == "write_off"
            assert inv.written_off_amount == Decimal("600.00")
            assert inv.write_off_reason == "customer closed — uncollectable"
            assert inv.balance_remaining == Decimal("0.00")
            assert inv.amount_paid == Decimal("400.00")  # stays received
            assert _fresh(db, cust).current_balance == Decimal("0.00")
        finally:
            _cleanup(db, [co.id])

    def test_guards(self, db):
        co, cust = _world(db, "w2")
        try:
            inv = _posted_invoice(db, co, cust)
            with pytest.raises(HTTPException):  # reason required
                ss.write_off_invoice(db, co.id, U1, inv.id, "")
            draft = Invoice(
                company_id=co.id, customer_id=cust.id,
                number=f"INV-X-{uuid.uuid4().hex[:6]}",
                invoice_date=datetime.now(timezone.utc),
                due_date=datetime.now(timezone.utc),
                status="draft", total=Decimal("100.00"),
            )
            db.add(draft)
            db.commit()
            with pytest.raises(HTTPException) as e:
                ss.write_off_invoice(db, co.id, U1, draft.id, "x")
            assert "draft" in e.value.detail.lower()
            paid = _posted_invoice(db, co, cust, total="50.00")
            paid.amount_paid = Decimal("50.00")
            paid.status = "paid"
            db.commit()
            with pytest.raises(HTTPException):
                ss.write_off_invoice(db, co.id, U1, paid.id, "x")
        finally:
            _cleanup(db, [co.id])

    def test_reinstate_is_deliberate_with_reason(self, db):
        co, cust = _world(db, "w3")
        try:
            inv = _posted_invoice(db, co, cust)
            inv.amount_paid = Decimal("400.00")
            inv.status = "partial"
            cust.current_balance = Decimal("600.00")
            db.commit()
            ss.write_off_invoice(db, co.id, U1, inv.id, "presumed gone")
            with pytest.raises(HTTPException):  # reason required
                ss.reinstate_invoice(db, co.id, U1, inv.id, " ")
            inv = ss.reinstate_invoice(db, co.id, U1, inv.id,
                                       "customer resurfaced and will pay")
            assert inv.status == "partial"
            assert inv.written_off_amount == Decimal("0.00")
            assert inv.write_off_reason is None
            assert inv.balance_remaining == Decimal("600.00")
            assert _fresh(db, cust).current_balance == Decimal("600.00")
            with pytest.raises(HTTPException):  # only write_off reinstates
                ss.reinstate_invoice(db, co.id, U1, inv.id, "again")
        finally:
            _cleanup(db, [co.id])

    def test_no_silent_patch_resurrection(self, db):
        """The generic status PATCH refuses write_off in BOTH directions —
        the verb is the door."""
        co, cust = _world(db, "w4")
        try:
            inv = _posted_invoice(db, co, cust)

            class _D:
                status = "write_off"
                notes = None
            with pytest.raises(HTTPException) as e:
                ss.update_invoice(db, co.id, U1, inv.id, _D())
            assert "money move" in e.value.detail
            ss.write_off_invoice(db, co.id, U1, inv.id, "gone")

            class _D2:
                status = "sent"
                notes = None
            with pytest.raises(HTTPException):
                ss.update_invoice(db, co.id, U1, inv.id, _D2())
        finally:
            _cleanup(db, [co.id])


class TestTheCreditPocket:
    def _pay(self, db, co, cust, inv, total, applied):
        from app.schemas.sales import CustomerPaymentCreate, PaymentApplicationCreate
        data = CustomerPaymentCreate(
            customer_id=cust.id,
            payment_date=datetime.now(timezone.utc),
            total_amount=Decimal(total),
            payment_method="check",
            applications=(
                [PaymentApplicationCreate(invoice_id=inv.id,
                                          amount_applied=Decimal(applied))]
                if applied else []
            ),
        )
        return ss.create_customer_payment(db, co.id, U1, data)

    def test_overpay_apply_disburse_hand_proven(self, db):
        """Overpay $200 → pocket $200 → apply $150 → pocket $50 →
        disburse $50 → pocket $0; invoice and AR honest at every step."""
        co, cust = _world(db, "p1")
        try:
            inv1 = _posted_invoice(db, co, cust)  # $1,000
            self._pay(db, co, cust, inv1, "1200.00", "1000.00")
            cust2 = _fresh(db, cust)
            assert cust2.credit_balance == Decimal("200.00")
            # balance law: only the APPLIED $1,000 left AR
            assert cust2.current_balance == Decimal("0.00")
            assert _fresh(db, inv1).status == "paid"

            inv2 = _posted_invoice(db, co, cust, total="500.00")
            out = ss.apply_customer_credit(
                db, co.id, U1, cust.id, inv2.id, Decimal("150.00"))
            assert out["credit_balance"] == 50.0
            assert out["invoice_balance_remaining"] == 350.0
            cust3 = _fresh(db, cust)
            assert cust3.credit_balance == Decimal("50.00")
            assert cust3.current_balance == Decimal("350.00")
            assert _fresh(db, inv2).status == "partial"

            with pytest.raises(HTTPException):  # note required
                ss.disburse_customer_credit(db, co.id, U1, cust.id,
                                            Decimal("50.00"), "")
            ss.disburse_customer_credit(
                db, co.id, U1, cust.id, Decimal("50.00"),
                "check #1042, mailed 7/21")
            cust4 = _fresh(db, cust)
            assert cust4.credit_balance == Decimal("0.00")
            assert cust4.current_balance == Decimal("350.00")  # unmoved

            entries = (
                db.query(CustomerCreditEntry)
                .filter(CustomerCreditEntry.customer_id == cust.id)
                .all()
            )
            assert {e.kind for e in entries} == {"apply", "disburse"}
        finally:
            _cleanup(db, [co.id])

    def test_over_apply_refuses(self, db):
        co, cust = _world(db, "p2")
        try:
            cust.credit_balance = Decimal("500.00")
            db.commit()
            inv = _posted_invoice(db, co, cust, total="100.00")
            with pytest.raises(HTTPException) as e:
                ss.apply_customer_credit(db, co.id, U1, cust.id,
                                         inv.id, Decimal("300.00"))
            assert "pocket" in e.value.detail
            with pytest.raises(HTTPException):
                ss.apply_customer_credit(db, co.id, U1, cust.id,
                                         inv.id, Decimal("600.00"))
        finally:
            _cleanup(db, [co.id])

    def test_void_payment_guards_spent_credit(self, db):
        """Voiding a payment whose overpay credit was already spent
        refuses loudly — no falsified balances."""
        co, cust = _world(db, "p3")
        try:
            inv1 = _posted_invoice(db, co, cust)
            payment = self._pay(db, co, cust, inv1, "1200.00", "1000.00")
            inv2 = _posted_invoice(db, co, cust, total="500.00")
            ss.apply_customer_credit(db, co.id, U1, cust.id,
                                     inv2.id, Decimal("200.00"))
            with pytest.raises(HTTPException) as e:
                ss.void_payment(db, payment.id, co.id, U1)
            assert "spent" in e.value.detail
        finally:
            _cleanup(db, [co.id])

    def test_void_payment_full_inverse(self, db):
        co, cust = _world(db, "p4")
        try:
            inv1 = _posted_invoice(db, co, cust)
            payment = self._pay(db, co, cust, inv1, "1200.00", "1000.00")
            ss.void_payment(db, payment.id, co.id, U1)
            cust2 = _fresh(db, cust)
            assert cust2.credit_balance == Decimal("0.00")
            assert cust2.current_balance == Decimal("1000.00")
            assert _fresh(db, inv1).status == "sent"
        finally:
            _cleanup(db, [co.id])


class TestARParityTheSweeperStaysZero:
    def test_full_exceptions_exercise_zero_drift(self, db):
        """THE AR PARITY PIN: after memos, a void, an overpay, an apply,
        a disburse, a write-off, and a reinstate, the nightly
        reconciliation corrects NOTHING — every verb obeyed the law."""
        from app.services.proactive_agents import run_ar_balance_reconciliation
        co, cust = _world(db, "z1")
        try:
            inv1 = _posted_invoice(db, co, cust)                       # +1000
            memo = ss.create_credit_memo(db, co.id, U1, inv1.id,
                                         Decimal("300.00"), "credit")  # -300
            ss.void_credit_memo(db, co.id, U1, memo.id)              # +300
            ss.create_credit_memo(db, co.id, U1, inv1.id,
                                  Decimal("100.00"), "adjust")         # -100
            TestTheCreditPocket._pay(TestTheCreditPocket(), db, co, cust,
                                     inv1, "1100.00", "900.00")        # -900, pocket 200
            inv2 = _posted_invoice(db, co, cust, total="500.00")       # +500
            ss.apply_customer_credit(db, co.id, U1, cust.id,
                                     inv2.id, Decimal("150.00"))       # -150
            ss.disburse_customer_credit(db, co.id, U1, cust.id,
                                        Decimal("50.00"), "check #9")  # AR unmoved
            inv3 = _posted_invoice(db, co, cust, total="250.00")       # +250
            ss.write_off_invoice(db, co.id, U1, inv3.id, "gone")     # -250
            ss.reinstate_invoice(db, co.id, U1, inv3.id, "back")     # +250
            ss.write_off_invoice(db, co.id, U1, inv3.id, "gone again")  # -250

            # hand math: 1000-100-900 = 0 (inv1 paid) · 500-150 = 350 · inv3 written off
            assert _fresh(db, cust).current_balance == Decimal("350.00")

            out = run_ar_balance_reconciliation(db, co.id)
            assert out["balances_corrected"] == 0
        finally:
            _cleanup(db, [co.id])


class TestIsolation:
    def test_every_new_path_is_tenant_scoped(self, db):
        co_a, cust_a = _world(db, "ia")
        co_b, cust_b = _world(db, "ib")
        try:
            inv = _posted_invoice(db, co_a, cust_a)
            memo = ss.create_credit_memo(db, co_a.id, U1, inv.id,
                                         Decimal("100.00"), "r")
            with pytest.raises(HTTPException) as e1:
                ss.create_credit_memo(db, co_b.id, U1, inv.id,
                                      Decimal("50.00"), "r")
            assert e1.value.status_code == 404
            with pytest.raises(HTTPException) as e2:
                ss.void_credit_memo(db, co_b.id, U1, memo.id)
            assert e2.value.status_code == 404
            with pytest.raises(HTTPException) as e3:
                ss.write_off_invoice(db, co_b.id, U1, inv.id, "r")
            assert e3.value.status_code == 404
            cust_a.credit_balance = Decimal("100.00")
            db.commit()
            with pytest.raises(HTTPException) as e4:
                ss.apply_customer_credit(db, co_b.id, U1, cust_a.id,
                                         inv.id, Decimal("50.00"))
            assert e4.value.status_code == 404
            with pytest.raises(HTTPException) as e5:
                ss.disburse_customer_credit(db, co_b.id, U1, cust_a.id,
                                            Decimal("50.00"), "check")
            assert e5.value.status_code == 404
        finally:
            _cleanup(db, [co_a.id, co_b.id])


class TestNumbering:
    def test_memo_numbers_allocate(self, db):
        co, cust = _world(db, "n1")
        try:
            inv = _posted_invoice(db, co, cust)
            m1 = ss.create_credit_memo(db, co.id, U1, inv.id,
                                       Decimal("10.00"), "a")
            m2 = ss.create_credit_memo(db, co.id, U1, inv.id,
                                       Decimal("10.00"), "b")
            year = datetime.now(timezone.utc).year
            assert m1.number == f"CM-{year}-0001"
            assert m2.number == f"CM-{year}-0002"
        finally:
            _cleanup(db, [co.id])
