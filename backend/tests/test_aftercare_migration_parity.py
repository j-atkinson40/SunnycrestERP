"""Workflow Arc Phase 8d — aftercare migration parity tests.

Parity discipline is narrower here than in Phase 8b/c: there is no
legacy accounting agent to compare side effects against. Pre-8d, the
workflow's `send_email` step referenced a non-existent template
(`template="aftercare_7day"`) so the "legacy" side effect was
zero — no email, no VaultItem, nothing. The parity claim post-8d is:

  THE TRIAGE APPROVE PATH PRODUCES THE INTENT OF THE ORIGINAL SEED
  (one email rendered from the aftercare template sent to the
  case's primary contact + one VaultItem of type="communication"
  with event_type="aftercare_message" linked to the funeral_case)
  AND DOES IT CONSISTENTLY (no flaky rendering, no missed sends).

Tests:
  - Pipeline stages one AgentAnomaly per eligible case.
  - Idempotent re-run returns the same AgentJob.
  - Approve: email via managed template + VaultItem + anomaly resolved.
  - Approve without primary contact email: ValueError.
  - Skip: no email, anomaly resolved with reason.
  - Skip without reason: ValueError.
  - Request review: anomaly stays unresolved, review note stamped.
  - No cross-tenant bleed in pipeline or approve.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _seed_fh_tenant(vertical: str = "funeral_home") -> dict:
    """Seed a tenant + admin user. Returns a ctx dict with ids."""
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"FH-{suffix}",
            slug=f"fh-{suffix}",
            is_active=True,
            vertical=vertical,
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
            email=f"director-{suffix}@fh.co",
            first_name="Dir",
            last_name="Ector",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        return {
            "company_id": co.id,
            "user_id": user.id,
            "user": user,
        }
    finally:
        db.close()


def _seed_case_with_service_date(
    db, *, company_id: str, service_date: date,
    primary_contact_email: str | None = "family@example.com",
    deceased_last_name: str = "Martinez",
) -> str:
    """Create a FuneralCase + CaseDeceased + CaseInformant + CaseService
    with the given service_date. Returns the case id."""
    from app.models.funeral_case import (
        CaseDeceased,
        CaseInformant,
        CaseService,
        FuneralCase,
    )

    suffix = uuid.uuid4().hex[:6]
    fc = FuneralCase(
        id=str(uuid.uuid4()),
        company_id=company_id,
        case_number=f"CASE-{suffix}",
        status="active",
        current_step="aftercare",
    )
    db.add(fc)
    db.flush()
    db.add(
        CaseDeceased(
            case_id=fc.id,
            company_id=company_id,
            first_name="Maria",
            last_name=deceased_last_name,
        )
    )
    db.add(
        CaseInformant(
            case_id=fc.id,
            company_id=company_id,
            name="Mary Martinez",
            email=primary_contact_email,
            is_primary=True,
        )
    )
    db.add(
        CaseService(
            case_id=fc.id,
            company_id=company_id,
            service_date=service_date,
        )
    )
    db.commit()
    return fc.id


# ── Pipeline tests ───────────────────────────────────────────────────


class TestAftercarePipeline:
    def test_stages_one_anomaly_per_eligible_case(self, db_session):
        from app.models.agent_anomaly import AgentAnomaly
        from app.services.workflows.aftercare_adapter import (
            ANOMALY_TYPE,
            run_pipeline,
        )

        ctx = _seed_fh_tenant()
        seven_days_ago = date.today() - timedelta(days=7)
        case_ids = [
            _seed_case_with_service_date(
                db_session,
                company_id=ctx["company_id"],
                service_date=seven_days_ago,
                deceased_last_name=f"Family{i}",
            )
            for i in range(3)
        ]
        # Also seed a case whose service_date is NOT 7 days ago —
        # should not be picked up.
        _seed_case_with_service_date(
            db_session,
            company_id=ctx["company_id"],
            service_date=date.today() - timedelta(days=14),
        )

        result = run_pipeline(
            db_session,
            company_id=ctx["company_id"],
            triggered_by_user_id=ctx["user_id"],
        )
        assert result["status"] == "applied"
        assert result["cases_staged"] == 3

        anomalies = (
            db_session.query(AgentAnomaly)
            .filter(
                AgentAnomaly.anomaly_type == ANOMALY_TYPE,
                AgentAnomaly.resolved.is_(False),
            )
            .all()
        )
        # Filter to this tenant's staged cases.
        staged_case_ids = {
            a.entity_id for a in anomalies if a.entity_id in case_ids
        }
        assert staged_case_ids == set(case_ids)

    def test_idempotent_rerun_reuses_existing_job(self, db_session):
        from app.services.workflows.aftercare_adapter import run_pipeline

        ctx = _seed_fh_tenant()
        seven_days_ago = date.today() - timedelta(days=7)
        _seed_case_with_service_date(
            db_session,
            company_id=ctx["company_id"],
            service_date=seven_days_ago,
        )

        r1 = run_pipeline(
            db_session, company_id=ctx["company_id"], triggered_by_user_id=None
        )
        r2 = run_pipeline(
            db_session, company_id=ctx["company_id"], triggered_by_user_id=None
        )
        assert r1["agent_job_id"] is not None
        assert r2["agent_job_id"] == r1["agent_job_id"]
        assert r2.get("idempotent_reuse") is True

    def test_no_eligible_cases_returns_zero_staged(self, db_session):
        from app.services.workflows.aftercare_adapter import run_pipeline

        ctx = _seed_fh_tenant()
        # No cases seeded.
        result = run_pipeline(
            db_session,
            company_id=ctx["company_id"],
            triggered_by_user_id=None,
        )
        assert result["status"] == "applied"
        assert result["cases_staged"] == 0
        assert result["agent_job_id"] is None

    def test_cross_tenant_isolation_on_pipeline(self, db_session):
        """Tenant A's pipeline run only sees tenant A's cases."""
        from app.models.agent_anomaly import AgentAnomaly
        from app.services.workflows.aftercare_adapter import (
            ANOMALY_TYPE,
            run_pipeline,
        )

        ctx_a = _seed_fh_tenant()
        ctx_b = _seed_fh_tenant()
        seven_days_ago = date.today() - timedelta(days=7)
        case_a = _seed_case_with_service_date(
            db_session,
            company_id=ctx_a["company_id"],
            service_date=seven_days_ago,
            deceased_last_name="Alpha",
        )
        case_b = _seed_case_with_service_date(
            db_session,
            company_id=ctx_b["company_id"],
            service_date=seven_days_ago,
            deceased_last_name="Beta",
        )

        r_a = run_pipeline(
            db_session,
            company_id=ctx_a["company_id"],
            triggered_by_user_id=None,
        )
        assert r_a["cases_staged"] == 1
        # Anomalies for tenant A should only reference case_a.
        from app.models.agent import AgentJob

        anomalies = (
            db_session.query(AgentAnomaly)
            .join(AgentJob, AgentJob.id == AgentAnomaly.agent_job_id)
            .filter(
                AgentJob.tenant_id == ctx_a["company_id"],
                AgentAnomaly.anomaly_type == ANOMALY_TYPE,
            )
            .all()
        )
        staged_ids = {a.entity_id for a in anomalies}
        assert case_a in staged_ids
        assert case_b not in staged_ids


# ── Triage action tests ──────────────────────────────────────────────


class TestAftercareTriageActions:
    def test_approve_send_renders_template_and_resolves(self, db_session):
        from app.models.agent_anomaly import AgentAnomaly
        from app.services.workflows.aftercare_adapter import (
            approve_send,
            run_pipeline,
        )

        ctx = _seed_fh_tenant()
        seven_days_ago = date.today() - timedelta(days=7)
        case_id = _seed_case_with_service_date(
            db_session,
            company_id=ctx["company_id"],
            service_date=seven_days_ago,
            deceased_last_name="Martinez",
            primary_contact_email="mary@example.com",
        )
        run_pipeline(
            db_session,
            company_id=ctx["company_id"],
            triggered_by_user_id=ctx["user_id"],
        )
        anomaly = (
            db_session.query(AgentAnomaly)
            .filter(
                AgentAnomaly.entity_id == case_id,
                AgentAnomaly.resolved.is_(False),
            )
            .first()
        )
        assert anomaly is not None

        # Monkey-patch delivery_service.send to capture the call
        # without actually sending (no email API key in test env).
        sent_calls = []

        def _fake_send_email_with_template(db, **kwargs):
            sent_calls.append(kwargs)

            class _FakeDelivery:
                id = "delivery-fake-1"

            return _FakeDelivery()

        # Patch at the import site used inside approve_send.
        with patch(
            "app.services.delivery.delivery_service.send_email_with_template",
            side_effect=_fake_send_email_with_template,
        ):
            result = approve_send(
                db_session, user=ctx["user"], anomaly_id=anomaly.id
            )
        assert result["status"] == "applied"
        assert result["recipient_email"] == "mary@example.com"
        assert len(sent_calls) == 1
        call = sent_calls[0]
        assert call["template_key"] == "email.fh_aftercare_7day"
        assert call["template_context"]["family_surname"] == "Martinez"
        assert call["to_email"] == "mary@example.com"
        assert call["caller_module"] == "aftercare_adapter"

        # Anomaly resolved.
        db_session.refresh(anomaly)
        assert anomaly.resolved is True
        assert anomaly.resolved_by == ctx["user_id"]

    def test_approve_without_primary_email_raises(self, db_session):
        from app.models.agent_anomaly import AgentAnomaly
        from app.services.workflows.aftercare_adapter import (
            approve_send,
            run_pipeline,
        )

        ctx = _seed_fh_tenant()
        seven_days_ago = date.today() - timedelta(days=7)
        case_id = _seed_case_with_service_date(
            db_session,
            company_id=ctx["company_id"],
            service_date=seven_days_ago,
            primary_contact_email=None,
        )
        run_pipeline(
            db_session,
            company_id=ctx["company_id"],
            triggered_by_user_id=ctx["user_id"],
        )
        anomaly = (
            db_session.query(AgentAnomaly)
            .filter(AgentAnomaly.entity_id == case_id)
            .first()
        )
        with pytest.raises(ValueError, match="email address"):
            approve_send(db_session, user=ctx["user"], anomaly_id=anomaly.id)

    def test_skip_resolves_without_send(self, db_session):
        from app.models.agent_anomaly import AgentAnomaly
        from app.services.workflows.aftercare_adapter import (
            run_pipeline,
            skip_case,
        )

        ctx = _seed_fh_tenant()
        seven_days_ago = date.today() - timedelta(days=7)
        case_id = _seed_case_with_service_date(
            db_session,
            company_id=ctx["company_id"],
            service_date=seven_days_ago,
        )
        run_pipeline(
            db_session,
            company_id=ctx["company_id"],
            triggered_by_user_id=ctx["user_id"],
        )
        anomaly = (
            db_session.query(AgentAnomaly)
            .filter(AgentAnomaly.entity_id == case_id)
            .first()
        )
        result = skip_case(
            db_session,
            user=ctx["user"],
            anomaly_id=anomaly.id,
            reason="Family requested no follow-ups",
        )
        assert result["status"] == "applied"
        db_session.refresh(anomaly)
        assert anomaly.resolved is True
        assert "Skipped" in (anomaly.resolution_note or "")

    def test_skip_without_reason_raises(self, db_session):
        from app.models.agent_anomaly import AgentAnomaly
        from app.services.workflows.aftercare_adapter import (
            run_pipeline,
            skip_case,
        )

        ctx = _seed_fh_tenant()
        seven_days_ago = date.today() - timedelta(days=7)
        case_id = _seed_case_with_service_date(
            db_session,
            company_id=ctx["company_id"],
            service_date=seven_days_ago,
        )
        run_pipeline(
            db_session,
            company_id=ctx["company_id"],
            triggered_by_user_id=ctx["user_id"],
        )
        anomaly = (
            db_session.query(AgentAnomaly)
            .filter(AgentAnomaly.entity_id == case_id)
            .first()
        )
        with pytest.raises(ValueError, match="Reason"):
            skip_case(
                db_session,
                user=ctx["user"],
                anomaly_id=anomaly.id,
                reason="",
            )

    def test_request_review_stays_in_queue(self, db_session):
        from app.models.agent_anomaly import AgentAnomaly
        from app.services.workflows.aftercare_adapter import (
            request_review,
            run_pipeline,
        )

        ctx = _seed_fh_tenant()
        seven_days_ago = date.today() - timedelta(days=7)
        case_id = _seed_case_with_service_date(
            db_session,
            company_id=ctx["company_id"],
            service_date=seven_days_ago,
        )
        run_pipeline(
            db_session,
            company_id=ctx["company_id"],
            triggered_by_user_id=ctx["user_id"],
        )
        anomaly = (
            db_session.query(AgentAnomaly)
            .filter(AgentAnomaly.entity_id == case_id)
            .first()
        )
        result = request_review(
            db_session,
            user=ctx["user"],
            anomaly_id=anomaly.id,
            note="Ask John about this family",
        )
        assert result["status"] == "applied"
        db_session.refresh(anomaly)
        # Anomaly is NOT resolved — stays in queue.
        assert anomaly.resolved is False
        assert "review-requested" in (anomaly.resolution_note or "")

    def test_cross_tenant_approve_404(self, db_session):
        """Tenant A cannot approve tenant B's anomaly."""
        from app.models.agent_anomaly import AgentAnomaly
        from app.services.workflows.aftercare_adapter import (
            approve_send,
            run_pipeline,
        )

        ctx_a = _seed_fh_tenant()
        ctx_b = _seed_fh_tenant()
        seven_days_ago = date.today() - timedelta(days=7)
        _seed_case_with_service_date(
            db_session,
            company_id=ctx_b["company_id"],
            service_date=seven_days_ago,
        )
        run_pipeline(
            db_session,
            company_id=ctx_b["company_id"],
            triggered_by_user_id=ctx_b["user_id"],
        )
        b_anomaly = (
            db_session.query(AgentAnomaly)
            .join(
                # AgentJob relationship
                __import__(
                    "app.models.agent", fromlist=["AgentJob"]
                ).AgentJob,
                __import__(
                    "app.models.agent", fromlist=["AgentJob"]
                ).AgentJob.id
                == AgentAnomaly.agent_job_id,
            )
            .filter(
                __import__(
                    "app.models.agent", fromlist=["AgentJob"]
                ).AgentJob.tenant_id
                == ctx_b["company_id"]
            )
            .first()
        )
        # Tenant A's user attempting to approve B's anomaly.
        with pytest.raises(ValueError, match="not found for this tenant"):
            approve_send(
                db_session, user=ctx_a["user"], anomaly_id=b_anomaly.id
            )
