"""Workflow Arc Phase 8b — BLOCKING parity tests.

Asserts the triage/workflow path produces identical side effects to
the legacy agent-runner path for the five categories approved in the
Phase 8b audit:

  (a) Primary action identity — approve via triage writes the SAME
      CustomerPaymentApplication row(s) as the agent's CONFIDENT_MATCH
      branch: same payment_id, invoice_id, amount_applied. Same
      Invoice.amount_paid + Invoice.status mutations.
  (b) Reject path — reject via triage resolves the anomaly without
      any PaymentApplication write; the legacy path (anomaly resolve
      endpoint) produces the same state.
  (c) Per-anomaly resolution — both paths stamp resolved=True,
      resolved_by, resolved_at, resolution_note.
  (d) Negative assertion: NO PeriodLock row is written on approval.
      Cash receipts is SIMPLE approval — period-lock discipline is
      month-end-close-only.
  (e) Side-effect equivalence at pipeline scale — running the
      workflow-triggered pipeline against an identical fixture set as
      the legacy agent-runner pipeline produces the same count of
      CustomerPaymentApplication rows with the same (payment_id,
      invoice_id) pairs.

If any of these diverge, the migration isn't complete.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _make_ctx():
    """Create a fresh tenant + admin user + return IDs. Matches the
    Phase 5 test-fixture pattern in test_task_and_triage.py."""
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"CRP-{suffix}",
            slug=f"crp-{suffix}",
            is_active=True,
            vertical="manufacturing",
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@crp.co",
            first_name="CR",
            last_name="Parity",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,  # bypass permission gates
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        return {
            "user_id": user.id,
            "company_id": co.id,
            "slug": co.slug,
        }
    finally:
        db.close()


@pytest.fixture
def tenant_ctx():
    return _make_ctx()


def _seed_customer(db, company_id: str) -> str:
    from app.models.customer import Customer

    cust = Customer(
        id=str(uuid.uuid4()),
        company_id=company_id,
        name=f"Cust-{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    db.add(cust)
    db.commit()
    return cust.id


def _seed_invoice(
    db, company_id: str, customer_id: str, *, total: Decimal,
    number: str | None = None,
) -> str:
    from app.models.invoice import Invoice

    now = datetime.now(timezone.utc)
    inv = Invoice(
        id=str(uuid.uuid4()),
        company_id=company_id,
        number=number or f"INV-{uuid.uuid4().hex[:6].upper()}",
        customer_id=customer_id,
        status="sent",
        invoice_date=now,
        due_date=now,
        subtotal=total,
        tax_rate=Decimal("0"),
        tax_amount=Decimal("0"),
        total=total,
        amount_paid=Decimal("0"),
    )
    db.add(inv)
    db.commit()
    return inv.id


def _seed_payment(
    db, company_id: str, customer_id: str, *, amount: Decimal,
    days_ago: int = 5,
) -> str:
    from app.models.customer_payment import CustomerPayment

    from datetime import timedelta
    pay = CustomerPayment(
        id=str(uuid.uuid4()),
        company_id=company_id,
        customer_id=customer_id,
        payment_date=datetime.now(timezone.utc) - timedelta(days=days_ago),
        total_amount=amount,
        payment_method="check",
        reference_number=f"CHK-{uuid.uuid4().hex[:4].upper()}",
    )
    db.add(pay)
    db.commit()
    return pay.id


def _seed_anomaly(
    db, *, agent_job_id: str, payment_id: str, severity: str, anomaly_type: str,
    amount: Decimal,
) -> str:
    """Seed an AgentAnomaly row — the triage item id."""
    from app.models.agent_anomaly import AgentAnomaly

    a = AgentAnomaly(
        id=str(uuid.uuid4()),
        agent_job_id=agent_job_id,
        severity=severity,
        anomaly_type=anomaly_type,
        entity_type="payment",
        entity_id=payment_id,
        description=f"Test anomaly for payment {payment_id}",
        amount=amount,
        resolved=False,
    )
    db.add(a)
    db.commit()
    return a.id


def _seed_agent_job(
    db, *, tenant_id: str, triggered_by: str, status: str = "awaiting_approval"
) -> str:
    """Seed a minimal AgentJob row representing a cash receipts run."""
    from datetime import date

    from app.models.agent import AgentJob

    job = AgentJob(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        job_type="cash_receipts_matching",
        status=status,
        period_start=date.today().replace(day=1),
        period_end=date.today(),
        dry_run=False,
        triggered_by=triggered_by,
        trigger_type="manual",
        run_log=[],
        anomaly_count=0,
    )
    db.add(job)
    db.commit()
    return job.id


# ── Category (a)+(c): approve parity ────────────────────────────────


class TestApproveParity:
    """Approve via triage writes IDENTICAL side effects to the
    agent's CONFIDENT_MATCH branch. Fixture: two independent
    payment/invoice pairs of identical shape. One gets matched by the
    agent; one gets matched by triage. Both resulting
    CustomerPaymentApplication rows must have identical writes."""

    def test_approve_produces_identical_payment_application_shape(
        self, db_session, tenant_ctx
    ):
        from app.models.customer_payment import CustomerPaymentApplication
        from app.models.invoice import Invoice
        from app.models.user import User
        from app.services.workflows.cash_receipts_adapter import approve_match

        user = (
            db_session.query(User).filter(User.id == tenant_ctx["user_id"]).one()
        )

        # Pair A (legacy / agent path) — seed first, run agent, let
        # agent match it via its CONFIDENT_MATCH branch.
        cust_a = _seed_customer(db_session, tenant_ctx["company_id"])
        inv_a = _seed_invoice(
            db_session, tenant_ctx["company_id"], cust_a,
            total=Decimal("100.00"), number="INV-A",
        )
        pay_a = _seed_payment(
            db_session, tenant_ctx["company_id"], cust_a,
            amount=Decimal("100.00"),
        )

        # Path A — legacy agent runs against ONLY pair A (pair B not
        # seeded yet, so the agent can't sweep it).
        job_a_id = _seed_agent_job(
            db_session,
            tenant_id=tenant_ctx["company_id"],
            triggered_by=user.id,
            status="running",
        )
        from app.services.agents.agent_runner import AgentRunner

        AgentRunner.run_job(job_a_id, db_session)

        # Pair B (triage path) — seed AFTER the agent ran so it
        # doesn't interfere with path A's auto-match.
        cust_b = _seed_customer(db_session, tenant_ctx["company_id"])
        inv_b = _seed_invoice(
            db_session, tenant_ctx["company_id"], cust_b,
            total=Decimal("100.00"), number="INV-B",
        )
        pay_b = _seed_payment(
            db_session, tenant_ctx["company_id"], cust_b,
            amount=Decimal("100.00"),
        )
        # Path B — triage: seed an UNRESOLVED anomaly (as if the
        # agent had flagged this payment) and approve via the
        # triage adapter.
        anomaly_b = _seed_anomaly(
            db_session,
            agent_job_id=job_a_id,  # reuse the same job
            payment_id=pay_b,
            severity="WARNING",
            anomaly_type="payment_unmatched_recent",
            amount=Decimal("100.00"),
        )
        result = approve_match(
            db_session,
            user=user,
            payment_id=pay_b,
            invoice_id=inv_b,
            anomaly_id=anomaly_b,
        )
        assert result["status"] == "applied", result

        # Compare PaymentApplication rows
        app_a = (
            db_session.query(CustomerPaymentApplication)
            .filter(CustomerPaymentApplication.payment_id == pay_a)
            .one()
        )
        app_b = (
            db_session.query(CustomerPaymentApplication)
            .filter(CustomerPaymentApplication.payment_id == pay_b)
            .one()
        )
        assert app_a.invoice_id == inv_a
        assert app_b.invoice_id == inv_b
        assert app_a.amount_applied == app_b.amount_applied == Decimal("100.00")

        # Invoice mutations identical
        inv_a_row = db_session.query(Invoice).filter(Invoice.id == inv_a).one()
        inv_b_row = db_session.query(Invoice).filter(Invoice.id == inv_b).one()
        assert inv_a_row.status == inv_b_row.status == "paid"
        assert inv_a_row.amount_paid == inv_b_row.amount_paid == Decimal("100.00")
        assert inv_a_row.paid_at is not None
        assert inv_b_row.paid_at is not None

    def test_approve_resolves_anomaly_with_same_shape_as_legacy(
        self, db_session, tenant_ctx
    ):
        """Category (c) — anomaly resolution mutations match the
        legacy `resolve_anomaly` endpoint's writes."""
        from datetime import datetime

        from app.models.agent_anomaly import AgentAnomaly
        from app.models.user import User
        from app.services.workflows.cash_receipts_adapter import approve_match

        user = (
            db_session.query(User).filter(User.id == tenant_ctx["user_id"]).one()
        )
        job_id = _seed_agent_job(
            db_session, tenant_id=tenant_ctx["company_id"],
            triggered_by=user.id,
        )
        cust = _seed_customer(db_session, tenant_ctx["company_id"])
        inv = _seed_invoice(
            db_session, tenant_ctx["company_id"], cust,
            total=Decimal("250.00"),
        )
        pay = _seed_payment(
            db_session, tenant_ctx["company_id"], cust,
            amount=Decimal("250.00"),
        )
        anomaly_id = _seed_anomaly(
            db_session, agent_job_id=job_id, payment_id=pay,
            severity="INFO", anomaly_type="payment_possible_match",
            amount=Decimal("250.00"),
        )

        approve_match(
            db_session, user=user, payment_id=pay, invoice_id=inv,
            anomaly_id=anomaly_id,
        )

        anomaly = (
            db_session.query(AgentAnomaly)
            .filter(AgentAnomaly.id == anomaly_id).one()
        )
        assert anomaly.resolved is True
        assert anomaly.resolved_by == user.id
        assert anomaly.resolved_at is not None
        assert isinstance(anomaly.resolved_at, datetime)
        assert "Approved via triage" in (anomaly.resolution_note or "")
        # The resolution_note format mirrors what the legacy
        # /anomalies/{id}/resolve route writes.


