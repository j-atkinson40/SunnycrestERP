"""Workflow Arc Phase 8b.5 — approval gate email migrated to D-7
managed template.

Coverage:
  1. Managed template `email.approval_gate_review` is seeded +
     renders from the registry (not from hardcoded HTML).
  2. Sending an approval email creates DocumentDelivery rows with
     `template_key="email.approval_gate_review"` and
     `caller_module="approval_gate.send_review_email"`.
  3. Rendered body contains the approval token URL + job_type_label.
  4. The rendered subject contains the job_type_label.
  5. `_build_review_email_html` was removed from ApprovalGateService
     (refactor is complete — no fallback to hardcoded HTML).
  6. Seed is idempotent — running the migration twice produces one
     template row, not two (guaranteed by the migration's existence
     check at the top of `upgrade()`).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _seed_tenant_and_user():
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"AppEmail-{suffix}",
            slug=f"appemail-{suffix}",
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
            email=f"admin-{suffix}@appemail.co",
            first_name="App",
            last_name="Admin",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        return {"company_id": co.id, "user_id": user.id, "user_email": user.email}
    finally:
        db.close()


def _seed_agent_job(company_id: str, triggered_by: str, *, anomaly_count: int = 0):
    """Create an AgentJob row in awaiting_approval state — what the
    approval gate email targets."""
    from app.database import SessionLocal
    from app.models.agent import AgentJob

    db = SessionLocal()
    try:
        job = AgentJob(
            id=str(uuid.uuid4()),
            tenant_id=company_id,
            job_type="cash_receipts_matching",
            status="awaiting_approval",
            period_start=date.today().replace(day=1),
            period_end=date.today(),
            dry_run=False,
            triggered_by=triggered_by,
            trigger_type="manual",
            run_log=[],
            anomaly_count=anomaly_count,
            report_payload={"anomalies": []} if anomaly_count == 0 else {
                "anomalies": [{"severity": "critical"}] * anomaly_count,
            },
        )
        db.add(job)
        db.commit()
        return job.id
    finally:
        db.close()


class TestApprovalEmailManagedTemplate:
    def test_managed_template_exists_in_registry(self, db_session):
        """The r37 migration has seeded the email template."""
        from app.services.documents import template_loader

        loaded = template_loader.load(
            "email.approval_gate_review", company_id=None, db=db_session
        )
        assert loaded is not None
        assert loaded.body_template
        # Subject template is a Jinja pattern containing job_type_label.
        assert loaded.subject_template is not None
        assert "job_type_label" in loaded.subject_template

    def test_managed_template_renders_with_context(self, db_session):
        """Render the template directly and verify variables are
        substituted + critical strings are present."""
        from app.services.documents import document_renderer

        result = document_renderer.render_html(
            db_session,
            template_key="email.approval_gate_review",
            context={
                "tenant_name": "Sunnycrest",
                "job_type_label": "Cash Receipts Matching",
                "period_label": "April 2026",
                "approve_url": (
                    "https://example.com/agents/JOB/review?"
                    "action=approve&token=TOKEN123"
                ),
                "reject_url": (
                    "https://example.com/agents/JOB/review?"
                    "action=reject&token=TOKEN123"
                ),
                "review_url": "https://example.com/agents/JOB/review",
                "anomaly_count": 3,
                "critical_count": 1,
                "dry_run": False,
            },
        )
        body = result.rendered_content
        subject = result.rendered_subject

        assert subject == "Agent Review: Cash Receipts Matching — April 2026"
        assert "Sunnycrest" in body
        assert "Cash Receipts Matching" in body
        assert "April 2026" in body
        assert "TOKEN123" in body, "Approval token must appear in body"
        assert "Approve" in body
        assert "Reject" in body
        # Anomaly summary for 3 anomalies + 1 critical
        assert "3 anomalies" in body
        assert "(1 critical)" in body

    def test_managed_template_renders_no_anomalies_variant(self, db_session):
        from app.services.documents import document_renderer

        result = document_renderer.render_html(
            db_session,
            template_key="email.approval_gate_review",
            context={
                "tenant_name": "Clean Co",
                "job_type_label": "Month-End Close",
                "period_label": "March 2026",
                "approve_url": "https://example.com/approve",
                "reject_url": "https://example.com/reject",
                "review_url": "https://example.com/review",
                "anomaly_count": 0,
                "critical_count": 0,
                "dry_run": False,
            },
        )
        body = result.rendered_content
        assert "No anomalies found" in body
        # Dry-run banner should NOT appear when dry_run is False.
        assert "Dry Run" not in body

    def test_managed_template_renders_dry_run_banner(self, db_session):
        from app.services.documents import document_renderer

        result = document_renderer.render_html(
            db_session,
            template_key="email.approval_gate_review",
            context={
                "tenant_name": "Test Co",
                "job_type_label": "Cash Receipts Matching",
                "period_label": "",
                "approve_url": "https://example.com/approve",
                "reject_url": "https://example.com/reject",
                "review_url": "https://example.com/review",
                "anomaly_count": 0,
                "critical_count": 0,
                "dry_run": True,
            },
        )
        body = result.rendered_content
        assert "Dry Run" in body
        assert "No changes were committed" in body


class TestSendReviewEmailMigration:
    """Integration — full send_review_email path creates
    DocumentDelivery rows via the D-7 managed-template flow."""

    def test_send_review_email_creates_document_delivery_with_template_key(
        self,
    ):
        from app.database import SessionLocal
        from app.models.agent import AgentJob
        from app.models.document_delivery import DocumentDelivery
        from app.services.agents.approval_gate import ApprovalGateService

        ctx = _seed_tenant_and_user()
        job_id = _seed_agent_job(ctx["company_id"], ctx["user_id"])
        token = "test-token-abc"

        # send_review_email is its own session-owning path, but the
        # `delivery_service.send_email_with_template` it calls writes
        # directly via the session we pass. Use a fresh session.
        db = SessionLocal()
        try:
            job = db.query(AgentJob).filter(AgentJob.id == job_id).one()
            ApprovalGateService.send_review_email(
                job=job,
                token=token,
                tenant_id=ctx["company_id"],
                db=db,
            )
            db.commit()

            # One DocumentDelivery row per recipient.
            deliveries = (
                db.query(DocumentDelivery)
                .filter(
                    DocumentDelivery.company_id == ctx["company_id"],
                    DocumentDelivery.template_key
                    == "email.approval_gate_review",
                )
                .all()
            )
            assert len(deliveries) >= 1, (
                "Expected at least one DocumentDelivery row for the "
                "approval email"
            )
            d = deliveries[0]
            assert d.template_key == "email.approval_gate_review"
            assert d.caller_module == "approval_gate.send_review_email"
            assert d.channel == "email"
            assert d.recipient_value == ctx["user_email"]
            assert d.subject is not None
            assert "Cash Receipts Matching" in (d.subject or "")
            # token leaked into body preview or subject? Body preview.
            # Actually the token is in the rendered body, which is
            # stored as `body_preview` (first 500 chars) — check body
            # or body_preview contains the token.
            assert token in (d.body_preview or "") or d.status in (
                "sent", "delivered"
            ), (
                "Expected token in body preview (test-mode sends "
                "populate body_preview) or a successful status"
            )
        finally:
            db.close()

    def test_send_review_email_subject_references_job_type_label(self):
        from app.database import SessionLocal
        from app.models.agent import AgentJob
        from app.models.document_delivery import DocumentDelivery
        from app.services.agents.approval_gate import ApprovalGateService

        ctx = _seed_tenant_and_user()
        job_id = _seed_agent_job(ctx["company_id"], ctx["user_id"])

        db = SessionLocal()
        try:
            job = db.query(AgentJob).filter(AgentJob.id == job_id).one()
            ApprovalGateService.send_review_email(
                job=job,
                token="subject-test",
                tenant_id=ctx["company_id"],
                db=db,
            )
            db.commit()
            d = (
                db.query(DocumentDelivery)
                .filter(
                    DocumentDelivery.company_id == ctx["company_id"],
                    DocumentDelivery.template_key
                    == "email.approval_gate_review",
                )
                .order_by(DocumentDelivery.created_at.desc())
                .first()
            )
            assert d is not None
            # Subject pattern: "Agent Review: <job_type_label> — <period>"
            assert d.subject.startswith("Agent Review: Cash Receipts Matching")
        finally:
            db.close()


class TestInlineHtmlRemoved:
    def test_build_review_email_html_is_gone(self):
        """Regression: the hardcoded HTML builder must be removed so
        no code path falls back to it."""
        from app.services.agents.approval_gate import ApprovalGateService

        assert not hasattr(ApprovalGateService, "_build_review_email_html"), (
            "_build_review_email_html should be removed — email "
            "migration to managed template is complete."
        )


class TestSeedIdempotent:
    def test_seed_function_returns_single_template(self):
        """The template seed list returns exactly one entry for
        email.approval_gate_review — guards against accidental
        duplication that would break the migration's idempotency
        guard."""
        from app.services.documents._template_seeds import (
            _approval_gate_seeds,
        )

        seeds = _approval_gate_seeds()
        keys = [s["template_key"] for s in seeds]
        assert keys == ["email.approval_gate_review"]
        # Each seed has the minimum shape required.
        for s in seeds:
            assert s["output_format"] == "html"
            assert s["document_type"] == "email"
            assert s["body_template"]
            assert s.get("subject_template")
