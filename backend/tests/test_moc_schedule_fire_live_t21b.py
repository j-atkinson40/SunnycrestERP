"""is_live promotion (Canvas↔Runtime Bridge T-2.1b) — the first REAL scheduled
fire, proven on a controlled benign target with the §6 compiled-only guard.

The platform's first autonomous real action: a clock, not a human, running a
workflow with a real effect. The safety-critical claim is that go_live has ONE
source — `_resolve_go_live` (is_live AND compiled) — so a real effect requires
BOTH a deliberate per-trigger promotion AND a compiled (single-owner) task; a
MIRROR task never fires live (§6 double-fire hazard).

Assembly tests (the effect boundary = a monkeypatch spy on `_execute_action`, the
handler that WOULD create a real invoice — it runs iff the fire is live):
  1. is_live DEFAULT FALSE (existing triggers unpromoted).
  2. PROMOTED COMPILED → fires LIVE (the effect handler IS invoked — the real
     effect happens).
  3. PROMOTED MIRROR → fires DRY-RUN (the §6 guard: handler NOT invoked, a dry-run
     run exists) even with is_live=True.
  4. UNPROMOTED → dry-run (handler not invoked).
  5. LIVE fires EXACTLY ONCE (the re-keyed idempotency holds for live too).
  6. A LIVE failure is recorded LOUDLY (status=failed + error_message).
  7. `_resolve_go_live` unit — the single-source derivation.
  8. patch_trigger sets is_live (the promotion API).
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
from app.models.workflow import Workflow, WorkflowRun, WorkflowStep
from app.models.workflow_template import WorkflowTemplate
from app.services.maps_of_content import triggers as triggers_svc
from app.services.maps_of_content.schedule_sweep import _resolve_go_live, check_moc_task_schedules

VERT = "manufacturing"
DUE_NOW = datetime(2026, 7, 1, 22, 5, 0, tzinfo=timezone.utc)      # 18:05 EDT
DUE_NOW_2 = datetime(2026, 7, 1, 22, 12, 0, tzinfo=timezone.utc)   # same window


def _action_canvas() -> dict:
    """Linear draft canvas with one action step (→ _execute_action, the effect
    boundary the spy watches)."""
    return {
        "version": 1, "trigger": {"type": "manual"},
        "nodes": [
            {"id": "n_start", "type": "start", "config": {}},
            {"id": "n_act", "type": "action", "label": "Act",
             "config": {"action_type": "log_vault_item", "title": "live probe"}},
            {"id": "n_end", "type": "end", "config": {}},
        ],
        "edges": [
            {"id": "e1", "source": "n_start", "target": "n_act"},
            {"id": "e2", "source": "n_act", "target": "n_end"},
        ],
    }


@pytest.fixture
def env():
    s = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    company = Company(
        id=str(uuid.uuid4()), name="Live Co", slug=f"live-{suffix}",
        vertical=VERT, timezone="America/New_York", is_active=True,
    )
    s.add(company)
    # a COMPILED (draft) template — eligible for live.
    draft = WorkflowTemplate(
        id=str(uuid.uuid4()), scope="vertical_default", vertical=VERT,
        workflow_type=f"t21b_draft_{suffix}", display_name="T-2.1b Draft",
        canvas_state=_action_canvas(), version=1, is_active=True,
    )
    # a runtime SOURCE workflow (with an action step) + a MIRROR template of it.
    # T-1 note: the source carries a LIVE runtime schedule (a 3am cron,
    # never due at DUE_NOW) — the §6 hazard as originally told ("the runtime
    # source is independently scheduled"). The T-1 narrowing keys on exactly
    # this; a manual source would now be live-capable.
    src = Workflow(id=str(uuid.uuid4()), company_id=None, name="T-2.1b Source",
                   trigger_type="scheduled", trigger_config={"cron": "0 3 * * *"},
                   scope="core", tier=1, is_active=True)
    s.add(draft)
    s.add(src)
    s.flush()
    s.add(WorkflowStep(id=str(uuid.uuid4()), workflow_id=src.id, step_order=1,
                       step_key="s1", step_type="action",
                       config={"action_type": "log_vault_item", "title": "mirror probe"}))
    mirror = WorkflowTemplate(
        id=str(uuid.uuid4()), scope="vertical_default", vertical=VERT,
        workflow_type=f"t21b_mirror_{suffix}", display_name="T-2.1b Mirror",
        canvas_state={"version": 1, "nodes": [], "edges": []}, version=1,
        is_active=True, mirrored_from_workflow_id=src.id,
    )
    s.add(mirror)
    s.flush()
    ctx = {"db": s, "company": company, "draft": draft, "mirror": mirror,
           "source_id": src.id, "task_ids": []}
    s.commit()
        # T-1 SCOPING: the dev/CI DB legitimately carries ADOPTED LIVE triggers
    # now (expense-cat's */15) — an unscoped full sweep in a test would fire
    # real pipelines. Scope the sweep population to THIS fixture's tasks.
    from unittest.mock import patch as _patch
    from app.services.maps_of_content import schedule_sweep as _sweep_mod
    _orig_pop = _sweep_mod._active_schedule_triggers
    _pop_patch = _patch.object(
        _sweep_mod, "_active_schedule_triggers",
        lambda db: [t for t in _orig_pop(db) if t.task_catalog_id in ctx["task_ids"]],
    )
    _pop_patch.start()
    yield ctx
    _pop_patch.stop()
    s.rollback()
    tid = [company.id]
    s.execute(sql_text(
        "DELETE FROM workflow_run_steps WHERE run_id IN (SELECT id FROM workflow_runs WHERE company_id = ANY(:c))"
    ), {"c": tid})
    s.execute(sql_text("DELETE FROM vault_items WHERE company_id = ANY(:c)"), {"c": tid})
    s.execute(sql_text("DELETE FROM workflow_runs WHERE company_id = ANY(:c)"), {"c": tid})
    s.refresh(draft)
    if draft.compiled_workflow_id:
        s.execute(sql_text("UPDATE workflow_templates SET compiled_workflow_id=NULL WHERE id=:t"), {"t": draft.id})
        s.execute(sql_text("DELETE FROM workflow_steps WHERE workflow_id=:w"), {"w": draft.compiled_workflow_id})
        s.execute(sql_text("DELETE FROM workflows WHERE id=:w"), {"w": draft.compiled_workflow_id})
    s.execute(sql_text("DELETE FROM moc_task_trigger WHERE task_catalog_id = ANY(:t)"), {"t": ctx["task_ids"] or [""]})
    s.execute(sql_text("DELETE FROM moc_task_catalog WHERE id = ANY(:t)"), {"t": ctx["task_ids"] or [""]})
    s.execute(sql_text("DELETE FROM workflow_steps WHERE workflow_id=:w"), {"w": ctx["source_id"]})
    s.execute(sql_text("DELETE FROM workflow_templates WHERE id IN (:d, :m)"), {"d": draft.id, "m": mirror.id})
    s.execute(sql_text("DELETE FROM workflows WHERE id=:w"), {"w": ctx["source_id"]})
    s.execute(sql_text("DELETE FROM companies WHERE id = ANY(:c)"), {"c": tid})
    s.commit()
    s.close()


def _mk_trigger(env, template: WorkflowTemplate, *, is_live: bool) -> MoCTaskTrigger:
    s = env["db"]
    task = MoCTaskCatalog(
        id=str(uuid.uuid4()), scope="tenant_override", vertical=VERT,
        tenant_id=env["company"].id, name=f"Live Task {uuid.uuid4().hex[:6]}",
        workflow_template_id=template.id, is_active=True,
    )
    s.add(task)
    s.flush()
    env["task_ids"].append(task.id)
    trig = MoCTaskTrigger(
        id=str(uuid.uuid4()), task_catalog_id=task.id, kind="schedule",
        config={"spec_kind": "time_of_day", "time": "18:00", "days": []},
        is_active=True, is_live=is_live,
    )
    s.add(trig)
    s.flush()
    s.commit()
    return trig


def _spy_execute_action(monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr(
        "app.services.workflow_engine._execute_action",
        lambda *a, **k: (calls.append(1), {"type": "spy"})[1],
    )
    return calls


def _runs_for(db, trigger_id: str):
    db.expire_all()
    return (
        db.query(WorkflowRun)
        .filter(
            WorkflowRun.trigger_source == "moc_task_schedule",
            WorkflowRun.trigger_context["moc_task_trigger_id"].astext == trigger_id,
        )
        .all()
    )


# ── 1. default FALSE ───────────────────────────────────────────────────


def test_is_live_defaults_false(env):
    trig = MoCTaskTrigger(id=str(uuid.uuid4()), task_catalog_id="x", kind="manual", config={})
    # ORM default before insert
    assert trig.is_live is False or trig.is_live is None
    # a real inserted trigger
    t = _mk_trigger(env, env["draft"], is_live=False)
    env["db"].refresh(t)
    assert t.is_live is False


# ── 2. promoted COMPILED → LIVE ────────────────────────────────────────


def test_promoted_compiled_fires_live(env, monkeypatch):
    trig = _mk_trigger(env, env["draft"], is_live=True)
    calls = _spy_execute_action(monkeypatch)

    check_moc_task_schedules(now=DUE_NOW)

    runs = _runs_for(env["db"], trig.id)
    assert len(runs) == 1
    assert calls == [1]   # LIVE — the effect handler WAS invoked (the real effect)
    assert (runs[0].output_data or {}).get("__dry_run__") is not True   # not dry-run


# ── 3. promoted MIRROR → DRY-RUN (the §6 guard) ────────────────────────


def test_promoted_mirror_fires_dry_run(env, monkeypatch):
    trig = _mk_trigger(env, env["mirror"], is_live=True)   # promoted, but a MIRROR
    calls = _spy_execute_action(monkeypatch)

    check_moc_task_schedules(now=DUE_NOW)

    runs = _runs_for(env["db"], trig.id)
    assert len(runs) == 1                 # it fired …
    assert calls == []                    # … but DRY-RUN — the §6 guard forced it
    assert (runs[0].output_data or {}).get("__dry_run__") is True


# ── 4. unpromoted → DRY-RUN ────────────────────────────────────────────


def test_unpromoted_compiled_fires_dry_run(env, monkeypatch):
    trig = _mk_trigger(env, env["draft"], is_live=False)
    calls = _spy_execute_action(monkeypatch)
    check_moc_task_schedules(now=DUE_NOW)
    assert calls == []   # not promoted → dry-run
    assert (_runs_for(env["db"], trig.id)[0].output_data or {}).get("__dry_run__") is True


# ── 5. LIVE fires exactly ONCE ─────────────────────────────────────────


def test_live_fires_exactly_once(env, monkeypatch):
    trig = _mk_trigger(env, env["draft"], is_live=True)
    calls = _spy_execute_action(monkeypatch)
    check_moc_task_schedules(now=DUE_NOW)       # tick 1 → live fire
    check_moc_task_schedules(now=DUE_NOW_2)     # tick 2, same window → deduped
    assert len(_runs_for(env["db"], trig.id)) == 1
    assert calls == [1]   # the real effect happened ONCE, not per-tick


# ── 6. LIVE failure recorded loudly ────────────────────────────────────


def test_live_failure_recorded_loudly(env, monkeypatch):
    trig = _mk_trigger(env, env["draft"], is_live=True)

    def _boom(*a, **k):
        raise RuntimeError("boom in a live step")

    monkeypatch.setattr("app.services.workflow_engine._execute_action", _boom)
    check_moc_task_schedules(now=DUE_NOW)

    runs = _runs_for(env["db"], trig.id)
    assert len(runs) == 1
    assert runs[0].status == "failed"
    assert runs[0].error_message and "boom in a live step" in runs[0].error_message


# ── 7. _resolve_go_live unit (the single source) ───────────────────────


def test_resolve_go_live_is_the_single_source(env):
    db = env["db"]
    compiled = env["draft"]   # mirrored_from_workflow_id is None
    mirror = env["mirror"]    # mirrored_from_workflow_id set (scheduled source)

    live = MoCTaskTrigger(id="a", task_catalog_id="t", kind="schedule", config={}, is_live=True)
    dry = MoCTaskTrigger(id="b", task_catalog_id="t", kind="schedule", config={}, is_live=False)

    assert _resolve_go_live(live, compiled, db) is True    # promoted + compiled → LIVE
    # §6 NARROWED (T-1): the hazard is the source's LIVE RUNTIME SCHEDULE,
    # not mirror-ness — this mirror's source is scheduled → dry.
    assert _resolve_go_live(live, mirror, db) is False
    assert _resolve_go_live(dry, compiled, db) is False    # unpromoted → dry
    assert _resolve_go_live(live, None, db) is True         # no template resolvable → compiled-ish (not a mirror)

    # The narrowing's other half: retire the source's schedule (the adopt's
    # write) → the same mirror becomes live-capable.
    from datetime import datetime, timezone as _tz
    src = db.get(Workflow, env["source_id"])
    src.schedule_retired_at = datetime.now(_tz.utc)
    db.flush()
    assert _resolve_go_live(live, mirror, db) is True
    src.schedule_retired_at = None
    db.flush()


# ── 8. patch_trigger sets is_live (the promotion API) ─────────────────


def test_patch_trigger_sets_is_live(env):
    trig = _mk_trigger(env, env["draft"], is_live=False)
    triggers_svc.patch_trigger(env["db"], trigger_id=trig.id, is_live=True)
    env["db"].commit()
    env["db"].refresh(trig)
    assert trig.is_live is True
