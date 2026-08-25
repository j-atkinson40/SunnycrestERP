"""LEDGER-1 A-2 — the audit pre-flight, which previously could not fail.

WHAT IT WAS. Five checks appending unconditionally to `passed`; `blocking` and
`warnings` initialised empty and never appended to anywhere in the function;
`status` therefore structurally always "passed"; committed to a durable
`AuditPreflightResult` row naming five satisfied checks. Not a guard that could
not fail — a guard that did not exist, writing down that it had run.

Cleans up its own `pf2-` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.models.company import Company
from app.services import report_intelligence_service as ri
from app.services.journal_entry_service import JournalLineSpec, create_journal_entry
from tests._cleanup import purge_companies_by_slug

_SLUG = "pf2-"
_AS_OF = date(2026, 6, 30)


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
    co = Company(id=str(uuid.uuid4()), name="PF2", slug=f"{_SLUG}{uuid.uuid4().hex[:8]}",
                 is_active=True, vertical="manufacturing")
    s.add(co); s.commit()
    yield {"s": s, "co": co.id}
    s.rollback(); s.close()


def _post_balanced(s, co, *, debit_acct="1000", credit_acct="4000", amount="500.00"):
    return create_journal_entry(
        s, tenant_id=co, entry_number=f"PF-{uuid.uuid4().hex[:6]}", entry_type="manual",
        status="posted", entry_date=_AS_OF, period_month=6, period_year=2026,
        description="probe",
        lines=[JournalLineSpec(gl_account_id=str(uuid.uuid4()), gl_account_number=debit_acct,
                               gl_account_name="D", debit_amount=Decimal(amount)),
               JournalLineSpec(gl_account_id=str(uuid.uuid4()), gl_account_number=credit_acct,
                               gl_account_name="C", credit_amount=Decimal(amount))])


def _codes(result, bucket):
    return {i["code"] for i in result[bucket]}


class TestTheEmptyLedgerBlocks:
    """The honest first output, and the reason A-2 exists."""

    def test_a_tenant_with_no_ledger_is_BLOCKED(self, env):
        r = ri.run_preflight(env["s"], env["co"], period_end=_AS_OF)
        assert r["status"] == "blocked"
        assert "trial_balance" in _codes(r, "blocking_issues")

    def test_and_the_message_says_EMPTY_not_balanced(self, env):
        """The old code said "Trial balance is balanced" here — true, because
        0 == 0, and worthless. The fact that matters is that there is nothing."""
        r = ri.run_preflight(env["s"], env["co"], period_end=_AS_OF)
        msg = next(i["message"] for i in r["blocking_issues"] if i["code"] == "trial_balance")
        assert "No posted journal entries" in msg
        assert "balanced" not in msg.lower()

    def test_the_durable_row_records_blocked(self, env):
        """The row is what an auditor reads. It must not say passed."""
        r = ri.run_preflight(env["s"], env["co"], period_end=_AS_OF)
        stored = ri.get_preflight_result(env["s"], r["id"], env["co"])
        assert stored["status"] == "blocked"
        assert stored["blocking_issues"], "the durable row must carry the reason"


class TestABalancedLedgerPasses:

    def test_posted_and_balanced_is_a_pass(self, env):
        _post_balanced(env["s"], env["co"])
        env["s"].commit()
        r = ri.run_preflight(env["s"], env["co"], period_end=_AS_OF)
        assert "trial_balance" in _codes(r, "passed_checks")
        assert r["status"] == "passed"

    def test_the_passing_message_carries_the_figures(self, env):
        """A pass that names 2 accounts and 500.00 = 500.00 can be checked by a
        human. "Trial balance is balanced" cannot."""
        _post_balanced(env["s"], env["co"], amount="500.00")
        env["s"].commit()
        r = ri.run_preflight(env["s"], env["co"], period_end=_AS_OF)
        msg = next(i["message"] for i in r["passed_checks"] if i["code"] == "trial_balance")
        assert "2 accounts" in msg
        assert "500.00" in msg


class TestAnUnbalancedLedgerBlocks:

    def test_out_of_balance_is_blocking(self, env):
        """`create_journal_entry` refuses an unbalanced entry, so this writes the
        lines directly — the pre-flight has to catch what the write path let in
        historically, not only what it would accept today."""
        e = _post_balanced(env["s"], env["co"], amount="500.00")
        env["s"].commit()
        env["s"].execute(text(
            "UPDATE journal_entry_lines SET debit_amount = 900.00 "
            "WHERE journal_entry_id = :e AND debit_amount > 0"), {"e": e.id})
        env["s"].commit()

        r = ri.run_preflight(env["s"], env["co"], period_end=_AS_OF)
        assert r["status"] == "blocked"
        issue = next(i for i in r["blocking_issues"] if i["code"] == "trial_balance")
        # debits 900.00 - credits 500.00 = 400.00
        assert "400.00" in issue["message"]
        assert issue["detail"]["difference"] == "400.00"


class TestTheDeletedChecksAreGone:
    """`reconciliation` and `w9_compliance` are ABSENT, not green.

    A deleted check is visibly missing from passed_checks. A stubbed one is
    indistinguishable from a satisfied one, which is exactly how the original
    five survived being read by people who trusted them.
    """

    @pytest.mark.parametrize("code", ["reconciliation", "w9_compliance"])
    def test_the_stub_no_longer_reports_anything(self, env, code):
        _post_balanced(env["s"], env["co"])
        env["s"].commit()
        r = ri.run_preflight(env["s"], env["co"], period_end=_AS_OF)
        everything = _codes(r, "passed_checks") | _codes(r, "warning_issues") | _codes(r, "blocking_issues")
        assert code not in everything

    def test_the_registry_is_the_only_source_of_checks(self, env):
        """No check can appear that is not registered — which is what makes the
        absence above provable rather than incidental."""
        _post_balanced(env["s"], env["co"])
        env["s"].commit()
        r = ri.run_preflight(env["s"], env["co"], period_end=_AS_OF)
        registered = {code for code, _ in ri._PREFLIGHT_CHECKS}
        everything = _codes(r, "passed_checks") | _codes(r, "warning_issues") | _codes(r, "blocking_issues")
        assert everything <= registered
        assert registered == {"trial_balance", "invoice_integrity", "ar_collectibility"}


class TestAThrowingCheckFailsClosed:
    """The defect being replaced was a safe state produced by absence. An
    exception swallowed into `passed` would reintroduce it in a form that is
    harder to see than the original comment was."""

    def test_an_exploding_check_becomes_BLOCKING_not_passed(self, env, monkeypatch):
        def boom(db, tenant_id, ps, pe):
            raise RuntimeError("database on fire")

        monkeypatch.setattr(ri, "_PREFLIGHT_CHECKS", (("trial_balance", boom),))
        r = ri.run_preflight(env["s"], env["co"], period_end=_AS_OF)
        assert r["status"] == "blocked"
        assert r["passed_count"] == 0
        issue = r["blocking_issues"][0]
        assert issue["code"] == "trial_balance"
        assert "database on fire" in issue["message"]
        assert issue["detail"]["error"] == "RuntimeError"

    def test_one_exploding_check_does_not_hide_the_others(self, env, monkeypatch):
        def boom(db, tenant_id, ps, pe):
            raise RuntimeError("boom")

        monkeypatch.setattr(ri, "_PREFLIGHT_CHECKS",
                            (("invoice_integrity", boom),
                             ("trial_balance", ri._check_trial_balance)))
        r = ri.run_preflight(env["s"], env["co"], period_end=_AS_OF)
        assert {"invoice_integrity", "trial_balance"} == _codes(r, "blocking_issues")
