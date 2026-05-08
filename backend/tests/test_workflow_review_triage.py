"""Phase R-6.0a — workflow_review_triage queue + decide endpoint tests.

Coverage:
  * platform_default _workflow_review_triage queue registered in
    the canonical singleton.
  * _dq_workflow_review surfaces pending items only (decision IS NULL),
    oldest first, tenant-scoped.
  * action_handlers HANDLERS map exposes the 3 workflow_review entries.
  * /api/v1/triage/workflow-review/{item_id}/decide endpoint flows
    through the canonical adapter + 404s on cross-tenant + 409s on
    already-decided.
"""

from __future__ import annotations

import os
import uuid

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("BRIDGEABLE_ENCRYPTION_KEY", Fernet.generate_key().decode())

from app.api.deps import get_current_user  # noqa: E402
from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.role import Role  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.workflow import Workflow, WorkflowRun  # noqa: E402
from app.models.workflow_review_item import WorkflowReviewItem  # noqa: E402
from app.services.triage import action_handlers, platform_defaults, registry  # noqa: E402
from app.services.triage.engine import _DIRECT_QUERIES  # noqa: E402


DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql://localhost:5432/bridgeable_dev"),
)
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def two_tenants(db):
    c1 = Company(
        id=str(uuid.uuid4()),
        name=f"R6 Triage A {uuid.uuid4().hex[:6]}",
        slug=f"r6ta-{uuid.uuid4().hex[:6]}",
        is_active=True,
        vertical="manufacturing",
    )
    c2 = Company(
        id=str(uuid.uuid4()),
        name=f"R6 Triage B {uuid.uuid4().hex[:6]}",
        slug=f"r6tb-{uuid.uuid4().hex[:6]}",
        is_active=True,
        vertical="manufacturing",
    )
    db.add_all([c1, c2])
    db.commit()
    yield c1, c2
    db.rollback()
    for t in [
        "workflow_review_items",
        "workflow_run_steps",
        "workflow_runs",
        "users",
        "roles",
        "workflows",
    ]:
        for cid in (c1.id, c2.id):
            try:
                db.execute(
                    sql_text(f"DELETE FROM {t} WHERE company_id = :cid"),
                    {"cid": cid},
                )
                db.commit()
            except Exception:
                db.rollback()
    for c in (c1, c2):
        try:
            db.delete(c)
            db.commit()
        except Exception:
            db.rollback()


def _make_user(db, company_id: str) -> User:
    r = Role(
        id=str(uuid.uuid4()),
        company_id=company_id,
        name="Admin",
        slug="admin",
        is_system=True,
    )
    db.add(r)
    db.commit()
    u = User(
        id=str(uuid.uuid4()),
        email=f"u-{uuid.uuid4().hex[:6]}@x.test",
        hashed_password="x",
        first_name="A",
        last_name="B",
        company_id=company_id,
        role_id=r.id,
        is_active=True,
    )
    db.add(u)
    db.commit()
    return u


