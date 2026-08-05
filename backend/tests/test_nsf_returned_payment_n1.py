"""N-1+2 — a returned cheque stops leaving the customer looking paid.

THE CORRECTNESS HALF, AND IT PREDATES THE LEDGER ENTIRELY. Before this, a
returned payment left the record fully intact: `amount_paid` overstated on every
invoice it touched, `current_balance` understated on the customer, and NOTHING
watching. The customer reads as paid when the money came back, so collections
does not chase them — a wrong number with no error signal. True with or without
a GL; this is not a posting bug.

WHY IT IS NOT `void_payment`. A void says the payment should never have been
recorded and soft-deletes the row. A return says it HAPPENED and the bank took
it back. The attempt is exactly what an operator needs when the same customer's
cheque bounces a second time, so the row survives carrying `returned_at` +
`returned_reason` (r156). Everything else unwinds identically, through the one
shared `_unwind_payment` core, so the two cannot drift.

THERE WAS NO DETECTION TO BUILD. Two mechanisms already existed and neither was
actionable: the keyword ladder classifies the line `nsf` and deliberately fails
closed (L-2 ruled `nsf` unmapped ON PURPOSE — "a bounced cheque reverses against
AR, not an expense"), and the matcher's `DIRECTION_MISMATCH` candidate ALREADY
links the exact-amount opposite-pool hit. The system knew which payment the
return reversed; it filed the link where nobody acted on it. This phase makes
that link actionable, which is why the action is small.

Cleans up its own `nsf1-` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.database import SessionLocal
from app.models.accounting_analysis import TenantGLMapping
from app.models.company import Company
from app.models.customer import Customer
from app.models.customer_payment import CustomerPayment
from app.models.financial_account import (
    FinancialAccount,
    ReconciliationMatchCandidate,
    ReconciliationRun,
    ReconciliationTransaction,
)
from app.models.invoice import Invoice
from app.models.journal_entry import JournalEntry, JournalEntryLine
from app.models.role import Role
from app.models.user import User
from app.services import sales_service
from tests._cleanup import purge_companies_by_slug

_SLUG = "nsf1-"


@pytest.fixture(autouse=True)
def _purge():
    yield
    s = SessionLocal()
    try:
        purge_companies_by_slug(s, f"{_SLUG}%")
    finally:
        s.close()


@pytest.fixture
def env():
    s = SessionLocal()
    yield _Env(s)
    s.rollback()
    s.close()


class _PaymentData:
    def __init__(self, *, customer_id, total_amount, applications):
        self.customer_id = customer_id
        self.total_amount = Decimal(total_amount)
        self.applications = applications
        self.payment_date = datetime(2026, 7, 10, 12, tzinfo=timezone.utc)
        self.payment_method = "check"
        self.reference_number = "4471"
        self.notes = None


class _App:
    def __init__(self, invoice_id, amount):
        self.invoice_id = invoice_id
        self.amount_applied = Decimal(amount)


class _Env:
    def __init__(self, s):
        self.s = s
        sfx = uuid.uuid4().hex[:8]
        self.company = Company(
            id=str(uuid.uuid4()), name=f"NSF1 {sfx}", slug=f"{_SLUG}{sfx}",
            is_active=True, vertical="manufacturing",
        )
        s.add(self.company); s.flush()
        self.co = self.company.id
        role = Role(id=str(uuid.uuid4()), company_id=self.co, name="Admin", slug="admin")
        s.add(role); s.flush()
        self.user = User(
            id=str(uuid.uuid4()), company_id=self.co, role_id=role.id,
            email=f"{_SLUG}{sfx}@test.local", hashed_password="x",
            first_name="N", last_name="S", is_active=True,
        )
        s.add(self.user); s.flush()
        self.cust = Customer(
            id=str(uuid.uuid4()), company_id=self.co, name="Hopkins FH",
            is_active=True, current_balance=Decimal("0.00"),
        )
        s.add(self.cust); s.flush()

        self.ar = self._mapping(name="ACCOUNTS RECEIVABLE-TRADE", number="1200")
        self.cash = self._mapping(name="CASH CHECKING", number="1030")
        self.bank = FinancialAccount(
            id=str(uuid.uuid4()), tenant_id=self.co, account_type="checking",
            account_name="Operating", gl_account_id=self.cash.id,
        )
        s.add(self.bank); s.flush()

        from app.services.ar_payment_posting import PAYMENT_BANK_SETTINGS_KEY
        from app.services.early_payment_discount_service import (
            ACCOUNTING_GL_SETTINGS_KEY,
        )
        self.company.set_setting(ACCOUNTING_GL_SETTINGS_KEY, {"ar": self.ar.id})
        self.company.set_setting(PAYMENT_BANK_SETTINGS_KEY, self.bank.id)
        s.commit()

    def _mapping(self, *, name, number) -> TenantGLMapping:
        m = TenantGLMapping(
            id=str(uuid.uuid4()), tenant_id=self.co, platform_category="current_asset",
            account_number=number, account_name=name, is_active=True,
        )
        self.s.add(m); self.s.flush()
        return m

    def invoice(self, *, total) -> Invoice:
        inv = Invoice(
            id=str(uuid.uuid4()), company_id=self.co, customer_id=self.cust.id,
            number=f"INV-{uuid.uuid4().hex[:6]}", status="sent",
            invoice_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
            due_date=datetime(2026, 7, 31, tzinfo=timezone.utc),
            subtotal=Decimal(total), tax_rate=Decimal("0"), tax_amount=Decimal("0"),
            total=Decimal(total), amount_paid=Decimal("0"),
        )
        self.s.add(inv); self.s.flush()
        return inv

    def pay(self, *, total, applications=()) -> CustomerPayment:
        p = sales_service.create_customer_payment(
            self.s, self.co, self.user.id,
            _PaymentData(customer_id=self.cust.id, total_amount=total,
                         applications=list(applications)),
        )
        self.s.commit()
        return p

    def nsf_line(self, *, amount, payment_id=None) -> ReconciliationTransaction:
        """A bank DEBIT the ladder would classify `nsf`, with the
        DIRECTION_MISMATCH candidate the matcher already draws when an
        exact-amount hit sits in the opposite pool."""
        run = ReconciliationRun(
            id=str(uuid.uuid4()), tenant_id=self.co,
            financial_account_id=self.bank.id,
            statement_date=datetime(2026, 7, 31, tzinfo=timezone.utc).date(),
            statement_closing_balance=Decimal("0.00"), status="in_progress",
        )
        self.s.add(run); self.s.flush()
        txn = ReconciliationTransaction(
            id=str(uuid.uuid4()), tenant_id=self.co,
            reconciliation_run_id=run.id,
            transaction_date=datetime(2026, 7, 20, tzinfo=timezone.utc).date(),
            description="RETURNED ITEM - NSF CHECK 4471",
            amount=Decimal(amount) * -1, transaction_type="debit",
            match_status="unmatched",
        )
        self.s.add(txn); self.s.flush()
        if payment_id:
            self.s.add(ReconciliationMatchCandidate(
                id=str(uuid.uuid4()), tenant_id=self.co,
                reconciliation_transaction_id=txn.id,
                candidate_record_type="customer_payment",
                candidate_record_id=payment_id,
                score=Decimal("0.000"), rank=1,
                rejection_reason="DIRECTION_MISMATCH",
            ))
            self.s.flush()
        return txn

    def act(self, txn, **payload) -> dict:
        from app.services.triage.action_handlers import HANDLERS

        return HANDLERS["reconciliation.return_payment"]({
            "db": self.s, "user": self.user, "entity_id": txn.id,
            "queue_id": "reconciliation_review_triage",
            "action_id": "return_payment", "payload": payload,
        })

    def ar_net(self) -> Decimal:
        rows = (
            self.s.query(JournalEntryLine)
            .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
            .filter(
                JournalEntryLine.tenant_id == self.co,
                JournalEntryLine.gl_account_id == self.ar.id,
                JournalEntry.status != "voided",
            ).all()
        )
        return (sum((r.credit_amount for r in rows), Decimal("0.00"))
                - sum((r.debit_amount for r in rows), Decimal("0.00")))


class TestTheCorrectnessHalf:
    """No GL involved in any assertion here. These would all have been true, and
    all have been wrong, before a single journal entry existed."""

    def test_a_returned_payment_stops_the_invoice_reading_as_paid(self, env):
        """THE LIVE BUG. HAND MATH: a 1000.00 invoice, a 400.00 cheque, then the
        cheque comes back.

            invoice.amount_paid  400.00 → 0.00
            still owed           600.00 → 1000.00
        """
        inv = env.invoice(total="1000.00")
        payment = env.pay(total="400.00", applications=[_App(inv.id, "400.00")])
        env.s.refresh(inv)
        assert inv.amount_paid == Decimal("400.00")

        sales_service.return_payment(
            env.s, payment.id, env.co, env.user.id, reason="NSF"
        )
        env.s.refresh(inv)

        assert inv.amount_paid == Decimal("0.00")
        assert inv.total - inv.amount_paid == Decimal("1000.00")

    def test_the_customer_stops_looking_paid(self, env):
        """The half that reaches collections. HAND MATH: applying 400.00 drives
        the balance to -400.00; the return puts it back to 0.00, so the customer
        is owed-from again rather than settled."""
        inv = env.invoice(total="1000.00")
        payment = env.pay(total="400.00", applications=[_App(inv.id, "400.00")])
        env.s.refresh(env.cust)
        assert env.cust.current_balance == Decimal("-400.00")

        sales_service.return_payment(env.s, payment.id, env.co, env.user.id)
        env.s.refresh(env.cust)

        assert env.cust.current_balance == Decimal("0.00")

    def test_a_payment_across_THREE_invoices_unwinds_all_three(self, env):
        """One cheque settling three invoices, returned. HAND MATH:
        500 + 300 + 200 = 1000.00 applied, all of it comes back."""
        a, b, c = (env.invoice(total="500.00"), env.invoice(total="300.00"),
                   env.invoice(total="200.00"))
        payment = env.pay(total="1000.00", applications=[
            _App(a.id, "500.00"), _App(b.id, "300.00"), _App(c.id, "200.00")])
        for inv in (a, b, c):
            env.s.refresh(inv)
        assert [i.amount_paid for i in (a, b, c)] == [
            Decimal("500.00"), Decimal("300.00"), Decimal("200.00")]

        result = sales_service.return_payment(env.s, payment.id, env.co, env.user.id)
        for inv in (a, b, c):
            env.s.refresh(inv)

        assert [i.amount_paid for i in (a, b, c)] == [Decimal("0.00")] * 3
        assert result["applied_reversed"] == "1000.00"


class TestTheRowSurvives:
    """The distinction from a void, which is the whole reason this is not just
    `void_payment` with a different name."""

    def test_the_payment_is_NOT_soft_deleted(self, env):
        """The attempt is what an operator needs when the same customer bounces
        a second time. A void erases it."""
        payment = env.pay(total="400.00")

        sales_service.return_payment(
            env.s, payment.id, env.co, env.user.id, reason="NSF — insufficient funds"
        )
        env.s.refresh(payment)

        assert payment.deleted_at is None
        assert payment.returned_at is not None
        assert payment.returned_reason == "NSF — insufficient funds"

    def test_a_second_return_is_REFUSED(self, env):
        """The unwind does not delete the application rows — it decrements the
        invoices they point at — so running it twice decrements twice and
        silently understates what those invoices have been paid. The guard lives
        in the shared core, so it protects the void path too."""
        inv = env.invoice(total="1000.00")
        payment = env.pay(total="400.00", applications=[_App(inv.id, "400.00")])
        sales_service.return_payment(env.s, payment.id, env.co, env.user.id)
        env.s.refresh(inv)
        assert inv.amount_paid == Decimal("0.00")

        with pytest.raises(HTTPException) as exc:
            sales_service.return_payment(env.s, payment.id, env.co, env.user.id)
        assert exc.value.status_code == 409
        env.s.rollback()
        env.s.refresh(inv)
        assert inv.amount_paid == Decimal("0.00")     # NOT -400.00

    def test_VOIDING_an_already_returned_payment_is_refused_too(self, env):
        """Same guard, the other caller. This is why it lives in the core."""
        inv = env.invoice(total="1000.00")
        payment = env.pay(total="400.00", applications=[_App(inv.id, "400.00")])
        sales_service.return_payment(env.s, payment.id, env.co, env.user.id)

        with pytest.raises(HTTPException) as exc:
            sales_service.void_payment(env.s, payment.id, env.co, env.user.id)
        assert exc.value.status_code == 409


class TestTheLedgerFollows:
    """AR-2 posted the payment, so the return has to undo that too — but it is
    the SAME undo the void does, through the same core."""

    def test_the_payment_entry_is_undone_and_AR_nets_to_zero(self, env):
        """HAND MATH: a 400.00 payment credits AR 400.00; the return undoes it,
        so AR nets to 0.00."""
        payment = env.pay(total="400.00")
        assert env.ar_net() == Decimal("400.00")

        sales_service.return_payment(env.s, payment.id, env.co, env.user.id)

        assert env.ar_net() == Decimal("0.00")
        entry = env.s.query(JournalEntry).filter(
            JournalEntry.id == payment.journal_entry_id).one()
        assert entry.status == "voided"      # it was a draft; never hit the books

    def test_an_UNPOSTED_payment_returns_cleanly(self, env):
        """AR-2 is fail-open, so an unconfigured tenant records payments that
        never posted. Returning one must not fail looking for an entry."""
        from app.services.early_payment_discount_service import (
            ACCOUNTING_GL_SETTINGS_KEY,
        )

        env.company.set_setting(ACCOUNTING_GL_SETTINGS_KEY, {"ar": None})
        env.s.commit()
        inv = env.invoice(total="1000.00")
        payment = env.pay(total="400.00", applications=[_App(inv.id, "400.00")])
        assert payment.journal_entry_id is None

        sales_service.return_payment(env.s, payment.id, env.co, env.user.id)
        env.s.refresh(inv); env.s.refresh(payment)

        assert inv.amount_paid == Decimal("0.00")
        assert payment.returned_at is not None


class TestTheActionOnTheExistingLink:
    """No detection was built. The matcher already draws the link; this asserts
    the action reads it and that it refuses to guess when it cannot."""

    def test_the_DIRECTION_MISMATCH_candidate_resolves_the_payment(self, env):
        """The operator clicks one button on the NSF card and the right payment
        is reversed — the id comes from the candidate the matcher already
        recorded, not from anything this phase invented."""
        inv = env.invoice(total="1000.00")
        payment = env.pay(total="400.00", applications=[_App(inv.id, "400.00")])
        txn = env.nsf_line(amount="400.00", payment_id=payment.id)
        env.s.commit()

        result = env.act(txn)

        assert result["status"] == "ok"
        env.s.refresh(payment); env.s.refresh(inv); env.s.refresh(txn)
        assert payment.returned_at is not None
        assert inv.amount_paid == Decimal("0.00")
        assert txn.match_status == "manually_matched"
        assert txn.matched_record_id == payment.id

    def test_with_NO_link_it_refuses_rather_than_guessing(self, env):
        """A bank line the ladder called `nsf` with nothing matching it. There
        is no payment to reverse and inventing one would be worse than asking."""
        txn = env.nsf_line(amount="400.00")
        env.s.commit()

        result = env.act(txn)

        assert result["status"] == "errored"
        assert result["code"] == "ambiguous_payment"

    def test_with_TWO_matching_payments_it_refuses_rather_than_guessing(self, env):
        """Two customers, same amount, one bounced. Picking either would reverse
        the wrong customer's payment — a wrong number with a confident UI."""
        p1 = env.pay(total="400.00")
        p2 = env.pay(total="400.00")
        txn = env.nsf_line(amount="400.00", payment_id=p1.id)
        env.s.add(ReconciliationMatchCandidate(
            id=str(uuid.uuid4()), tenant_id=env.co,
            reconciliation_transaction_id=txn.id,
            candidate_record_type="customer_payment", candidate_record_id=p2.id,
            score=Decimal("0.000"), rank=2, rejection_reason="DIRECTION_MISMATCH",
        ))
        env.s.commit()

        result = env.act(txn)

        assert result["status"] == "errored"
        assert result["code"] == "ambiguous_payment"
        env.s.refresh(p1); env.s.refresh(p2)
        assert p1.returned_at is None and p2.returned_at is None

    def test_an_explicit_payment_id_overrides_the_candidate(self, env):
        """The escape hatch for the ambiguous cases above — the operator names
        the payment and the same reversal runs."""
        p1 = env.pay(total="400.00")
        p2 = env.pay(total="400.00")
        txn = env.nsf_line(amount="400.00", payment_id=p1.id)
        env.s.commit()

        result = env.act(txn, payment_id=p2.id, reason="operator identified")

        assert result["status"] == "ok"
        env.s.refresh(p1); env.s.refresh(p2)
        assert p2.returned_at is not None
        assert p1.returned_at is None

    def test_a_refusal_from_the_service_reaches_the_operator_in_words(self, env):
        """The 409 re-entrancy guard surfaces as copy on the card rather than a
        stack trace — the second click on a card someone already actioned."""
        payment = env.pay(total="400.00")
        txn = env.nsf_line(amount="400.00", payment_id=payment.id)
        env.s.commit()
        assert env.act(txn)["status"] == "ok"

        txn2 = env.nsf_line(amount="400.00", payment_id=payment.id)
        env.s.commit()
        result = env.act(txn2)

        assert result["status"] == "errored"
        assert result["code"] == "cannot_return"
        assert "already recorded as returned" in result["message"]
