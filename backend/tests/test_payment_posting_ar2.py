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


# ── the invariant the SCOPE note was blocking ───────────────────────────────


class TestTheInvariantAfterAR2:
    """What the L-2 SCOPE note existed to defer, now assertable.

    The note said the cash-leg equality was not a platform invariant because an
    `auto_cleared` payment match cleared against nothing. It does not any more.
    The invariant it becomes is:

        cash movement equals what the reconciliation cleared, OR a reported
        unposted-payment anomaly explains the difference.

    The second clause is what makes it survive misconfiguration. A bare equality
    would fail on a fail-open tenant and report a broken invariant when what
    exists is a known, enumerated gap that says so itself.
    """

    def test_a_posted_payment_puts_real_cash_movement_in_the_ledger(self, env):
        """THE CLAIM THE SCOPE NOTE DEFERRED. Before AR-2 the left side of this
        comparison was 0.00 for any payment — nothing was ever written.

        HAND MATH: two receipts, 400.00 and 250.00.
             cash debits  650.00
             cash credits   0.00
             net movement = 650.00 - 0.00 = +650.00   (money IN)
        """
        _ar, cash, _bank = _configured(env)
        env.pay(total="400.00")
        env.pay(total="250.00")
        env.s.commit()

        lines = (
            env.s.query(JournalEntryLine)
            .filter(
                JournalEntryLine.tenant_id == env.co,
                JournalEntryLine.gl_account_id == cash.id,
            ).all()
        )
        debits = sum((ln.debit_amount for ln in lines), Decimal("0.00"))
        credits = sum((ln.credit_amount for ln in lines), Decimal("0.00"))
        assert debits == Decimal("650.00")
        assert credits == Decimal("0.00")
        assert debits - credits == Decimal("650.00")

    def test_the_ar_leg_mirrors_it_exactly(self, env):
        """Every receipt is two legs and they are the same magnitude, so the AR
        credits must equal the cash debits. If they ever diverge, one side is
        posting and the other is not."""
        ar, cash, _bank = _configured(env)
        env.pay(total="400.00")
        env.pay(total="250.00")
        env.s.commit()

        def _net(gl_id):
            rows = (
                env.s.query(JournalEntryLine)
                .filter(
                    JournalEntryLine.tenant_id == env.co,
                    JournalEntryLine.gl_account_id == gl_id,
                ).all()
            )
            return (sum((r.debit_amount for r in rows), Decimal("0.00")),
                    sum((r.credit_amount for r in rows), Decimal("0.00")))

        cash_d, cash_c = _net(cash.id)
        ar_d, ar_c = _net(ar.id)
        assert cash_d == ar_c == Decimal("650.00")
        assert cash_c == ar_d == Decimal("0.00")

    def test_an_UNPOSTED_payment_is_the_difference_AND_declares_itself(self, env):
        """THE SECOND CLAUSE, which is the whole reason the invariant is not a
        bare equality.

        HAND MATH: three receipts of 100.00, one of them on a tenant that cannot
        post... except a tenant is configured or not, so this uses the honest
        version: configure, post two, then break the config and take a third.

             posted to the ledger   200.00
             received in reality    300.00
             difference             100.00  ← explained by exactly one anomaly
        """
        from app.models.agent import AgentJob
        from app.models.agent_anomaly import AgentAnomaly
        from app.services.early_payment_discount_service import (
            ACCOUNTING_GL_SETTINGS_KEY,
        )

        _ar, cash, _bank = _configured(env)
        env.pay(total="100.00")
        env.pay(total="100.00")
        env.s.commit()

        # The AR account is unmapped after the fact — a real state, since the
        # panel permits deliberately-unmapped and an account can be deactivated.
        env.company.set_setting(ACCOUNTING_GL_SETTINGS_KEY, {"ar": None})
        env.s.commit()
        env.pay(total="100.00")
        env.s.commit()

        lines = (
            env.s.query(JournalEntryLine)
            .filter(
                JournalEntryLine.tenant_id == env.co,
                JournalEntryLine.gl_account_id == cash.id,
            ).all()
        )
        posted = sum((ln.debit_amount for ln in lines), Decimal("0.00"))
        received = sum(
            (p.total_amount for p in
             env.s.query(CustomerPayment).filter(
                 CustomerPayment.company_id == env.co).all()),
            Decimal("0.00"),
        )
        assert posted == Decimal("200.00")
        assert received == Decimal("300.00")

        # ...and the difference is not a mystery. It is enumerated, with its
        # amount, by the anomalies the unposted payments raised.
        unexplained = received - posted
        reported = sum(
            (a.amount for a in
             env.s.query(AgentAnomaly)
             .join(AgentJob, AgentAnomaly.agent_job_id == AgentJob.id)
             .filter(AgentJob.tenant_id == env.co).all()),
            Decimal("0.00"),
        )
        assert reported == unexplained == Decimal("100.00")

    def test_every_posted_payment_points_at_its_entry(self, env):
        """The link that makes "which payments are unposted" answerable — and
        therefore makes the second clause computable rather than rhetorical."""
        _configured(env)
        env.pay(total="100.00")
        env.pay(total="200.00")
        env.s.commit()

        payments = env.s.query(CustomerPayment).filter(
            CustomerPayment.company_id == env.co).all()
        assert len(payments) == 2
        for p in payments:
            assert p.journal_entry_id is not None
            entry = env.s.query(JournalEntry).filter(
                JournalEntry.id == p.journal_entry_id).one()
            assert entry.total_debits == entry.total_credits == p.total_amount


