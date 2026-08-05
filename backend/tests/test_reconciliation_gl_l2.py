"""Ledger Posting arc L-2 — keyword rows book, or they do not clear.

L-1 built the config layer and proved it fails closed. L-2 consumes it: the
keyword ladder (`bank_fee` / `payroll` / `nsf`) now produces a balanced
two-legged DRAFT journal entry before a row may clear, and a row that cannot
book stays open as an exception that names the missing CONFIGURATION.

Three things this file pins, in order of how much they matter:

  1. THE cleared_total ARITHMETIC, BOTH WAYS, hand-computed as literals. A row
     that books moves cleared_total; a row that cannot book moves nothing. Both
     directions appear in a single run in `test_partial_config_...` so the rule
     is shown to be per-row, not per-tenant.

  2. THE LEDGER AGREES WITH THE RECONCILIATION. Not asserted by restating the
     same sum, but by reading the OTHER side: the net movement on the bank's own
     cash GL account across the journal lines L-2 wrote, compared to the run's
     platform_cleared_balance. Pre-L-2 that comparison was -5000 vs 0 and there
     was no way to write it down.

  3. THE THIRD CARD FORM. A blocked keyword row reaches Books Review carrying
     its classification AND its reason, with zero candidates — so the display
     can say "Bank fee — no GL account configured for bank fees" instead of
     falling through to the coding card and asking the operator to code, one at
     a time, rows the system has already identified.

The four blocked reasons are pinned distinctly because they call for different
operator actions, which was L-1's stated rationale for logging them separately;
L-2 is where that distinction becomes visible to a human.

Cleans up its own `rgl2-` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.api.routes.reconciliation import trigger_matching
from app.database import SessionLocal
from app.models.accounting_analysis import TenantGLMapping
from app.models.company import Company
from app.models.financial_account import (
    FinancialAccount,
    ReconciliationException,
    ReconciliationRun,
    ReconciliationTransaction,
)
from app.models.journal_entry import JournalEntry, JournalEntryLine
from app.models.role import Role
from app.models.user import User
from app.services import reconciliation_gl
from tests._cleanup import purge_companies_by_slug

_SLUG_PREFIX = "rgl2-"

# The three keyword rows used by every arithmetic test, so the hand math below
# is comparing like with like. Signed amounts are the BANK's point of view:
# negative is money leaving the account.
_PAYROLL_AMT = Decimal("-5000")
_FEE_AMT = Decimal("-15")
_NSF_AMT = Decimal("-100")

_OPENING = Decimal("1000")
_CLOSING = Decimal("2000")


@pytest.fixture(autouse=True)
def _purge():
    yield
    s = SessionLocal()
    try:
        purge_companies_by_slug(s, f"{_SLUG_PREFIX}%")
    finally:
        s.close()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


# ── substrate ───────────────────────────────────────────────────────────────


def _mapping(db, tenant_id, *, name, number, active=True) -> TenantGLMapping:
    m = TenantGLMapping(
        id=str(uuid.uuid4()), tenant_id=tenant_id, platform_category=name.lower(),
        account_number=number, account_name=name, is_active=active,
    )
    db.add(m)
    return m


def _company(db) -> Company:
    sfx = uuid.uuid4().hex[:8]
    co = Company(
        id=str(uuid.uuid4()), name=f"RGL2 {sfx}", slug=f"{_SLUG_PREFIX}{sfx}",
        is_active=True, vertical="manufacturing",
    )
    db.add(co)
    db.flush()
    return co


def _user(db, co) -> User:
    role = Role(id=str(uuid.uuid4()), company_id=co.id, name="Admin", slug="admin")
    db.add(role)
    db.flush()
    u = User(
        id=str(uuid.uuid4()), company_id=co.id, role_id=role.id,
        email=f"{_SLUG_PREFIX}{uuid.uuid4().hex[:8]}@test.local",
        hashed_password="x", first_name="R", last_name="G", is_active=True,
    )
    db.add(u)
    db.flush()
    return u


def _run(db, co, acct, *, opening=_OPENING, closing=_CLOSING) -> ReconciliationRun:
    run = ReconciliationRun(
        id=str(uuid.uuid4()), tenant_id=co.id, financial_account_id=acct.id,
        statement_date=date(2026, 6, 30), statement_closing_balance=closing,
        period_start=date(2026, 6, 1), opening_balance=opening,
    )
    db.add(run)
    db.flush()
    return run


def _txn(db, run, *, day, amount, desc, order) -> ReconciliationTransaction:
    t = ReconciliationTransaction(
        id=str(uuid.uuid4()), tenant_id=run.tenant_id,
        reconciliation_run_id=run.id, transaction_date=date(2026, 6, day),
        description=desc, amount=Decimal(str(amount)),
        transaction_type="debit" if Decimal(str(amount)) < 0 else "credit",
        sort_order=order,
    )
    db.add(t)
    return t


def _substrate(db, *, keyword_map="all", contra=True):
    """A tenant, a bank account, GL mappings, and a run.

    `keyword_map`: "all" | "none" | an iterable of classifications to map.
    `contra`: whether the bank account gets its cash GL account set.

    Returns (co, user, acct, run, gl_ids).
    """
    co = _company(db)
    user = _user(db, co)

    cash = _mapping(db, co.id, name="Operating Cash", number="1010")
    fee = _mapping(db, co.id, name="Bank Charges", number="6010")
    payroll = _mapping(db, co.id, name="Payroll Expense", number="6020")
    nsf = _mapping(db, co.id, name="Returned Items", number="6030")
    db.flush()

    by_class = {"bank_fee": fee.id, "payroll": payroll.id, "nsf": nsf.id}
    if keyword_map == "all":
        chosen = dict(by_class)
    elif keyword_map == "none":
        chosen = {}
    else:
        chosen = {k: by_class[k] for k in keyword_map}
    if chosen:
        co.set_setting(reconciliation_gl.KEYWORD_GL_SETTINGS_KEY, chosen)

    acct = FinancialAccount(
        id=str(uuid.uuid4()), tenant_id=co.id,
        account_type="checking", account_name="Operating",
        gl_account_id=cash.id if contra else None,
    )
    db.add(acct)
    db.flush()

    run = _run(db, co, acct)
    db.commit()
    return co, user, acct, run, {
        "cash": cash.id, "bank_fee": fee.id, "payroll": payroll.id, "nsf": nsf.id,
    }


def _three_keyword_rows(db, run):
    _txn(db, run, day=15, amount=_PAYROLL_AMT, desc="GUSTO PAYROLL", order=0)
    _txn(db, run, day=16, amount=_FEE_AMT, desc="MONTHLY SERVICE CHARGE", order=1)
    _txn(db, run, day=17, amount=_NSF_AMT, desc="NSF RETURNED CHECK", order=2)
    db.commit()


def _lines_for(db, entry_id) -> list[JournalEntryLine]:
    return (
        db.query(JournalEntryLine)
        .filter(JournalEntryLine.journal_entry_id == entry_id)
        .order_by(JournalEntryLine.line_number)
        .all()
    )


# ── 1. the entry itself ─────────────────────────────────────────────────────


class TestTheEntry:
    def test_bank_fee_books_a_balanced_two_legged_draft(self, db):
        """HAND MATH — a -15.00 service charge is money OUT:
             line 1  DEBIT  Bank Charges   15.00
             line 2  CREDIT Operating Cash 15.00
             total_debits == total_credits == 15.00
        The line amounts are the MAGNITUDE; the sign lives in which side each
        leg takes. A journal line never carries a negative number.
        """
        co, user, acct, run, gl = _substrate(db)
        _txn(db, run, day=16, amount=_FEE_AMT, desc="MONTHLY SERVICE CHARGE", order=0)
        db.commit()

        trigger_matching(run.id, current_user=user, db=db)

        txn = db.query(ReconciliationTransaction).filter(
            ReconciliationTransaction.reconciliation_run_id == run.id).one()
        assert txn.match_status == "bank_fee"
        assert txn.journal_entry_id is not None

        entry = db.query(JournalEntry).filter(
            JournalEntry.id == txn.journal_entry_id).one()
        assert entry.status == "draft"          # L-2 books; a human posts.
        assert entry.entry_type == "reconciliation"
        assert entry.entry_number.startswith("RECON-")
        assert entry.entry_date == date(2026, 6, 16)
        assert entry.period_month == 6 and entry.period_year == 2026
        assert entry.total_debits == Decimal("15.00")
        assert entry.total_credits == Decimal("15.00")

        debit, credit = _lines_for(db, entry.id)
        assert debit.gl_account_id == gl["bank_fee"]
        assert debit.debit_amount == Decimal("15.00")
        assert debit.credit_amount == Decimal("0.00")
        assert credit.gl_account_id == gl["cash"]
        assert credit.credit_amount == Decimal("15.00")
        assert credit.debit_amount == Decimal("0.00")

    def test_lines_carry_the_gl_account_number_and_name(self, db):
        """The entry has to be READABLE, not merely balanced.

        `JournalLineSpec` does no lookups by design — the caller denormalizes
        account number + name onto each line. `/journal-entries` renders those
        columns, and `year_end_close_agent` + `estimated_tax_prep_agent` match
        on them. Booking with only `gl_account_id` produces an entry that is
        arithmetically correct and shows a human two blank rows.

        Caught by reading the first entry on testco rather than by a test —
        which is why this test now exists.
        """
        co, user, acct, run, gl = _substrate(db)
        _txn(db, run, day=16, amount=_FEE_AMT, desc="MONTHLY SERVICE CHARGE", order=0)
        db.commit()

        trigger_matching(run.id, current_user=user, db=db)
        txn = db.query(ReconciliationTransaction).filter(
            ReconciliationTransaction.reconciliation_run_id == run.id).one()

        debit, credit = _lines_for(db, txn.journal_entry_id)
        # Values come from `_substrate`'s mappings, stated as literals.
        assert debit.gl_account_number == "6010"
        assert debit.gl_account_name == "Bank Charges"
        assert credit.gl_account_number == "1010"
        assert credit.gl_account_name == "Operating Cash"

    def test_positive_amount_reverses_both_legs(self, db):
        """HAND MATH — a +15.00 fee REFUND is money IN, so the legs swap:
             line 1  DEBIT  Operating Cash 15.00
             line 2  CREDIT Bank Charges   15.00
        Same magnitude, opposite sides. The sign of the bank line is the only
        input that decides direction.
        """
        co, user, acct, run, gl = _substrate(db)
        _txn(db, run, day=16, amount="15", desc="MONTHLY SERVICE CHARGE REFUND", order=0)
        db.commit()

        trigger_matching(run.id, current_user=user, db=db)
        txn = db.query(ReconciliationTransaction).filter(
            ReconciliationTransaction.reconciliation_run_id == run.id).one()

        debit, credit = _lines_for(db, txn.journal_entry_id)
        assert debit.gl_account_id == gl["cash"]
        assert debit.debit_amount == Decimal("15.00")
        assert credit.gl_account_id == gl["bank_fee"]
        assert credit.credit_amount == Decimal("15.00")

    def test_all_three_classifications_book_to_their_own_account(self, db):
        """The symmetry L-2 introduces: fee, payroll and nsf are equally
        certain classifications and are now treated identically — each books to
        the account its own settings entry names, against the same cash leg."""
        co, user, acct, run, gl = _substrate(db)
        _three_keyword_rows(db, run)

        trigger_matching(run.id, current_user=user, db=db)

        txns = db.query(ReconciliationTransaction).filter(
            ReconciliationTransaction.reconciliation_run_id == run.id
        ).order_by(ReconciliationTransaction.sort_order).all()
        expected = ["payroll", "bank_fee", "nsf"]
        assert [t.match_status for t in txns] == expected

        for t, classification in zip(txns, expected):
            assert t.journal_entry_id is not None
            debit, credit = _lines_for(db, t.journal_entry_id)
            assert debit.gl_account_id == gl[classification]
            assert credit.gl_account_id == gl["cash"]


# ── 2. the cleared_total arithmetic, both ways ──────────────────────────────


class TestClearedTotalArithmetic:
    def test_configured_tenant_all_three_clear(self, db):
        """HAND MATH — every row books, so every row clears:
             payroll  -5000
             bank_fee   -15
             nsf       -100
             cleared_total = -5000 + -15 + -100 = -5115
             difference    = closing - opening - cleared
                           = 2000 - 1000 - (-5115) = 6115
             auto 3 · suggested 0 · unmatched 0

        FLIPPED FROM PRE-L-2, where this tenant cleared -5000 (payroll alone)
        and booked nothing at all. The fee and the nsf were withheld from
        cleared_total for no reason the ledger could see.
        """
        co, user, acct, run, gl = _substrate(db)
        _three_keyword_rows(db, run)

        result = trigger_matching(run.id, current_user=user, db=db)
        assert result["auto_cleared"] == 3
        assert result["suggested"] == 0
        assert result["unmatched"] == 0

        db.refresh(run)
        assert run.platform_cleared_balance == Decimal("-5115")
        assert run.difference == Decimal("6115")

    def test_unconfigured_tenant_clears_nothing(self, db):
        """HAND MATH — the other direction. No keyword map, so no row can book,
        so NO row clears:
             cleared_total = 0
             difference    = 2000 - 1000 - 0 = 1000
             auto 0 · suggested 0 · unmatched 3

        FLIPPED FROM PRE-L-2, where this same unconfigured tenant reported
        cleared_total = -5000 against an empty ledger. That number was the
        defect; this one is the fix.
        """
        co, user, acct, run, gl = _substrate(db, keyword_map="none")
        _three_keyword_rows(db, run)

        result = trigger_matching(run.id, current_user=user, db=db)
        assert result["auto_cleared"] == 0
        assert result["unmatched"] == 3

        db.refresh(run)
        assert run.platform_cleared_balance == Decimal("0")
        assert run.difference == Decimal("1000")
        assert db.query(JournalEntry).filter(JournalEntry.tenant_id == co.id).count() == 0

    def test_partial_config_clears_only_the_row_that_booked(self, db):
        """HAND MATH — BOTH directions inside ONE run. Only `bank_fee` is
        mapped, so only the fee books:
             payroll  -5000  blocked → contributes  0
             bank_fee   -15  booked  → contributes -15
             nsf       -100  blocked → contributes  0
             cleared_total = -15
             difference    = 2000 - 1000 - (-15) = 1015
             auto 1 · unmatched 2

        This is the test that shows the rule is per-ROW, not per-tenant: the
        licence to clear is that particular row's own journal entry.
        """
        co, user, acct, run, gl = _substrate(db, keyword_map=["bank_fee"])
        _three_keyword_rows(db, run)

        result = trigger_matching(run.id, current_user=user, db=db)
        assert result["auto_cleared"] == 1
        assert result["unmatched"] == 2

        db.refresh(run)
        assert run.platform_cleared_balance == Decimal("-15")
        assert run.difference == Decimal("1015")
        assert db.query(JournalEntry).filter(JournalEntry.tenant_id == co.id).count() == 1

    def test_contra_unset_blocks_every_row_even_with_a_full_keyword_map(self, db):
        """A fully-configured keyword map still cannot book without the bank
        account's own cash account — a journal entry needs both legs. Nothing
        clears; nothing is one-legged."""
        co, user, acct, run, gl = _substrate(db, contra=False)
        _three_keyword_rows(db, run)

        result = trigger_matching(run.id, current_user=user, db=db)
        assert result["auto_cleared"] == 0
        assert result["unmatched"] == 3

        db.refresh(run)
        assert run.platform_cleared_balance == Decimal("0")
        assert db.query(JournalEntry).filter(JournalEntry.tenant_id == co.id).count() == 0


# ── 3. the reconciliation and the ledger agree ─────────────────────────────


class TestLedgerAgreesWithReconciliation:
    def test_cash_leg_movement_equals_platform_cleared_balance(self, db):
        """The arc's central claim, checked from the OTHER side.

        cleared_total is computed from the bank transactions. This reads the
        journal lines L-2 wrote against the bank's own cash GL account and nets
        them:

             cash debits  0.00
             cash credits 5115.00   (5000 payroll + 15 fee + 100 nsf)
             net movement = debits - credits = 0 - 5115 = -5115
             platform_cleared_balance                    = -5115   ✓

        Pre-L-2 the left side was 0.00 (nothing was ever written) and the right
        side was -5000. There was no third column to compare them in.

        SCOPE — this run contains ONLY keyword rows, and that is deliberate.
        The equality is not yet a platform invariant: an `auto_cleared` payment
        match still clears on the strength of the matched payment record and
        books nothing, so a run containing one would break this equality by
        exactly that payment's amount. Closing that is L-3. Do not generalise
        this assertion until it does.
        """
        co, user, acct, run, gl = _substrate(db)
        _three_keyword_rows(db, run)

        trigger_matching(run.id, current_user=user, db=db)
        db.refresh(run)

        cash_lines = (
            db.query(JournalEntryLine)
            .filter(
                JournalEntryLine.tenant_id == co.id,
                JournalEntryLine.gl_account_id == gl["cash"],
            )
            .all()
        )
        debits = sum((line.debit_amount for line in cash_lines), Decimal(0))
        credits = sum((line.credit_amount for line in cash_lines), Decimal(0))
        assert debits == Decimal("0.00")
        assert credits == Decimal("5115.00")

        net_cash_movement = debits - credits
        assert net_cash_movement == Decimal("-5115")
        assert net_cash_movement == run.platform_cleared_balance

    def test_every_cleared_keyword_row_points_at_its_entry(self, db):
        """The join that makes the agreement checkable on real data rather than
        only in a test that already knows both numbers."""
        co, user, acct, run, gl = _substrate(db)
        _three_keyword_rows(db, run)
        trigger_matching(run.id, current_user=user, db=db)

        txns = db.query(ReconciliationTransaction).filter(
            ReconciliationTransaction.reconciliation_run_id == run.id).all()
        for t in txns:
            entry = db.query(JournalEntry).filter(
                JournalEntry.id == t.journal_entry_id).one()
            # The entry's own magnitude matches the bank line it came from.
            assert entry.total_debits == abs(t.amount)
            assert entry.total_credits == abs(t.amount)


# ── 4. fail-closed, with distinct reasons ──────────────────────────────────


class TestBlockedReasonsAreDistinct:
    def test_unmapped_records_keyword_gl_unmapped(self, db):
        co, user, acct, run, gl = _substrate(db, keyword_map="none")
        _txn(db, run, day=16, amount=_FEE_AMT, desc="MONTHLY SERVICE CHARGE", order=0)
        db.commit()
        trigger_matching(run.id, current_user=user, db=db)

        exc = db.query(ReconciliationException).filter(
            ReconciliationException.tenant_id == co.id).one()
        assert exc.keyword_classification == "bank_fee"
        assert exc.blocked_reason == reconciliation_gl.BLOCK_KEYWORD_GL_UNMAPPED

    def test_dangling_records_keyword_gl_dangling(self, db):
        """Mapped, but the mapping was deactivated afterwards. A different
        operator action (re-map) than an absent entry (configure), so a
        different reason."""
        co, user, acct, run, gl = _substrate(db)
        db.query(TenantGLMapping).filter(
            TenantGLMapping.id == gl["bank_fee"]).one().is_active = False
        _txn(db, run, day=16, amount=_FEE_AMT, desc="MONTHLY SERVICE CHARGE", order=0)
        db.commit()
        trigger_matching(run.id, current_user=user, db=db)

        exc = db.query(ReconciliationException).filter(
            ReconciliationException.tenant_id == co.id).one()
        assert exc.keyword_classification == "bank_fee"
        assert exc.blocked_reason == reconciliation_gl.BLOCK_KEYWORD_GL_DANGLING

    def test_contra_unset_records_contra_gl_unset(self, db):
        co, user, acct, run, gl = _substrate(db, contra=False)
        _txn(db, run, day=16, amount=_FEE_AMT, desc="MONTHLY SERVICE CHARGE", order=0)
        db.commit()
        trigger_matching(run.id, current_user=user, db=db)

        exc = db.query(ReconciliationException).filter(
            ReconciliationException.tenant_id == co.id).one()
        assert exc.blocked_reason == reconciliation_gl.BLOCK_CONTRA_GL_UNSET

    def test_foreign_tenant_mapping_is_blocked_not_borrowed(self, db):
        """A settings entry pointing at ANOTHER tenant's active mapping. It
        resolves to nothing here, so the row does not book and does not clear —
        the tenant gate holds at the posting layer, not just the resolver."""
        co, user, acct, run, gl = _substrate(db)
        other = _company(db)
        foreign = _mapping(db, other.id, name="Their Charges", number="6010")
        db.flush()
        co.set_setting(
            reconciliation_gl.KEYWORD_GL_SETTINGS_KEY,
            {**co.get_setting(reconciliation_gl.KEYWORD_GL_SETTINGS_KEY),
             "bank_fee": foreign.id},
        )
        _txn(db, run, day=16, amount=_FEE_AMT, desc="MONTHLY SERVICE CHARGE", order=0)
        db.commit()
        trigger_matching(run.id, current_user=user, db=db)

        db.refresh(run)
        assert run.platform_cleared_balance == Decimal("0")
        exc = db.query(ReconciliationException).filter(
            ReconciliationException.tenant_id == co.id).one()
        assert exc.blocked_reason == reconciliation_gl.BLOCK_KEYWORD_GL_DANGLING


# ── 5. the manual-label side door ──────────────────────────────────────────


class TestManualLabelDoesNotClear:
    def test_hand_set_payroll_status_without_an_entry_moves_nothing(self, db):
        """`POST .../transactions/{id}/action` with `mark_payroll` sets
        match_status = "payroll" directly and books nothing. If the tally keyed
        on the status STRING, that manual action would move cleared_total
        against an empty ledger — reintroducing the exact defect L-2 removes,
        through a side door. The tally keys on the journal entry instead.

        HAND MATH: cleared_total = 0; difference = 2000 - 1000 - 0 = 1000.
        """
        co, user, acct, run, gl = _substrate(db)
        t = _txn(db, run, day=15, amount=_PAYROLL_AMT, desc="Cheque 1041", order=0)
        db.flush()
        t.match_status = "payroll"          # the manual route's write
        t.journal_entry_id = None           # ...which books nothing
        db.commit()

        result = trigger_matching(run.id, current_user=user, db=db)
        # Not "unmatched", so the non-destructive gate leaves it alone entirely.
        assert result["auto_cleared"] == 0

        db.refresh(run)
        assert run.platform_cleared_balance == Decimal("0")
        assert run.difference == Decimal("1000")


# ── 6. the third card form reaches Books Review ────────────────────────────


class TestBlockedRowReachesBooksReview:
    def test_row_carries_classification_and_reason_with_no_candidates(self, db):
        """The queue row must carry enough for the display to render the CONFIG
        card. Zero candidates is what would otherwise route it to the coding
        card — the classification is what stops that.
        """
        from app.services.triage.engine import _dq_reconciliation_review

        co, user, acct, run, gl = _substrate(db, keyword_map="none")
        _txn(db, run, day=16, amount=_FEE_AMT, desc="MONTHLY SERVICE CHARGE", order=0)
        db.commit()
        trigger_matching(run.id, current_user=user, db=db)

        rows = _dq_reconciliation_review(db, user)
        assert len(rows) == 1
        row = rows[0]
        assert row["candidates"] == []
        assert row["keyword_classification"] == "bank_fee"
        assert row["blocked_reason"] == reconciliation_gl.BLOCK_KEYWORD_GL_UNMAPPED

    def test_ordinary_coding_row_carries_neither(self, db):
        """The discriminator must be absent on a genuine coding case, or every
        card becomes a config card."""
        from app.services.triage.engine import _dq_reconciliation_review

        co, user, acct, run, gl = _substrate(db)
        _txn(db, run, day=16, amount="-42", desc="ACME HARDWARE", order=0)
        db.commit()
        trigger_matching(run.id, current_user=user, db=db)

        rows = _dq_reconciliation_review(db, user)
        assert len(rows) == 1
        assert rows[0]["keyword_classification"] is None
        assert rows[0]["blocked_reason"] is None


class TestDeliberatelyUnmapped:
    """The THIRD settings state (L-2.1c).

    `payroll: None` present in the map means the operator decided this class does
    not post automatically. The production chart makes that the CORRECT answer for
    payroll and nsf, not an unfinished one — so it has to be distinguishable from
    "nobody has configured this yet", because the card says different things.

    What must NOT change: it still fails closed. A deliberate unmapping is a
    reason, never a licence.
    """

    def test_explicit_null_is_intentional_not_unmapped(self, db):
        co, user, acct, run, gl = _substrate(db, keyword_map="none")
        co.set_setting(reconciliation_gl.KEYWORD_GL_SETTINGS_KEY, {"bank_fee": None})
        db.commit()
        _txn(db, run, day=16, amount=_FEE_AMT, desc="MONTHLY SERVICE CHARGE", order=0)
        db.commit()
        trigger_matching(run.id, current_user=user, db=db)

        exc = db.query(ReconciliationException).filter(
            ReconciliationException.tenant_id == co.id).one()
        assert exc.keyword_classification == "bank_fee"
        assert exc.blocked_reason == reconciliation_gl.BLOCK_KEYWORD_GL_INTENTIONAL

    def test_absent_key_is_still_unmapped(self, db):
        """The other side of the same distinction. An empty map is 'nobody has
        decided'; it must not drift into reading as a decision."""
        co, user, acct, run, gl = _substrate(db, keyword_map="none")
        co.set_setting(reconciliation_gl.KEYWORD_GL_SETTINGS_KEY, {"payroll": None})
        db.commit()
        _txn(db, run, day=16, amount=_FEE_AMT, desc="MONTHLY SERVICE CHARGE", order=0)
        db.commit()
        trigger_matching(run.id, current_user=user, db=db)

        exc = db.query(ReconciliationException).filter(
            ReconciliationException.tenant_id == co.id).one()
        # bank_fee is ABSENT from a map that carries a deliberate payroll entry.
        assert exc.blocked_reason == reconciliation_gl.BLOCK_KEYWORD_GL_UNMAPPED

    def test_deliberate_and_absent_coexist_in_one_run(self, db):
        """Both states in the SAME map, resolved per row. This is the shape a
        real tenant has: bank_fee mapped, payroll deliberately off, nsf not yet
        decided."""
        co, user, acct, run, gl = _substrate(db, keyword_map=["bank_fee"])
        co.set_setting(
            reconciliation_gl.KEYWORD_GL_SETTINGS_KEY,
            {"bank_fee": gl["bank_fee"], "payroll": None},
        )
        db.commit()
        _three_keyword_rows(db, run)
        trigger_matching(run.id, current_user=user, db=db)

        by_class = {
            e.keyword_classification: e.blocked_reason
            for e in db.query(ReconciliationException).filter(
                ReconciliationException.tenant_id == co.id).all()
        }
        assert "bank_fee" not in by_class  # mapped → booked → cleared, no exception
        assert by_class["payroll"] == reconciliation_gl.BLOCK_KEYWORD_GL_INTENTIONAL
        assert by_class["nsf"] == reconciliation_gl.BLOCK_KEYWORD_GL_UNMAPPED

    def test_deliberate_unmapping_still_books_nothing_and_clears_nothing(self, db):
        """THE PIN THAT MATTERS. A deliberate unmapping is a REASON, not a
        licence — the row must stay unmatched with no journal entry behind it,
        exactly like every other blocked reason. If this ever passes while a JE
        exists, 'booking is the licence to clear' has been broken by a copy
        change.

        HAND MATH — one -15.00 row, deliberately unmapped:
             journal entries       0
             cleared_total         0.00
             difference  = 2000 - 1000 - 0 = 1000.00
        """
        co, user, acct, run, gl = _substrate(db, keyword_map="none")
        co.set_setting(reconciliation_gl.KEYWORD_GL_SETTINGS_KEY, {"bank_fee": None})
        db.commit()
        _txn(db, run, day=16, amount=_FEE_AMT, desc="MONTHLY SERVICE CHARGE", order=0)
        db.commit()
        trigger_matching(run.id, current_user=user, db=db)

        txn = db.query(ReconciliationTransaction).filter(
            ReconciliationTransaction.reconciliation_run_id == run.id).one()
        assert txn.match_status == "unmatched"
        assert txn.journal_entry_id is None
        assert db.query(JournalEntry).filter(
            JournalEntry.tenant_id == co.id).count() == 0

        db.refresh(run)
        assert run.auto_cleared_count == 0
        assert run.unmatched_count == 1
        assert run.platform_cleared_balance == Decimal("0")
        assert run.difference == Decimal("1000")

    def test_falsy_non_null_is_unmapped_not_intentional(self, db):
        """Only an explicit null is a decision. An empty string — the shape a
        careless settings writer produces — is NOT one, and must read as
        unconfigured rather than silently claiming the operator chose it."""
        co, user, acct, run, gl = _substrate(db, keyword_map="none")
        co.set_setting(reconciliation_gl.KEYWORD_GL_SETTINGS_KEY, {"bank_fee": ""})
        db.commit()
        _txn(db, run, day=16, amount=_FEE_AMT, desc="MONTHLY SERVICE CHARGE", order=0)
        db.commit()
        trigger_matching(run.id, current_user=user, db=db)

        exc = db.query(ReconciliationException).filter(
            ReconciliationException.tenant_id == co.id).one()
        assert exc.blocked_reason == reconciliation_gl.BLOCK_KEYWORD_GL_UNMAPPED

    def test_reason_fits_the_column(self):
        """`blocked_reason` is String(30). A reason that silently truncates would
        make the card fall through to the unrecognised-reason copy."""
        assert len(reconciliation_gl.BLOCK_KEYWORD_GL_INTENTIONAL) <= 30

    def test_all_reasons_are_distinct(self):
        """Six now. Two that collide would render one card for two situations."""
        reasons = [
            reconciliation_gl.BLOCK_KEYWORD_GL_UNMAPPED,
            reconciliation_gl.BLOCK_KEYWORD_GL_INTENTIONAL,
            reconciliation_gl.BLOCK_KEYWORD_GL_DANGLING,
            reconciliation_gl.BLOCK_CONTRA_GL_UNSET,
            reconciliation_gl.BLOCK_CONTRA_GL_DANGLING,
            reconciliation_gl.BLOCK_PERIOD_LOCKED,
        ]
        assert len(set(reasons)) == len(reasons)