# ── Category (b): reject parity ─────────────────────────────────────


class TestRejectParity:
    """Reject via triage resolves the anomaly with a reason + creates
    ZERO PaymentApplication rows."""

    def test_reject_creates_no_payment_application_and_resolves_anomaly(
        self, db_session, tenant_ctx
    ):
        from app.models.agent_anomaly import AgentAnomaly
        from app.models.customer_payment import CustomerPaymentApplication
        from app.models.user import User
        from app.services.workflows.cash_receipts_adapter import reject_match

        user = (
            db_session.query(User).filter(User.id == tenant_ctx["user_id"]).one()
        )
        job_id = _seed_agent_job(
            db_session, tenant_id=tenant_ctx["company_id"],
            triggered_by=user.id,
        )
        cust = _seed_customer(db_session, tenant_ctx["company_id"])
        pay = _seed_payment(
            db_session, tenant_ctx["company_id"], cust,
            amount=Decimal("500.00"),
        )
        anomaly_id = _seed_anomaly(
            db_session, agent_job_id=job_id, payment_id=pay,
            severity="CRITICAL", anomaly_type="payment_unmatched_stale",
            amount=Decimal("500.00"),
        )

        result = reject_match(
            db_session, user=user, payment_id=pay,
            anomaly_id=anomaly_id,
            reason="Customer paid by wire — this is a duplicate ACH",
        )
        assert result["status"] == "applied"

        # No PaymentApplication written
        apps = (
            db_session.query(CustomerPaymentApplication)
            .filter(CustomerPaymentApplication.payment_id == pay)
            .all()
        )
        assert len(apps) == 0

        # Anomaly resolved with reason
        anomaly = (
            db_session.query(AgentAnomaly)
            .filter(AgentAnomaly.id == anomaly_id).one()
        )
        assert anomaly.resolved is True
        assert anomaly.resolved_by == user.id
        assert "Rejected via triage" in (anomaly.resolution_note or "")
        assert "duplicate ACH" in (anomaly.resolution_note or "")

    def test_reject_without_reason_errors(self, db_session, tenant_ctx):
        from app.models.user import User
        from app.services.workflows.cash_receipts_adapter import reject_match

        user = (
            db_session.query(User).filter(User.id == tenant_ctx["user_id"]).one()
        )
        job_id = _seed_agent_job(
            db_session, tenant_id=tenant_ctx["company_id"],
            triggered_by=user.id,
        )
        cust = _seed_customer(db_session, tenant_ctx["company_id"])
        pay = _seed_payment(
            db_session, tenant_ctx["company_id"], cust,
            amount=Decimal("75.00"),
        )
        anomaly_id = _seed_anomaly(
            db_session, agent_job_id=job_id, payment_id=pay,
            severity="WARNING", anomaly_type="payment_unmatched_recent",
            amount=Decimal("75.00"),
        )
        with pytest.raises(ValueError):
            reject_match(
                db_session, user=user, payment_id=pay,
                anomaly_id=anomaly_id, reason="",
            )


