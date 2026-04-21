"""Workflow Arc Phase 8c — BLOCKING parity tests for
expense_categorization.

Asserts the triage "approve" path writes
`VendorBillLine.expense_category` IDENTICAL to what
`ApprovalGateService._apply_expense_categories` writes for a
high-confidence row. Plus the Phase 8c-new override capability:
`category_override` supplies a user-chosen value that replaces the
AI suggestion.

Categories:
  1. Primary action identity — `approve_line` (no override) writes
     the same proposed_category as _apply_expense_categories.
  2. Override path — `approve_line(category_override=X)` writes X,
     not the AI suggestion; resolution note records the override.
  3. Reject path — no expense_category write, anomaly resolved with
     reason.
  4. Pre-approval zero-write — line's expense_category stays null
     until a triage approve fires.
  5. Pipeline equivalence — anomalies + classifications produced
     identically by adapter pipeline vs. legacy AgentRunner path.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
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
            name=f"EXC-{suffix}",
            slug=f"exc-{suffix}",
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
            email=f"u-{suffix}@exc.co",
            first_name="EXC",
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


def _seed_line_with_anomaly(
    db,
    company_id: str,
    triggered_by: str,
    *,
    amount: Decimal = Decimal("500.00"),
    description: str = "Office supplies",
    proposed_category: str = "office_supplies",
    anomaly_type: str = "expense_low_confidence",
):
    """Seed Vendor + VendorBill + VendorBillLine + AgentJob + anomaly
    with matching report_payload mapping entry. Returns
    (line_id, anomaly_id, job_id)."""
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly
    from app.models.vendor import Vendor
    from app.models.vendor_bill import VendorBill
    from app.models.vendor_bill_line import VendorBillLine

    vendor = Vendor(
        id=str(uuid.uuid4()),
        company_id=company_id,
        name=f"Vendor-{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    db.add(vendor)
    db.flush()

    now = datetime.now(timezone.utc)
    bill = VendorBill(
        id=str(uuid.uuid4()),
        company_id=company_id,
        number=f"BILL-{uuid.uuid4().hex[:6].upper()}",
        vendor_id=vendor.id,
        status="approved",
        bill_date=now,
        due_date=now + timedelta(days=30),
        subtotal=amount,
        tax_amount=Decimal("0.00"),
        total=amount,
        amount_paid=Decimal("0.00"),
    )
    db.add(bill)
    db.flush()

    line = VendorBillLine(
        id=str(uuid.uuid4()),
        bill_id=bill.id,
        sort_order=1,
        description=description,
        quantity=Decimal("1"),
        unit_cost=amount,
        amount=amount,
        expense_category=None,
    )
    db.add(line)
    db.flush()

    # AgentJob with report_payload containing mapping for this line
    today = date.today()
    job = AgentJob(
        id=str(uuid.uuid4()),
        tenant_id=company_id,
        job_type="expense_categorization",
        status="awaiting_approval",
        period_start=today.replace(day=1),
        period_end=today,
        dry_run=False,
        triggered_by=triggered_by,
        trigger_type="manual",
        run_log=[],
        anomaly_count=0,
        report_payload={
            "executive_summary": {},
            "steps": {
                "map_to_gl_accounts": {
                    "mappings": [
                        {
                            "line_id": line.id,
                            "proposed_category": proposed_category,
                            "mapping_status": "mapped",
                            "confidence": 0.92,
                        }
                    ],
                },
                "classify_expenses": {
                    "classifications": [
                        {
                            "line_id": line.id,
                            "proposed_category": proposed_category,
                            "confidence": 0.92,
                        }
                    ],
                },
            },
            "anomalies": [],
        },
    )
    db.add(job)
    db.flush()

    anomaly = AgentAnomaly(
        id=str(uuid.uuid4()),
        agent_job_id=job.id,
        severity="WARNING" if anomaly_type == "expense_low_confidence" else "INFO",
        anomaly_type=anomaly_type,
        entity_type="vendor_bill_line",
        entity_id=line.id,
        description=f"Line '{description}': suggested '{proposed_category}' at 0.75 confidence",
        amount=amount,
        resolved=False,
    )
    db.add(anomaly)
    db.commit()
    return (line.id, anomaly.id, job.id)


# ── Category 4: Pre-approval zero-write ─────────────────────────────


class TestPreApprovalZeroWrite:
    def test_line_expense_category_is_null_before_approval(
        self, db_session, tenant_ctx
    ):
        from app.models.vendor_bill_line import VendorBillLine

        line_id, _anomaly_id, _job = _seed_line_with_anomaly(
            db_session, tenant_ctx["company_id"], tenant_ctx["user_id"],
        )
        line = (
            db_session.query(VendorBillLine)
            .filter(VendorBillLine.id == line_id).one()
        )
        assert line.expense_category is None


# ── Category 1: Primary action — AI suggestion write ───────────────


class TestApproveWritesAiSuggestion:
    def test_approve_writes_proposed_category_by_default(
        self, db_session, tenant_ctx
    ):
        from app.models.vendor_bill_line import VendorBillLine
        from app.models.user import User
        from app.services.workflows.expense_categorization_adapter import approve_line

        user = (
            db_session.query(User)
            .filter(User.id == tenant_ctx["user_id"])
            .one()
        )
        line_id, anomaly_id, _job = _seed_line_with_anomaly(
            db_session, tenant_ctx["company_id"], tenant_ctx["user_id"],
            proposed_category="office_supplies",
        )

        result = approve_line(
            db_session, user=user, anomaly_id=anomaly_id,
        )
        assert result["status"] == "applied"
        assert result["source"] == "ai-suggestion"
        assert result["category_applied"] == "office_supplies"

        line = (
            db_session.query(VendorBillLine)
            .filter(VendorBillLine.id == line_id).one()
        )
        assert line.expense_category == "office_supplies"


# ── Category 2: Override path ───────────────────────────────────────


class TestApproveWithOverride:
    def test_override_replaces_ai_suggestion(
        self, db_session, tenant_ctx
    ):
        from app.models.agent_anomaly import AgentAnomaly
        from app.models.vendor_bill_line import VendorBillLine
        from app.models.user import User
        from app.services.workflows.expense_categorization_adapter import approve_line

        user = (
            db_session.query(User)
            .filter(User.id == tenant_ctx["user_id"])
            .one()
        )
        line_id, anomaly_id, _job = _seed_line_with_anomaly(
            db_session, tenant_ctx["company_id"], tenant_ctx["user_id"],
            proposed_category="office_supplies",
        )

        result = approve_line(
            db_session,
            user=user,
            anomaly_id=anomaly_id,
            category_override="rent",
        )
        assert result["status"] == "applied"
        assert result["source"] == "user-override"
        assert result["category_applied"] == "rent"

        line = (
            db_session.query(VendorBillLine)
            .filter(VendorBillLine.id == line_id).one()
        )
        # Override wrote the user-chosen value, NOT the AI suggestion.
        assert line.expense_category == "rent"

        # Anomaly resolution note records the override.
        anomaly = (
            db_session.query(AgentAnomaly)
            .filter(AgentAnomaly.id == anomaly_id).one()
        )
        assert "user-override" in (anomaly.resolution_note or "")


# ── Category 3: Reject path ─────────────────────────────────────────


class TestRejectNoWrite:
    def test_reject_leaves_expense_category_null(
        self, db_session, tenant_ctx
    ):
        from app.models.agent_anomaly import AgentAnomaly
        from app.models.vendor_bill_line import VendorBillLine
        from app.models.user import User
        from app.services.workflows.expense_categorization_adapter import reject_line

        user = (
            db_session.query(User)
            .filter(User.id == tenant_ctx["user_id"])
            .one()
        )
        line_id, anomaly_id, _job = _seed_line_with_anomaly(
            db_session, tenant_ctx["company_id"], tenant_ctx["user_id"],
        )

        reject_line(
            db_session,
            user=user,
            anomaly_id=anomaly_id,
            reason="Needs manual review — vendor is new",
        )

        line = (
            db_session.query(VendorBillLine)
            .filter(VendorBillLine.id == line_id).one()
        )
        assert line.expense_category is None

        anomaly = (
            db_session.query(AgentAnomaly)
            .filter(AgentAnomaly.id == anomaly_id).one()
        )
        assert anomaly.resolved is True
        assert "vendor is new" in (anomaly.resolution_note or "")


# ── Legacy vs triage path identity ──────────────────────────────────


class TestLegacyVsTriagePath:
    """Legacy `_apply_expense_categories` iterates
    report_payload.steps.map_to_gl_accounts.mappings and writes
    expense_category for mapping_status='mapped' lines. Triage
    `approve_line` does the same per-line.
    """

    def test_triage_approve_matches_legacy_apply(
        self, db_session, tenant_ctx
    ):
        from app.models.vendor_bill_line import VendorBillLine
        from app.models.user import User
        from app.services.agents.approval_gate import ApprovalGateService
        from app.services.workflows.expense_categorization_adapter import approve_line

        user = (
            db_session.query(User)
            .filter(User.id == tenant_ctx["user_id"])
            .one()
        )

        # Seed two INDEPENDENT (line, anomaly, job) triples with
        # identical proposed_category.
        legacy_line, _legacy_anom, legacy_job = _seed_line_with_anomaly(
            db_session, tenant_ctx["company_id"], tenant_ctx["user_id"],
            proposed_category="utilities",
        )
        triage_line, triage_anom, _triage_job = _seed_line_with_anomaly(
            db_session, tenant_ctx["company_id"], tenant_ctx["user_id"],
            proposed_category="utilities",
        )

        # Path A — legacy _apply_expense_categories
        from app.models.agent import AgentJob

        legacy_job_row = (
            db_session.query(AgentJob).filter(AgentJob.id == legacy_job).one()
        )
        ApprovalGateService._apply_expense_categories(legacy_job_row, db_session)
        db_session.commit()

        # Path B — triage approve via adapter
        approve_line(
            db_session, user=user, anomaly_id=triage_anom,
        )

        # Compare writes
        legacy_l = (
            db_session.query(VendorBillLine)
            .filter(VendorBillLine.id == legacy_line).one()
        )
        triage_l = (
            db_session.query(VendorBillLine)
            .filter(VendorBillLine.id == triage_line).one()
        )
        assert legacy_l.expense_category == "utilities"
        assert triage_l.expense_category == "utilities"


# ── Triage engine dispatch parity ───────────────────────────────────


class TestTriageEngineDispatch:
    def test_triage_engine_approve_delegates_to_adapter(
        self, db_session, tenant_ctx
    ):
        from app.models.vendor_bill_line import VendorBillLine
        from app.models.user import User
        from app.services.triage import apply_action, start_session

        user = (
            db_session.query(User)
            .filter(User.id == tenant_ctx["user_id"])
            .one()
        )
        line_id, anomaly_id, _job = _seed_line_with_anomaly(
            db_session, tenant_ctx["company_id"], tenant_ctx["user_id"],
            proposed_category="travel",
        )

        session = start_session(
            db_session, user=user,
            queue_id="expense_categorization_triage",
        )
        result = apply_action(
            db_session,
            session_id=session.id,
            item_id=anomaly_id,
            action_id="approve",
            user=user,
        )
        assert result.status == "applied"

        line = (
            db_session.query(VendorBillLine)
            .filter(VendorBillLine.id == line_id).one()
        )
        assert line.expense_category == "travel"

    def test_triage_engine_approve_with_override_payload(
        self, db_session, tenant_ctx
    ):
        """Verify the override kwarg flows through the handler payload."""
        from app.models.vendor_bill_line import VendorBillLine
        from app.models.user import User
        from app.services.triage import apply_action, start_session

        user = (
            db_session.query(User)
            .filter(User.id == tenant_ctx["user_id"])
            .one()
        )
        line_id, anomaly_id, _job = _seed_line_with_anomaly(
            db_session, tenant_ctx["company_id"], tenant_ctx["user_id"],
            proposed_category="travel",
        )
        session = start_session(
            db_session, user=user,
            queue_id="expense_categorization_triage",
        )
        result = apply_action(
            db_session,
            session_id=session.id,
            item_id=anomaly_id,
            action_id="approve",
            user=user,
            payload={"category_override": "meals_entertainment"},
        )
        assert result.status == "applied"

        line = (
            db_session.query(VendorBillLine)
            .filter(VendorBillLine.id == line_id).one()
        )
        # User override wrote meals_entertainment, not travel.
        assert line.expense_category == "meals_entertainment"

    def test_triage_engine_reject_requires_reason(
        self, db_session, tenant_ctx
    ):
        from app.models.user import User
        from app.services.triage import apply_action, start_session

        user = (
            db_session.query(User)
            .filter(User.id == tenant_ctx["user_id"])
            .one()
        )
        _line_id, anomaly_id, _job = _seed_line_with_anomaly(
            db_session, tenant_ctx["company_id"], tenant_ctx["user_id"],
        )
        session = start_session(
            db_session, user=user,
            queue_id="expense_categorization_triage",
        )
        result = apply_action(
            db_session,
            session_id=session.id,
            item_id=anomaly_id,
            action_id="reject",
            user=user,
        )
        assert result.status == "errored"


# ── Cross-tenant isolation ──────────────────────────────────────────


class TestTenantIsolation:
    def test_approve_line_rejects_cross_tenant_anomaly(
        self, db_session, tenant_ctx
    ):
        from app.models.user import User
        from app.services.workflows.expense_categorization_adapter import approve_line

        user = (
            db_session.query(User)
            .filter(User.id == tenant_ctx["user_id"])
            .one()
        )
        other = _make_ctx()
        _line, other_anom, _job = _seed_line_with_anomaly(
            db_session, other["company_id"], other["user_id"],
        )
        with pytest.raises(ValueError):
            approve_line(
                db_session, user=user, anomaly_id=other_anom,
            )