def _make_run_and_item(
    db,
    company_id: str,
    *,
    decision: str | None = None,
    review_focus_id: str = "decedent_info_review",
) -> WorkflowReviewItem:
    wf = Workflow(
        id=f"wf-{uuid.uuid4().hex[:8]}",
        name="R6 Triage Test Workflow",
        company_id=company_id,
        vertical="manufacturing",
        tier=4,
        scope="tenant",
        is_active=True,
        is_coming_soon=False,
        trigger_type="manual",
        trigger_config={},
    )
    db.add(wf)
    db.commit()
    run = WorkflowRun(
        id=str(uuid.uuid4()),
        workflow_id=wf.id,
        company_id=company_id,
        triggered_by_user_id=None,
        trigger_source="test",
        status="awaiting_approval" if decision is None else "running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    item = WorkflowReviewItem(
        run_id=run.id,
        company_id=company_id,
        review_focus_id=review_focus_id,
        input_data={"deceased_name": "John Smith"},
        decision=decision,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


# ── Platform default registration ───────────────────────────────────


def _get_platform_cfg(queue_id: str):
    for cfg in registry.list_platform_configs():
        if cfg.queue_id == queue_id:
            return cfg
    return None


class TestPlatformDefaultQueue:
    """workflow_review_triage queue registered + canonically shaped."""

    def test_queue_registered(self):
        cfg = _get_platform_cfg("workflow_review_triage")
        assert cfg is not None
        assert cfg.queue_id == "workflow_review_triage"
        assert cfg.source_direct_query_key == "workflow_review"
        assert cfg.item_entity_type == "workflow_review_item"

    def test_queue_has_three_canonical_actions(self):
        cfg = _get_platform_cfg("workflow_review_triage")
        action_ids = {a.action_id for a in cfg.action_palette}
        assert {"approve", "reject", "edit_and_approve"} <= action_ids

    def test_queue_has_no_ai_panel(self):
        """Phase 8d precedent — review-style queues do NOT carry
        AI question panels."""
        cfg = _get_platform_cfg("workflow_review_triage")
        from app.services.triage.types import ContextPanelType

        panel_types = {p.panel_type for p in cfg.context_panels}
        assert ContextPanelType.AI_QUESTION not in panel_types

    def test_queue_is_cross_vertical(self):
        cfg = _get_platform_cfg("workflow_review_triage")
        assert cfg.required_vertical is None
        assert cfg.permissions == []


# ── Direct query builder ────────────────────────────────────────────


class TestDirectQuery:
    """_dq_workflow_review surfaces pending-only, tenant-scoped, oldest first."""

    def test_registered_in_dispatch_table(self):
        assert "workflow_review" in _DIRECT_QUERIES

    def test_returns_pending_only(self, db, two_tenants):
        c1, _ = two_tenants
        u = _make_user(db, c1.id)
        # One pending, one already decided.
        _make_run_and_item(db, c1.id, decision=None)
        _make_run_and_item(db, c1.id, decision="approve")

        rows = _DIRECT_QUERIES["workflow_review"](db, u)
        # Only pending ones surface.
        assert len(rows) == 1

    def test_tenant_isolation(self, db, two_tenants):
        c1, c2 = two_tenants
        u_a = _make_user(db, c1.id)
        u_b = _make_user(db, c2.id)
        _make_run_and_item(db, c1.id)
        _make_run_and_item(db, c2.id)
        rows_a = _DIRECT_QUERIES["workflow_review"](db, u_a)
        rows_b = _DIRECT_QUERIES["workflow_review"](db, u_b)
        # Each tenant sees exactly one item — their own.
        assert len(rows_a) == 1
        assert len(rows_b) == 1


# ── Action handler registry ─────────────────────────────────────────


class TestHandlerRegistry:
    """All 3 workflow_review handlers registered + callable."""

    def test_three_handlers_registered(self):
        keys = action_handlers.list_handler_keys()
        assert "workflow_review.approve" in keys
        assert "workflow_review.reject" in keys
        assert "workflow_review.edit_and_approve" in keys


# ── Decide endpoint ─────────────────────────────────────────────────


class TestDecideEndpoint:
    """POST /api/v1/triage/workflow-review/{item_id}/decide round-trip."""

    def test_approve_round_trip(self, db, two_tenants, monkeypatch):
        c1, _ = two_tenants
        u = _make_user(db, c1.id)
        item = _make_run_and_item(db, c1.id)
        # Stub advance_run so the underlying workflow run lookup
        # doesn't try to walk steps.
        monkeypatch.setattr(
            "app.services.workflow_engine.advance_run",
            lambda db, run_id, step_input: None,
        )

        def _override_user():
            return u

        def _override_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_current_user] = _override_user
        app.dependency_overrides[get_db] = _override_db
        try:
            client = TestClient(app)
            r = client.post(
                f"/api/v1/triage/workflow-review/{item.id}/decide",
                json={"decision": "approve"},
            )
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["decision"] == "approve"
            assert data["item_id"] == item.id
            assert data["review_focus_id"] == item.review_focus_id
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)

    def test_cross_tenant_returns_404(self, db, two_tenants, monkeypatch):
        c1, c2 = two_tenants
        u_b = _make_user(db, c2.id)
        item_a = _make_run_and_item(db, c1.id)
        monkeypatch.setattr(
            "app.services.workflow_engine.advance_run",
            lambda db, run_id, step_input: None,
        )

        def _override_user():
            return u_b

        def _override_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_current_user] = _override_user
        app.dependency_overrides[get_db] = _override_db
        try:
            client = TestClient(app)
            r = client.post(
                f"/api/v1/triage/workflow-review/{item_a.id}/decide",
                json={"decision": "approve"},
            )
            assert r.status_code == 404, r.text
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)

    def test_already_decided_returns_409(self, db, two_tenants, monkeypatch):
        c1, _ = two_tenants
        u = _make_user(db, c1.id)
        item = _make_run_and_item(db, c1.id, decision="approve")
        monkeypatch.setattr(
            "app.services.workflow_engine.advance_run",
            lambda db, run_id, step_input: None,
        )

        def _override_user():
            return u

        def _override_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_current_user] = _override_user
        app.dependency_overrides[get_db] = _override_db
        try:
            client = TestClient(app)
            r = client.post(
                f"/api/v1/triage/workflow-review/{item.id}/decide",
                json={"decision": "reject", "decision_notes": "wrong data"},
            )
            assert r.status_code == 409, r.text
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)

    def test_edit_and_approve_round_trip(self, db, two_tenants, monkeypatch):
        c1, _ = two_tenants
        u = _make_user(db, c1.id)
        item = _make_run_and_item(db, c1.id)
        monkeypatch.setattr(
            "app.services.workflow_engine.advance_run",
            lambda db, run_id, step_input: None,
        )

        def _override_user():
            return u

        def _override_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_current_user] = _override_user
        app.dependency_overrides[get_db] = _override_db
        try:
            client = TestClient(app)
            r = client.post(
                f"/api/v1/triage/workflow-review/{item.id}/decide",
                json={
                    "decision": "edit_and_approve",
                    "edited_data": {"deceased_name": "John Michael Smith"},
                },
            )
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["decision"] == "edit_and_approve"
            db.refresh(item)
            assert item.edited_data == {"deceased_name": "John Michael Smith"}
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)
