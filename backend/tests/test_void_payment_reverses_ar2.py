"""AR-2 REGRESSION — voiding a payment left its journal entry standing.

CHARACTERIZATION FIRST, and the wrongness here is one AR-2 introduced four
commits ago rather than one it inherited.

`void_payment` (`sales_service.py:2505`) was a thorough reversal when a payment
posted nothing: it unwinds each application, restores `invoice.amount_paid`,
re-derives settlement status, restores `current_balance`, refuses loudly if the
credit pocket has since been spent, and soft-deletes the payment.

AR-2 made it incomplete. A payment now books `Dr bank / Cr AR` at receipt, and
`void_payment` does not touch that entry — so the subledger reverses completely,
the ledger does not, and cash stays overstated by the payment amount with no
anomaly, because nothing is watching for it. That is the exact class this arc
has been eliminating: a subledger and a ledger disagreeing, silently, with no
detector.

THE FIX HAS TWO BRANCHES, because the entry's status decides what "undo" means:

  * DRAFT — it never hit the books. There is nothing to reverse; reversing it
    would leave two drafts netting to zero, which is noise. It is VOIDED, which
    preserves the record while `post_entry`'s existing status guard keeps it
    from ever posting.
  * POSTED — a human posted it, so it DID hit the books and the only honest undo
    is a reversing entry in the current period. Deleting or voiding a posted
    entry would be rewriting history.

Cleans up its own `vp2-` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models.accounting_analysis import TenantGLMapping
from app.models.company import Company
from app.models.customer import Customer
from app.models.customer_payment import CustomerPayment
from app.models.financial_account import FinancialAccount
from app.models.invoice import Invoice
from app.models.journal_entry import JournalEntry, JournalEntryLine
from app.models.role import Role
from app.models.user import User
from app.services import sales_service
from tests._cleanup import purge_companies_by_slug

_SLUG = "vp2-"


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
        self.reference_number = "9001"
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
            id=str(uuid.uuid4()), name=f"VP2 {sfx}", slug=f"{_SLUG}{sfx}",
            is_active=True, vertical="manufacturing",
        )
        s.add(self.company); s.flush()
        self.co = self.company.id
        role = Role(id=str(uuid.uuid4()), company_id=self.co, name="Admin", slug="admin")
        s.add(role); s.flush()
        self.user = User(
            id=str(uuid.uuid4()), company_id=self.co, role_id=role.id,
            email=f"{_SLUG}{sfx}@test.local", hashed_password="x",
            first_name="V", last_name="P", is_active=True,
        )
        s.add(self.user); s.flush()
        self.cust = Customer(
            id=str(uuid.uuid4()), company_id=self.co, name="Hopkins FH",
            is_active=True, current_balance=Decimal("0.00"),
        )
        s.add(self.cust); s.flush()

        self.ar = self._mapping(name="ACCOUNTS RECEIVABLE-TRADE", number="1200")
        self.cash = self._mapping(name="JANDHA LLC - CASH CHECKING", number="1030")
        bank = FinancialAccount(
            id=str(uuid.uuid4()), tenant_id=self.co, account_type="checking",
            account_name="Operating", gl_account_id=self.cash.id,
        )
        s.add(bank); s.flush()

        from app.services.ar_payment_posting import PAYMENT_BANK_SETTINGS_KEY
        from app.services.early_payment_discount_service import (
            ACCOUNTING_GL_SETTINGS_KEY,
        )
        self.company.set_setting(ACCOUNTING_GL_SETTINGS_KEY, {"ar": self.ar.id})
        self.company.set_setting(PAYMENT_BANK_SETTINGS_KEY, bank.id)
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

    def void(self, payment_id):
        return sales_service.void_payment(
            self.s, payment_id, self.co, self.user.id
        )

    def cash_net(self) -> Decimal:
        """Debits minus credits on the bank's own GL account — what the LEDGER
        says the bank holds because of this tenant's payments."""
        rows = (
            self.s.query(JournalEntryLine)
            .join(JournalEntry, JournalEntryLine.journal_entry_id == JournalEntry.id)
            .filter(
                JournalEntryLine.tenant_id == self.co,
                JournalEntryLine.gl_account_id == self.cash.id,
                JournalEntry.status != "voided",
            ).all()
        )
        return (sum((r.debit_amount for r in rows), Decimal("0.00"))
                - sum((r.credit_amount for r in rows), Decimal("0.00")))