class TestOneResolverTwoCallers:
    """L-2.1f — the matcher and the display must not be able to disagree.

    Two code paths computing "why is this blocked" that can drift is the
    divergence the membership seam and `_count_config` exist to prevent. There
    is one `KeywordPostingContext`; these pin that it really is one.
    """

    def test_context_decide_matches_the_single_row_wrapper(self, db):
        """`resolve_keyword_posting` is a WRAPPER, not a second implementation.
        Every (classification × config) combination must agree with `decide`."""
        co, user, acct, run, gl = _substrate(db, keyword_map=["bank_fee"])
        co.set_setting(
            reconciliation_gl.KEYWORD_GL_SETTINGS_KEY,
            {"bank_fee": gl["bank_fee"], "payroll": None},
        )
        db.commit()
        ctx = reconciliation_gl.build_keyword_posting_context(db, co, [acct])
        for classification in reconciliation_gl.KEYWORD_CLASSIFICATIONS:
            wrapped, wrapped_reason = reconciliation_gl.resolve_keyword_posting(
                db, co, acct, classification, date(2026, 6, 16),
            )
            batched, batched_reason = ctx.decide(
                classification=classification,
                financial_account_id=acct.id,
                entry_date=date(2026, 6, 16),
            )
            assert wrapped_reason == batched_reason, classification
            assert (wrapped is None) == (batched is None), classification
            if wrapped is not None:
                assert wrapped == batched, classification

    def test_decide_is_pure(self, db):
        """No database. A context built once and reused across a page of rows
        must not quietly issue a query per row — that is the whole reason the
        display can afford to re-resolve."""
        co, user, acct, run, gl = _substrate(db)
        ctx = reconciliation_gl.build_keyword_posting_context(db, co, [acct])
        db.close()  # any query from here raises
        posting, reason = ctx.decide(
            classification="bank_fee",
            financial_account_id=acct.id,
            entry_date=date(2026, 6, 16),
        )
        assert posting is not None and reason is None

    def test_check_order_is_keyword_then_contra_then_period(self, db):
        """The order decides WHICH reason a blocked row reports, so it is part
        of the contract. With all three broken at once, the keyword leg wins."""
        co, user, acct, run, gl = _substrate(db, keyword_map="none", contra=False)
        db.commit()
        ctx = reconciliation_gl.build_keyword_posting_context(db, co, [acct])
        _posting, reason = ctx.decide(
            classification="bank_fee",
            financial_account_id=acct.id,
            entry_date=date(2026, 6, 16),
        )
        assert reason == reconciliation_gl.BLOCK_KEYWORD_GL_UNMAPPED

    def test_unknown_account_id_fails_closed_as_contra_unset(self, db):
        """A row whose bank account is not in the context — a caller bug, but it
        must fail CLOSED rather than KeyError or (worse) book against nothing."""
        co, user, acct, run, gl = _substrate(db)
        ctx = reconciliation_gl.build_keyword_posting_context(db, co, [acct])
        _posting, reason = ctx.decide(
            classification="bank_fee",
            financial_account_id="not-an-account",
            entry_date=date(2026, 6, 16),
        )
        assert reason == reconciliation_gl.BLOCK_CONTRA_GL_UNSET


