"""Live event-fire (Canvas↔Runtime Bridge T-2.2c) — the first real EVENT-driven
action, proven on the benign marker substrate with the §6 compiled-only guard.

The event path now derives go_live from `_resolve_go_live` — the SAME single
source as the schedule path (is_live AND compiled). Asserted at the REAL
persisted effect (a moc_witness_marker row — it exists IFF the fire was live):

  1. PROMOTED COMPILED event-trigger → a matching event fires LIVE → a real,
     attributable marker row (the first real event-driven autonomous effect).
  2. PROMOTED MIRROR event-trigger → DRY-RUN (§6 — no marker) even is_live=True.
  3. UNPROMOTED → dry-run (no marker).
  4. LIVE fires ONCE — redelivering the same event does NOT double-fire (the
     (trigger, event) dedup holds for live fires).
  5. A LIVE failure records LOUDLY (status=failed + error_message).
  6. The witness seed ships the event-trigger UNPROMOTED + PRESERVES an
     operator promotion across re-runs.

State-immunity: fixture-scoped assertions (markers by company; runs by pair).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.company import Company
from app.models.moc_domain_event import MoCDomainEvent
from app.models.moc_task_catalog import MoCTaskCatalog
from app.models.moc_task_trigger import MoCTaskTrigger
from app.models.moc_witness_marker import MoCWitnessMarker
from app.models.workflow import Workflow, WorkflowRun
from app.models.workflow_template import WorkflowTemplate
from app.services.maps_of_content import triggers as triggers_svc
from app.services.maps_of_content.event_matcher import check_moc_domain_events

VERT = "manufacturing"


def _marker_canvas() -> dict:
    return {
        "version": 1, "trigger": {"type": "manual"},
        "nodes": [
            {"id": "n_start", "type": "start", "config": {}},
            {"id": "n_m", "type": "record_marker", "label": "Marker",
             "config": {"note": "event witness"}},
            {"id": "n_end", "type": "end", "config": {}},
        ],
        "edges": [
            {"id": "e1", "source": "n_start", "target": "n_m"},
            {"id": "e2", "source": "n_m", "target": "n_end"},
        ],
    }


@pytest.fixture
def env():
    s = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    company = Company(id=str(uuid.uuid4()), name="EvLive Co", slug=f"evlive-{suffix}",
                      vertical=VERT, timezone="America/New_York", is_active=True)
    s.add(company)
    draft = WorkflowTemplate(id=str(uuid.uuid4()), scope="vertical_default", vertical=VERT,
                             workflow_type=f"t22c_draft_{suffix}", display_name="T-2.2c Draft",
                             canvas_state=_marker_canvas(), version=1, is_active=True)
    src = Workflow(id=str(uuid.uuid4()), company_id=None, name="T-2.2c Source",
                   trigger_type="manual", scope="core", tier=1, is_active=True)
    s.add_all([draft, src])
    s.flush()
    mirror = WorkflowTemplate(id=str(uuid.uuid4()), scope="vertical_default", vertical=VERT,
                              workflow_type=f"t22c_mirror_{suffix}", display_name="T-2.2c Mirror",
                              canvas_state={"version": 1, "nodes": [], "edges": []}, version=1,
                              is_active=True, mirrored_from_workflow_id=src.id)
    s.add(mirror)
    s.flush()
    ctx = {"db": s, "company": company, "draft": draft, "mirror": mirror,
           "src_id": src.id, "task_ids": []}
    s.commit()
    yield ctx
    s.rollback()
    cid = company.id
    s.execute(sql_text("DELETE FROM moc_witness_marker WHERE company_id = :c"), {"c": cid})
    s.execute(sql_text(
        "DELETE FROM workflow_run_steps WHERE run_id IN "
        "(SELECT id FROM workflow_runs WHERE company_id = :c)"), {"c": cid})
    s.execute(sql_text("DELETE FROM workflow_runs WHERE company_id = :c"), {"c": cid})
    s.refresh(draft)
    if draft.compiled_workflow_id:
        cw = draft.compiled_workflow_id
        s.execute(sql_text("UPDATE workflow_templates SET compiled_workflow_id=NULL WHERE id=:t"), {"t": draft.id})
        s.execute(sql_text("DELETE FROM workflow_steps WHERE workflow_id=:w"), {"w": cw})
        s.execute(sql_text("DELETE FROM workflows WHERE id=:w"), {"w": cw})
    s.execute(sql_text("DELETE FROM moc_task_trigger WHERE task_catalog_id = ANY(:t)"),
              {"t": ctx["task_ids"] or [""]})
    s.execute(sql_text("DELETE FROM moc_task_catalog WHERE id = ANY(:t)"),
              {"t": ctx["task_ids"] or [""]})
    s.execute(sql_text("DELETE FROM moc_domain_event WHERE company_id = :c"), {"c": cid})
    s.execute(sql_text("DELETE FROM workflow_steps WHERE workflow_id = :w"), {"w": ctx["src_id"]})
    s.execute(sql_text("DELETE FROM workflow_templates WHERE id IN (:d, :m)"),
              {"d": draft.id, "m": mirror.id})
    s.execute(sql_text("DELETE FROM workflows WHERE id = :w"), {"w": ctx["src_id"]})
    s.execute(sql_text("DELETE FROM companies WHERE id = :c"), {"c": cid})
    s.commit()
    s.close()


EVENT_KEY = "witness.marker_requested"


def _mk_event_trigger(env, template, *, is_live: bool) -> MoCTaskTrigger:
    s = env["db"]
    task = MoCTaskCatalog(id=str(uuid.uuid4()), scope="tenant_override", vertical=VERT,
                          tenant_id=env["company"].id, name=f"EvLive {uuid.uuid4().hex[:6]}",
                          workflow_template_id=template.id, is_active=True)
    s.add(task)
    s.flush()
    env["task_ids"].append(task.id)
    trig = MoCTaskTrigger(id=str(uuid.uuid4()), task_catalog_id=task.id, kind="event",
                          config={"event": EVENT_KEY, "conditions": []},
                          is_active=True, is_live=is_live)
    s.add(trig)
    s.flush()
    s.commit()
    return trig


def _emit(env) -> MoCDomainEvent:
    s = env["db"]
    ev = MoCDomainEvent(id=str(uuid.uuid4()), company_id=env["company"].id,
                        event_key=EVENT_KEY, payload={})
    s.add(ev)
    s.commit()
    return ev


def _markers(db, company_id: str) -> list[MoCWitnessMarker]:
    db.expire_all()
    return db.query(MoCWitnessMarker).filter(MoCWitnessMarker.company_id == company_id).all()


def _runs_for_pair(db, trigger_id: str, event_id: str) -> list[WorkflowRun]:
    db.expire_all()
    return (
        db.query(WorkflowRun)
        .filter(
            WorkflowRun.trigger_source == "moc_task_event",
            WorkflowRun.trigger_context["moc_task_trigger_id"].astext == trigger_id,
            WorkflowRun.trigger_context["event_id"].astext == event_id,
        )
        .all()
    )


# ── 1. promoted compiled → LIVE (the real event-driven effect) ─────────


def test_promoted_compiled_event_trigger_fires_live(env):
    trig = _mk_event_trigger(env, env["draft"], is_live=True)
    ev = _emit(env)

    check_moc_domain_events()

    markers = _markers(env["db"], env["company"].id)
    assert len(markers) == 1                       # THE REAL EFFECT
    assert markers[0].moc_task_trigger_id == trig.id
    runs = _runs_for_pair(env["db"], trig.id, ev.id)
    assert len(runs) == 1
    assert (runs[0].output_data or {}).get("__dry_run__") is not True   # LIVE
    assert runs[0].trigger_context["event_key"] == EVENT_KEY            # event provenance


# ── 2. promoted MIRROR → DRY-RUN (§6) ──────────────────────────────────


def test_promoted_mirror_event_trigger_fires_dry_run(env):
    trig = _mk_event_trigger(env, env["mirror"], is_live=True)   # promoted, MIRROR
    ev = _emit(env)
    check_moc_domain_events()

    assert _markers(env["db"], env["company"].id) == []          # NO real effect
    runs = _runs_for_pair(env["db"], trig.id, ev.id)
    assert len(runs) == 1                                        # fired …
    assert (runs[0].output_data or {}).get("__dry_run__") is True  # … DRY-RUN (§6)


# ── 3. unpromoted → dry-run ────────────────────────────────────────────


def test_unpromoted_event_trigger_fires_dry_run(env):
    trig = _mk_event_trigger(env, env["draft"], is_live=False)
    ev = _emit(env)
    check_moc_domain_events()
    assert _markers(env["db"], env["company"].id) == []
    assert (_runs_for_pair(env["db"], trig.id, ev.id)[0].output_data or {}).get("__dry_run__") is True


# ── 4. LIVE fires ONCE (dedup holds live) ──────────────────────────────


def test_live_event_fire_happens_exactly_once(env):
    trig = _mk_event_trigger(env, env["draft"], is_live=True)
    ev = _emit(env)
    check_moc_domain_events()                       # live fire
    # at-least-once redelivery of the SAME event
    env["db"].execute(sql_text(
        "UPDATE moc_domain_event SET processed_at = NULL WHERE id = :e"), {"e": ev.id})
    env["db"].commit()
    check_moc_domain_events()                       # re-process
    assert len(_markers(env["db"], env["company"].id)) == 1     # ONE real effect
    assert len(_runs_for_pair(env["db"], trig.id, ev.id)) == 1  # ONE run


# ── 5. LIVE failure recorded loudly ────────────────────────────────────


def test_live_event_failure_recorded_loudly(env, monkeypatch):
    trig = _mk_event_trigger(env, env["draft"], is_live=True)

    def _boom(*a, **k):
        raise RuntimeError("boom in a live event step")

    monkeypatch.setattr("app.services.workflow_engine._execute_action", _boom)
    ev = _emit(env)
    check_moc_domain_events()

    runs = _runs_for_pair(env["db"], trig.id, ev.id)
    assert len(runs) == 1
    assert runs[0].status == "failed"
    assert runs[0].error_message and "boom in a live event step" in runs[0].error_message


# ── 6. the seed — event-trigger unpromoted + promotion preserved ───────


def test_seed_event_trigger_unpromoted_and_promotion_preserved(env):
    from scripts import seed_moc_witness_marker as seed_mod

    db = env["db"]
    r1 = seed_mod.seed(db, company_slug=env["company"].slug)
    try:
        assert r1["witness_event_key"] == EVENT_KEY
        ev_trig = db.get(MoCTaskTrigger, r1["event_trigger_id"])
        assert ev_trig.kind == "event"
        assert ev_trig.is_live is False                          # ships UNPROMOTED
        assert ev_trig.config == {"event": EVENT_KEY, "conditions": []}
        # operator promotes; a re-seed must NOT reset it
        triggers_svc.patch_trigger(db, trigger_id=ev_trig.id, is_live=True)
        db.commit()
        r2 = seed_mod.seed(db, company_slug=env["company"].slug)
        assert r2["event_trigger_id"] == r1["event_trigger_id"]
        db.refresh(ev_trig)
        assert ev_trig.is_live is True                           # promotion PRESERVED
    finally:
        db.execute(sql_text("DELETE FROM moc_witness_marker WHERE moc_task_trigger_id IN (:a, :b)"),
                   {"a": r1["trigger_id"], "b": r1["event_trigger_id"]})
        db.execute(sql_text("DELETE FROM moc_task_trigger WHERE task_catalog_id = :t"), {"t": r1["task_id"]})
        db.execute(sql_text("DELETE FROM moc_task_catalog WHERE id = :t"), {"t": r1["task_id"]})
        tmpl = db.get(WorkflowTemplate, r1["template_id"])
        if tmpl and tmpl.compiled_workflow_id:
            cw = tmpl.compiled_workflow_id
            db.execute(sql_text("UPDATE workflow_templates SET compiled_workflow_id=NULL WHERE id=:t"), {"t": tmpl.id})
            db.execute(sql_text("DELETE FROM workflow_steps WHERE workflow_id=:w"), {"w": cw})
            db.execute(sql_text("DELETE FROM workflows WHERE id=:w"), {"w": cw})
        db.execute(sql_text("DELETE FROM workflow_templates WHERE id = :t"), {"t": r1["template_id"]})
        db.commit()
