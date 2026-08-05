"""AR-2 — customer payments post to the GL. CHARACTERIZATION FIRST.

`create_customer_payment` writes a payment, its applications, and moves
`customer.current_balance` — and posts NO journal entry. AR is subledger-tracked
and the GL has no AR balance, which is why an `auto_cleared` reconciliation row
clears against an entry that does not exist. The L-2 SCOPE note says so.

THE DECIDED SHAPE (operator's call, AR-2 v2):

  * CHECKS POST DIRECT TO BANK. No undeposited-funds account, no chart addition.
    A payment debits the bank when recorded; the reconciliation match CONFIRMS
    it and posts nothing, so cash is debited exactly once and L-3's position
    survives unchanged.
  * The bank is a TENANT DEFAULT naming a `FinancialAccount`, and the cash GL
    leg resolves through that account's existing `gl_account_id` — one fact,
    one home. Storing a separate cash mapping would be a second definition of
    "which GL account is this bank", which is the drift that produced four AR
    formulas.
  * FAIL-OPEN ON THE RECORD, FAIL-CLOSED ON THE LEDGER. A payment is an event
    that already happened; refusing to record it means the books stop describing
    reality and a collections notice goes to someone who paid. So the payment
    records, the posting is refused, and the gap is REPORTED.

Cleans up its own `ar2-` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
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

_SLUG = "ar2-"


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
    """The shape `create_customer_payment` reads off its `data` argument."""

    def __init__(self, *, customer_id, total_amount, applications, payment_date=None):
        self.customer_id = customer_id
        self.total_amount = Decimal(total_amount)
        self.applications = applications
        self.payment_date = payment_date or datetime(2026, 7, 10, 12, tzinfo=timezone.utc)
        self.payment_method = "check"
        self.reference_number = "1234"
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
            id=str(uuid.uuid4()), name=f"AR2 {sfx}", slug=f"{_SLUG}{sfx}",
            is_active=True, vertical="manufacturing",
        )
        s.add(self.company); s.flush()
        self.co = self.company.id
        role = Role(id=str(uuid.uuid4()), company_id=self.co, name="Admin", slug="admin")
        s.add(role); s.flush()
        self.user = User(
            id=str(uuid.uuid4()), company_id=self.co, role_id=role.id,
            email=f"{_SLUG}{sfx}@test.local", hashed_password="x",
            first_name="A", last_name="R", is_active=True,
        )
        s.add(self.user); s.flush()
        self.cust = Customer(
            id=str(uuid.uuid4()), company_id=self.co, name="Hopkins FH",
            is_active=True, current_balance=Decimal("0.00"),
        )
        s.add(self.cust); s.flush()

    def mapping(self, *, name, number, active=True) -> TenantGLMapping:
        m = TenantGLMapping(
            id=str(uuid.uuid4()), tenant_id=self.co, platform_category="current_asset",
            account_number=number, account_name=name, is_active=active,
        )
        self.s.add(m); self.s.flush()
        return m

    def bank(self, *, gl: TenantGLMapping | None) -> FinancialAccount:
        a = FinancialAccount(
            id=str(uuid.uuid4()), tenant_id=self.co, account_type="checking",
            account_name="Operating",
            gl_account_id=gl.id if gl is not None else None,
        )
        self.s.add(a); self.s.flush()
        return a

    def invoice(self, *, total, status="sent") -> Invoice:
        inv = Invoice(
            id=str(uuid.uuid4()), company_id=self.co, customer_id=self.cust.id,
            number=f"INV-{uuid.uuid4().hex[:6]}", status=status,
            invoice_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
            due_date=datetime(2026, 7, 31, tzinfo=timezone.utc),
            subtotal=Decimal(total), tax_rate=Decimal("0"), tax_amount=Decimal("0"),
            total=Decimal(total), amount_paid=Decimal("0"),
        )
        self.s.add(inv); self.s.flush()
        return inv

    def configure(self, *, ar: TenantGLMapping, bank: FinancialAccount):
        """Both legs, in the two places they live — `accounting_gl.ar` on the
        tenant (E-2's panel) and `gl_account_id` on the bank account (L-2.1e's
        per-account form). AR-2 needs BOTH, and they are configured separately."""
        from app.services.early_payment_discount_service import (
            ACCOUNTING_GL_SETTINGS_KEY,
        )
        from app.services.ar_payment_posting import PAYMENT_BANK_SETTINGS_KEY

        self.company.set_setting(ACCOUNTING_GL_SETTINGS_KEY, {"ar": ar.id})
        self.company.set_setting(PAYMENT_BANK_SETTINGS_KEY, bank.id)
        self.s.flush()

    def pay(self, *, total, applications=()) -> CustomerPayment:
        return sales_service.create_customer_payment(
            self.s, self.co, self.user.id,
            _PaymentData(customer_id=self.cust.id, total_amount=total,
                         applications=list(applications)),
        )

    def je_count(self) -> int:
        return self.s.query(JournalEntry).count()


def _lines(env, entry_id) -> tuple[JournalEntryLine, JournalEntryLine]:
    rows = (
        env.s.query(JournalEntryLine)
        .filter(JournalEntryLine.journal_entry_id == entry_id).all()
    )
    assert len(rows) == 2, f"expected two legs, got {len(rows)}"
    debit = next(r for r in rows if r.debit_amount and r.debit_amount > 0)
    credit = next(r for r in rows if r.credit_amount and r.credit_amount > 0)
    return debit, credit


def _configured(env):
    ar = env.mapping(name="ACCOUNTS RECEIVABLE-TRADE", number="1200")
    cash = env.mapping(name="JANDHA LLC - CASH CHECKING", number="1030")
    bank = env.bank(gl=cash)
    env.configure(ar=ar, bank=bank)
    env.s.commit()
    return ar, cash, bank


# ── the arithmetic ──────────────────────────────────────────────────────────


class TestAPaymentPosts:
    def test_a_payment_against_an_invoice_debits_bank_and_credits_ar(self, env):
        """HAND MATH — a 400.00 payment settling a 1000.00 invoice:

             debit  1030 JANDHA LLC - CASH CHECKING  400.00
             credit 1200 ACCOUNTS RECEIVABLE-TRADE   400.00
             debits - credits = 0.00

        The FULL payment posts, not the applied portion: the bank received 400
        and the customer owes 400 less, whether or not it was matched to an
        invoice. Application is a subledger detail; the GL sees cash and AR.
        """
        ar, cash, _bank = _configured(env)
        inv = env.invoice(total="1000.00")
        env.s.commit()

        payment = env.pay(total="400.00", applications=[_App(inv.id, "400.00")])
        env.s.commit()

        entry = env.s.query(JournalEntry).filter(
            JournalEntry.id == payment.journal_entry_id).one()
        assert entry.total_debits == entry.total_credits == Decimal("400.00")
        debit, credit = _lines(env, entry.id)
        assert debit.gl_account_id == cash.id
        assert debit.debit_amount == Decimal("400.00")
        assert credit.gl_account_id == ar.id
        assert credit.credit_amount == Decimal("400.00")
        assert credit.gl_account_number == "1200"      # denormalized

    def test_an_UNAPPLIED_payment_posts_the_full_amount(self, env):
        """3 of 5 production payments have no application. The entry is the
        same: cash in, AR down — the customer's AR simply goes negative, which
        is the standard representation of money held on account and needs no
        separate liability.

        HAND MATH: 250.00 received, nothing applied.
             debit  1030 cash  250.00
             credit 1200 AR    250.00
        """
        ar, cash, _bank = _configured(env)
        payment = env.pay(total="250.00", applications=[])
        env.s.commit()

        entry = env.s.query(JournalEntry).filter(
            JournalEntry.id == payment.journal_entry_id).one()
        debit, credit = _lines(env, entry.id)
        assert debit.gl_account_id == cash.id and debit.debit_amount == Decimal("250.00")
        assert credit.gl_account_id == ar.id and credit.credit_amount == Decimal("250.00")

    def test_an_overpayment_posts_the_full_amount_not_the_applied_part(self, env):
        """HAND MATH: 600.00 received against a 400.00 invoice.
             applied to the invoice      400.00
             overpayment to the pocket   200.00
             THE ENTRY                   600.00 both sides

        The subledger splits it; the ledger does not. Posting only the applied
        400 would leave 200 of real cash unrecorded.
        """
        ar, cash, _bank = _configured(env)
        inv = env.invoice(total="400.00")
        env.s.commit()

        payment = env.pay(total="600.00", applications=[_App(inv.id, "400.00")])
        env.s.commit()
        env.s.refresh(env.cust)

        assert env.cust.credit_balance == Decimal("200.00")      # the pocket
        entry = env.s.query(JournalEntry).filter(
            JournalEntry.id == payment.journal_entry_id).one()
        assert entry.total_debits == Decimal("600.00")           # the whole receipt
        debit, credit = _lines(env, entry.id)
        assert debit.gl_account_id == cash.id
        assert credit.gl_account_id == ar.id

    def test_the_entry_is_a_draft_and_the_payment_links_to_it(self, env):
        """Draft, following L-2/L-3 rather than EPD's auto-post: a human posts.
        The link is what makes "which payments are unposted" answerable."""
        _configured(env)
        payment = env.pay(total="100.00")
        env.s.commit()

        entry = env.s.query(JournalEntry).filter(
            JournalEntry.id == payment.journal_entry_id).one()
        assert entry.status == "draft"
        assert entry.entry_type == "reconciliation"
        assert entry.entry_number.startswith("RECON-")


# ── fail-open on the record, fail-closed on the ledger ──────────────────────


class TestFailOpenOnTheRecord:
    def test_no_ar_configured_RECORDS_the_payment_and_does_not_post(self, env):
        """THE DECIDED DISCIPLINE. A payment already happened in the world.
        Refusing to record it does not un-receive the money — it means the books
        stop describing reality and a collections notice goes to someone who
        paid."""
        cash = env.mapping(name="JANDHA LLC - CASH CHECKING", number="1030")
        bank = env.bank(gl=cash)
        from app.services.ar_payment_posting import PAYMENT_BANK_SETTINGS_KEY
        env.company.set_setting(PAYMENT_BANK_SETTINGS_KEY, bank.id)
        env.s.commit()                      # NO accounting_gl.ar
        before = env.je_count()

        payment = env.pay(total="500.00")
        env.s.commit()

        assert payment is not None                       # RECORDED
        assert payment.total_amount == Decimal("500.00")
        env.s.refresh(env.cust)
        # THE BALANCE LAW, unchanged by AR-2: only the APPLIED portion reduces
        # current_balance, and nothing was applied here, so the whole receipt
        # lands in the credit pocket. (My first draft of this test asserted
        # -500.00 on current_balance, which contradicts the law quoted in
        # TestTheSubledgerIsUnchanged below — the suite caught it.)
        assert env.cust.current_balance == Decimal("0.00")
        assert env.cust.credit_balance == Decimal("500.00")
        assert payment.journal_entry_id is None          # NOT posted
        assert env.je_count() == before

    def test_no_bank_default_configured_also_records_without_posting(self, env):
        ar = env.mapping(name="ACCOUNTS RECEIVABLE-TRADE", number="1200")
        from app.services.early_payment_discount_service import (
            ACCOUNTING_GL_SETTINGS_KEY,
        )
        env.company.set_setting(ACCOUNTING_GL_SETTINGS_KEY, {"ar": ar.id})
        env.s.commit()                      # NO bank default
        before = env.je_count()

        payment = env.pay(total="500.00")
        env.s.commit()

        assert payment.journal_entry_id is None
        assert env.je_count() == before

    def test_the_bank_accounts_contra_being_unset_also_fails_open(self, env):
        """THE CASE PRODUCTION IS IN TODAY: one FinancialAccount, gl_account_id
        NULL. Two settings in two places, and this is the second one."""
        ar = env.mapping(name="ACCOUNTS RECEIVABLE-TRADE", number="1200")
        bank = env.bank(gl=None)            # contra unset
        env.configure(ar=ar, bank=bank)
        env.s.commit()
        before = env.je_count()

        payment = env.pay(total="500.00")
        env.s.commit()

        assert payment.journal_entry_id is None
        assert env.je_count() == before

    def test_an_unposted_payment_is_reported_not_swallowed(self, env):
        """Fail-open is only safe if the gap is VISIBLE. AR-1's precedent: an
        AgentAnomaly carrying the payment and what could not post."""
        from app.models.agent import AgentJob
        from app.models.agent_anomaly import AgentAnomaly

        env.s.commit()                      # nothing configured at all
        payment = env.pay(total="500.00")
        env.s.commit()

        anomaly = (
            env.s.query(AgentAnomaly)
            .join(AgentJob, AgentAnomaly.agent_job_id == AgentJob.id)
            .filter(AgentJob.tenant_id == env.co).one()
        )
        assert anomaly.entity_type == "customer_payment"
        assert anomaly.entity_id == payment.id
        assert anomaly.amount == Decimal("500.00")
        assert anomaly.resolved is False
        assert "not post" in anomaly.description.lower()

    def test_a_posted_payment_reports_nothing(self, env):
        from app.models.agent import AgentJob

        _configured(env)
        env.pay(total="100.00")
        env.s.commit()

        assert env.s.query(AgentJob).filter(AgentJob.tenant_id == env.co).count() == 0


# ── what does NOT change ────────────────────────────────────────────────────


class TestTheSubledgerIsUnchanged:
    def test_balances_move_exactly_as_before(self, env):
        """Posting is ADDITIVE. The applied portion still reduces
        current_balance, the excess still goes to the pocket, and the invoice
        still settles — none of that is touched.

        HAND MATH: 1000.00 invoice, 600.00 payment fully applied.
             current_balance  0.00 - 600.00 = -600.00
             invoice.amount_paid            =  600.00
             invoice.status                 = "partial"
        """
        _configured(env)
        inv = env.invoice(total="1000.00")
        env.s.commit()

        env.pay(total="600.00", applications=[_App(inv.id, "600.00")])
        env.s.commit()
        env.s.refresh(env.cust); env.s.refresh(inv)

        assert env.cust.current_balance == Decimal("-600.00")
        assert inv.amount_paid == Decimal("600.00")
        assert inv.status == "partial"

    def test_a_locked_period_still_refuses_the_whole_payment(self, env):
        """The period lock predates AR-2 and is NOT fail-open: a payment into a
        closed period was already refused outright, and posting does not soften
        that."""
        from app.services.agents.period_lock import PeriodLockedError, PeriodLockService

        _configured(env)
        PeriodLockService.lock_period(
            env.s, env.co, __import__("datetime").date(2026, 7, 1),
            __import__("datetime").date(2026, 7, 31), reason="closed")
        env.s.commit()
        before = env.je_count()

        with pytest.raises(PeriodLockedError):
            env.pay(total="100.00")
        env.s.rollback()
        assert env.je_count() == before