# ── AR-2.1: the default's silent-wrongness is made loud ─────────────────────


class TestBankMismatchDetection:
    """The bank a payment posts to is a TENANT DEFAULT. With one operating
    account it cannot be wrong; with two it can be, and it would be wrong
    SILENTLY — one account overstated, the other understated, by the same
    amount, with nothing to notice it.

    The reconciliation match is the moment the truth arrives: the bank line
    belongs to a known FinancialAccount, so pairing it with a payment says where
    the money REALLY went. The default is not made safe by being a better guess;
    it is made safe by the mismatch being reported.

    REPORTED, NEVER CORRECTED. Amending a posted entry from a background match
    is the behaviour AR-1 spent a phase removing.
    """

    def _second_bank(self, env):
        other_cash = env.mapping(name="CHECKING-FIVE STAR", number="1050")
        return env.bank(gl=other_cash), other_cash

    def _anomalies(self, env, anomaly_type):
        from app.models.agent import AgentJob
        from app.models.agent_anomaly import AgentAnomaly

        return (
            env.s.query(AgentAnomaly)
            .join(AgentJob, AgentAnomaly.agent_job_id == AgentJob.id)
            .filter(
                AgentJob.tenant_id == env.co,
                AgentAnomaly.anomaly_type == anomaly_type,
            ).all()
        )

    def test_a_match_against_a_DIFFERENT_bank_is_reported(self, env):
        """HAND MATH: a 400.00 payment posts to 1030 (the default). Its bank
        line belongs to an account whose GL is 1050. Both accounts are now
        misstated by 400.00 — 1030 over, 1050 under."""
        from app.services import ar_payment_posting

        _ar, _cash, _bank = _configured(env)
        other_bank, _other_gl = self._second_bank(env)
        payment = env.pay(total="400.00")
        env.s.commit()
        assert payment.journal_entry_id is not None

        ok = ar_payment_posting.check_match_bank_consistency(
            env.s, company_id=env.co,
            run_financial_account_id=other_bank.id,     # the OTHER account
            payment_id=payment.id,
        )
        env.s.commit()

        assert ok is False
        found = self._anomalies(env, "ar_payment_bank_mismatch")
        assert len(found) == 1
        assert found[0].entity_id == payment.id
        assert found[0].amount == Decimal("400.00")
        assert "1050" in found[0].description        # where it actually landed

    def test_a_match_against_the_SAME_bank_is_silent(self, env):
        from app.services import ar_payment_posting

        _ar, _cash, bank = _configured(env)
        payment = env.pay(total="400.00")
        env.s.commit()

        ok = ar_payment_posting.check_match_bank_consistency(
            env.s, company_id=env.co,
            run_financial_account_id=bank.id,          # the same account
            payment_id=payment.id,
        )
        env.s.commit()

        assert ok is True
        assert self._anomalies(env, "ar_payment_bank_mismatch") == []

    def test_an_UNPOSTED_payment_is_not_double_reported(self, env):
        """It already has an `ar_payment_unposted` anomaly. Reporting a bank
        mismatch too would count one gap as two, and the second would be
        meaningless — there is no entry to disagree with."""
        from app.services import ar_payment_posting

        bank, _gl = self._second_bank(env)
        env.s.commit()                                  # nothing configured
        payment = env.pay(total="400.00")
        env.s.commit()
        assert payment.journal_entry_id is None

        ok = ar_payment_posting.check_match_bank_consistency(
            env.s, company_id=env.co,
            run_financial_account_id=bank.id, payment_id=payment.id,
        )
        assert ok is True
        assert self._anomalies(env, "ar_payment_bank_mismatch") == []
        assert len(self._anomalies(env, "ar_payment_unposted")) == 1

    def test_it_reports_and_does_NOT_touch_the_entry(self, env):
        """The entry is left exactly as posted. A background match amending a
        journal entry is the AR-1 sweeper's mistake in a new place."""
        from app.services import ar_payment_posting

        _ar, cash, _bank = _configured(env)
        other_bank, _other_gl = self._second_bank(env)
        payment = env.pay(total="400.00")
        env.s.commit()
        before = _lines(env, payment.journal_entry_id)
        before_debit_account = before[0].gl_account_id

        ar_payment_posting.check_match_bank_consistency(
            env.s, company_id=env.co,
            run_financial_account_id=other_bank.id, payment_id=payment.id,
        )
        env.s.commit()

        after = _lines(env, payment.journal_entry_id)
        assert after[0].gl_account_id == before_debit_account == cash.id
        assert after[0].debit_amount == Decimal("400.00")

    def test_a_bank_line_whose_own_account_has_no_gl_is_not_this_checks_problem(self, env):
        """Reconciliation already surfaces `contra_gl_unset` on its own terms.
        Duplicating it here would report one configuration gap twice."""
        from app.services import ar_payment_posting

        _configured(env)
        unmapped_bank = env.bank(gl=None)
        payment = env.pay(total="400.00")
        env.s.commit()

        ok = ar_payment_posting.check_match_bank_consistency(
            env.s, company_id=env.co,
            run_financial_account_id=unmapped_bank.id, payment_id=payment.id,
        )
        assert ok is True
        assert self._anomalies(env, "ar_payment_bank_mismatch") == []