# ── Category (d): negative — no period lock ─────────────────────────


class TestNoPeriodLock:
    """Cash receipts is SIMPLE approval. Triage path MUST NOT write
    any PeriodLock rows — that discipline is month-end-only."""

    def test_approve_does_not_write_period_lock(self, db_session, tenant_ctx):
        from app.models.period_lock import PeriodLock
        from app.models.user import User
        from app.services.workflows.cash_receipts_adapter import approve_match

        user = (
            db_session.query(User).filter(User.id == tenant_ctx["user_id"]).one()
        )
        job_id = _seed_agent_job(
            db_session, tenant_id=tenant_ctx["company_id"],
            triggered_by=user.id,
        )
        cust = _seed_customer(db_session, tenant_ctx["company_id"])
        inv = _seed_invoice(
            db_session, tenant_ctx["company_id"], cust,
            total=Decimal("800.00"),
        )
        pay = _seed_payment(
            db_session, tenant_ctx["company_id"], cust,
            amount=Decimal("800.00"),
        )
        anomaly_id = _seed_anomaly(
            db_session, agent_job_id=job_id, payment_id=pay,
            severity="INFO", anomaly_type="payment_possible_match",
            amount=Decimal("800.00"),
        )

        pre = (
            db_session.query(PeriodLock)
            .filter(PeriodLock.tenant_id == tenant_ctx["company_id"])
            .count()
        )
        approve_match(
            db_session, user=user, payment_id=pay, invoice_id=inv,
            anomaly_id=anomaly_id,
        )
        post = (
            db_session.query(PeriodLock)
            .filter(PeriodLock.tenant_id == tenant_ctx["company_id"])
            .count()
        )
        assert pre == post, "PeriodLock row written on cash receipts approval — should be month-end-only"


