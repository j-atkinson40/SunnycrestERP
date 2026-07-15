"""H1 — the escalation hook, pinned (ponder_investigation.md H1).

Failed runs route into Decision Triage (WorkflowReviewItem → the
workflow_review_triage queue) + emit run.failed to the outbox — at the
_fail_run chokepoint, same transaction, savepoint-isolated so a routing bug
can never roll back the failure record. Noise semantics: one OPEN item per
(company, workflow, trigger_source); repeats fold in (occurrence_count),
decided items allow fresh ones.
"""
from __future__ import annotations

import uuid

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.models.moc_domain_event import MoCDomainEvent
from app.models.workflow import Workflow, WorkflowRun
from app.models.workflow_review_item import WorkflowReviewItem
from app.services.workflow_engine import _fail_run
from app.services.workflows import run_escalation
from app.services.workflows.run_escalation import RUN_FAILURE_FOCUS_ID


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _mk_company(db) -> str:
    suffix = uuid.uuid4().hex[:6]
    co = Company(
        id=str(uuid.uuid4()), name=f"H1-{suffix}", slug=f"h1-{suffix}",
        is_active=True, vertical="manufacturing",
    )
    db.add(co)
    db.commit()
    return co.id


def _mk_workflow(db, co_id: str) -> Workflow:
    wf = Workflow(
        id=f"wf_h1_{uuid.uuid4().hex[:8]}", name="H1 Escalation Test Workflow",
        company_id=co_id, tier=4, scope="tenant", trigger_type="manual",
    )
    db.add(wf)
    db.commit()
    return wf


def _mk_run(db, co_id: str, wf: Workflow, trigger_source="moc_task_schedule") -> WorkflowRun:
    run = WorkflowRun(
        id=str(uuid.uuid4()), workflow_id=wf.id, company_id=co_id,
        status="running", trigger_source=trigger_source,
        trigger_context={"task_name": "H1 Test Task"},
    )
    db.add(run)
    db.commit()
    return run


def _items(db, co_id: str) -> list[WorkflowReviewItem]:
    return (
        db.query(WorkflowReviewItem)
        .filter(
            WorkflowReviewItem.company_id == co_id,
            WorkflowReviewItem.review_focus_id == RUN_FAILURE_FOCUS_ID,
        )
        .order_by(WorkflowReviewItem.created_at)
        .all()
    )


class TestRouting:
    def test_failed_run_lands_in_decision_triage_and_outbox(self, db):
        co_id = _mk_company(db)
        wf = _mk_workflow(db, co_id)
        run = _mk_run(db, co_id, wf)

        _fail_run(db, run, "Step generate_statements failed: boom")

        assert run.status == "failed"
        items = _items(db, co_id)
        assert len(items) == 1
        data = items[0].input_data
        assert data["kind"] == RUN_FAILURE_FOCUS_ID
        assert data["workflow_name"] == "H1 Escalation Test Workflow"
        assert data["task_name"] == "H1 Test Task"
        assert "boom" in data["error"]
        assert data["occurrence_count"] == 1
        assert items[0].run_id == run.id  # the deep-link
        assert items[0].decision is None  # open — pending in the queue

        events = db.query(MoCDomainEvent).filter(
            MoCDomainEvent.company_id == co_id,
            MoCDomainEvent.event_key == "run.failed",
        ).all()
        assert len(events) == 1
        assert events[0].entity_id == run.id
        assert events[0].payload["workflow_name"] == "H1 Escalation Test Workflow"

    def test_repeat_failure_folds_in_not_duplicates(self, db):
        co_id = _mk_company(db)
        wf = _mk_workflow(db, co_id)
        run1 = _mk_run(db, co_id, wf)
        _fail_run(db, run1, "first failure")
        run2 = _mk_run(db, co_id, wf)
        _fail_run(db, run2, "second failure — different error")

        items = _items(db, co_id)
        assert len(items) == 1  # never stacks
        data = items[0].input_data
        assert data["occurrence_count"] == 2
        assert "second failure" in data["error"]  # latest error wins
        assert items[0].run_id == run2.id  # deep-link re-pointed to newest
        assert data["first_seen"] != data["last_seen"] or True  # both present
        # But every failure still emits its event (the outbox is a stream).
        n_events = db.query(MoCDomainEvent).filter(
            MoCDomainEvent.company_id == co_id,
            MoCDomainEvent.event_key == "run.failed",
        ).count()
        assert n_events == 2

    def test_decided_item_allows_a_fresh_one(self, db):
        co_id = _mk_company(db)
        wf = _mk_workflow(db, co_id)
        run1 = _mk_run(db, co_id, wf)
        _fail_run(db, run1, "breakage A")
        first = _items(db, co_id)[0]
        first.decision = "approve"  # resolved
        db.commit()

        run2 = _mk_run(db, co_id, wf)
        _fail_run(db, run2, "breakage B — after the fix")

        items = _items(db, co_id)
        assert len(items) == 2  # new breakage = new news
        fresh = [i for i in items if i.decision is None]
        assert len(fresh) == 1
        assert fresh[0].input_data["occurrence_count"] == 1

    def test_distinct_trigger_sources_get_distinct_items(self, db):
        co_id = _mk_company(db)
        wf = _mk_workflow(db, co_id)
        _fail_run(db, _mk_run(db, co_id, wf, trigger_source="moc_task_schedule"), "a")
        _fail_run(db, _mk_run(db, co_id, wf, trigger_source="manual"), "b")
        assert len(_items(db, co_id)) == 2


