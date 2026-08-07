"""Ledger Posting arc L-3 — a coded row books, or it does not clear.

L-2 gave keyword rows the rule: a balanced two-legged draft JE exists, or the
row stays open. L-3 extends it to the one remaining place a human could clear a
row against nothing — the coding accept, which pre-L-3 wrote free text to
`match_notes` and called it resolved.

THE INVARIANT'S SECOND CLAUSE (ratified 2026-08-05): a row clears when the
economic event is on the books — either because this action posts it, or because
it was already posted by the transaction being matched. Keyword rows post. Coded
rows post at accept, which is this file. Matched payments clear against an entry
that should already exist and are OUT of L-3 (a matched payment posts nothing;
reconciliation is not an economic event).

What this file pins, in order of how much it matters:

  1. THE ARITHMETIC, BOTH DIRECTIONS, hand-computed as literals with the sides
     spelled out. Money out debits the coded account and credits cash; money in
     reverses both. Magnitudes are absolute — a line carries a side, never a
     negative.

  2. NOTHING CLEARS UNBOOKED. Every refusal path asserts the platform
     `journal_entries` count is unchanged AND the transaction is still
     `unmatched`. A message without that assertion would let a half-write pass.

  3. THE CONTRA IS A CONFIGURATION PROBLEM, NAMED AS ONE. An operator can pick a
     coding account all day; without the bank account's own GL account there is
     no second leg. The refusal says which thing to fix.

  4. THE EXISTENCE-ORACLE DISCIPLINE HOLDS AT THIS BOUNDARY TOO (L-2.1b). A
     foreign-tenant account id and a nonexistent one produce BYTE-IDENTICAL
     messages; inactive may be named, because it is the operator's own data.

  5. AN OMITTED NOTE DOES NOT CLEAR `match_notes`. Plaid writes
     "[bank retracted this transaction]" onto unmatched rows and it is the
     operator's only trace of that; an unconditional assign would erase it. The
     legacy `PATCH /transactions/{id}/action` route DOES assign unconditionally
     — recorded as a known quiet-clear, deliberately not copied here.

DELIBERATE PIN FLIP: `test_reconciliation_review_b3.py::
test_coding_accept_requires_and_records_a_coding` asserted that payload
`{"coding": "6100 · Interest"}` accepted the row and wrote that string to
`match_notes`. That behavior is gone — the string named no account, resolved to
nothing, and cleared a row against no entry. The B-3 test is updated in this
commit to assert the refusal instead; its prior body is quoted in its docstring.

Cleans up its own `rl3-` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

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
from app.services.agents.period_lock import PeriodLockService
from app.services.triage.action_handlers import _handle_reconciliation_accept
from app.services.triage.engine import _dq_reconciliation_review
from tests._cleanup import purge_companies_by_slug

_SLUG = "rl3-"

# The coded amount used by the arithmetic tests, so the hand math below compares
# like with like. Signed from the BANK's point of view: negative is money out.
_OUT = Decimal("-377.00")
_IN = Decimal("412.50")


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


class _Env:
    def __init__(self, s):
        self.s = s
        sfx = uuid.uuid4().hex[:8]
        self.company = Company(
            id=str(uuid.uuid4()), name=f"RL3 {sfx}", slug=f"{_SLUG}{sfx}",
            is_active=True, vertical="manufacturing",
        )
        s.add(self.company); s.flush()
        role = Role(id=str(uuid.uuid4()), company_id=self.company.id,
                    name="Admin", slug="admin")
        s.add(role); s.flush()
        self.user = User(
            id=str(uuid.uuid4()), company_id=self.company.id, role_id=role.id,
            email=f"{_SLUG}{sfx}@test.local", hashed_password="x",
            first_name="R", last_name="L3", is_active=True,
        )
        s.add(self.user); s.flush()
        self.co = self.company.id

    def mapping(self, *, name, number, active=True, tenant_id=None) -> TenantGLMapping:
        m = TenantGLMapping(
            id=str(uuid.uuid4()), tenant_id=tenant_id or self.co,
            platform_category=name.lower().replace(" ", "_"),
            account_number=number, account_name=name, is_active=active,
        )
        self.s.add(m); self.s.flush()
        return m

    def account(self, *, contra: TenantGLMapping | None) -> FinancialAccount:
        a = FinancialAccount(
            id=str(uuid.uuid4()), tenant_id=self.co, account_type="checking",
            account_name="Operating",
            gl_account_id=contra.id if contra is not None else None,
        )
        self.s.add(a); self.s.flush()
        return a

    def txn(self, account, *, amount: Decimal, day=15, notes=None):
        run = ReconciliationRun(
            id=str(uuid.uuid4()), tenant_id=self.co, financial_account_id=account.id,
            statement_date=date(2026, 7, 31), statement_closing_balance=Decimal("0"),
            period_start=date(2026, 7, 1), opening_balance=Decimal("0"),
        )
        self.s.add(run); self.s.flush()
        t = ReconciliationTransaction(
            id=str(uuid.uuid4()), tenant_id=self.co, reconciliation_run_id=run.id,
            transaction_date=date(2026, 7, day),
            # Deliberately NOT a keyword-ladder description — a coded row is one
            # the system could not classify, which is why a human is coding it.
            description="ACH DEBIT 4471 CONSOLIDATED SUPPLY",
            amount=amount,
            transaction_type="debit" if amount < 0 else "credit",
            match_status="unmatched", sort_order=0, match_notes=notes,
        )
        self.s.add(t); self.s.flush()
        exc = ReconciliationException(
            id=str(uuid.uuid4()), tenant_id=self.co,
            reconciliation_transaction_id=t.id, reconciliation_run_id=run.id,
        )
        self.s.add(exc); self.s.flush()
        return t, exc

    def ctx(self, txn_id, **payload):
        return {
            "db": self.s, "user": self.user,
            "entity_type": "reconciliation_exception", "entity_id": txn_id,
            "queue_id": "reconciliation_review_triage", "action_id": "accept",
            "reason": None, "reason_code": None, "note": None,
            "payload": payload or {},
        }

    def je_count(self) -> int:
        """PLATFORM-wide, deliberately not tenant-scoped: a refusal must write
        no entry anywhere, and a tenant filter would hide a mis-scoped write."""
        return self.s.query(JournalEntry).count()


def _lines(env, entry_id) -> tuple[JournalEntryLine, JournalEntryLine]:
    """(the debit line, the credit line) — by side, not by insertion order."""
    rows = (
        env.s.query(JournalEntryLine)
        .filter(JournalEntryLine.journal_entry_id == entry_id)
        .all()
    )
    assert len(rows) == 2, f"expected exactly two legs, got {len(rows)}"
    debit = next(r for r in rows if r.debit_amount and r.debit_amount > 0)
    credit = next(r for r in rows if r.credit_amount and r.credit_amount > 0)
    return debit, credit


def _configured(env, *, amount=_OUT, notes=None):
    """A tenant that can post: cash mapped on the bank account, an expense
    account for the operator to choose, and one unclassifiable row."""
    cash = env.mapping(name="Operating Cash", number="1010")
    expense = env.mapping(name="Shop Supplies", number="6400")
    account = env.account(contra=cash)
    txn, exc = env.txn(account, amount=amount, notes=notes)
    env.s.commit()
    return cash, expense, txn, exc


# ── 1. the arithmetic, both directions ──────────────────────────────────────


class TestArithmetic:
    def test_money_out_debits_the_coded_account_and_credits_cash(self, env):
        """HAND MATH — amount -377.00 (money leaving the bank):

             magnitude          = abs(-377.00) = 377.00
             debit  6400 Shop Supplies  377.00
             credit 1010 Operating Cash 377.00
             total_debits == total_credits == 377.00, difference 0.00
        """
        cash, expense, txn, _ = _configured(env, amount=_OUT)

        res = _handle_reconciliation_accept(env.ctx(txn.id, gl_account_id=expense.id))
        env.s.commit()
        assert res["status"] == "applied"

        env.s.refresh(txn)
        entry = env.s.query(JournalEntry).filter(
            JournalEntry.id == txn.journal_entry_id).one()
        assert entry.total_debits == Decimal("377.00")
        assert entry.total_credits == Decimal("377.00")
        assert entry.total_debits - entry.total_credits == Decimal("0.00")

        debit, credit = _lines(env, entry.id)
        assert debit.gl_account_id == expense.id
        assert debit.debit_amount == Decimal("377.00")
        assert debit.credit_amount == Decimal("0.00")
        assert credit.gl_account_id == cash.id
        assert credit.credit_amount == Decimal("377.00")
        assert credit.debit_amount == Decimal("0.00")

    def test_money_in_debits_cash_and_credits_the_coded_account(self, env):
        """HAND MATH — amount +412.50 (money arriving in the bank):

             magnitude          = abs(412.50) = 412.50
             debit  1010 Operating Cash 412.50
             credit 6400 Shop Supplies  412.50
             total_debits == total_credits == 412.50, difference 0.00

        The mirror of the case above: a refund or credit-back reverses BOTH legs.
        """
        cash, expense, txn, _ = _configured(env, amount=_IN)

        res = _handle_reconciliation_accept(env.ctx(txn.id, gl_account_id=expense.id))
        env.s.commit()
        assert res["status"] == "applied"

        env.s.refresh(txn)
        entry = env.s.query(JournalEntry).filter(
            JournalEntry.id == txn.journal_entry_id).one()
        assert entry.total_debits == Decimal("412.50")
        assert entry.total_credits == Decimal("412.50")

        debit, credit = _lines(env, entry.id)
        assert debit.gl_account_id == cash.id
        assert debit.debit_amount == Decimal("412.50")
        assert credit.gl_account_id == expense.id
        assert credit.credit_amount == Decimal("412.50")

    def test_lines_carry_the_account_number_and_name(self, env):
        """JournalLineSpec does no lookups — number + name travel with the id or
        the register renders blank account columns."""
        _, expense, txn, _ = _configured(env)
        _handle_reconciliation_accept(env.ctx(txn.id, gl_account_id=expense.id))
        env.s.commit()
        env.s.refresh(txn)

        debit, credit = _lines(env, txn.journal_entry_id)
        assert debit.gl_account_number == "6400"
        assert debit.gl_account_name == "Shop Supplies"
        assert credit.gl_account_number == "1010"
        assert credit.gl_account_name == "Operating Cash"

    def test_entry_is_a_draft_recon_entry_and_the_row_points_at_it(self, env):
        """Draft, never posted — L-2's stated reason `journal_entries` going
        non-zero is safe to ship. A human posts."""
        _, expense, txn, exc = _configured(env)
        _handle_reconciliation_accept(env.ctx(txn.id, gl_account_id=expense.id))
        env.s.commit()
        env.s.refresh(txn); env.s.refresh(exc)

        entry = env.s.query(JournalEntry).filter(
            JournalEntry.id == txn.journal_entry_id).one()
        assert entry.status == "draft"
        assert entry.entry_type == "reconciliation"
        assert entry.entry_number.startswith("RECON-")
        assert entry.entry_date == date(2026, 7, 15)
        assert txn.match_status == "manually_matched"
        assert txn.reviewed_by == env.user.id
        assert exc.resolved is True


# ── 2. nothing clears unbooked ──────────────────────────────────────────────


class TestNothingClearsUnbooked:
    def test_no_account_refuses_and_posts_nothing(self, env):
        _, _, txn, _ = _configured(env)
        before = env.je_count()

        res = _handle_reconciliation_accept(env.ctx(txn.id))
        env.s.commit()

        assert res["status"] == "errored"
        assert "choose the GL account" in res["message"]
        env.s.refresh(txn)
        assert txn.match_status == "unmatched"
        assert txn.journal_entry_id is None
        assert env.je_count() == before

    def test_contra_unset_refuses_naming_the_bank_account(self, env):
        """The operator's coding account is perfectly good; the BANK account has
        no GL account, so there is no second leg."""
        expense = env.mapping(name="Shop Supplies", number="6400")
        account = env.account(contra=None)
        txn, _ = env.txn(account, amount=_OUT)
        env.s.commit()
        before = env.je_count()

        res = _handle_reconciliation_accept(env.ctx(txn.id, gl_account_id=expense.id))
        env.s.commit()

        assert res["status"] == "errored"
        assert "no GL cash account set" in res["message"]
        assert "second leg" in res["message"]
        env.s.refresh(txn)
        assert txn.match_status == "unmatched"
        assert txn.journal_entry_id is None
        assert env.je_count() == before

    def test_contra_dangling_refuses_and_says_re_map(self, env):
        """Set, but the mapping is inactive — a different operator action from
        'never set', which is why the two reasons are distinct."""
        dead_cash = env.mapping(name="Old Cash", number="1009", active=False)
        expense = env.mapping(name="Shop Supplies", number="6400")
        account = env.account(contra=dead_cash)
        txn, _ = env.txn(account, amount=_OUT)
        env.s.commit()
        before = env.je_count()

        res = _handle_reconciliation_accept(env.ctx(txn.id, gl_account_id=expense.id))
        env.s.commit()

        assert res["status"] == "errored"
        assert "no longer resolves" in res["message"]
        env.s.refresh(txn)
        assert txn.match_status == "unmatched"
        assert env.je_count() == before

    def test_locked_period_refuses_and_posts_nothing(self, env):
        _, expense, txn, _ = _configured(env)
        PeriodLockService.lock_period(
            env.s, env.co, date(2026, 7, 1), date(2026, 7, 31), reason="closed")
        env.s.commit()
        before = env.je_count()

        res = _handle_reconciliation_accept(env.ctx(txn.id, gl_account_id=expense.id))
        env.s.commit()

        assert res["status"] == "errored"
        assert "locked" in res["message"].lower()
        env.s.refresh(txn)
        assert txn.match_status == "unmatched"
        assert txn.journal_entry_id is None
        assert env.je_count() == before

    def test_a_row_that_already_has_an_entry_is_refused(self, env):
        """Belt to the match_status brace: never a second entry for one row."""
        _, expense, txn, _ = _configured(env)
        _handle_reconciliation_accept(env.ctx(txn.id, gl_account_id=expense.id))
        env.s.commit()
        env.s.refresh(txn)
        first_entry_id = txn.journal_entry_id
        after_first = env.je_count()

        # Force the row back to unmatched so the FIRST guard cannot be what
        # refuses — this test is about the journal_entry_id guard specifically.
        txn.match_status = "unmatched"
        env.s.commit()

        res = _handle_reconciliation_accept(env.ctx(txn.id, gl_account_id=expense.id))
        env.s.commit()

        assert res["status"] == "errored"
        assert "already has a journal entry" in res["message"]
        env.s.refresh(txn)
        assert txn.journal_entry_id == first_entry_id
        assert env.je_count() == after_first


# ── 3. the coded account crosses a validated boundary (L-2.1b / L-2.2) ──────


class TestCodedAccountValidation:
    def test_foreign_tenant_account_is_refused_not_borrowed(self, env):
        other = Company(id=str(uuid.uuid4()), name="Other",
                        slug=f"{_SLUG}other-{uuid.uuid4().hex[:6]}",
                        is_active=True, vertical="manufacturing")
        env.s.add(other); env.s.flush()
        theirs = env.mapping(name="Their Expense", number="6999",
                             tenant_id=other.id)
        _, _, txn, _ = _configured(env)
        before = env.je_count()

        res = _handle_reconciliation_accept(env.ctx(txn.id, gl_account_id=theirs.id))
        env.s.commit()

        assert res["status"] == "errored"
        env.s.refresh(txn)
        assert txn.match_status == "unmatched"
        assert env.je_count() == before
        # Their account number and name must not leak into the message.
        assert "6999" not in res["message"]
        assert "Their Expense" not in res["message"]

    def test_foreign_and_nonexistent_are_byte_identical(self, env):
        """The existence-oracle pin. Distinguishing the two would let anyone
        enumerate another tenant's chart by watching error strings."""
        other = Company(id=str(uuid.uuid4()), name="Other",
                        slug=f"{_SLUG}other-{uuid.uuid4().hex[:6]}",
                        is_active=True, vertical="manufacturing")
        env.s.add(other); env.s.flush()
        theirs = env.mapping(name="Their Expense", number="6999",
                             tenant_id=other.id)
        # ONE configured tenant, TWO rows — `uq_gl_mapping` is on
        # (tenant_id, platform_category, account_number), so seeding the same
        # chart twice for one tenant is a unique violation, not a fixture.
        cash = env.mapping(name="Operating Cash", number="1010")
        account = env.account(contra=cash)
        txn_a, _ = env.txn(account, amount=_OUT)
        txn_b, _ = env.txn(account, amount=_OUT)
        env.s.commit()

        foreign = _handle_reconciliation_accept(
            env.ctx(txn_a.id, gl_account_id=theirs.id))
        nonexistent = _handle_reconciliation_accept(
            env.ctx(txn_b.id, gl_account_id=str(uuid.uuid4())))

        assert foreign["message"] == nonexistent["message"]
        assert foreign["message"] == "That GL account is not in your chart of accounts."

    def test_inactive_own_account_is_named_because_it_is_actionable(self, env):
        """Inactive is the operator's OWN data and the fix is theirs, so the
        message may name it — the asymmetry L-2.1b ruled deliberately."""
        cash = env.mapping(name="Operating Cash", number="1010")
        dead = env.mapping(name="Retired Supplies", number="6401", active=False)
        account = env.account(contra=cash)
        txn, _ = env.txn(account, amount=_OUT)
        env.s.commit()
        before = env.je_count()

        res = _handle_reconciliation_accept(env.ctx(txn.id, gl_account_id=dead.id))
        env.s.commit()

        assert res["status"] == "errored"
        assert "6401" in res["message"] and "Retired Supplies" in res["message"]
        assert "inactive" in res["message"]
        assert env.je_count() == before