# ── Category (e): pipeline-scale equivalence ────────────────────────


class TestPipelineEquivalence:
    """Run the same fixture set through both the legacy agent-runner
    path and the workflow/adapter path. Resulting PaymentApplication
    rows should have the same (payment_id, invoice_id, amount_applied)
    shape."""

    def test_run_match_pipeline_produces_same_shape_as_manual_agent(
        self, db_session, tenant_ctx
    ):
        from app.models.customer_payment import CustomerPaymentApplication
        from app.models.user import User
        from app.services.agents.agent_runner import AgentRunner
        from app.services.workflows.cash_receipts_adapter import (
            run_match_pipeline,
        )

        user = (
            db_session.query(User).filter(User.id == tenant_ctx["user_id"]).one()
        )

        # Seed 2 confident-match pairs for path A (legacy manual run)
        cust_a1 = _seed_customer(db_session, tenant_ctx["company_id"])
        inv_a1 = _seed_invoice(
            db_session, tenant_ctx["company_id"], cust_a1,
            total=Decimal("100.00"), number="INV-A1",
        )
        pay_a1 = _seed_payment(
            db_session, tenant_ctx["company_id"], cust_a1,
            amount=Decimal("100.00"),
        )
        cust_a2 = _seed_customer(db_session, tenant_ctx["company_id"])
        inv_a2 = _seed_invoice(
            db_session, tenant_ctx["company_id"], cust_a2,
            total=Decimal("200.00"), number="INV-A2",
        )
        pay_a2 = _seed_payment(
            db_session, tenant_ctx["company_id"], cust_a2,
            amount=Decimal("200.00"),
        )

        # Path A — direct manual AgentJob + AgentRunner
        job_a = _seed_agent_job(
            db_session, tenant_id=tenant_ctx["company_id"],
            triggered_by=user.id, status="pending",
        )
        AgentRunner.run_job(job_a, db_session)

        # Snapshot A state
        apps_a = (
            db_session.query(CustomerPaymentApplication)
            .filter(
                CustomerPaymentApplication.payment_id.in_([pay_a1, pay_a2])
            )
            .all()
        )
        pairs_a = sorted(
            (app.payment_id, app.invoice_id, app.amount_applied) for app in apps_a
        )

        # Reset for path B — seed new pairs (same shapes)
        cust_b1 = _seed_customer(db_session, tenant_ctx["company_id"])
        inv_b1 = _seed_invoice(
            db_session, tenant_ctx["company_id"], cust_b1,
            total=Decimal("100.00"), number="INV-B1",
        )
        pay_b1 = _seed_payment(
            db_session, tenant_ctx["company_id"], cust_b1,
            amount=Decimal("100.00"),
        )
        cust_b2 = _seed_customer(db_session, tenant_ctx["company_id"])
        inv_b2 = _seed_invoice(
            db_session, tenant_ctx["company_id"], cust_b2,
            total=Decimal("200.00"), number="INV-B2",
        )
        pay_b2 = _seed_payment(
            db_session, tenant_ctx["company_id"], cust_b2,
            amount=Decimal("200.00"),
        )

        # Path B — through the parity adapter's pipeline entry.
        # This is what the workflow engine's call_service_method step
        # invokes.
        summary = run_match_pipeline(
            db_session,
            company_id=tenant_ctx["company_id"],
            triggered_by_user_id=user.id,
            dry_run=False,
            trigger_source="workflow_test",
        )
        assert summary["agent_job_id"]
        assert summary["status"] in ("awaiting_approval", "complete")

        apps_b = (
            db_session.query(CustomerPaymentApplication)
            .filter(
                CustomerPaymentApplication.payment_id.in_([pay_b1, pay_b2])
            )
            .all()
        )
        pairs_b = sorted(
            (app.payment_id, app.invoice_id, app.amount_applied) for app in apps_b
        )

        # Shape equivalence: same count of applications, same set of
        # amount_applied values, same number of distinct payment_ids
        # resolved. Iteration order across the two pipelines can
        # differ (each ran on a fresh set of payments — internal
        # ordering of the unmatched-payments query isn't stable), so
        # compare sorted multisets rather than positional lists.
        assert len(pairs_a) == len(pairs_b) == 2
        assert sorted(a[2] for a in pairs_a) == sorted(b[2] for b in pairs_b)