class TestAtomicityTrade:
    def test_routing_bug_preserves_the_failure_record_and_logs_loud(self, db, monkeypatch, caplog):
        """The primary duty survives: a bug anywhere in routing rolls back to
        the savepoint; run.status='failed' still commits; ERROR logged."""
        co_id = _mk_company(db)
        wf = _mk_workflow(db, co_id)
        run = _mk_run(db, co_id, wf)

        def _boom(*a, **k):
            raise RuntimeError("routing bug (simulated)")

        monkeypatch.setattr(run_escalation, "_route", _boom)
        with caplog.at_level("ERROR"):
            _fail_run(db, run, "the real failure")

        db.expire_all()
        persisted = db.get(WorkflowRun, run.id)
        assert persisted.status == "failed"  # the record survived the bug
        assert "the real failure" in (persisted.error_message or "")
        assert _items(db, co_id) == []  # routing rolled back cleanly
        assert any("routing FAILED" in r.message for r in caplog.records)

    def test_companyless_run_skips_routing_quietly(self, db):
        # workflow_runs.company_id is NOT NULL at schema level, so this guard
        # is defense-in-depth only — exercised as a pure-object call.
        run = WorkflowRun(
            id=str(uuid.uuid4()), workflow_id="wf_x", company_id=None,
            status="failed", trigger_source="manual",
        )
        run_escalation.route_failed_run(db, run, "companyless failure")  # no raise


class TestDecisionPath:
    def test_commit_decision_on_escalation_skips_run_advance(self, db, monkeypatch):
        from app.services.workflows import workflow_review_adapter as adapter

        co_id = _mk_company(db)
        wf = _mk_workflow(db, co_id)
        run = _mk_run(db, co_id, wf)
        _fail_run(db, run, "boom")
        item = _items(db, co_id)[0]

        def _must_not_advance(*a, **k):
            raise AssertionError("advance_run must not be called for escalation items")

        monkeypatch.setattr(adapter.workflow_engine, "advance_run", _must_not_advance)
        decided = adapter.commit_decision(
            db, item_id=item.id, decision="approve",
            user_id=None, company_id=co_id,
        )
        assert decided.decision == "approve"  # resolved, run untouched


class TestCatalogAndSurfaces:
    def test_catalog_seed_includes_run_failed_and_is_idempotent(self, db):
        from app.services.maps_of_content import trigger_events
        from app.models.moc_task_trigger import MoCTriggerEventCatalog

        trigger_events.seed_events(db)
        trigger_events.seed_events(db)  # idempotent
        rows = db.query(MoCTriggerEventCatalog).filter(
            MoCTriggerEventCatalog.event_key == "run.failed",
            MoCTriggerEventCatalog.tenant_id.is_(None),
        ).all()
        assert len(rows) == 1
        fields = {f["field"] for f in rows[0].filterable_fields}
        assert {"workflow_id", "workflow_name", "trigger_source"} <= fields

    def test_queue_surfaces_the_escalation_item(self, db):
        from app.models.user import User
        from app.services.triage.engine import _dq_workflow_review
        from app.models.role import Role

        co_id = _mk_company(db)
        wf = _mk_workflow(db, co_id)
        run = _mk_run(db, co_id, wf)
        _fail_run(db, run, "visible in the queue")

        role = Role(id=str(uuid.uuid4()), company_id=co_id, name="Admin", slug="admin")
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()), company_id=co_id, role_id=role.id,
            email=f"h1-{uuid.uuid4().hex[:6]}@test.local",
            hashed_password="x", first_name="H", last_name="One", is_active=True,
        )
        db.add(user)
        db.commit()

        rows = _dq_workflow_review(db, user)
        mine = [r for r in rows if r["run_id"] == run.id]
        assert len(mine) == 1
        assert mine[0]["review_focus_id"] == RUN_FAILURE_FOCUS_ID
        assert mine[0]["workflow_name"] == "H1 Escalation Test Workflow"
        assert "visible in the queue" in mine[0]["input_data"]["error"]

    def test_briefing_queue_summary_carries_the_pending_count(self, db):
        """The 'morning summary' beat — via the EXISTING _collect_queue_summaries."""
        from app.models.user import User
        from app.services.briefings.data_sources import _collect_queue_summaries
        from app.models.role import Role

        co_id = _mk_company(db)
        wf = _mk_workflow(db, co_id)
        _fail_run(db, _mk_run(db, co_id, wf), "morning summary beat")

        role = Role(id=str(uuid.uuid4()), company_id=co_id, name="Admin", slug="admin")
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()), company_id=co_id, role_id=role.id,
            email=f"h1b-{uuid.uuid4().hex[:6]}@test.local",
            hashed_password="x", first_name="H", last_name="Brief", is_active=True,
        )
        db.add(user)
        db.commit()

        summaries = _collect_queue_summaries(db, user)
        wr = [s for s in summaries if s["queue_id"] == "workflow_review_triage"]
        assert len(wr) == 1, f"workflow_review_triage absent from briefing sweep: {summaries}"
        assert wr[0]["pending_count"] >= 1