class TestBlockedReasonIsLiveNotASnapshot:
    """L-2.1f — configure, come back, and the card must have changed.

    `blocked_reason` is stamped at matcher-run time. Left as a snapshot, an
    operator who fixes the config sees cards saying exactly what they said
    before — the settings panel appearing not to work.
    """

    def _row(self, db, user):
        from app.services.triage.engine import _dq_reconciliation_review
        rows = _dq_reconciliation_review(db, user)
        assert len(rows) == 1
        return rows[0]

    def test_reason_changes_after_the_map_is_configured(self, db):
        co, user, acct, run, gl = _substrate(db, keyword_map="none")
        _txn(db, run, day=16, amount=_FEE_AMT, desc="MONTHLY SERVICE CHARGE", order=0)
        db.commit()
        trigger_matching(run.id, current_user=user, db=db)

        before = self._row(db, user)
        assert before["blocked_reason"] == reconciliation_gl.BLOCK_KEYWORD_GL_UNMAPPED
        assert before["can_post_now"] is False

        # The operator configures the map. NO re-run.
        co.set_setting(
            reconciliation_gl.KEYWORD_GL_SETTINGS_KEY, {"bank_fee": gl["bank_fee"]}
        )
        db.commit()

        after = self._row(db, user)
        assert after["blocked_reason"] is None
        assert after["can_post_now"] is True

    def test_the_snapshot_is_still_reported_separately(self, db):
        """The persisted reason stays available as `blocked_reason_at_match` —
        'why it could not book when the statement was scored' is a different and
        still-true fact, and the audit trail should not be lost to a rename."""
        co, user, acct, run, gl = _substrate(db, keyword_map="none")
        _txn(db, run, day=16, amount=_FEE_AMT, desc="MONTHLY SERVICE CHARGE", order=0)
        db.commit()
        trigger_matching(run.id, current_user=user, db=db)
        co.set_setting(
            reconciliation_gl.KEYWORD_GL_SETTINGS_KEY, {"bank_fee": gl["bank_fee"]}
        )
        db.commit()

        row = self._row(db, user)
        assert row["blocked_reason"] is None
        assert row["blocked_reason_at_match"] == reconciliation_gl.BLOCK_KEYWORD_GL_UNMAPPED

    def test_reason_changes_to_the_NEW_reason_not_just_to_none(self, db):
        """Configured the keyword leg but not the contra: the reason must move
        on to the next real blocker rather than clearing."""
        co, user, acct, run, gl = _substrate(db, keyword_map="none", contra=False)
        _txn(db, run, day=16, amount=_FEE_AMT, desc="MONTHLY SERVICE CHARGE", order=0)
        db.commit()
        trigger_matching(run.id, current_user=user, db=db)
        co.set_setting(
            reconciliation_gl.KEYWORD_GL_SETTINGS_KEY, {"bank_fee": gl["bank_fee"]}
        )
        db.commit()

        row = self._row(db, user)
        assert row["blocked_reason"] == reconciliation_gl.BLOCK_CONTRA_GL_UNSET
        assert row["can_post_now"] is False

    def test_deliberate_unmapping_after_the_run_shows_as_intentional(self, db):
        co, user, acct, run, gl = _substrate(db, keyword_map="none")
        _txn(db, run, day=16, amount=_FEE_AMT, desc="MONTHLY SERVICE CHARGE", order=0)
        db.commit()
        trigger_matching(run.id, current_user=user, db=db)
        co.set_setting(reconciliation_gl.KEYWORD_GL_SETTINGS_KEY, {"bank_fee": None})
        db.commit()

        row = self._row(db, user)
        assert row["blocked_reason"] == reconciliation_gl.BLOCK_KEYWORD_GL_INTENTIONAL
        assert row["can_post_now"] is False

    def test_non_keyword_rows_are_untouched(self, db):
        """An ordinary coding exception has no classification, so it must not be
        re-resolved, must not gain can_post_now, and must not pay for any of it."""
        co, user, acct, run, gl = _substrate(db)
        _txn(db, run, day=16, amount="-42", desc="Touchstone Climbing", order=0)
        db.commit()
        trigger_matching(run.id, current_user=user, db=db)

        row = self._row(db, user)
        assert row["keyword_classification"] is None
        assert row["blocked_reason"] is None
        assert row["can_post_now"] is False

    def test_every_row_carries_an_as_of(self, db):
        """F3's line. The reason is live but the CANDIDATE set beside it is
        still whatever the last run computed, so the card says when that was."""
        co, user, acct, run, gl = _substrate(db, keyword_map="none")
        _txn(db, run, day=16, amount=_FEE_AMT, desc="MONTHLY SERVICE CHARGE", order=0)
        db.commit()
        trigger_matching(run.id, current_user=user, db=db)
        assert self._row(db, user)["evaluated_at"] is not None