class TestVoidingADraftBackedPayment:
    def test_the_subledger_reverses_completely(self, env):
        """Unchanged by the fix — this is what void_payment already did well,
        and the regression must not disturb it.

        HAND MATH: a 400.00 payment on a 1000.00 invoice, then voided.
             invoice.amount_paid  400.00 → 0.00
             current_balance     -400.00 → 0.00
        """
        inv = env.invoice(total="1000.00")
        payment = env.pay(total="400.00", applications=[_App(inv.id, "400.00")])
        env.s.refresh(env.cust)
        assert env.cust.current_balance == Decimal("-400.00")

        env.void(payment.id)
        env.s.commit()
        env.s.refresh(env.cust); env.s.refresh(inv); env.s.refresh(payment)

        assert inv.amount_paid == Decimal("0.00")
        assert env.cust.current_balance == Decimal("0.00")
        assert payment.deleted_at is not None

    def test_THE_LEDGER_REVERSES_TOO(self, env):
        """THE REGRESSION. Pre-fix the entry stood after the void and the bank
        was overstated by the payment amount forever.

        HAND MATH: 400.00 in, then voided.
             ledger cash before void  +400.00
             ledger cash after  void     0.00
        """
        inv = env.invoice(total="1000.00")
        payment = env.pay(total="400.00", applications=[_App(inv.id, "400.00")])
        assert env.cash_net() == Decimal("400.00")

        env.void(payment.id)
        env.s.commit()

        assert env.cash_net() == Decimal("0.00")

    def test_a_draft_entry_is_VOIDED_not_reversed(self, env):
        """A draft never hit the books, so there is nothing to reverse — a
        mirror draft would just be two drafts netting to zero. Voiding preserves
        the record, and `post_entry`'s existing status guard (draft /
        pending_review only) keeps a voided entry from ever posting."""
        payment = env.pay(total="400.00")
        entry_id = payment.journal_entry_id
        assert env.s.query(JournalEntry).filter(
            JournalEntry.id == entry_id).one().status == "draft"

        env.void(payment.id)
        env.s.commit()

        entry = env.s.query(JournalEntry).filter(JournalEntry.id == entry_id).one()
        assert entry.status == "voided"
        # NOT reversed — no mirror entry was created.
        assert env.s.query(JournalEntry).filter(
            JournalEntry.tenant_id == env.co).count() == 1

    def test_the_payment_still_points_at_its_entry(self, env):
        """The link is kept so the void is auditable: which entry was voided,
        and by which payment. Nulling it would make that unanswerable."""
        payment = env.pay(total="400.00")
        entry_id = payment.journal_entry_id

        env.void(payment.id)
        env.s.commit()
        env.s.refresh(payment)

        assert payment.journal_entry_id == entry_id


class TestVoidingAPostedBackedPayment:
    def _post(self, env, entry_id):
        """A human posted the draft, the way the arc intends drafts to be
        posted."""
        entry = env.s.query(JournalEntry).filter(JournalEntry.id == entry_id).one()
        entry.status = "posted"
        env.s.commit()

    def test_a_posted_entry_is_REVERSED_not_voided(self, env):
        """It DID hit the books, so the only honest undo is a reversing entry.
        Voiding or deleting a posted entry would be rewriting history."""
        payment = env.pay(total="400.00")
        entry_id = payment.journal_entry_id
        self._post(env, entry_id)

        env.void(payment.id)
        env.s.commit()

        original = env.s.query(JournalEntry).filter(JournalEntry.id == entry_id).one()
        assert original.status == "reversed"        # not "voided"
        reversal = (
            env.s.query(JournalEntry)
            .filter(
                JournalEntry.tenant_id == env.co,
                JournalEntry.reversal_of_entry_id == entry_id,
            ).one()
        )
        assert reversal.is_reversal is True
        assert reversal.status == "posted"

    def test_the_reversal_mirrors_the_legs_and_nets_cash_to_zero(self, env):
        """HAND MATH: original Dr cash 400.00 / Cr AR 400.00; the reversal is
        Dr AR 400.00 / Cr cash 400.00, so the bank nets to 0.00."""
        payment = env.pay(total="400.00")
        self._post(env, payment.journal_entry_id)
        assert env.cash_net() == Decimal("400.00")

        env.void(payment.id)
        env.s.commit()

        assert env.cash_net() == Decimal("0.00")

    def test_the_reversal_posts_in_the_CURRENT_period(self, env):
        """Standard practice, and the same rule reverse_entry already followed:
        you reverse a closed-period entry INTO the open current period, you do
        not reach back. Reaching back would also trip the period-lock guard on
        every reversal of a locked-period entry."""
        payment = env.pay(total="400.00")          # payment_date 2026-07-10
        self._post(env, payment.journal_entry_id)

        env.void(payment.id)
        env.s.commit()

        reversal = (
            env.s.query(JournalEntry)
            .filter(
                JournalEntry.tenant_id == env.co,
                JournalEntry.reversal_of_entry_id == payment.journal_entry_id,
            ).one()
        )
        today = date.today()
        assert reversal.period_month == today.month
        assert reversal.period_year == today.year


class TestAnUnpostedPaymentVoidsCleanly:
    def test_a_payment_that_never_posted_voids_without_a_ledger_step(self, env):
        """Fail-open means a payment can exist with no entry at all. Voiding one
        must not fail looking for an entry that was never written."""
        from app.services.early_payment_discount_service import (
            ACCOUNTING_GL_SETTINGS_KEY,
        )

        env.company.set_setting(ACCOUNTING_GL_SETTINGS_KEY, {"ar": None})
        env.s.commit()
        payment = env.pay(total="400.00")
        assert payment.journal_entry_id is None

        env.void(payment.id)
        env.s.commit()
        env.s.refresh(payment)

        assert payment.deleted_at is not None
        assert env.cash_net() == Decimal("0.00")