# ── 4. the note is a note ───────────────────────────────────────────────────


class TestNote:
    def test_an_omitted_note_does_not_clear_existing_match_notes(self, env):
        """THE REGRESSION THIS CLASS EXISTS FOR. Plaid appends
        "[bank retracted this transaction]" to unmatched rows; an unconditional
        assign on accept would erase the operator's only trace of it."""
        _, expense, txn, _ = _configured(
            env, notes="[bank retracted this transaction]")

        res = _handle_reconciliation_accept(env.ctx(txn.id, gl_account_id=expense.id))
        env.s.commit()
        assert res["status"] == "applied"

        env.s.refresh(txn)
        assert txn.match_notes == "[bank retracted this transaction]"

    def test_a_supplied_note_is_recorded_alongside_the_account(self, env):
        _, expense, txn, _ = _configured(env)

        res = _handle_reconciliation_accept(
            env.ctx(txn.id, gl_account_id=expense.id, note="Q3 shop restock"))
        env.s.commit()
        assert res["status"] == "applied"

        env.s.refresh(txn)
        assert txn.match_notes == "Q3 shop restock"
        # The note does not replace the posting — both exist.
        assert txn.journal_entry_id is not None

    def test_the_message_names_the_account_and_the_entry(self, env):
        _, expense, txn, _ = _configured(env)
        res = _handle_reconciliation_accept(env.ctx(txn.id, gl_account_id=expense.id))
        env.s.commit()
        env.s.refresh(txn)
        entry = env.s.query(JournalEntry).filter(
            JournalEntry.id == txn.journal_entry_id).one()
        assert "6400" in res["message"]
        assert entry.entry_number in res["message"]


