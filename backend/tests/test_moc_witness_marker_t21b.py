"""MoC witness marker (Canvas↔Runtime Bridge T-2.1b-WITNESS) — the benign-but-real
first autonomous scheduled fire, proven END-TO-END on the real DB.

Unlike the T-2.1b assembly test (which spies on `_execute_action` as the effect
boundary), THIS suite asserts on the REAL persisted effect: a `moc_witness_marker`
row. That row is the witness — it exists IFF a compiled task fired LIVE. Because
the marker table is the isolated effect (nothing else writes it), assertions
scoped to the fixture company are immune to any other schedule trigger the sweep
happens to fire.

The crossing, proven:
  1. the seed produces a COMPILED (not mirror) task + an UNPROMOTED (is_live=False)
     cron trigger — ships safe;
  2. UNPROMOTED → the sweep fires DRY-RUN → NO marker row (the "would execute
     action:record_marker" preview only);
  3. PROMOTED → the sweep fires LIVE → a REAL marker row, EXACTLY ONE, fully
     ATTRIBUTABLE (company + run + trigger);
  4. REVERSIBILITY — de-promote → the next window fires DRY-RUN again, NO new live
     marker (the OFF switch works);
  5. `_handle_record_marker` writes a real row (unit) + does NOT swallow a failure
     (loud, unlike log_vault_item);
  6. the seed is idempotent + PRESERVES an operator promotion across a re-run.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.company import Company
from app.models.moc_task_catalog import MoCTaskCatalog
from app.models.moc_task_trigger import MoCTaskTrigger
from app.models.moc_witness_marker import MoCWitnessMarker
from app.models.workflow import Workflow, WorkflowRun
from app.models.workflow_template import WorkflowTemplate
from app.services.maps_of_content import triggers as triggers_svc
from app.services.maps_of_content.schedule_sweep import check_moc_task_schedules
from scripts import seed_moc_witness_marker as seed_mod

VERT = "manufacturing"
DUE_NOW = datetime(2026, 7, 1, 22, 5, 0, tzinfo=timezone.utc)     # 18:05 EDT
DUE_NOW_2 = datetime(2026, 7, 1, 22, 12, 0, tzinfo=timezone.utc)  # same 18:00 window
LATER_WINDOW = datetime(2026, 7, 2, 22, 5, 0, tzinfo=timezone.utc)  # next day's 18:00


def _marker_canvas() -> dict:
    return {
        "version": 1, "trigger": {"type": "manual"},
        "nodes": [
            {"id": "n_start", "type": "start", "config": {}},
            {"id": "n_marker", "type": "record_marker", "label": "Marker",
             "config": {"note": "witness"}},
            {"id": "n_end", "type": "end", "config": {}},
        ],
        "edges": [
            {"id": "e1", "source": "n_start", "target": "n_marker"},
            {"id": "e2", "source": "n_marker", "target": "n_end"},
        ],
    }


@pytest.fixture
def env():
    s = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    company = Company(
        id=str(uuid.uuid4()), name="Witness Co", slug=f"witness-{suffix}",
        vertical=VERT, timezone="America/New_York", is_active=True,
    )
    s.add(company)
    tmpl = WorkflowTemplate(
        id=str(uuid.uuid4()), scope="vertical_default", vertical=VERT,
        workflow_type=f"t21bw_{suffix}", display_name="Witness Draft",
        canvas_state=_marker_canvas(), version=1, is_active=True,
    )  # COMPILED (mirrored_from_workflow_id is None) → eligible for live
    s.add(tmpl)
    s.flush()
    task = MoCTaskCatalog(
        id=str(uuid.uuid4()), scope="tenant_override", vertical=VERT,
        tenant_id=company.id, name=f"Witness Task {suffix}",
        workflow_template_id=tmpl.id, is_active=True,
    )
    s.add(task)
    # a bare Workflow so hand-built unit-test runs satisfy workflow_runs.workflow_id NOT NULL
    wf = Workflow(id=str(uuid.uuid4()), company_id=company.id, name="Witness WF",
                  trigger_type="manual", scope="tenant", tier=4, is_active=True)
    s.add(wf)
    s.flush()
    ctx = {"db": s, "company": company, "tmpl": tmpl, "task": task, "wf_id": wf.id}
    s.commit()
    yield ctx
    # teardown
    s.rollback()
    cid = company.id
    s.execute(sql_text("DELETE FROM moc_witness_marker WHERE company_id = :c"), {"c": cid})
    s.execute(sql_text(
        "DELETE FROM workflow_run_steps WHERE run_id IN "
        "(SELECT id FROM workflow_runs WHERE company_id = :c)"
    ), {"c": cid})
    s.execute(sql_text("DELETE FROM workflow_runs WHERE company_id = :c"), {"c": cid})
    s.refresh(tmpl)
    if tmpl.compiled_workflow_id:
        cwid = tmpl.compiled_workflow_id
        s.execute(sql_text("UPDATE workflow_templates SET compiled_workflow_id=NULL WHERE id=:t"), {"t": tmpl.id})
        s.execute(sql_text("DELETE FROM workflow_steps WHERE workflow_id=:w"), {"w": cwid})
        s.execute(sql_text("DELETE FROM workflows WHERE id=:w"), {"w": cwid})
    s.execute(sql_text("DELETE FROM moc_task_trigger WHERE task_catalog_id = :t"), {"t": task.id})
    s.execute(sql_text("DELETE FROM moc_task_catalog WHERE id = :t"), {"t": task.id})
    s.execute(sql_text("DELETE FROM workflow_templates WHERE id = :t"), {"t": tmpl.id})
    s.execute(sql_text("DELETE FROM workflows WHERE id = :w"), {"w": ctx["wf_id"]})
    s.execute(sql_text("DELETE FROM companies WHERE id = :c"), {"c": cid})
    s.commit()
    s.close()


def _mk_trigger(env, *, is_live: bool, spec: dict | None = None) -> MoCTaskTrigger:
    s = env["db"]
    trig = MoCTaskTrigger(
        id=str(uuid.uuid4()), task_catalog_id=env["task"].id, kind="schedule",
        config=spec or {"spec_kind": "time_of_day", "time": "18:00", "days": []},
        is_active=True, is_live=is_live,
    )
    s.add(trig)
    s.flush()
    s.commit()
    return trig


def _markers(db, company_id: str) -> list[MoCWitnessMarker]:
    db.expire_all()
    return db.query(MoCWitnessMarker).filter(MoCWitnessMarker.company_id == company_id).all()


def _runs(db, trigger_id: str) -> list[WorkflowRun]:
    db.expire_all()
    return (
        db.query(WorkflowRun)
        .filter(
            WorkflowRun.trigger_source == "moc_task_schedule",
            WorkflowRun.trigger_context["moc_task_trigger_id"].astext == trigger_id,
        )
        .all()
    )


# ── 1. unpromoted → DRY-RUN → NO marker (the preview only) ──────────────


def test_unpromoted_fires_dry_run_no_marker(env):
    trig = _mk_trigger(env, is_live=False)
    check_moc_task_schedules(now=DUE_NOW)

    assert _markers(env["db"], env["company"].id) == []   # NO real effect
    runs = _runs(env["db"], trig.id)
    assert len(runs) == 1
    assert (runs[0].output_data or {}).get("__dry_run__") is True


# ── 2. promoted COMPILED → LIVE → a REAL, attributable marker, ONCE ─────


def test_promoted_fires_live_writes_real_marker(env):
    trig = _mk_trigger(env, is_live=True)
    check_moc_task_schedules(now=DUE_NOW)

    markers = _markers(env["db"], env["company"].id)
    assert len(markers) == 1                       # THE REAL EFFECT — a persisted row
    m = markers[0]
    assert m.moc_task_trigger_id == trig.id        # attributable to the trigger
    assert m.run_id is not None                     # attributable to the run
    assert m.note                                   # the marker note was written
    runs = _runs(env["db"], trig.id)
    assert len(runs) == 1
    assert (runs[0].output_data or {}).get("__dry_run__") is not True  # LIVE, not dry-run


def test_live_writes_marker_exactly_once(env):
    trig = _mk_trigger(env, is_live=True)
    check_moc_task_schedules(now=DUE_NOW)        # tick 1 → live
    check_moc_task_schedules(now=DUE_NOW_2)      # tick 2, same window → deduped
    assert len(_markers(env["db"], env["company"].id)) == 1   # ONCE, not per-tick


# ── 3. REVERSIBILITY — de-promote → next window fires DRY-RUN, no new marker ─


def test_depromote_stops_live_fire(env):
    trig = _mk_trigger(env, is_live=True)
    check_moc_task_schedules(now=DUE_NOW)                 # window 1 → LIVE marker
    assert len(_markers(env["db"], env["company"].id)) == 1

    # THE OFF SWITCH: pull the promotion back.
    triggers_svc.patch_trigger(env["db"], trigger_id=trig.id, is_live=False)
    env["db"].commit()

    check_moc_task_schedules(now=LATER_WINDOW)            # next day's window → DRY-RUN
    # still exactly ONE marker — the de-promoted tick wrote NO new live marker.
    assert len(_markers(env["db"], env["company"].id)) == 1
    later_run = [r for r in _runs(env["db"], trig.id)
                 if (r.trigger_context or {}).get("intended_fire", "").startswith("2026-07-02")]
    assert len(later_run) == 1
    assert (later_run[0].output_data or {}).get("__dry_run__") is True


# ── 4. _handle_record_marker unit — writes a row + does NOT swallow ─────


def test_record_marker_writes_real_row(env):
    from app.services.workflow_engine import _handle_record_marker
    run = WorkflowRun(
        id=str(uuid.uuid4()), workflow_id=env["wf_id"], company_id=env["company"].id,
        trigger_source="unit", trigger_context={"moc_task_trigger_id": "trig-x"},
        status="running",
    )
    env["db"].add(run)
    env["db"].commit()
    out = _handle_record_marker(env["db"], {"note": "hello"}, run)
    assert out["type"] == "witness_marker"
    m = _markers(env["db"], env["company"].id)
    assert len(m) == 1 and m[0].note == "hello" and m[0].run_id == run.id


def test_record_marker_does_not_swallow(env):
    """A bad company_id (FK violation) must RAISE, not silently return — the
    T-2.1b 'recorded loudly' invariant (contrast log_vault_item's silent swallow)."""
    from app.services.workflow_engine import _handle_record_marker
    # In-memory run (NOT persisted) with a bad company_id — the handler reads
    # run.company_id and the marker INSERT trips the companies FK. If the handler
    # swallowed (like log_vault_item), this would return a dict instead of raising.
    run = WorkflowRun(
        id=str(uuid.uuid4()), workflow_id=env["wf_id"], company_id="nonexistent-company",
        trigger_source="unit", trigger_context={}, status="running",
    )
    with pytest.raises(Exception):
        _handle_record_marker(env["db"], {"note": "x"}, run)
    env["db"].rollback()


# ── 5. the seed — compiled + benign + unpromoted, idempotent, preserves promotion ─


def _cleanup_seed(db, result: dict):
    if "trigger_id" not in result:
        return
    db.execute(sql_text("DELETE FROM moc_witness_marker WHERE moc_task_trigger_id = :t"), {"t": result["trigger_id"]})
    db.execute(sql_text("DELETE FROM moc_task_trigger WHERE task_catalog_id = :t"), {"t": result["task_id"]})
    db.execute(sql_text("DELETE FROM moc_task_catalog WHERE id = :t"), {"t": result["task_id"]})
    tmpl = db.get(WorkflowTemplate, result["template_id"])
    if tmpl and tmpl.compiled_workflow_id:
        cwid = tmpl.compiled_workflow_id
        db.execute(sql_text("UPDATE workflow_templates SET compiled_workflow_id=NULL WHERE id=:t"), {"t": tmpl.id})
        db.execute(sql_text("DELETE FROM workflow_steps WHERE workflow_id=:w"), {"w": cwid})
        db.execute(sql_text("DELETE FROM workflows WHERE id=:w"), {"w": cwid})
    db.execute(sql_text("DELETE FROM workflow_templates WHERE id = :t"), {"t": result["template_id"]})
    db.commit()


def test_seed_produces_compiled_benign_unpromoted(env):
    db = env["db"]
    result = seed_mod.seed(db, company_slug=env["company"].slug)
    try:
        assert result.get("trigger_id")
        tmpl = db.get(WorkflowTemplate, result["template_id"])
        assert tmpl.mirrored_from_workflow_id is None       # COMPILED, not a mirror
        task = db.get(MoCTaskCatalog, result["task_id"])
        assert task.scope == "tenant_override"              # ONE-tenant fan-out (not vertical)
        assert task.tenant_id == env["company"].id
        trig = db.get(MoCTaskTrigger, result["trigger_id"])
        assert trig.is_live is False                        # ships UNPROMOTED
        assert trig.config.get("cron") == "*/15 * * * *"    # witnessable cadence
    finally:
        _cleanup_seed(db, result)


def test_seed_rerun_preserves_is_live(env):
    db = env["db"]
    r1 = seed_mod.seed(db, company_slug=env["company"].slug)
    try:
        # operator promotes
        triggers_svc.patch_trigger(db, trigger_id=r1["trigger_id"], is_live=True)
        db.commit()
        # re-seed (idempotent deploy re-run) MUST NOT reset the promotion
        r2 = seed_mod.seed(db, company_slug=env["company"].slug)
        assert r2["trigger_id"] == r1["trigger_id"]         # same trigger (idempotent)
        assert r2["trigger_created"] is False
        trig = db.get(MoCTaskTrigger, r1["trigger_id"])
        db.refresh(trig)
        assert trig.is_live is True                         # promotion PRESERVED
    finally:
        _cleanup_seed(db, r1)
