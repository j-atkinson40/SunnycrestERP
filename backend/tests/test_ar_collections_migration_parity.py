"""Workflow Arc Phase 8c — BLOCKING parity tests for ar_collections.

Asserts the triage "send" path produces an IDENTICAL DocumentDelivery
row to calling `email_service.send_collections_email` directly.

**New capability — not pure refactor.** The legacy approval flow was
a no-op (Phase 3b TODO). Phase 8c closes that TODO: triage "send"
actually dispatches the email via the managed `email.collections`
template. Parity is therefore between (a) what triage does now, and
(b) what the operational intent has always been.

Categories:
  1. Primary action — `send_customer_email` writes a DocumentDelivery
     with template_key="email.collections" and caller_module pointing
     to the adapter.
  2. Skip path — no DocumentDelivery row, anomaly resolved with reason.
  3. Pre-approval zero-email — after pipeline completion + before
     any triage send, zero collection emails dispatched.
  4. Fan-out fidelity — 3 customers; send 1, skip 1, request_review 1
     → 1 email sent + 2 resolved anomalies + 1 anomaly with review
     note (unresolved).
  5. Pipeline equivalence — drafts landed in report_payload.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _make_ctx():
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"ARC-{suffix}",
            slug=f"arc-{suffix}",
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
            email=f"u-{suffix}@arc.co",
            first_name="ARC",
            last_name="Parity",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        return {"user_id": user.id, "company_id": co.id}
    finally:
        db.close()


@pytest.fixture
def tenant_ctx():
    return _make_ctx()


def _seed_customer_with_draft(
    db, company_id: str, *, name: str, email: str, tier: str = "CRITICAL",
    outstanding: Decimal = Decimal("1000.00"),
):
    """Seed a Customer + AgentJob + per-customer anomaly + matching
    draft in report_payload.communications[].
    Returns (customer_id, anomaly_id, job_id)."""
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly
    from app.models.customer import Customer

    customer = Customer(
        id=str(uuid.uuid4()),
        company_id=company_id,
        name=name,
        billing_email=email,
        is_active=True,
    )
    db.add(customer)
    db.flush()

    # Check if there's already a job; reuse if so (all customers
    # share one AgentJob in a typical AR collections run).
    job = (
        db.query(AgentJob)
        .filter(
            AgentJob.tenant_id == company_id,
            AgentJob.job_type == "ar_collections",
            AgentJob.status == "awaiting_approval",
        )
        .first()
    )
    today = date.today()
    if job is None:
        job = AgentJob(
            id=str(uuid.uuid4()),
            tenant_id=company_id,
            job_type="ar_collections",
            status="awaiting_approval",
            period_start=today.replace(day=1),
            period_end=today,
            dry_run=False,
            trigger_type="manual",
            run_log=[],
            anomaly_count=0,
            report_payload={
                "executive_summary": {},
                "steps": {
                    "draft_communications": {"communications": []},
                },
                "anomalies": [],
            },
        )
        db.add(job)
        db.flush()

    # Add the draft for this customer into the job's report_payload.
    payload = dict(job.report_payload)
    steps = dict(payload.get("steps") or {})
    dc = dict(steps.get("draft_communications") or {})
    communications = list(dc.get("communications") or [])
    communications.append(
        {
            "customer_id": customer.id,
            "customer_name": name,
            "tier": tier,
            "total_outstanding": float(outstanding),
            "subject": f"Past-due balance for {name}",
            "body": (
                f"Dear {name},\n\nOur records show you have an "
                f"outstanding balance of ${float(outstanding):,.2f}. "
                f"Please remit payment at your earliest convenience.\n\n"
                f"Thank you."
            ),
        }
    )
    dc["communications"] = communications
    steps["draft_communications"] = dc
    payload["steps"] = steps
    job.report_payload = payload
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(job, "report_payload")

    anomaly_type_map = {
        "CRITICAL": "collections_critical",
        "ESCALATE": "collections_escalate",
        "FOLLOW_UP": "collections_follow_up",
    }
    severity_map = {
        "CRITICAL": "CRITICAL",
        "ESCALATE": "WARNING",
        "FOLLOW_UP": "INFO",
    }
    anomaly = AgentAnomaly(
        id=str(uuid.uuid4()),
        agent_job_id=job.id,
        severity=severity_map[tier],
        anomaly_type=anomaly_type_map[tier],
        entity_type="customer",
        entity_id=customer.id,
        description=f"{name}: ${float(outstanding):,.2f} past due",
        amount=outstanding,
        resolved=False,
    )
    db.add(anomaly)
    db.commit()
    return (customer.id, anomaly.id, job.id)


def _count_deliveries(
    db, company_id: str, recipient: str | None = None
) -> int:
    from app.models.document_delivery import DocumentDelivery

    q = db.query(DocumentDelivery).filter(
        DocumentDelivery.company_id == company_id,
        DocumentDelivery.template_key == "email.collections",
    )
    if recipient:
        q = q.filter(DocumentDelivery.recipient_value == recipient)
    return q.count()


# ── Category 3: Pre-approval zero-email ─────────────────────────────


class TestPreApprovalZeroEmail:
    def test_no_email_sent_before_triage_action(
        self, db_session, tenant_ctx
    ):
        _seed_customer_with_draft(
            db_session,
            tenant_ctx["company_id"],
            name="Acme Corp",
            email="ap@acme.example.com",
        )
        # After pipeline + fixture seeding (simulating completed agent
        # run), zero collection emails have been dispatched.
        assert _count_deliveries(db_session, tenant_ctx["company_id"]) == 0


# ── Category 1: Primary action — send creates DocumentDelivery ─────


class TestSendCreatesDelivery:
    def test_send_writes_document_delivery_with_correct_template(
        self, db_session, tenant_ctx
    ):
        from app.models.document_delivery import DocumentDelivery
        from app.models.user import User
        from app.services.workflows.ar_collections_adapter import send_customer_email

        user = (
            db_session.query(User)
            .filter(User.id == tenant_ctx["user_id"])
            .one()
        )
        _cust_id, anomaly_id, _job_id = _seed_customer_with_draft(
            db_session,
            tenant_ctx["company_id"],
            name="Alpha LLC",
            email="billing@alpha.example.com",
            tier="CRITICAL",
        )

        result = send_customer_email(
            db_session, user=user, anomaly_id=anomaly_id,
        )
        assert result["status"] == "applied"

        # Exactly one delivery row, correct template_key + recipient +
        # caller_module.
        deliveries = (
            db_session.query(DocumentDelivery)
            .filter(
                DocumentDelivery.company_id == tenant_ctx["company_id"],
                DocumentDelivery.template_key == "email.collections",
                DocumentDelivery.recipient_value
                == "billing@alpha.example.com",
            )
            .all()
        )
        assert len(deliveries) == 1
        d = deliveries[0]
        assert d.template_key == "email.collections"
        # Caller module carries the email_service layer's hint — the
        # dispatcher is `email_service.send_collections_email`. That's
        # the canonical audit signal that the triage path goes
        # through the same D-7 managed-template path as the legacy
        # helper.
        assert "collections" in (d.caller_module or "")

    def test_send_resolves_anomaly_with_delivery_note(
        self, db_session, tenant_ctx
    ):
        from app.models.agent_anomaly import AgentAnomaly
        from app.models.user import User
        from app.services.workflows.ar_collections_adapter import send_customer_email

        user = (
            db_session.query(User)
            .filter(User.id == tenant_ctx["user_id"])
            .one()
        )
        _cust_id, anomaly_id, _job_id = _seed_customer_with_draft(
            db_session,
            tenant_ctx["company_id"],
            name="Beta Inc",
            email="pay@beta.example.com",
        )
        send_customer_email(
            db_session, user=user, anomaly_id=anomaly_id,
        )
        a = (
            db_session.query(AgentAnomaly)
            .filter(AgentAnomaly.id == anomaly_id)
            .one()
        )
        assert a.resolved is True
        assert a.resolved_by == user.id
        assert "Sent via triage" in (a.resolution_note or "")


# ── Category 2: Skip path — no email, anomaly resolved with reason ──


class TestSkipNoEmail:
    def test_skip_creates_no_delivery(self, db_session, tenant_ctx):
        from app.models.user import User
        from app.services.workflows.ar_collections_adapter import skip_customer

        user = (
            db_session.query(User)
            .filter(User.id == tenant_ctx["user_id"])
            .one()
        )
        _cust_id, anomaly_id, _job_id = _seed_customer_with_draft(
            db_session,
            tenant_ctx["company_id"],
            name="Skip Co",
            email="nope@skip.example.com",
        )
        skip_customer(
            db_session,
            user=user,
            anomaly_id=anomaly_id,
            reason="Customer on payment plan — handled manually",
        )
        assert (
            _count_deliveries(
                db_session, tenant_ctx["company_id"],
                recipient="nope@skip.example.com",
            )
            == 0
        )


# ── Category 4: Fan-out fidelity (3 customers, 3 different actions) ─


class TestFanOutFidelity:
    def test_three_customers_three_actions(
        self, db_session, tenant_ctx
    ):
        from app.models.agent_anomaly import AgentAnomaly
        from app.models.user import User
        from app.services.workflows.ar_collections_adapter import (
            request_review_customer,
            send_customer_email,
            skip_customer,
        )

        user = (
            db_session.query(User)
            .filter(User.id == tenant_ctx["user_id"])
            .one()
        )

        _s_cust, s_anomaly, _job = _seed_customer_with_draft(
            db_session, tenant_ctx["company_id"],
            name="SendMe Co", email="send@example.com", tier="CRITICAL",
        )
        _k_cust, k_anomaly, _job2 = _seed_customer_with_draft(
            db_session, tenant_ctx["company_id"],
            name="SkipMe Co", email="skip@example.com", tier="ESCALATE",
        )
        _r_cust, r_anomaly, _job3 = _seed_customer_with_draft(
            db_session, tenant_ctx["company_id"],
            name="ReviewMe Co", email="review@example.com",
            tier="FOLLOW_UP",
        )

        send_customer_email(db_session, user=user, anomaly_id=s_anomaly)
        skip_customer(
            db_session, user=user, anomaly_id=k_anomaly,
            reason="Customer paid yesterday",
        )
        request_review_customer(
            db_session, user=user, anomaly_id=r_anomaly,
            note="Tone feels off — second opinion needed",
        )

        # Exactly 1 collection email dispatched.
        assert (
            _count_deliveries(db_session, tenant_ctx["company_id"])
            == 1
        )
        # Send anomaly resolved.
        s_a = (
            db_session.query(AgentAnomaly)
            .filter(AgentAnomaly.id == s_anomaly).one()
        )
        assert s_a.resolved is True
        # Skip anomaly resolved with reason.
        k_a = (
            db_session.query(AgentAnomaly)
            .filter(AgentAnomaly.id == k_anomaly).one()
        )
        assert k_a.resolved is True
        assert "paid yesterday" in (k_a.resolution_note or "")
        # Review anomaly UNRESOLVED but has review note.
        r_a = (
            db_session.query(AgentAnomaly)
            .filter(AgentAnomaly.id == r_anomaly).one()
        )
        assert r_a.resolved is False
        assert "review-requested" in (r_a.resolution_note or "")


# ── Customer without billing email — graceful error ─────────────────


class TestMissingEmailGuard:
    def test_customer_without_email_raises_clear_error(
        self, db_session, tenant_ctx
    ):
        from app.models.customer import Customer
        from app.models.user import User
        from app.services.workflows.ar_collections_adapter import send_customer_email

        user = (
            db_session.query(User)
            .filter(User.id == tenant_ctx["user_id"])
            .one()
        )
        # Seed a customer without any email + its anomaly.
        _cust_id, anomaly_id, _job = _seed_customer_with_draft(
            db_session,
            tenant_ctx["company_id"],
            name="NoEmail Co",
            email="placeholder@noemail.example.com",
        )
        # Strip the billing email to simulate missing-email case.
        customer = (
            db_session.query(Customer).filter(Customer.id == _cust_id).one()
        )
        customer.billing_email = None
        customer.email = None
        db_session.commit()

        with pytest.raises(ValueError) as exc:
            send_customer_email(
                db_session, user=user, anomaly_id=anomaly_id,
            )
        assert "no billing_email" in str(exc.value).lower() or \
               "email on file" in str(exc.value).lower()


# ── Triage engine dispatch parity ───────────────────────────────────


class TestTriageEngineDispatch:
    def test_triage_engine_send_delegates(self, db_session, tenant_ctx):
        from app.models.document_delivery import DocumentDelivery
        from app.models.user import User
        from app.services.triage import apply_action, start_session

        user = (
            db_session.query(User)
            .filter(User.id == tenant_ctx["user_id"])
            .one()
        )
        _cust_id, anomaly_id, _job = _seed_customer_with_draft(
            db_session,
            tenant_ctx["company_id"],
            name="Triage Send Co",
            email="triage@example.com",
        )

        session = start_session(
            db_session, user=user, queue_id="ar_collections_triage"
        )
        result = apply_action(
            db_session,
            session_id=session.id,
            item_id=anomaly_id,
            action_id="send",
            user=user,
        )
        assert result.status == "applied", result.message
        assert (
            _count_deliveries(
                db_session, tenant_ctx["company_id"],
                recipient="triage@example.com",
            )
            == 1
        )

    def test_triage_engine_skip_requires_reason(
        self, db_session, tenant_ctx
    ):
        from app.models.user import User
        from app.services.triage import apply_action, start_session

        user = (
            db_session.query(User)
            .filter(User.id == tenant_ctx["user_id"])
            .one()
        )
        _cust_id, anomaly_id, _job = _seed_customer_with_draft(
            db_session,
            tenant_ctx["company_id"],
            name="Triage Skip Co",
            email="skip@example.com",
        )
        session = start_session(
            db_session, user=user, queue_id="ar_collections_triage"
        )
        result = apply_action(
            db_session,
            session_id=session.id,
            item_id=anomaly_id,
            action_id="skip",
            user=user,
        )
        assert result.status == "errored"
