"""MoC schedule sweep (Canvas↔Runtime Bridge T-2.1a) — the dry-run sweep, proven
safe + correct + non-bloating BEFORE any live fire.

Assembly tests:
  1. DUE FIRE: a due time_of_day trigger → the sweep fires it DRY-RUN → a
     WorkflowRun with "would do X" + NO real effect (the effect handler is never
     invoked — the T-2.0b guarantee holds THROUGH the sweep).
  2. IDEMPOTENCY: the sweep across multiple ticks in a trigger's window → fires
     ONCE, not N times (re-keyed on the trigger, not the ephemeral workflow).
  3. TIMEZONE: a 6pm-tenant-local trigger fires at 6pm TENANT time (22:00 UTC in
     EDT), NOT at 18:00 UTC — the tz fix (no inherited UTC bug).
  4. CATCH-UP: a trigger due outside the 15-min window → SKIPPED (no backlog fire).
  5. CACHE: a draft-task fanned to two companies COMPILES ONCE — both runs reuse
     the cached compiled workflow (no per-fire bloat, §7).
  6. OBSERVABILITY: the dry-run fires are visible in the run-log with their
     "would do X" records.

STATE-IMMUNITY DISCIPLINE (2026-07-06): every assertion is scoped to THIS
test's fixture trigger ids (`_runs_for`), never to the sweep's GLOBAL result
counts. The shared dev DB legitimately carries other active schedule triggers
(e.g. the seeded witness marker's cron */15, due in EVERY window) — a global
`fired_dry_run == N` assertion breaks under any of them. The suite must pass
with the witness seed present. Where "the sweep reported my fire" matters, the
global count is asserted as `>= 1` (foreign fires only inflate it). Same class
as the R-7-δ order-coupling lesson: tests sharing a DB are state-coupled unless
their assertions are self-scoped.
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
from app.models.workflow import WorkflowRun
from app.models.workflow_template import WorkflowTemplate
from app.services.maps_of_content.schedule_sweep import (
    check_moc_task_schedules,
    list_schedule_runs,
)

VERT = "manufacturing"
# 2026-07-01 22:05 UTC = 18:05 America/New_York (EDT, UTC-4) → in [18:00,18:15).
DUE_NOW = datetime(2026, 7, 1, 22, 5, 0, tzinfo=timezone.utc)
# Same window, a later tick — same intended_fire (18:00 local).
DUE_NOW_2 = datetime(2026, 7, 1, 22, 12, 0, tzinfo=timezone.utc)
# 18:05 UTC = 14:05 EDT — NOT the tenant's 6pm.
UTC_6PM = datetime(2026, 7, 1, 18, 5, 0, tzinfo=timezone.utc)
# 23:30 UTC = 19:30 EDT — outside the 18:00 window (backlog).
BACKLOG_NOW = datetime(2026, 7, 1, 23, 30, 0, tzinfo=timezone.utc)


def _effect_canvas() -> dict:
    """A linear draft canvas with one effectful action node (log_vault_item)."""
    return {
        "version": 1, "trigger": {"type": "manual"},
        "nodes": [
            {"id": "n_start", "type": "start", "config": {}},
            {"id": "n_log", "type": "action", "label": "Log",
             "config": {"action_type": "log_vault_item", "item_type": "event", "title": "sweep probe"}},
            {"id": "n_end", "type": "end", "config": {}},
        ],
        "edges": [
            {"id": "e1", "source": "n_start", "target": "n_log"},
            {"id": "e2", "source": "n_log", "target": "n_end"},
        ],
    }


@pytest.fixture
def env():
    s = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    companies = []
    for i in range(2):
        c = Company(
            id=str(uuid.uuid4()), name=f"Sweep Co {i}", slug=f"sweep-{suffix}-{i}",
            vertical=VERT, timezone="America/New_York", is_active=True,
        )
        s.add(c)
        companies.append(c)
    s.flush()
    tmpl = WorkflowTemplate(
        id=str(uuid.uuid4()), scope="vertical_default", vertical=VERT,
        workflow_type=f"t21a_{suffix}", display_name="T-2.1a Probe",
        canvas_state=_effect_canvas(), version=1, is_active=True,
    )
    s.add(tmpl)
    s.flush()
    ctx = {"db": s, "companies": companies, "template": tmpl, "task_ids": [], "trigger_ids": []}
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
    # teardown — FK order.
    s.rollback()
    cids = [c.id for c in companies]
    s.execute(sql_text(
        "DELETE FROM workflow_run_steps WHERE run_id IN "
        "(SELECT id FROM workflow_runs WHERE company_id = ANY(:c) AND trigger_source='moc_task_schedule')"
    ), {"c": cids})
    s.execute(sql_text("DELETE FROM vault_items WHERE company_id = ANY(:c)"), {"c": cids})
    s.execute(sql_text("DELETE FROM workflow_runs WHERE company_id = ANY(:c)"), {"c": cids})
    # the compiled (cached) workflow — grab from the template first
    s.refresh(tmpl)
    if tmpl.compiled_workflow_id:
        s.execute(sql_text("UPDATE workflow_templates SET compiled_workflow_id=NULL WHERE id=:t"), {"t": tmpl.id})
        s.execute(sql_text("DELETE FROM workflow_steps WHERE workflow_id=:w"), {"w": tmpl.compiled_workflow_id})
        s.execute(sql_text("DELETE FROM workflows WHERE id=:w"), {"w": tmpl.compiled_workflow_id})
    s.execute(sql_text("DELETE FROM moc_task_trigger WHERE task_catalog_id = ANY(:t)"), {"t": ctx["task_ids"] or [""]})
    s.execute(sql_text("DELETE FROM moc_task_catalog WHERE id = ANY(:t)"), {"t": ctx["task_ids"] or [""]})
    s.execute(sql_text("DELETE FROM workflow_templates WHERE id=:t"), {"t": tmpl.id})
    s.execute(sql_text("DELETE FROM companies WHERE id = ANY(:c)"), {"c": cids})
    s.commit()
    s.close()


def _mk_task(env, *, scope: str, tenant_id: str | None = None) -> MoCTaskCatalog:
    s = env["db"]
    t = MoCTaskCatalog(
        id=str(uuid.uuid4()), scope=scope, vertical=(None if scope == "platform_default" else VERT),
        tenant_id=tenant_id, name=f"Sweep Task {uuid.uuid4().hex[:6]}",
        workflow_template_id=env["template"].id, is_active=True,
    )
    s.add(t)
    s.flush()
    env["task_ids"].append(t.id)
    return t


def _mk_time_of_day_trigger(env, task: MoCTaskCatalog) -> MoCTaskTrigger:
    s = env["db"]
    trig = MoCTaskTrigger(
        id=str(uuid.uuid4()), task_catalog_id=task.id, kind="schedule",
        config={"spec_kind": "time_of_day", "time": "18:00", "days": []}, is_active=True,
    )
    s.add(trig)
    s.flush()
    env["trigger_ids"].append(trig.id)
    s.commit()
    return trig


def _runs_for(db, trigger_id: str) -> list[WorkflowRun]:
    db.expire_all()
    return (
        db.query(WorkflowRun)
        .filter(
            WorkflowRun.trigger_source == "moc_task_schedule",
            WorkflowRun.trigger_context["moc_task_trigger_id"].astext == trigger_id,
        )
        .all()
    )


# ── 1. DUE FIRE — dry-run, no real effect ──────────────────────────────


def test_due_trigger_fires_dry_run_no_real_effect(env, monkeypatch):
    task = _mk_task(env, scope="tenant_override", tenant_id=env["companies"][0].id)
    trig = _mk_time_of_day_trigger(env, task)

    calls: list[int] = []
    monkeypatch.setattr(
        "app.services.workflow_engine._execute_action",
        lambda *a, **k: (calls.append(1), {"type": "spy"})[1],
    )

    result = check_moc_task_schedules(now=DUE_NOW)
    # ≥1, not ==1: foreign due triggers on the shared DB inflate the global
    # count; MY fire is asserted trigger-scoped below.
    assert result["fired_dry_run"] >= 1

    runs = _runs_for(env["db"], trig.id)
    assert len(runs) == 1
    assert (runs[0].output_data or {}).get("__dry_run__") is True   # dry-run
    assert calls == []   # the effect handler was NEVER invoked → no real effect


# ── 2. IDEMPOTENCY — fires once across ticks in the window ─────────────


def test_idempotent_across_sweep_ticks(env):
    task = _mk_task(env, scope="tenant_override", tenant_id=env["companies"][0].id)
    trig = _mk_time_of_day_trigger(env, task)

    check_moc_task_schedules(now=DUE_NOW)     # first tick in the window
    check_moc_task_schedules(now=DUE_NOW_2)   # later tick, SAME window → same intended_fire

    assert len(_runs_for(env["db"], trig.id)) == 1   # fired ONCE, not twice


# ── 3. TIMEZONE — tenant-local 6pm, not UTC 6pm ────────────────────────


def test_time_of_day_is_tenant_local(env):
    task = _mk_task(env, scope="tenant_override", tenant_id=env["companies"][0].id)
    trig = _mk_time_of_day_trigger(env, task)

    # UTC 18:05 (= 14:05 tenant EDT) → NOT the tenant's 6pm → MY trigger did
    # not fire (trigger-scoped — a foreign trigger due at this tick is fine).
    check_moc_task_schedules(now=UTC_6PM)
    assert len(_runs_for(env["db"], trig.id)) == 0

    # Tenant 18:05 (= 22:05 UTC) → the tenant's 6pm → MY trigger fires.
    check_moc_task_schedules(now=DUE_NOW)
    assert len(_runs_for(env["db"], trig.id)) == 1


# ── 4. CATCH-UP — backlog outside the window is skipped ────────────────


def test_backlog_outside_window_is_skipped(env):
    task = _mk_task(env, scope="tenant_override", tenant_id=env["companies"][0].id)
    trig = _mk_time_of_day_trigger(env, task)

    # 19:30 tenant-local — past the 18:00 window → MY trigger not fired (no
    # backlog storm). Trigger-scoped: a foreign trigger due at 19:30 is fine.
    check_moc_task_schedules(now=BACKLOG_NOW)
    assert len(_runs_for(env["db"], trig.id)) == 0


# ── 5. CACHE — one compile reused across fires ────────────────────────


# Day 2, same tenant-local 18:05 → a DIFFERENT intended_fire (not deduped).
DUE_NOW_DAY2 = datetime(2026, 7, 2, 22, 5, 0, tzinfo=timezone.utc)


def test_draft_compiles_once_across_fires(env):
    """tenant_override (one company, deterministic) fired on two different days →
    two fires, but the draft canvas COMPILES ONCE — both runs reuse the cached
    compiled workflow (no per-fire bloat, §7)."""
    task = _mk_task(env, scope="tenant_override", tenant_id=env["companies"][0].id)
    trig = _mk_time_of_day_trigger(env, task)

    check_moc_task_schedules(now=DUE_NOW)        # day 1
    check_moc_task_schedules(now=DUE_NOW_DAY2)   # day 2 — different intended_fire

    runs = _runs_for(env["db"], trig.id)
    assert len(runs) == 2   # two fires (different days), not deduped
    # THE CACHE: both runs reuse the SAME compiled workflow (compiled once).
    assert runs[0].workflow_id == runs[1].workflow_id
    env["db"].refresh(env["template"])
    assert env["template"].compiled_workflow_id == runs[0].workflow_id
    assert env["template"].compiled_version == env["template"].version


# ── 6. OBSERVABILITY — the dry-run fires are visible ───────────────────


def test_dry_run_fires_are_visible_in_run_log(env):
    task = _mk_task(env, scope="tenant_override", tenant_id=env["companies"][0].id)
    trig = _mk_time_of_day_trigger(env, task)
    check_moc_task_schedules(now=DUE_NOW)

    log = list_schedule_runs(env["db"], limit=20)
    mine = [r for r in log if r["moc_task_trigger_id"] == trig.id]
    assert len(mine) == 1
    entry = mine[0]
    assert entry["is_dry_run"] is True
    assert entry["task_name"] == task.name
    assert entry["status"] == "completed"
    # the "would do X" record for the suppressed effect step is present.
    assert any("would execute action:log_vault_item" in w for w in entry["would_do"])


# ── 7. THE FIRE CAP (sweep hardening — the runaway bound) ──────────────


def test_fire_cap_defers_within_window_exactly_once(env):
    """Over-cap load: exactly `fire_cap` fire this tick; the capped remainder
    DEFERS via the unclaimed idempotency key and fires on the next in-window
    tick — total exactly N+k, nothing lost, nothing doubled. The trip is LOUD
    (cap_tripped in the return)."""
    trigs = []
    for _ in range(3):
        task = _mk_task(env, scope="tenant_override", tenant_id=env["companies"][0].id)
        trigs.append(_mk_time_of_day_trigger(env, task))

    r1 = check_moc_task_schedules(now=DUE_NOW, fire_cap=2)
    assert r1["cap_tripped"] is True                      # loud
    mine_after_1 = sum(len(_runs_for(env["db"], t.id)) for t in trigs)
    assert mine_after_1 == 2                              # exactly the cap

    r2 = check_moc_task_schedules(now=DUE_NOW_2, fire_cap=100)  # same window
    assert r2["cap_tripped"] is False
    per_trigger = [len(_runs_for(env["db"], t.id)) for t in trigs]
    assert sorted(per_trigger) == [1, 1, 1]               # all fired, none doubled


def test_under_cap_is_invisible(env):
    """Under-cap load: zero behavior change — the cap only exists when needed."""
    task = _mk_task(env, scope="tenant_override", tenant_id=env["companies"][0].id)
    trig = _mk_time_of_day_trigger(env, task)
    r = check_moc_task_schedules(now=DUE_NOW)             # default cap
    assert r["cap_tripped"] is False
    assert len(_runs_for(env["db"], trig.id)) == 1


# ── 8. FAN-OUT scoping (pure function — no real-tenant fires) ──────────


def test_fanout_scoping():
    from app.services.maps_of_content.schedule_sweep import _fanout_companies

    cA = Company(id="a", name="A", slug="a", vertical="manufacturing", is_active=True)
    cB = Company(id="b", name="B", slug="b", vertical="funeral_home", is_active=True)
    both = [cA, cB]

    # vertical_default manufacturing → only the manufacturing company.
    t_vert = MoCTaskCatalog(scope="vertical_default", vertical="manufacturing")
    assert [c.id for c in _fanout_companies(t_vert, both)] == ["a"]
    # platform_default → every company.
    t_plat = MoCTaskCatalog(scope="platform_default", vertical=None)
    assert {c.id for c in _fanout_companies(t_plat, both)} == {"a", "b"}
    # tenant_override → only the named tenant.
    t_ten = MoCTaskCatalog(scope="tenant_override", tenant_id="b")
    assert [c.id for c in _fanout_companies(t_ten, both)] == ["b"]
