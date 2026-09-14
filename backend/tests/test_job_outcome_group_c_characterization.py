"""(c) commit 2c — CHARACTERIZATION FIRST, for the three targets whose count
must be AUTHORED rather than forwarded.

⚠️ WRITTEN AND GREEN BEFORE ANY COUNT EXISTS. Commit 2b is the argument for
this order: three of its seven targets got new failure-branch code, and a break
test proved NOTHING covered it -- the counts were authored into a vacuum and
only luck would have caught a wrong one. Group C is that situation by
definition, so the coverage goes first.

These tests pin CURRENT behaviour, including the behaviour that is wrong. Every
`# WRONGNESS` marker below is a defect this file DELIBERATELY asserts, so that
the migration commit can be read as a diff against a known state rather than
against nobody's idea of what these functions did.

The wrongness is the same shape in all three: A RUN THAT DID NOTHING AND A RUN
WHOSE EVERY ITEM FAILED RETURN THE SAME VALUE.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

canonical_tenant = make_canonical_tenant_fixture()
TENANT = TESTCO_ID


@pytest.fixture
def db_session():
    from app.database import SessionLocal
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def _isolate(db_session):
    def purge():
        db_session.execute(text(
            "DELETE FROM invoices WHERE company_id=:t AND number LIKE 'GRPC-%'"), {"t": TENANT})
        db_session.execute(text(
            "DELETE FROM invoices WHERE company_id=:t AND sales_order_id IN "
            "(SELECT id FROM sales_orders WHERE company_id=:t AND number LIKE 'GRPC-%')"), {"t": TENANT})
        db_session.execute(text(
            "DELETE FROM sales_order_lines WHERE sales_order_id IN "
            "(SELECT id FROM sales_orders WHERE company_id=:t AND number LIKE 'GRPC-%')"), {"t": TENANT})
        db_session.execute(text(
            "DELETE FROM sales_orders WHERE company_id=:t AND number LIKE 'GRPC-%'"), {"t": TENANT})
        db_session.execute(text(
            "DELETE FROM agent_alerts WHERE tenant_id=:t AND alert_type IN "
            "('draft_invoices_ready','unconfirmed_services')"), {"t": TENANT})
        db_session.execute(text(
            "DELETE FROM delivery_settings WHERE company_id=:t"), {"t": TENANT})
        db_session.execute(text(
            "DELETE FROM customers WHERE company_id=:t AND name='Group C Fixture'"), {"t": TENANT})
        db_session.execute(text(
            "DELETE FROM reconciliation_adjustments WHERE tenant_id=:t AND description LIKE 'GRPC %'"), {"t": TENANT})
        db_session.execute(text(
            "DELETE FROM reconciliation_runs WHERE tenant_id=:t AND financial_account_id IN "
            "(SELECT id FROM financial_accounts WHERE tenant_id=:t AND account_name='Group C Account')"), {"t": TENANT})
        db_session.execute(text(
            "DELETE FROM financial_accounts WHERE tenant_id=:t AND account_name='Group C Account'"), {"t": TENANT})
        db_session.commit()
    purge(); yield; purge()


def _settings(db, *, mode: str, require_driver: bool = False):
    from app.services.delivery_settings_service import get_settings
    s = get_settings(db, TENANT)
    s.invoice_generation_mode = mode
    s.require_driver_status_updates = require_driver
    db.commit()
    return s


def _customer(db) -> str:
    from app.models.customer import Customer
    c = Customer(id=str(uuid.uuid4()), company_id=TENANT, name="Group C Fixture",
                 account_number=f"GC-{uuid.uuid4().hex[:6]}", is_active=True)
    db.add(c); db.commit(); return c.id


def _order(db, *, status: str = "delivered"):
    from app.models.sales_order import SalesOrder
    o = SalesOrder(
        id=str(uuid.uuid4()), company_id=TENANT, customer_id=_customer(db),
        number=f"GRPC-{uuid.uuid4().hex[:6]}", status=status,
        order_date=date.today(), scheduled_date=date.today(),
        order_type="funeral",
        subtotal=Decimal("200.00"), tax_amount=Decimal("0.00"), total=Decimal("200.00"),
    )
    db.add(o); db.commit(); return o


# ═══════════════════════════════════════════════════════════════════════════
# 1. generate_draft_invoices — FOUR DISTINCT OUTCOMES, ONE RETURN VALUE
# ═══════════════════════════════════════════════════════════════════════════


def test_not_applicable_is_NO_WORK_with_a_reason(db_session):
    """Tenant is not in end_of_day mode. The job does not apply to it at all."""
    from app.services.draft_invoice_service import generate_draft_invoices

    _settings(db_session, mode="immediate")
    out = generate_draft_invoices(db_session, TENANT)
    # SUPERSEDED by (c) 2c step 2. Was: `assert ... is None`
    assert out.state == "no_work"
    assert out.detail["skipped"] == "mode_not_end_of_day"


def test_no_work_is_NO_WORK_without_a_skip_reason(db_session):
    """In end_of_day mode with nothing uninvoiced."""
    from app.services.draft_invoice_service import generate_draft_invoices

    _settings(db_session, mode="end_of_day")
    out = generate_draft_invoices(db_session, TENANT)
    # SUPERSEDED by (c) 2c step 2. Was: `assert ... is None`
    # Same STATE as not-applicable above, and that is correct -- both did no
    # work. The detail is what separates them, and it now exists.
    assert out.state == "no_work"
    assert "skipped" not in out.detail
    assert out.detail["uninvoiced"] == 0


def test_success_is_OK(db_session):
    """One eligible order, invoice created. Work HAPPENED."""
    from app.models.invoice import Invoice
    from app.services.draft_invoice_service import generate_draft_invoices

    _settings(db_session, mode="end_of_day")
    order = _order(db_session)

    out = generate_draft_invoices(db_session, TENANT)
    # SUPERSEDED by (c) 2c step 2. Was: `assert ... is None`
    assert out.state == "ok"
    assert out.succeeded == 1
    assert out.failed == 0

    # Control that work actually happened — without this the test below
    # proves nothing, because "no invoice created" is also what a broken
    # fixture produces.
    made = (db_session.query(Invoice)
            .filter(Invoice.company_id == TENANT,
                    Invoice.sales_order_id == order.id).count())
    assert made == 1, "fixture did not produce an invoice; the collapse test below would be vacuous"


def test_EVERY_ITEM_FAILED_is_COMPLETED_WITH_ERRORS(db_session, monkeypatch):
    """⚠️ WRONGNESS. Two eligible orders, EVERY invoice creation raises.

    Returns None — byte-identical to the not-applicable case, the no-work case,
    and the total-success case above. Four different things the operator would
    want to tell apart, and the function says the same word for all of them.

    Nothing is written to job_runs that distinguishes them either: the wrapper
    has no counts to record because the target reports none.
    """
    from app.services import sales_service
    from app.services.draft_invoice_service import generate_draft_invoices
    from app.models.invoice import Invoice

    _settings(db_session, mode="end_of_day")
    o1, o2 = _order(db_session), _order(db_session)

    attempts = {"n": 0}

    def exploding(*a, **k):
        attempts["n"] += 1
        raise RuntimeError("injected invoice-creation failure")

    monkeypatch.setattr(sales_service, "create_invoice_from_order", exploding)

    result = generate_draft_invoices(db_session, TENANT)

    # Control that the break APPLIED — a marker count, not a green.
    assert attempts["n"] == 2, f"expected both orders attempted, got {attempts['n']}"
    # And nothing was created, so this really is the total-failure case.
    assert (db_session.query(Invoice)
            .filter(Invoice.company_id == TENANT,
                    Invoice.sales_order_id.in_([o1.id, o2.id])).count()) == 0

    # SUPERSEDED by (c) 2c step 2. Was: `assert result is None  # the wrongness`
    #
    # ⚠️ THIS IS THE WHOLE OF (c) IN ONE ASSERTION. The three tests above and
    # this one exercise four different things that were ALL `None`. They are
    # now no_work/skipped, no_work/uninvoiced, ok, and completed_with_errors.
    assert result.state == "completed_with_errors"
    assert result.failed == 2
    assert result.succeeded == 0


# ═══════════════════════════════════════════════════════════════════════════
# 2. run_reorder_suggestion_job — SEVEN RETURNS, ALL `suggestions: 0`
# ═══════════════════════════════════════════════════════════════════════════


def test_reorder_SEVEN_ZEROS_became_three_aborts_and_four_no_works(db_session):
    """⚠️ WRONGNESS, READ OFF THE SOURCE RATHER THAN EXERCISED.

    Each of these branches needs a different inventory fixture to reach, and
    the point is not any one of them — it is that they all report the same
    number. Asserting the SET of zero-returns from the AST is a stronger claim
    than reaching two of them and generalising, and it cannot silently stop
    covering a branch that gets added later.
    """
    import ast, inspect
    from app.services import proactive_agents

    src = inspect.getsource(proactive_agents.run_reorder_suggestion_job)
    fn = ast.parse(src).body[0]
    returns = [ast.unparse(n.value) for n in ast.walk(fn)
               if isinstance(n, ast.Return) and n.value is not None]

    # SUPERSEDED by (c) 2c step 2. This previously asserted SEVEN returns all
    # carrying `'suggestions': 0`, and that the set contained `mode: produce`,
    # `status: stock_ok`, `status: po_exists`, `error: no_supplier` and
    # `error: str(e)` -- five different facts wearing one number.
    #
    # The seven are now three aborts and four no-works. The count is held so
    # that COLLAPSING THEM BACK goes red: anyone who returns a bare zero from a
    # new branch, or merges two of these, breaks this test.
    assert not [r for r in returns if "'suggestions': 0" in r], \
        f"a bare zero-return is back: {[r for r in returns if chr(39)+'suggestions'+chr(39)+': 0' in r]}"

    aborts = [r for r in returns if "JobOutcome.aborted" in r]
    no_work = [r for r in returns if "JobOutcome.nothing_to_do" in r]
    worked = [r for r in returns if "JobOutcome.worked" in r]

    assert len(aborts) == 3, f"expected 3 aborts, got {aborts}"
    assert len(no_work) == 4, f"expected 4 no-works, got {no_work}"
    assert len(worked) == 1, f"expected 1 worked, got {worked}"
    assert len(aborts) + len(no_work) == 7, "the seven zeros must still be seven returns"

    # And they are still DISTINGUISHABLE -- each carries its own detail.
    joined = " | ".join(aborts + no_work)
    assert "mode_produce" in joined
    assert "stock_ok" in joined
    assert "po_exists" in joined
    assert "no vault supplier configured" in joined


# ═══════════════════════════════════════════════════════════════════════════
# 3. run_uncleared_check_monitor — per-item failures logged, never counted
# ═══════════════════════════════════════════════════════════════════════════


def test_uncleared_check_COUNTS_its_insight_failures(db_session, monkeypatch):
    """⚠️ WRONGNESS. The per-item handler logs and drops. A run whose every
    item failed returns the same empty result as a run with no items."""
    import ast, inspect
    from app.services import proactive_agents

    src = inspect.getsource(proactive_agents.run_uncleared_check_monitor)
    fn = ast.parse(src).body[0]
    handlers = [h for h in ast.walk(fn) if isinstance(h, ast.ExceptHandler)]
    assert handlers, "expected at least one except handler"
    # SUPERSEDED by (c) 2c step 2. This previously asserted the handler LOGS
    # AND DOES NOT COUNT, and carried a staleness guard (`not hasattr(out,
    # "failed")`) so it would go red rather than quietly vacuous once migrated.
    # The guard fired, which is the only reason this block is being rewritten
    # rather than silently passing against a function it no longer describes.
    for h in handlers:
        bodies = [ast.unparse(s) for s in h.body]
        assert any("logger." in b for b in bodies), bodies
        assert any("insight_failures" in b for b in bodies), \
            f"the handler stopped counting: {bodies}"

    out = proactive_agents.run_uncleared_check_monitor(db_session, TENANT)
    assert hasattr(out, "failed"), "regressed to a shape with no failure channel"
    # ⚠️ `succeeded` is INSIGHTS WRITTEN, not checks FLAGGED. With no stale
    # checks this is no_work; the distinction that matters is that a run which
    # found checks and failed to surface them is no longer identical to one
    # that surfaced them all.
    assert out.state in ("no_work", "ok", "completed_with_errors")
    assert out.failed == 0


def _stale_check(db, *, days_old: int = 60):
    """An outstanding-check adjustment older than the 45-day cutoff."""
    from app.models.financial_account import (
        FinancialAccount, ReconciliationAdjustment, ReconciliationRun,
    )
    acct = FinancialAccount(
        id=str(uuid.uuid4()), tenant_id=TENANT, account_type="bank",
        account_name="Group C Account", is_active=True, is_primary=False, sort_order=99,
    )
    db.add(acct); db.commit()
    run = ReconciliationRun(
        id=str(uuid.uuid4()), tenant_id=TENANT, financial_account_id=acct.id,
        status="completed", statement_date=date.today() - timedelta(days=days_old),
        statement_closing_balance=Decimal("0.00"), total_statement_transactions=0,
        auto_cleared_count=0, suggested_count=0, unmatched_count=0,
        outstanding_checks_total=Decimal("0.00"), outstanding_deposits_total=Decimal("0.00"),
        adjustments_total=Decimal("0.00"), difference=Decimal("0.00"),
    )
    db.add(run); db.commit()
    adj = ReconciliationAdjustment(
        id=str(uuid.uuid4()), tenant_id=TENANT, reconciliation_run_id=run.id,
        adjustment_type="outstanding_check", description="GRPC stale check",
        amount=Decimal("125.00"),
        created_at=datetime.now(timezone.utc) - timedelta(days=days_old),
    )
    db.add(adj); db.commit()
    return adj


def test_uncleared_check_a_FAILED_INSIGHT_is_not_a_clean_run(db_session, monkeypatch):
    """⚠️ THIS TEST EXISTS BECAUSE A BREAK TEST CAUGHT ITS ABSENCE.

    2c was written coverage-first specifically to avoid 2b's miss, and STILL
    left this count untested: the coverage written first was STRUCTURAL (an AST
    assertion on the handler) plus a no-work path. Neither runs the failure
    branch. Break I silenced `insight_failures` and twenty tests stayed green.

    Writing coverage first is not the same as covering the thing you are about
    to author. The break test is what tells them apart.
    """
    from app.services import behavioral_analytics_service, proactive_agents

    _stale_check(db_session)

    calls = {"n": 0}

    def exploding(*a, **k):
        calls["n"] += 1
        raise RuntimeError("injected insight-write failure")

    monkeypatch.setattr(behavioral_analytics_service, "generate_insight", exploding)

    out = proactive_agents.run_uncleared_check_monitor(db_session, TENANT)

    # Control that the break APPLIED.
    assert calls["n"] == 1, f"generate_insight was never reached: {calls['n']}"

    assert out.detail["flagged"] >= 1, "the query found nothing; this test is vacuous"
    assert out.failed == 1
    assert out.succeeded == 0
    assert out.state == "completed_with_errors"


def test_uncleared_check_a_WRITTEN_INSIGHT_is_ok(db_session):
    """The control, so the test above is read against a working path rather
    than against itself. Same fixture, no injection."""
    from app.services import proactive_agents

    _stale_check(db_session)

    out = proactive_agents.run_uncleared_check_monitor(db_session, TENANT)

    assert out.detail["flagged"] >= 1
    assert out.failed == 0
    assert out.succeeded == 1
    assert out.state == "ok"
