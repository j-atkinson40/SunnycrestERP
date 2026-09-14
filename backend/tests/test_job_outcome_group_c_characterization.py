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


def test_CHAR_not_applicable_returns_None(db_session):
    """Tenant is not in end_of_day mode. The job does not apply to it at all."""
    from app.services.draft_invoice_service import generate_draft_invoices

    _settings(db_session, mode="immediate")
    assert generate_draft_invoices(db_session, TENANT) is None


def test_CHAR_no_work_returns_None(db_session):
    """In end_of_day mode with nothing uninvoiced."""
    from app.services.draft_invoice_service import generate_draft_invoices

    _settings(db_session, mode="end_of_day")
    assert generate_draft_invoices(db_session, TENANT) is None


def test_CHAR_success_returns_None(db_session):
    """One eligible order, invoice created. Work HAPPENED."""
    from app.models.invoice import Invoice
    from app.services.draft_invoice_service import generate_draft_invoices

    _settings(db_session, mode="end_of_day")
    order = _order(db_session)

    assert generate_draft_invoices(db_session, TENANT) is None

    # Control that work actually happened — without this the test below
    # proves nothing, because "no invoice created" is also what a broken
    # fixture produces.
    made = (db_session.query(Invoice)
            .filter(Invoice.company_id == TENANT,
                    Invoice.sales_order_id == order.id).count())
    assert made == 1, "fixture did not produce an invoice; the collapse test below would be vacuous"


def test_CHAR_EVERY_ITEM_FAILED_also_returns_None(db_session, monkeypatch):
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

    assert result is None  # ← the wrongness, asserted


# ═══════════════════════════════════════════════════════════════════════════
# 2. run_reorder_suggestion_job — SEVEN RETURNS, ALL `suggestions: 0`
# ═══════════════════════════════════════════════════════════════════════════


def test_CHAR_reorder_collapses_distinct_outcomes_onto_one_number(db_session):
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

    zeros = [r for r in returns if "'suggestions': 0" in r]
    assert len(zeros) == 7, f"expected 7 zero-returns, found {len(zeros)}: {zeros}"

    # They are NOT the same outcome. Present in the set, all wearing the zero:
    joined = " | ".join(zeros)
    assert "'mode': 'produce'" in joined      # not applicable to this tenant
    assert "'status': 'stock_ok'" in joined   # no work needed
    assert "'status': 'po_exists'" in joined  # no work needed, different reason
    assert "'error': 'no_supplier'" in joined # a data defect
    assert "'error': str(e)" in joined        # an abort

    # Only ONE return reports work done.
    assert len([r for r in returns if "'suggestions': 1" in r]) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 3. run_uncleared_check_monitor — per-item failures logged, never counted
# ═══════════════════════════════════════════════════════════════════════════


def test_CHAR_uncleared_check_swallows_per_item_failures_uncounted(db_session, monkeypatch):
    """⚠️ WRONGNESS. The per-item handler logs and drops. A run whose every
    item failed returns the same empty result as a run with no items."""
    import ast, inspect
    from app.services import proactive_agents

    src = inspect.getsource(proactive_agents.run_uncleared_check_monitor)
    fn = ast.parse(src).body[0]
    handlers = [h for h in ast.walk(fn) if isinstance(h, ast.ExceptHandler)]
    assert handlers, "expected at least one except handler"
    for h in handlers:
        bodies = [ast.unparse(s) for s in h.body]
        # Logs. Does not count, does not re-raise.
        assert any("logger." in b for b in bodies), bodies
        assert not any("+=" in b for b in bodies), f"already counts: {bodies}"
        assert not any(b.startswith("raise") for b in bodies), bodies

    # And the clean path returns a bare container with no failure channel.
    out = proactive_agents.run_uncleared_check_monitor(db_session, TENANT)
    assert not hasattr(out, "failed"), "already migrated — this characterization is stale"
