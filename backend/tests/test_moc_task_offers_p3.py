"""Tenant Ponder-Editor P3 — the fires strip + task-tier offer-reach pins.

THE BOUNDARY PIN (non-negotiable): editing a vertical-default task creates
ZERO offer rows — offers exist only through the deliberate publish moment.
Plus: offers per differing fork only (matching forks get no noise);
supersede per edge; ACCEPT NEVER PROMOTES (taking the standard's schedule
copies triggers at is_live=False even when the standard's are live);
per-field keep-mine; decline recallable; cross-tenant isolation with
not-found semantics; the fires strip company-scoped with the H1 review
link and the honest never-fired empty state.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.artifact_update import ArtifactPublish, ArtifactUpdateOffer
from app.models.moc_task_catalog import MoCTaskCatalog
from app.models.moc_task_trigger import MoCTaskTrigger
from app.models.workflow import Workflow, WorkflowRun, WorkflowStep
from app.models.workflow_template import WorkflowTemplate
from app.services.maps_of_content import task_offers
from app.services.maps_of_content.ponder import build_ponder_script, recent_fires
from app.services.maps_of_content.task_catalog import patch_task
from app.services.maps_of_content.task_fork import fork_task_for_tenant

VERT = "manufacturing"


@pytest.fixture
def db():
    s = SessionLocal()
    created = {"tasks": [], "templates": [], "workflows": [], "companies": []}
    s._p3 = created  # type: ignore[attr-defined]
    yield s
    s.rollback()
    task_ids = list(created["tasks"])
    if task_ids:
        s.execute(sql_text(
            "DELETE FROM artifact_update_offers WHERE target_slug = ANY(:t) "
            "OR source_slug = ANY(:t)"
        ), {"t": task_ids})
        s.execute(sql_text(
            "DELETE FROM artifact_publishes WHERE artifact_type = 'moc_task' "
            "AND source_slug = ANY(:t)"
        ), {"t": task_ids})
        s.execute(sql_text(
            "DELETE FROM moc_task_trigger WHERE task_catalog_id = ANY(:t)"
        ), {"t": task_ids})
        s.execute(sql_text("DELETE FROM moc_task_catalog WHERE id = ANY(:t)"), {"t": task_ids})
    for tpl in created["templates"]:
        s.execute(sql_text("DELETE FROM workflow_templates WHERE id = :t"), {"t": tpl})
    for cid in created["companies"]:
        s.execute(sql_text(
            "DELETE FROM workflow_enrollments WHERE company_id = :c"), {"c": cid})
    for wid in created["workflows"]:
        s.execute(sql_text(
            "DELETE FROM workflow_review_items WHERE run_id IN "
            "(SELECT id FROM workflow_runs WHERE workflow_id = :w)"
        ), {"w": wid})
        s.execute(sql_text(
            "DELETE FROM workflow_run_steps WHERE run_id IN "
            "(SELECT id FROM workflow_runs WHERE workflow_id = :w)"
        ), {"w": wid})
        s.execute(sql_text("DELETE FROM workflow_runs WHERE workflow_id = :w"), {"w": wid})
        s.execute(sql_text("DELETE FROM workflow_steps WHERE workflow_id = :w"), {"w": wid})
        s.execute(sql_text("DELETE FROM workflows WHERE id = :w"), {"w": wid})
    for cid in created["companies"]:
        s.execute(sql_text("DELETE FROM companies WHERE id = :c"), {"c": cid})
    s.commit()
    s.close()


def _mk_company(db, name: str) -> str:
    from app.models.company import Company

    suffix = uuid.uuid4().hex[:6]
    co = Company(id=str(uuid.uuid4()), name=f"{name}-{suffix}",
                 slug=f"{name.lower()}-{suffix}", is_active=True, vertical=VERT)
    db.add(co)
    db.flush()
    db._p3["companies"].append(co.id)
    return co.id


def _mk_default_task(db, *, live_trigger: bool = True) -> MoCTaskCatalog:
    """A vertical-default task with a mirror workflow + an ordinal schedule
    trigger (live by default — the accept-never-promotes raw material)."""
    suffix = uuid.uuid4().hex[:8]
    wf_id = f"wf_test_p3_{suffix}"
    db.add(Workflow(id=wf_id, company_id=None, name=f"P3 {suffix}", tier=1,
                    scope="core", trigger_type="scheduled",
                    trigger_config={"cron": "0 6 1 * *"}, is_active=True))
    db.add(WorkflowStep(workflow_id=wf_id, step_order=1, step_key="go",
                        step_type="action", config={"description": "Go"}))
    tpl = WorkflowTemplate(
        id=str(uuid.uuid4()), scope="vertical_default", vertical=VERT,
        workflow_type=f"p3_{suffix}", display_name=f"P3 {suffix}", version=1,
        is_active=True,
        canvas_state={"version": 1, "nodes": [
            {"id": "go", "type": "action", "label": "go",
             "config": {"description": "Go"}}], "edges": []},
        mirrored_from_workflow_id=wf_id,
    )
    db.add(tpl)
    db.flush()
    task = MoCTaskCatalog(
        scope="vertical_default", vertical=VERT, name=f"P3 Task {suffix}",
        description="The standard description.",
        workflow_template_id=tpl.id,
    )
    db.add(task)
    db.flush()
    db.add(MoCTaskTrigger(
        task_catalog_id=task.id, kind="schedule",
        config={"spec_kind": "ordinal_weekday", "ordinal": 1,
                "weekday": "mon", "time": "16:00"},
        is_live=live_trigger,
    ))
    db.commit()
    db._p3["workflows"].append(wf_id)
    db._p3["templates"].append(tpl.id)
    db._p3["tasks"].append(task.id)
    return task


def _fork(db, task: MoCTaskCatalog, company_id: str) -> MoCTaskCatalog:
    fork = fork_task_for_tenant(
        db, task_id=task.id, company_id=company_id, company_vertical=VERT,
    )
    db.commit()
    db._p3["tasks"].append(fork.id)
    return fork


class TestTheBoundary:
    def test_editing_a_default_creates_zero_offers(self, db):
        """THE PIN: plain edits are private; only the deliberate publish
        offers."""
        task = _mk_default_task(db)
        co = _mk_company(db, "TB")
        _fork(db, task, co)
        patch_task(db, task_id=task.id, description="Edited quietly.")
        db.commit()
        n = db.query(ArtifactUpdateOffer).filter(
            ArtifactUpdateOffer.source_slug == task.id).count()
        assert n == 0
        p = db.query(ArtifactPublish).filter(
            ArtifactPublish.source_slug == task.id).count()
        assert p == 0

    def test_publish_offers_only_differing_forks(self, db):
        task = _mk_default_task(db)
        co_same = _mk_company(db, "SAME")
        co_diff = _mk_company(db, "DIFF")
        _fork(db, task, co_same)          # stays identical
        fork_b = _fork(db, task, co_diff)
        patch_task(db, task_id=fork_b.id, description="Their own words.")
        db.commit()

        out = task_offers.publish_task_update(
            db, task_id=task.id, patch_notes="Standard refresh", actor_id=None)
        assert out["fork_count"] == 2
        assert out["offers_created"] == 1  # the matching fork gets NO noise
        offer = db.query(ArtifactUpdateOffer).filter(
            ArtifactUpdateOffer.source_slug == task.id).one()
        assert offer.target_slug == fork_b.id
        assert offer.target_tenant_id == co_diff
        assert offer.status == "pending"
        assert "description" in offer.derived_diff["fields"]

    def test_publish_supersedes_prior_live_offers(self, db):
        task = _mk_default_task(db)
        co = _mk_company(db, "SUP")
        fork = _fork(db, task, co)
        patch_task(db, task_id=fork.id, description="Mine.")
        db.commit()
        task_offers.publish_task_update(db, task_id=task.id, patch_notes=None, actor_id=None)
        first = db.query(ArtifactUpdateOffer).filter(
            ArtifactUpdateOffer.target_slug == fork.id).one()
        task_offers.publish_task_update(db, task_id=task.id, patch_notes=None, actor_id=None)
        db.refresh(first)
        assert first.status == "superseded"
        live = db.query(ArtifactUpdateOffer).filter(
            ArtifactUpdateOffer.target_slug == fork.id,
            ArtifactUpdateOffer.status == "pending").one()
        assert live.source_version_to == 2  # publish-count versions

    def test_publish_without_forks_refuses(self, db):
        task = _mk_default_task(db)
        with pytest.raises(task_offers.TaskOfferError):
            task_offers.publish_task_update(db, task_id=task.id, patch_notes=None, actor_id=None)


class TestAcceptDecline:
    def _diverged(self, db):
        """Default (live first-Monday trigger) + a fork whose schedule AND
        description the tenant changed."""
        task = _mk_default_task(db, live_trigger=True)
        co = _mk_company(db, "ACC")
        fork = _fork(db, task, co)
        patch_task(db, task_id=fork.id, description="Tenant words.")
        trig = fork.triggers[0]
        trig.config = {"spec_kind": "ordinal_weekday", "ordinal": "last",
                       "weekday": "fri", "time": "09:30"}
        db.commit()
        task_offers.publish_task_update(db, task_id=task.id, patch_notes="Back to Mondays", actor_id=None)
        offer = db.query(ArtifactUpdateOffer).filter(
            ArtifactUpdateOffer.target_slug == fork.id,
            ArtifactUpdateOffer.status == "pending").one()
        return task, co, fork, offer

    def test_diff_speaks_the_prose_grammar(self, db):
        _, _, _, offer = self._diverged(db)
        sched = offer.derived_diff["fields"]["schedule"]
        assert sched["from"] == ["The last Friday of every month at 9:30 AM"]
        assert sched["to"] == ["The first Monday of every month at 4:00 PM"]

    def test_accept_applies_and_never_promotes(self, db):
        task, co, fork, offer = self._diverged(db)
        out = task_offers.accept_offer(
            db, offer_id=offer.id, company_id=co, choices={}, actor_id=None)
        assert set(out["applied"]) == {"description", "schedule"}
        db.refresh(fork)
        assert fork.description == "The standard description."
        scheds = [t for t in fork.triggers if t.kind == "schedule"]
        assert len(scheds) == 1
        assert scheds[0].config["ordinal"] == 1 and scheds[0].config["weekday"] == "mon"
        # THE PIN: the standard's trigger is LIVE; the accepted copy is NOT.
        assert scheds[0].is_live is False
        db.refresh(offer)
        assert offer.status == "accepted"

    def test_per_field_keep_mine(self, db):
        task, co, fork, offer = self._diverged(db)
        out = task_offers.accept_offer(
            db, offer_id=offer.id, company_id=co,
            choices={"description": "keep"}, actor_id=None)
        assert out["kept"] == ["description"]
        db.refresh(fork)
        assert fork.description == "Tenant words."          # kept mine
        scheds = [t for t in fork.triggers if t.kind == "schedule"]
        assert scheds[0].config["weekday"] == "mon"          # took the standard

    def test_decline_is_recallable(self, db):
        task, co, fork, offer = self._diverged(db)
        task_offers.decline_offer(db, offer_id=offer.id, company_id=co, actor_id=None)
        db.refresh(offer)
        assert offer.status == "declined"
        # The badge state drops to the gap chip...
        state = task_offers.offer_states_for_forks(
            db, company_id=co, fork_task_ids=[fork.id])
        assert state[fork.id]["offer_status"] == "declined"
        # ...and accept still works from here (the recall path).
        out = task_offers.accept_offer(db, offer_id=offer.id, company_id=co, actor_id=None)
        assert "schedule" in out["applied"]

    def test_accept_superseded_points_at_latest(self, db):
        task, co, fork, offer = self._diverged(db)
        task_offers.publish_task_update(db, task_id=task.id, patch_notes=None, actor_id=None)
        with pytest.raises(task_offers.TaskOfferError) as exc:
            task_offers.accept_offer(db, offer_id=offer.id, company_id=co, actor_id=None)
        assert exc.value.latest_offer_id is not None

    def test_cross_tenant_isolation(self, db):
        task, co, fork, offer = self._diverged(db)
        other = _mk_company(db, "OTHER")
        # B's badge query never sees A's offer.
        assert task_offers.offer_states_for_forks(
            db, company_id=other, fork_task_ids=[fork.id]) == {}
        # B reading/deciding A's offer: NOT FOUND — never a hint.
        for fn in (task_offers.get_offer, task_offers.decline_offer):
            with pytest.raises(task_offers.TaskOfferError, match="not found"):
                fn(db, offer_id=offer.id, company_id=other)
        with pytest.raises(task_offers.TaskOfferError, match="not found"):
            task_offers.accept_offer(db, offer_id=offer.id, company_id=other)


class TestFiresStrip:
    def _runs(self, db, wf_id: str, company_id: str, *specs):
        for status, dry, ctx in specs:
            db.add(WorkflowRun(
                id=str(uuid.uuid4()), workflow_id=wf_id, company_id=company_id,
                status=status, trigger_source="moc_task_schedule",
                trigger_context=ctx or {},
                output_data={"__dry_run__": True} if dry else {},
            ))
        db.commit()

    def test_company_scoped_with_honest_badges(self, db):
        task = _mk_default_task(db)
        wf_id = task.workflow_template_id and db.get(
            WorkflowTemplate, task.workflow_template_id).mirrored_from_workflow_id
        co_a = _mk_company(db, "FA")
        co_b = _mk_company(db, "FB")
        self._runs(db, wf_id, co_a,
                   ("completed", True, {"event_key": "order.created"}),
                   ("completed", False, None))
        self._runs(db, wf_id, co_b, ("failed", False, None))

        fires_a = recent_fires(db, runtime_workflow_id=wf_id, company_id=co_a)
        assert len(fires_a) == 2  # THEIR fires only — B's failure absent
        assert {f["status"] for f in fires_a} == {"completed"}
        assert any(f["is_dry_run"] for f in fires_a)
        assert any(f["event_key"] == "order.created" for f in fires_a)

    def test_failed_fire_carries_the_h1_review_link(self, db):
        from app.models.workflow_review_item import WorkflowReviewItem

        task = _mk_default_task(db)
        wf_id = db.get(WorkflowTemplate, task.workflow_template_id).mirrored_from_workflow_id
        co = _mk_company(db, "FR")
        run = WorkflowRun(id=str(uuid.uuid4()), workflow_id=wf_id, company_id=co,
                          status="failed", trigger_source="schedule",
                          error_message="boom")
        db.add(run)
        db.flush()
        db.add(WorkflowReviewItem(
            run_id=run.id, company_id=co, review_focus_id="run_failure",
            input_data={"error": "boom"},
        ))
        db.commit()
        fires = recent_fires(db, runtime_workflow_id=wf_id, company_id=co)
        assert fires[0]["status"] == "failed"
        assert fires[0]["review_item_id"] is not None

    def test_never_fired_is_empty_honest(self, db):
        task = _mk_default_task(db)
        co = _mk_company(db, "FE")
        script = build_ponder_script(db, task.id, company_id=co)
        assert script["fires"] == []  # says so plainly — nothing fabricated

    def test_platform_read_carries_no_strip(self, db):
        task = _mk_default_task(db)
        script = build_ponder_script(db, task.id)
        assert script["fires"] is None
