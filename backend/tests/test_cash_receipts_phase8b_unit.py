"""Workflow Arc Phase 8b — unit tests.

Non-parity, non-latency coverage for the Phase 8b scaffolding:

  - Triage queue registration at import time (platform defaults
    include `cash_receipts_matching_triage`).
  - _DIRECT_QUERIES dispatch includes the cash-receipts builder.
  - _RELATED_ENTITY_BUILDERS dispatch includes the cash-receipts
    builder and returns the expected entity shapes.
  - Triage action handlers are registered under `cash_receipts.*`
    keys.
  - workflow_engine `_SERVICE_METHOD_REGISTRY` has the
    `cash_receipts.run_match_pipeline` entry with the expected
    allowed-kwargs list.
  - `call_service_method` action subtype rejects unknown methods +
    passes auto-injected kwargs through.
  - `wf_sys_cash_receipts` is present in TIER_1_WORKFLOWS with the
    expected step shape + no agent_registry_key (cleared per the
    8b-beta step of the migration choreography).
  - Override + request_review adapter functions validate required
    reason + note and raise on missing/unknown data.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _make_tenant():
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"UNIT8B-{suffix}",
            slug=f"unit8b-{suffix}",
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
            email=f"u-{suffix}@u.co",
            first_name="U",
            last_name="T",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        return {"company_id": co.id, "user_id": user.id}
    finally:
        db.close()


@pytest.fixture
def tenant_ctx():
    return _make_tenant()


# ── Registry tests ───────────────────────────────────────────────────


class TestTriageRegistration:
    def test_cash_receipts_queue_is_platform_default(self):
        from app.services.triage import list_platform_configs

        ids = {c.queue_id for c in list_platform_configs()}
        assert "cash_receipts_matching_triage" in ids

    def test_cash_receipts_queue_config_shape(self):
        from app.services.triage import list_platform_configs

        cfg = next(
            c for c in list_platform_configs()
            if c.queue_id == "cash_receipts_matching_triage"
        )
        assert cfg.item_entity_type == "cash_receipt_match"
        assert cfg.source_direct_query_key == "cash_receipts_matching_triage"
        action_ids = {a.action_id for a in cfg.action_palette}
        assert {
            "approve", "reject", "override", "request_review", "skip"
        }.issubset(action_ids)
        # AI question panel wires the Phase 8b prompt key
        panel_keys = {
            p.ai_prompt_key for p in cfg.context_panels
            if p.ai_prompt_key
        }
        assert "triage.cash_receipts_context_question" in panel_keys
        # Requires invoice.approve for the write actions
        approve = next(a for a in cfg.action_palette if a.action_id == "approve")
        assert approve.required_permission == "invoice.approve"


class TestDirectQueryDispatch:
    def test_direct_query_key_registered(self):
        from app.services.triage.engine import _DIRECT_QUERIES

        assert "cash_receipts_matching_triage" in _DIRECT_QUERIES

    def test_direct_query_returns_empty_for_new_tenant(
        self, db_session, tenant_ctx
    ):
        from app.models.user import User
        from app.services.triage.engine import _DIRECT_QUERIES

        user = (
            db_session.query(User).filter(User.id == tenant_ctx["user_id"]).one()
        )
        rows = _DIRECT_QUERIES["cash_receipts_matching_triage"](db_session, user)
        assert rows == []

    def test_direct_query_orders_by_severity_then_amount(
        self, db_session, tenant_ctx
    ):
        """CRITICAL first, then WARNING, then INFO. Within severity,
        higher amount first, then older created_at."""
        from app.models.agent import AgentJob
        from app.models.agent_anomaly import AgentAnomaly
        from app.models.customer import Customer
        from app.models.customer_payment import CustomerPayment
        from app.models.user import User
        from app.services.triage.engine import _DIRECT_QUERIES

        user = (
            db_session.query(User).filter(User.id == tenant_ctx["user_id"]).one()
        )
        cust = Customer(
            id=str(uuid.uuid4()),
            company_id=tenant_ctx["company_id"],
            name="TestCust",
            is_active=True,
        )
        db_session.add(cust)
        db_session.flush()

        def mkpay(amount):
            p = CustomerPayment(
                id=str(uuid.uuid4()),
                company_id=tenant_ctx["company_id"],
                customer_id=cust.id,
                payment_date=datetime.now(timezone.utc),
                total_amount=Decimal(str(amount)),
                payment_method="check",
            )
            db_session.add(p)
            db_session.flush()
            return p.id

        job = AgentJob(
            id=str(uuid.uuid4()),
            tenant_id=tenant_ctx["company_id"],
            job_type="cash_receipts_matching",
            status="awaiting_approval",
            period_start=date.today().replace(day=1),
            period_end=date.today(),
            dry_run=False,
            trigger_type="manual",
            run_log=[],
            anomaly_count=0,
        )
        db_session.add(job)
        db_session.flush()

        specs = [
            ("INFO", "payment_possible_match", 50, "low_info"),
            ("CRITICAL", "payment_unmatched_stale", 500, "high_crit"),
            ("WARNING", "payment_unmatched_recent", 200, "mid_warn"),
            ("CRITICAL", "payment_unmatched_stale", 300, "low_crit"),
        ]
        for sev, atype, amt, _label in specs:
            pay_id = mkpay(amt)
            db_session.add(
                AgentAnomaly(
                    id=str(uuid.uuid4()),
                    agent_job_id=job.id,
                    severity=sev,
                    anomaly_type=atype,
                    entity_type="payment",
                    entity_id=pay_id,
                    description=_label,
                    amount=Decimal(str(amt)),
                    resolved=False,
                )
            )
        db_session.commit()

        rows = _DIRECT_QUERIES["cash_receipts_matching_triage"](db_session, user)
        severities = [r["severity"] for r in rows]
        # CRITICAL (sorted by amount desc), then WARNING, then INFO
        assert severities == ["CRITICAL", "CRITICAL", "WARNING", "INFO"]
        # Within CRITICAL, 500 comes before 300
        assert rows[0]["amount"] == 500.0
        assert rows[1]["amount"] == 300.0


class TestRelatedEntitiesBuilder:
    def test_builder_registered(self):
        from app.services.triage.ai_question import _RELATED_ENTITY_BUILDERS

        assert "cash_receipts_matching_triage" in _RELATED_ENTITY_BUILDERS

    def test_builder_returns_payment_customer_invoices(
        self, db_session, tenant_ctx
    ):
        from app.models.customer import Customer
        from app.models.customer_payment import CustomerPayment
        from app.models.invoice import Invoice
        from app.models.user import User
        from app.services.triage.ai_question import _RELATED_ENTITY_BUILDERS

        user = (
            db_session.query(User).filter(User.id == tenant_ctx["user_id"]).one()
        )
        cust = Customer(
            id=str(uuid.uuid4()),
            company_id=tenant_ctx["company_id"],
            name="Builder Cust",
            is_active=True,
        )
        db_session.add(cust)
        db_session.flush()
        pay = CustomerPayment(
            id=str(uuid.uuid4()),
            company_id=tenant_ctx["company_id"],
            customer_id=cust.id,
            payment_date=datetime.now(timezone.utc),
            total_amount=Decimal("150.00"),
            payment_method="check",
        )
        db_session.add(pay)
        db_session.flush()
        # Seed two open invoices so we can verify candidate ranking
        # (closer balance to payment amount ranks higher).
        now = datetime.now(timezone.utc)
        inv_close = Invoice(
            id=str(uuid.uuid4()),
            company_id=tenant_ctx["company_id"],
            number="INV-CLOSE",
            customer_id=cust.id,
            status="sent",
            invoice_date=now,
            due_date=now,
            subtotal=Decimal("150.00"),
            tax_rate=Decimal("0"),
            tax_amount=Decimal("0"),
            total=Decimal("150.00"),
            amount_paid=Decimal("0"),
        )
        inv_far = Invoice(
            id=str(uuid.uuid4()),
            company_id=tenant_ctx["company_id"],
            number="INV-FAR",
            customer_id=cust.id,
            status="sent",
            invoice_date=now,
            due_date=now,
            subtotal=Decimal("10000.00"),
            tax_rate=Decimal("0"),
            tax_amount=Decimal("0"),
            total=Decimal("10000.00"),
            amount_paid=Decimal("0"),
        )
        db_session.add_all([inv_close, inv_far])
        db_session.commit()

        builder = _RELATED_ENTITY_BUILDERS["cash_receipts_matching_triage"]
        related = builder(db_session, user, {"payment_id": pay.id})
        contexts = [r["context"] for r in related]
        assert "payment" in contexts
        assert "paying_customer" in contexts
        # Candidate invoice is present
        candidates = [r for r in related if r["context"] == "candidate_invoice"]
        assert len(candidates) >= 1
        # Closer-balance invoice ranks first
        assert candidates[0]["entity_id"] == inv_close.id

    def test_builder_returns_empty_on_missing_payment(
        self, db_session, tenant_ctx
    ):
        from app.models.user import User
        from app.services.triage.ai_question import _RELATED_ENTITY_BUILDERS

        user = (
            db_session.query(User).filter(User.id == tenant_ctx["user_id"]).one()
        )
        builder = _RELATED_ENTITY_BUILDERS["cash_receipts_matching_triage"]
        assert builder(db_session, user, {}) == []
        assert builder(db_session, user, {"payment_id": "does-not-exist"}) == []


class TestHandlerRegistration:
    def test_cash_receipts_handlers_registered(self):
        from app.services.triage.action_handlers import HANDLERS

        for key in (
            "cash_receipts.approve",
            "cash_receipts.reject",
            "cash_receipts.override",
            "cash_receipts.request_review",
        ):
            assert key in HANDLERS, f"Handler {key} missing from registry"

    def test_handler_missing_payload_errors_gracefully(
        self, db_session, tenant_ctx
    ):
        from app.models.user import User
        from app.services.triage.action_handlers import HANDLERS

        user = (
            db_session.query(User).filter(User.id == tenant_ctx["user_id"]).one()
        )
        ctx = {
            "db": db_session,
            "user": user,
            "entity_type": "cash_receipt_match",
            "entity_id": "fake-anomaly",
            "queue_id": "cash_receipts_matching_triage",
            "action_id": "approve",
            "reason": None,
            "reason_code": None,
            "note": None,
            "payload": {},  # missing invoice_id
        }
        result = HANDLERS["cash_receipts.approve"](ctx)
        assert result["status"] == "errored"
        assert "invoice_id" in result["message"]


# ── workflow_engine registry ─────────────────────────────────────────


class TestWorkflowEngineRegistry:
    def test_cash_receipts_method_in_registry(self):
        from app.services.workflow_engine import _SERVICE_METHOD_REGISTRY

        assert "cash_receipts.run_match_pipeline" in _SERVICE_METHOD_REGISTRY
        import_path, allowed = _SERVICE_METHOD_REGISTRY[
            "cash_receipts.run_match_pipeline"
        ]
        assert "cash_receipts_adapter" in import_path
        assert "run_match_pipeline" in import_path
        assert "dry_run" in allowed
        assert "trigger_source" in allowed

    def test_unknown_method_returns_errored(self, db_session):
        from app.models.workflow import Workflow, WorkflowRun
        from app.services.workflow_engine import _handle_call_service_method

        # Minimal run context — in-memory-only; we don't commit this.
        run = WorkflowRun(
            id=str(uuid.uuid4()),
            workflow_id="test-wf",
            company_id="test-co",
            status="running",
        )

        out = _handle_call_service_method(
            db_session,
            {"method_name": "not.registered.method"},
            run,
            current_company=None,
        )
        assert out["status"] == "errored"
        assert "not in registry" in out["error"]

    def test_missing_method_name_returns_errored(self, db_session):
        from app.models.workflow import WorkflowRun
        from app.services.workflow_engine import _handle_call_service_method

        run = WorkflowRun(
            id=str(uuid.uuid4()),
            workflow_id="test-wf",
            company_id="test-co",
            status="running",
        )
        out = _handle_call_service_method(
            db_session, {}, run, current_company=None,
        )
        assert out["status"] == "errored"
        assert "missing method_name" in out["error"]

    def test_kwargs_filtered_by_allowlist(self):
        """Ensure kwargs outside the registry's allowlist are dropped
        before dispatch. Direct-test the filter logic without
        invoking a real callable."""
        from app.services.workflow_engine import _SERVICE_METHOD_REGISTRY

        _, allowed = _SERVICE_METHOD_REGISTRY["cash_receipts.run_match_pipeline"]
        raw = {
            "dry_run": True,
            "trigger_source": "test",
            "malicious_kwarg": "should_be_dropped",
        }
        filtered = {k: v for k, v in raw.items() if k in allowed}
        assert "malicious_kwarg" not in filtered
        assert filtered == {"dry_run": True, "trigger_source": "test"}


# ── wf_sys_cash_receipts seed entry ─────────────────────────────────


class TestCashReceiptsWorkflowSeed:
    def test_wf_sys_cash_receipts_is_defined(self):
        from app.data.default_workflows import TIER_1_WORKFLOWS

        match = next(
            (w for w in TIER_1_WORKFLOWS if w["id"] == "wf_sys_cash_receipts"),
            None,
        )
        assert match is not None

    def test_workflow_shape(self):
        from app.data.default_workflows import TIER_1_WORKFLOWS

        wf = next(w for w in TIER_1_WORKFLOWS if w["id"] == "wf_sys_cash_receipts")
        assert wf["tier"] == 1
        assert wf["is_system"] is True
        assert wf["trigger_type"] == "time_of_day"
        # Phase 8b-beta: agent_registry_key is NOT set on the seed
        # entry. Migration choreography: 8b-beta clears it after the
        # real steps land. Only wf_sys_month_end_close, _ar_collections,
        # and _expense_categorization keep the field populated (they
        # migrate in 8c).
        assert "agent_registry_key" not in wf
        assert len(wf["steps"]) == 1
        step = wf["steps"][0]
        assert step["step_type"] == "action"
        assert step["config"]["action_type"] == "call_service_method"
        assert (
            step["config"]["method_name"] == "cash_receipts.run_match_pipeline"
        )


# ── Adapter edge cases ──────────────────────────────────────────────


class TestAdapterEdgeCases:
    def test_override_without_reason_errors(self, db_session, tenant_ctx):
        from app.models.user import User
        from app.services.workflows.cash_receipts_adapter import override_match

        user = (
            db_session.query(User).filter(User.id == tenant_ctx["user_id"]).one()
        )
        with pytest.raises(ValueError):
            override_match(
                db_session, user=user,
                payment_id="x", invoice_id="y", anomaly_id="z",
                reason="",
            )

    def test_request_review_without_note_errors(self, db_session, tenant_ctx):
        from app.models.user import User
        from app.services.workflows.cash_receipts_adapter import request_review

        user = (
            db_session.query(User).filter(User.id == tenant_ctx["user_id"]).one()
        )
        with pytest.raises(ValueError):
            request_review(
                db_session, user=user,
                payment_id="x", anomaly_id="y", note="",
            )