class TestPostItReResolvesAtExecution:
    """L-2.1f — the card's verdict is a render-time opinion, never trusted.

    Between "this can post now" rendering and the operator clicking, config can
    change, a period can lock, and a matcher re-run can book the row. Same
    discipline as `_try_claim` re-checking the pool rather than trusting scoring.
    """

    def _post(self, db, user, txn_id):
        from app.services.triage.action_handlers import HANDLERS
        return HANDLERS["reconciliation.post_keyword"](
            {"db": db, "user": user, "entity_id": txn_id, "payload": {}}
        )

    def _blocked_row(self, db):
        co, user, acct, run, gl = _substrate(db, keyword_map="none")
        _txn(db, run, day=16, amount=_FEE_AMT, desc="MONTHLY SERVICE CHARGE", order=0)
        db.commit()
        trigger_matching(run.id, current_user=user, db=db)
        txn = db.query(ReconciliationTransaction).filter(
            ReconciliationTransaction.reconciliation_run_id == run.id).one()
        return co, user, acct, run, gl, txn

    def test_posts_and_clears_once_configured(self, db):
        """HAND MATH — a -15.00 fee, posted from the card:
             DEBIT  Bank Charges   15.00
             CREDIT Operating Cash 15.00
        and the row clears BECAUSE the entry exists, not because of the click.
        """
        co, user, acct, run, gl, txn = self._blocked_row(db)
        co.set_setting(
            reconciliation_gl.KEYWORD_GL_SETTINGS_KEY, {"bank_fee": gl["bank_fee"]}
        )
        db.commit()

        result = self._post(db, user, txn.id)
        assert result["status"] == "applied"

        db.refresh(txn)
        assert txn.match_status == "bank_fee"
        assert txn.journal_entry_id is not None
        entry = db.query(JournalEntry).filter(
            JournalEntry.id == txn.journal_entry_id).one()
        assert entry.status == "draft"
        assert entry.total_debits == Decimal("15.00")
        assert entry.total_credits == Decimal("15.00")
        debit, credit = _lines_for(db, entry.id)
        assert debit.gl_account_id == gl["bank_fee"]
        assert credit.gl_account_id == gl["cash"]

    def test_refuses_when_the_config_went_away_after_render(self, db):
        """The card computed 'can post'; by click time the mapping is gone. The
        message must report the CURRENT reason, not the stale verdict."""
        co, user, acct, run, gl, txn = self._blocked_row(db)
        co.set_setting(
            reconciliation_gl.KEYWORD_GL_SETTINGS_KEY, {"bank_fee": gl["bank_fee"]}
        )
        db.commit()
        # …and then it is un-configured between render and click.
        co.set_setting(reconciliation_gl.KEYWORD_GL_SETTINGS_KEY, {})
        db.commit()

        result = self._post(db, user, txn.id)
        assert result["status"] == "errored"
        assert reconciliation_gl.BLOCK_KEYWORD_GL_UNMAPPED in result["message"]
        db.refresh(txn)
        assert txn.match_status == "unmatched"
        assert db.query(JournalEntry).filter(
            JournalEntry.tenant_id == co.id).count() == 0

    def test_refuses_when_a_rerun_already_booked_it(self, db):
        """THE DOUBLE-BOOK RACE. Configure, re-run the matcher (which books it),
        then click the button the stale card is still showing."""
        co, user, acct, run, gl, txn = self._blocked_row(db)
        co.set_setting(
            reconciliation_gl.KEYWORD_GL_SETTINGS_KEY, {"bank_fee": gl["bank_fee"]}
        )
        db.commit()
        trigger_matching(run.id, current_user=user, db=db)  # books it
        db.refresh(txn)
        assert txn.journal_entry_id is not None
        before = db.query(JournalEntry).filter(JournalEntry.tenant_id == co.id).count()

        result = self._post(db, user, txn.id)
        assert result["status"] == "errored"
        after = db.query(JournalEntry).filter(JournalEntry.tenant_id == co.id).count()
        assert after == before  # no second entry

    def test_refuses_when_the_period_locked_after_render(self, db):
        from app.models.period_lock import PeriodLock

        co, user, acct, run, gl, txn = self._blocked_row(db)
        co.set_setting(
            reconciliation_gl.KEYWORD_GL_SETTINGS_KEY, {"bank_fee": gl["bank_fee"]}
        )
        db.add(PeriodLock(
            id=str(uuid.uuid4()), tenant_id=co.id, period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30), is_active=True,
        ))
        db.commit()

        result = self._post(db, user, txn.id)
        assert result["status"] == "errored"
        assert reconciliation_gl.BLOCK_PERIOD_LOCKED in result["message"]
        assert db.query(JournalEntry).filter(
            JournalEntry.tenant_id == co.id).count() == 0

    def test_refuses_a_row_that_is_not_a_keyword_row(self, db):
        co, user, acct, run, gl = _substrate(db)
        _txn(db, run, day=16, amount="-42", desc="Touchstone Climbing", order=0)
        db.commit()
        trigger_matching(run.id, current_user=user, db=db)
        txn = db.query(ReconciliationTransaction).filter(
            ReconciliationTransaction.reconciliation_run_id == run.id).one()

        result = self._post(db, user, txn.id)
        assert result["status"] == "errored"
        assert db.query(JournalEntry).filter(
            JournalEntry.tenant_id == co.id).count() == 0

    def test_is_tenant_scoped(self, db):
        co, user, acct, run, gl, txn = self._blocked_row(db)
        other = _company(db)
        other_user = _user(db, other)
        db.commit()
        result = self._post(db, other_user, txn.id)
        assert result["status"] == "errored"