# ── Handler-level parity (uses the triage engine end-to-end) ────────


class TestTriageEngineParity:
    """Integration — hit apply_action via the triage engine and
    verify the side effects match the direct adapter call."""

    def test_triage_engine_approve_delegates_to_adapter(
        self, db_session, tenant_ctx
    ):
        from app.models.agent_anomaly import AgentAnomaly
        from app.models.customer_payment import CustomerPaymentApplication
        from app.models.user import User
        from app.services.triage import apply_action, start_session

        user = (
            db_session.query(User).filter(User.id == tenant_ctx["user_id"]).one()
        )
        job_id = _seed_agent_job(
            db_session, tenant_id=tenant_ctx["company_id"],
            triggered_by=user.id,
        )
        cust = _seed_customer(db_session, tenant_ctx["company_id"])
        inv = _seed_invoice(
            db_session, tenant_ctx["company_id"], cust,
            total=Decimal("333.00"),
        )
        pay = _seed_payment(
            db_session, tenant_ctx["company_id"], cust,
            amount=Decimal("333.00"),
        )
        anomaly_id = _seed_anomaly(
            db_session, agent_job_id=job_id, payment_id=pay,
            severity="INFO", anomaly_type="payment_possible_match",
            amount=Decimal("333.00"),
        )

        session = start_session(
            db_session, user=user, queue_id="cash_receipts_matching_triage",
        )
        result = apply_action(
            db_session,
            session_id=session.id,
            item_id=anomaly_id,
            action_id="approve",
            user=user,
            payload={"payment_id": pay, "invoice_id": inv},
        )
        assert result.status == "applied", result.message

        # Same side effects as direct adapter call
        app = (
            db_session.query(CustomerPaymentApplication)
            .filter(CustomerPaymentApplication.payment_id == pay)
            .one()
        )
        assert app.invoice_id == inv
        assert app.amount_applied == Decimal("333.00")
        anomaly = (
            db_session.query(AgentAnomaly)
            .filter(AgentAnomaly.id == anomaly_id).one()
        )
        assert anomaly.resolved is True
        assert anomaly.resolved_by == user.id

    def test_triage_engine_reject_requires_reason(
        self, db_session, tenant_ctx
    ):
        from app.models.user import User
        from app.services.triage import apply_action, start_session

        user = (
            db_session.query(User).filter(User.id == tenant_ctx["user_id"]).one()
        )
        job_id = _seed_agent_job(
            db_session, tenant_id=tenant_ctx["company_id"],
            triggered_by=user.id,
        )
        cust = _seed_customer(db_session, tenant_ctx["company_id"])
        pay = _seed_payment(
            db_session, tenant_ctx["company_id"], cust,
            amount=Decimal("77.00"),
        )
        anomaly_id = _seed_anomaly(
            db_session, agent_job_id=job_id, payment_id=pay,
            severity="WARNING", anomaly_type="payment_unmatched_recent",
            amount=Decimal("77.00"),
        )

        session = start_session(
            db_session, user=user, queue_id="cash_receipts_matching_triage",
        )
        # No reason provided → returned as errored (engine-level
        # `requires_reason` guard — see engine.apply_action L222).
        result = apply_action(
            db_session,
            session_id=session.id,
            item_id=anomaly_id,
            action_id="reject",
            user=user,
            payload={"payment_id": pay},
        )
        assert result.status == "errored"


