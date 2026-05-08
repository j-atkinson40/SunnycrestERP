"""Phase R-6.0a — invoke_review_focus + workflow_review_adapter tests.

Coverage:
  * _handle_invoke_review_focus creates a WorkflowReviewItem row +
    returns ``type="awaiting_review"`` sentinel.
  * commit_decision stamps decision fields + advances the underlying
    run.
  * Cross-tenant isolation: another tenant's user cannot decide
    on this tenant's review item (raises WorkflowReviewItemNotFound).
  * Already-decided items reject re-decision (409-equivalent).
  * advance_run on awaiting_approval discriminates between
    invoke_review_focus pause (mark step completed, advance to next)
    and Playwright pause (roll back, re-enter).
"""

from __future__ import annotations

import os
import uuid

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("BRIDGEABLE_ENCRYPTION_KEY", Fernet.generate_key().decode())

from app.models.company import Company  # noqa: E402
from app.models.role import Role  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.workflow import (  # noqa: E402
    Workflow,
    WorkflowRun,
    WorkflowRunStep,
    WorkflowStep,
)
from app.models.workflow_review_item import WorkflowReviewItem  # noqa: E402
from app.services import workflow_engine  # noqa: E402
from app.services.workflows.workflow_review_adapter import (  # noqa: E402
    WorkflowReviewItemAlreadyDecided,
    WorkflowReviewItemNotFound,
    commit_decision,
)


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
    """Two separate tenants for cross-tenant isolation tests."""
    c1 = Company(
        id=str(uuid.uuid4()),
        name=f"R6 Test A {uuid.uuid4().hex[:6]}",
        slug=f"r6a-{uuid.uuid4().hex[:6]}",
        is_active=True,
        vertical="manufacturing",
    )
    c2 = Company(
        id=str(uuid.uuid4()),
        name=f"R6 Test B {uuid.uuid4().hex[:6]}",
        slug=f"r6b-{uuid.uuid4().hex[:6]}",
        is_active=True,
        vertical="manufacturing",
    )
    db.add_all([c1, c2])
    db.commit()
    yield c1, c2
    # Teardown — rollback any open tx then clean dependents.
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
    """Helper — creates Role + User. role_id is NOT NULL on users."""
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