# ── 5. the card learns it BEFORE the form (Y-4 seam) ────────────────────────


class TestBuilderSurfacesTheCodingBlock:
    """The queue builder resolves the contra leg for CODING rows too.

    Without this the card can only discover an unmapped bank account by letting
    the operator choose an account, write a note, hit Accept, and read a refusal
    — a wasted decision about a fix that is not theirs to make. The reason is
    resolved LIVE at build time, through the same context the matcher uses, so
    configuring the account and coming back shows the change (the L-2.1f
    snapshot lesson, applied to the other leg).
    """

    def test_a_coding_row_with_no_contra_carries_the_reason(self, env):
        env.mapping(name="Shop Supplies", number="6400")
        account = env.account(contra=None)
        txn, _ = env.txn(account, amount=_OUT)
        env.s.commit()

        row = next(
            r for r in _dq_reconciliation_review(env.s, env.user) if r["id"] == txn.id
        )
        assert row["coding_blocked_reason"] == "contra_gl_unset"
        # It is NOT a keyword row — the two card forms must stay distinguishable.
        assert row["keyword_classification"] is None
        assert row["candidates"] == []

    def test_a_coding_row_that_can_post_carries_no_reason(self, env):
        _, _, txn, _ = _configured(env)

        row = next(
            r for r in _dq_reconciliation_review(env.s, env.user) if r["id"] == txn.id
        )
        assert row["coding_blocked_reason"] is None

    def test_a_dangling_contra_is_distinguished_from_an_unset_one(self, env):
        """Different operator actions — re-map vs. set — so different reasons."""
        dead = env.mapping(name="Old Cash", number="1009", active=False)
        env.mapping(name="Shop Supplies", number="6400")
        account = env.account(contra=dead)
        txn, _ = env.txn(account, amount=_OUT)
        env.s.commit()

        row = next(
            r for r in _dq_reconciliation_review(env.s, env.user) if r["id"] == txn.id
        )
        assert row["coding_blocked_reason"] == "contra_gl_dangling"

    def test_a_locked_period_blocks_the_coding_form_too(self, env):
        _, _, txn, _ = _configured(env)
        PeriodLockService.lock_period(
            env.s, env.co, date(2026, 7, 1), date(2026, 7, 31), reason="closed")
        env.s.commit()

        row = next(
            r for r in _dq_reconciliation_review(env.s, env.user) if r["id"] == txn.id
        )
        assert row["coding_blocked_reason"] == "period_locked"

    def test_the_live_reason_follows_configuration_without_a_re_run(self, env):
        """THE L-2.1f LESSON ON THE OTHER LEG. Configure the bank account, come
        back, and the card must stop refusing — without re-running the matcher."""
        cash = env.mapping(name="Operating Cash", number="1010")
        env.mapping(name="Shop Supplies", number="6400")
        account = env.account(contra=None)
        txn, _ = env.txn(account, amount=_OUT)
        env.s.commit()

        blocked = next(
            r for r in _dq_reconciliation_review(env.s, env.user) if r["id"] == txn.id
        )
        assert blocked["coding_blocked_reason"] == "contra_gl_unset"

        account.gl_account_id = cash.id           # the settings change
        env.s.commit()

        after = next(
            r for r in _dq_reconciliation_review(env.s, env.user) if r["id"] == txn.id
        )
        assert after["coding_blocked_reason"] is None