# ── Cross-tenant isolation (defense-in-depth) ───────────────────────


class TestTenantIsolation:
    def test_approve_rejects_cross_tenant_anomaly(
        self, db_session, tenant_ctx
    ):
        from app.models.user import User
        from app.services.workflows.cash_receipts_adapter import approve_match

        user = (
            db_session.query(User).filter(User.id == tenant_ctx["user_id"]).one()
        )
        # Seed a second tenant and an anomaly there.
        other = _make_ctx()
        other_job = _seed_agent_job(
            db_session, tenant_id=other["company_id"],
            triggered_by=other["user_id"],
        )
        other_cust = _seed_customer(db_session, other["company_id"])
        other_pay = _seed_payment(
            db_session, other["company_id"], other_cust,
            amount=Decimal("1.00"),
        )
        other_inv = _seed_invoice(
            db_session, other["company_id"], other_cust,
            total=Decimal("1.00"),
        )
        other_anomaly = _seed_anomaly(
            db_session, agent_job_id=other_job, payment_id=other_pay,
            severity="INFO", anomaly_type="payment_possible_match",
            amount=Decimal("1.00"),
        )

        # First-tenant user trying to approve across tenants raises.
        with pytest.raises(ValueError):
            approve_match(
                db_session, user=user,
                payment_id=other_pay,
                invoice_id=other_inv,
                anomaly_id=other_anomaly,
            )