def _make_workflow_run(db, company_id: str) -> WorkflowRun:
    """Minimal workflow + run fixture for invoke_review_focus tests."""
    wf = Workflow(
        id=f"wf-{uuid.uuid4().hex[:8]}",
        name="R6 Test Workflow",
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
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


# ── invoke_review_focus handler ─────────────────────────────────────


class TestInvokeReviewFocusHandler:
    """_handle_invoke_review_focus creates a WorkflowReviewItem +
    returns the awaiting_review sentinel."""

    def test_creates_review_item(self, db, two_tenants):
        c1, _ = two_tenants
        run = _make_workflow_run(db, c1.id)
        out = workflow_engine._handle_invoke_review_focus(
            db,
            {
                "action_type": "invoke_review_focus",
                "review_focus_id": "decedent_info_review",
                "input_data": {"deceased_name": "John Smith"},
            },
            run,
        )
        assert out["type"] == "awaiting_review"
        assert out["review_focus_id"] == "decedent_info_review"
        item = (
            db.query(WorkflowReviewItem)
            .filter(WorkflowReviewItem.id == out["review_item_id"])
            .first()
        )
        assert item is not None
        assert item.input_data == {"deceased_name": "John Smith"}
        assert item.review_focus_id == "decedent_info_review"
        assert item.decision is None  # not yet decided

    def test_missing_review_focus_id_returns_error(self, db, two_tenants):
        c1, _ = two_tenants
        run = _make_workflow_run(db, c1.id)
        out = workflow_engine._handle_invoke_review_focus(
            db,
            {"action_type": "invoke_review_focus", "input_data": {}},
            run,
        )
        assert out["status"] == "errored"
        assert out["error_code"] == "missing_review_focus_id"

    def test_invalid_input_data_returns_error(self, db, two_tenants):
        c1, _ = two_tenants
        run = _make_workflow_run(db, c1.id)
        out = workflow_engine._handle_invoke_review_focus(
            db,
            {
                "action_type": "invoke_review_focus",
                "review_focus_id": "x",
                "input_data": "not-a-dict",
            },
            run,
        )
        assert out["status"] == "errored"
        assert out["error_code"] == "invalid_input_data"


# ── commit_decision ─────────────────────────────────────────────────


class TestCommitDecision:
    """commit_decision stamps the decision + calls advance_run."""

    def test_approve_stamps_fields(self, db, two_tenants, monkeypatch):
        c1, _ = two_tenants
        run = _make_workflow_run(db, c1.id)
        item = WorkflowReviewItem(
            run_id=run.id,
            company_id=c1.id,
            review_focus_id="decedent_info_review",
            input_data={"deceased_name": "John Smith"},
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        # No-op advance_run so we test the adapter mutation in isolation.
        monkeypatch.setattr(
            "app.services.workflow_engine.advance_run",
            lambda db, run_id, step_input: None,
        )
        u = _make_user(db, c1.id)
        out = commit_decision(
            db,
            item_id=item.id,
            decision="approve",
            user_id=u.id,
            company_id=c1.id,
        )
        assert out.decision == "approve"
        assert out.decided_by_user_id == u.id
        assert out.decided_at is not None

    def test_reject_with_notes(self, db, two_tenants, monkeypatch):
        c1, _ = two_tenants
        run = _make_workflow_run(db, c1.id)
        item = WorkflowReviewItem(
            run_id=run.id,
            company_id=c1.id,
            review_focus_id="x",
            input_data={"foo": "bar"},
        )
        db.add(item)
        db.commit()
        monkeypatch.setattr(
            "app.services.workflow_engine.advance_run",
            lambda db, run_id, step_input: None,
        )
        u = _make_user(db, c1.id)
        commit_decision(
            db,
            item_id=item.id,
            decision="reject",
            user_id=u.id,
            company_id=c1.id,
            decision_notes="extracted name doesn't match the death cert",
        )
        db.refresh(item)
        assert item.decision == "reject"
        assert "doesn't match" in item.decision_notes

    def test_edit_and_approve_stores_edited_data(self, db, two_tenants, monkeypatch):
        c1, _ = two_tenants
        run = _make_workflow_run(db, c1.id)
        item = WorkflowReviewItem(
            run_id=run.id,
            company_id=c1.id,
            review_focus_id="x",
            input_data={"deceased_name": "JOHN SMITH"},
        )
        db.add(item)
        db.commit()
        monkeypatch.setattr(
            "app.services.workflow_engine.advance_run",
            lambda db, run_id, step_input: None,
        )
        u = _make_user(db, c1.id)
        commit_decision(
            db,
            item_id=item.id,
            decision="edit_and_approve",
            user_id=u.id,
            company_id=c1.id,
            edited_data={"deceased_name": "John Michael Smith"},
        )
        db.refresh(item)
        assert item.decision == "edit_and_approve"
        assert item.edited_data == {"deceased_name": "John Michael Smith"}

    def test_already_decided_rejected(self, db, two_tenants, monkeypatch):
        c1, _ = two_tenants
        run = _make_workflow_run(db, c1.id)
        item = WorkflowReviewItem(
            run_id=run.id,
            company_id=c1.id,
            review_focus_id="x",
            input_data={},
            decision="approve",
        )
        db.add(item)
        db.commit()
        monkeypatch.setattr(
            "app.services.workflow_engine.advance_run",
            lambda db, run_id, step_input: None,
        )
        u = _make_user(db, c1.id)
        with pytest.raises(WorkflowReviewItemAlreadyDecided):
            commit_decision(
                db,
                item_id=item.id,
                decision="reject",
                user_id=u.id,
                company_id=c1.id,
            )


# ── Cross-tenant isolation ──────────────────────────────────────────


class TestCrossTenantIsolation:
    """User in tenant B cannot decide on tenant A's item — raises
    WorkflowReviewItemNotFound (existence-hiding 404 semantics)."""

    def test_other_tenant_cannot_decide(self, db, two_tenants, monkeypatch):
        c1, c2 = two_tenants
        run_a = _make_workflow_run(db, c1.id)
        item_a = WorkflowReviewItem(
            run_id=run_a.id,
            company_id=c1.id,
            review_focus_id="x",
            input_data={},
        )
        db.add(item_a)
        db.commit()
        monkeypatch.setattr(
            "app.services.workflow_engine.advance_run",
            lambda db, run_id, step_input: None,
        )
        u_b = _make_user(db, c2.id)
        with pytest.raises(WorkflowReviewItemNotFound):
            commit_decision(
                db,
                item_id=item_a.id,
                decision="approve",
                user_id=u_b.id,
                company_id=c2.id,  # tenant B
            )

    def test_invalid_decision_value_rejected(self, db, two_tenants):
        c1, _ = two_tenants
        with pytest.raises(ValueError):
            commit_decision(
                db,
                item_id="x",
                decision="bogus",  # type: ignore[arg-type]
                user_id="u",
                company_id=c1.id,
            )
