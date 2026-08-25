"""LEDGER-1 A-2 — the trial balance, and what it says when there is nothing.

Reads `journal_entry_lines`, which is what makes it a LEDGER report. The income
statement next to it derives its figures from invoices and vendor bills and
cannot see a manual journal entry at all; that rewire is A-3.

WHAT WAS THERE BEFORE. Nothing. `report_intelligence_service.run_preflight`
carried `# Would call getTrialBalance() — simplified for now` and then appended
`"Trial balance is balanced"` to its passed list unconditionally. That string
was TRUE — an empty trial balance balances, 0 == 0 — and worth nothing, which
is harder to notice than a falsehood.

Money math is stated as literals with the arithmetic shown, never computed
using the code under test.

Cleans up its own `tb2-` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.services import financial_report_service as frs
from app.services import journal_entry_service as jes
from app.services.journal_entry_service import JournalLineSpec
from tests._cleanup import purge_companies_by_slug

_SLUG = "tb2-"
_TODAY = date(2026, 6, 30)


@pytest.fixture(autouse=True)
def _purge():
    yield
    s = SessionLocal()
    try:
        purge_companies_by_slug(s, f"{_SLUG}%")
    finally:
        s.close()


class _Env:
    def __init__(self, s):
        self.s = s
        sfx = uuid.uuid4().hex[:8]
        self.company = Company(id=str(uuid.uuid4()), name=f"TB2 {sfx}",
                               slug=f"{_SLUG}{sfx}", is_active=True,
                               vertical="manufacturing")
        s.add(self.company); s.flush()
        self.co = self.company.id
        self._n = 0

    def entry(self, *, pairs, when=None, status="posted"):
        """`pairs` is [(account_number, account_name, debit, credit), ...]."""
        self._n += 1
        when = when or _TODAY
        return jes.create_journal_entry(
            self.s, tenant_id=self.co, entry_number=f"TB-{self._n:04d}",
            entry_type="manual", status=status, entry_date=when,
            period_month=when.month, period_year=when.year,
            description=f"probe {self._n}",
            lines=[JournalLineSpec(gl_account_id=str(uuid.uuid4()),
                                   gl_account_number=num, gl_account_name=nm,
                                   debit_amount=Decimal(d), credit_amount=Decimal(c))
                   for num, nm, d, c in pairs],
        )


@pytest.fixture
def env():
    s = SessionLocal()
    e = _Env(s)
    yield e
    s.rollback(); s.close()


def _by_number(result) -> dict:
    return {a["account_number"]: a for a in result["accounts"]}


class TestTheEmptyLedgerIsTheHonestFirstAnswer:
    """The whole reason `has_postings` is a separate field."""

    def test_a_tenant_with_no_entries_has_no_postings(self, env):
        r = frs.get_trial_balance(env.s, env.co, as_of=_TODAY)
        assert r["has_postings"] is False
        assert r["accounts"] == []
        assert r["account_count"] == 0

    def test_and_it_reports_BALANCED_because_zero_equals_zero(self, env):
        """Not a bug — arithmetic. 0 debits == 0 credits, so `balanced` is True.

        This is exactly why the pre-flight's old `"Trial balance is balanced"`
        was worthless: it was reporting this state as a passing check. A caller
        that reads `balanced` alone cannot distinguish a clean set of books from
        the absence of books, which is the distinction an auditor needs most.
        """
        r = frs.get_trial_balance(env.s, env.co, as_of=_TODAY)
        assert r["balanced"] is True
        assert r["total_debits"] == Decimal("0")
        assert r["total_credits"] == Decimal("0")
        assert r["has_postings"] is False, "balanced must not be read as evidence"


class TestArithmetic:
    """Expected values are literals with the sum shown. Never computed by frs."""

    def test_one_balanced_entry(self, env):
        env.entry(pairs=[("1000", "Cash", "1500.00", "0.00"),
                         ("4000", "Revenue", "0.00", "1500.00")])
        env.s.commit()
        r = frs.get_trial_balance(env.s, env.co, as_of=_TODAY)
        acc = _by_number(r)

        # 1000 Cash:    debits 1500.00, credits 0.00 -> balance  1500.00
        # 4000 Revenue: debits    0.00, credits 1500.00 -> balance -1500.00
        assert acc["1000"]["debits"] == Decimal("1500.00")
        assert acc["1000"]["balance"] == Decimal("1500.00")
        assert acc["4000"]["credits"] == Decimal("1500.00")
        assert acc["4000"]["balance"] == Decimal("-1500.00")

        # totals: debits 1500.00 == credits 1500.00, difference 0.00
        assert r["total_debits"] == Decimal("1500.00")
        assert r["total_credits"] == Decimal("1500.00")
        assert r["difference"] == Decimal("0.00")
        assert r["balanced"] is True
        assert r["has_postings"] is True

    def test_several_entries_accumulate_per_account(self, env):
        env.entry(pairs=[("1000", "Cash", "100.00", "0.00"),
                         ("4000", "Revenue", "0.00", "100.00")])
        env.entry(pairs=[("1000", "Cash", "250.50", "0.00"),
                         ("4000", "Revenue", "0.00", "250.50")])
        env.entry(pairs=[("1000", "Cash", "0.00", "75.25"),
                         ("6000", "Expense", "75.25", "0.00")])
        env.s.commit()
        r = frs.get_trial_balance(env.s, env.co, as_of=_TODAY)
        acc = _by_number(r)

        # 1000 Cash: debits 100.00 + 250.50 = 350.50; credits 75.25
        #            balance 350.50 - 75.25 = 275.25
        assert acc["1000"]["debits"] == Decimal("350.50")
        assert acc["1000"]["credits"] == Decimal("75.25")
        assert acc["1000"]["balance"] == Decimal("275.25")
        # 4000 Revenue: credits 100.00 + 250.50 = 350.50
        assert acc["4000"]["credits"] == Decimal("350.50")
        # 6000 Expense: debits 75.25
        assert acc["6000"]["debits"] == Decimal("75.25")

        # totals: debits 350.50 + 75.25 = 425.75; credits 75.25 + 350.50 = 425.75
        assert r["total_debits"] == Decimal("425.75")
        assert r["total_credits"] == Decimal("425.75")
        assert r["difference"] == Decimal("0.00")

    def test_the_amounts_are_Decimal_not_float(self, env):
        env.entry(pairs=[("1000", "Cash", "0.10", "0.00"),
                         ("4000", "Revenue", "0.00", "0.10")])
        env.entry(pairs=[("1000", "Cash", "0.20", "0.00"),
                         ("4000", "Revenue", "0.00", "0.20")])
        env.s.commit()
        r = frs.get_trial_balance(env.s, env.co, as_of=_TODAY)
        # 0.10 + 0.20 == 0.30 exactly. In binary float it is 0.30000000000000004.
        assert _by_number(r)["1000"]["debits"] == Decimal("0.30")
        assert isinstance(r["total_debits"], Decimal)


class TestTheReversalTrap:
    """The reason `_LEDGER_STATUSES` is ("posted", "reversed") and not "posted".

    `reverse_journal_entry` creates a NEW entry with status="posted" holding the
    mirrored lines, then sets the ORIGINAL to "reversed". The original's lines
    are still in the table.

    A `status == "posted"` filter — the codebase's most common idiom, used in
    proactive_agents, estimated_tax_prep_agent and elsewhere — therefore keeps
    the reversal and drops what it reverses. Every account in the pair reports
    the NEGATION of a figure that should be zero.

    And the totals still balance, because the reversing entry is internally
    balanced. So the single check a trial balance exists to perform passes while
    every line in it is wrong. That is why this is tested rather than trusted.
    """

    def test_a_reversed_pair_nets_to_zero(self, env):
        e = env.entry(pairs=[("1000", "Cash", "800.00", "0.00"),
                             ("4000", "Revenue", "0.00", "800.00")])
        env.s.commit()
        jes.reverse_journal_entry(env.s, tenant_id=env.co, entry_id=e.id,
                                  actor_user_id=None)
        env.s.commit()

        r = frs.get_trial_balance(env.s, env.co, as_of=date.today())
        acc = _by_number(r)
        # 1000 Cash:    original debit 800.00, reversal credit 800.00
        #               -> balance 800.00 - 800.00 = 0.00
        # 4000 Revenue: original credit 800.00, reversal debit 800.00
        #               -> balance 800.00 - 800.00 = 0.00
        assert acc["1000"]["balance"] == Decimal("0.00")
        assert acc["4000"]["balance"] == Decimal("0.00")
        assert acc["1000"]["debits"] == Decimal("800.00")
        assert acc["1000"]["credits"] == Decimal("800.00")

    def test_the_reversed_original_is_still_counted(self, env):
        """Stated separately from the netting test, because a filter that
        dropped BOTH sides would also produce a zero balance — and would be
        just as wrong, in the other direction."""
        e = env.entry(pairs=[("1000", "Cash", "800.00", "0.00"),
                             ("4000", "Revenue", "0.00", "800.00")])
        env.s.commit()
        jes.reverse_journal_entry(env.s, tenant_id=env.co, entry_id=e.id,
                                  actor_user_id=None)
        env.s.commit()

        r = frs.get_trial_balance(env.s, env.co, as_of=date.today())
        # 2 lines from the original + 2 from the reversal = 4, on 2 accounts
        assert sum(a["line_count"] for a in r["accounts"]) == 4
        assert r["has_postings"] is True
        # totals: debits 800.00 + 800.00 = 1600.00, credits likewise
        assert r["total_debits"] == Decimal("1600.00")
        assert r["total_credits"] == Decimal("1600.00")


class TestWhatIsExcluded:

    def test_drafts_do_not_reach_the_ledger(self, env):
        env.entry(pairs=[("1000", "Cash", "500.00", "0.00"),
                         ("4000", "Revenue", "0.00", "500.00")], status="draft")
        env.s.commit()
        r = frs.get_trial_balance(env.s, env.co, as_of=_TODAY)
        assert r["has_postings"] is False
        assert r["total_debits"] == Decimal("0")

    def test_excluded_rows_are_REPORTED_not_silently_dropped(self, env):
        """A trial balance that quietly omits rows is worse than one that
        refuses — the omission is invisible precisely when it matters."""
        env.entry(pairs=[("1000", "Cash", "500.00", "0.00"),
                         ("4000", "Revenue", "0.00", "500.00")], status="draft")
        env.s.commit()
        r = frs.get_trial_balance(env.s, env.co, as_of=_TODAY)
        assert r["excluded_statuses"] == {"draft": 2}

    def test_entries_after_as_of_are_excluded(self, env):
        env.entry(pairs=[("1000", "Cash", "10.00", "0.00"),
                         ("4000", "Revenue", "0.00", "10.00")], when=_TODAY)
        env.entry(pairs=[("1000", "Cash", "99.00", "0.00"),
                         ("4000", "Revenue", "0.00", "99.00")],
                  when=_TODAY + timedelta(days=1))
        env.s.commit()
        r = frs.get_trial_balance(env.s, env.co, as_of=_TODAY)
        # only the 10.00 entry is on or before as_of
        assert r["total_debits"] == Decimal("10.00")

    def test_another_tenants_ledger_is_not_visible(self, env):
        other = Company(id=str(uuid.uuid4()), name="TB2 other",
                        slug=f"{_SLUG}other-{uuid.uuid4().hex[:8]}",
                        is_active=True, vertical="manufacturing")
        env.s.add(other); env.s.flush()
        jes.create_journal_entry(
            env.s, tenant_id=other.id, entry_number="TB-OTHER", entry_type="manual",
            status="posted", entry_date=_TODAY, period_month=6, period_year=2026,
            description="theirs",
            lines=[JournalLineSpec(gl_account_id=str(uuid.uuid4()),
                                   gl_account_number="1000", gl_account_name="Cash",
                                   debit_amount=Decimal("4242.00")),
                   JournalLineSpec(gl_account_id=str(uuid.uuid4()),
                                   gl_account_number="4000", gl_account_name="Revenue",
                                   credit_amount=Decimal("4242.00"))])
        env.s.commit()
        r = frs.get_trial_balance(env.s, env.co, as_of=_TODAY)
        assert r["has_postings"] is False
        assert r["total_debits"] == Decimal("0")
