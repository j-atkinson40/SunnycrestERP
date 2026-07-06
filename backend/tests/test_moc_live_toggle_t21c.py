"""T-2.1c Live-toggle data path — what the frontend toggle + confirm consume.

Three read-shape claims:
  1. `resolve_task` exposes `is_live` per trigger (the badge state) and
     `workflow.is_mirror` (the §6 compiled-vs-mirror discriminator — a mirror
     task's toggle must be DISABLED, so the frontend needs the real capability).
  2. `list_schedule_runs(trigger_id=...)` scopes to one trigger — the go-live
     confirm's latest-preview fetch (limit=1).
  3. The is_mirror flag matches the sweep's own discriminator
     (`mirrored_from_workflow_id`) — the UI and the guard can never disagree.
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
from app.models.workflow import Workflow, WorkflowRun, WorkflowRunStep, WorkflowStep
from app.models.workflow_template import WorkflowTemplate
from app.services.maps_of_content.schedule_sweep import list_schedule_runs
from app.services.maps_of_content.task_catalog import resolve_task

VERT = "manufacturing"


@pytest.fixture
def env():
    s = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    company = Company(id=str(uuid.uuid4()), name="Toggle Co", slug=f"toggle-{suffix}",
                      vertical=VERT, timezone="America/New_York", is_active=True)
    s.add(company)
    draft = WorkflowTemplate(id=str(uuid.uuid4()), scope="vertical_default", vertical=VERT,
                             workflow_type=f"t21c_draft_{suffix}", display_name="T-2.1c Draft",
                             canvas_state={"version": 1, "nodes": [], "edges": []},
                             version=1, is_active=True)
    src = Workflow(id=str(uuid.uuid4()), company_id=None, name="T-2.1c Source",
                   trigger_type="manual", scope="core", tier=1, is_active=True)
    s.add(draft)
    s.add(src)
    s.flush()
    mirror = WorkflowTemplate(id=str(uuid.uuid4()), scope="vertical_default", vertical=VERT,
                              workflow_type=f"t21c_mirror_{suffix}", display_name="T-2.1c Mirror",
                              canvas_state={"version": 1, "nodes": [], "edges": []},
                              version=1, is_active=True, mirrored_from_workflow_id=src.id)
    s.add(mirror)
    s.flush()
    ctx = {"db": s, "company": company, "draft": draft, "mirror": mirror,
           "src_id": src.id, "task_ids": [], "run_ids": []}
    s.commit()
    yield ctx
    s.rollback()
    if ctx["run_ids"]:
        s.execute(sql_text("DELETE FROM workflow_run_steps WHERE run_id = ANY(:r)"), {"r": ctx["run_ids"]})
        s.execute(sql_text("DELETE FROM workflow_runs WHERE id = ANY(:r)"), {"r": ctx["run_ids"]})
    if ctx["task_ids"]:
        s.execute(sql_text("DELETE FROM moc_task_trigger WHERE task_catalog_id = ANY(:t)"), {"t": ctx["task_ids"]})
        s.execute(sql_text("DELETE FROM moc_task_catalog WHERE id = ANY(:t)"), {"t": ctx["task_ids"]})
    s.execute(sql_text("DELETE FROM workflow_templates WHERE id IN (:d, :m)"),
              {"d": draft.id, "m": mirror.id})
    # the probe workflow + its step (company-scoped; must go before the company)
    s.execute(sql_text(
        "DELETE FROM workflow_steps WHERE workflow_id IN "
        "(SELECT id FROM workflows WHERE company_id = :c)"
    ), {"c": company.id})
    s.execute(sql_text("DELETE FROM workflows WHERE company_id = :c"), {"c": company.id})
    s.execute(sql_text("DELETE FROM workflows WHERE id = :w"), {"w": ctx["src_id"]})
    s.execute(sql_text("DELETE FROM companies WHERE id = :c"), {"c": company.id})
    s.commit()
    s.close()


def _mk_task(env, template, *, is_live: bool):
    s = env["db"]
    task = MoCTaskCatalog(id=str(uuid.uuid4()), scope="tenant_override", vertical=VERT,
                          tenant_id=env["company"].id, name=f"T {uuid.uuid4().hex[:6]}",
                          workflow_template_id=template.id, is_active=True)
    s.add(task)
    s.flush()
    env["task_ids"].append(task.id)
    trig = MoCTaskTrigger(id=str(uuid.uuid4()), task_catalog_id=task.id, kind="schedule",
                          config={"spec_kind": "time_of_day", "time": "18:00", "days": []},
                          is_active=True, is_live=is_live)
    s.add(trig)
    s.flush()
    s.commit()
    return task, trig


# ── 1. resolve_task exposes is_live + is_mirror ────────────────────────


def test_resolve_task_exposes_is_live(env):
    task, _ = _mk_task(env, env["draft"], is_live=True)
    env["db"].refresh(task)
    shape = resolve_task(env["db"], task)
    assert shape["triggers"][0]["is_live"] is True

    task2, _ = _mk_task(env, env["draft"], is_live=False)
    env["db"].refresh(task2)
    assert resolve_task(env["db"], task2)["triggers"][0]["is_live"] is False


def test_resolve_task_exposes_is_mirror(env):
    compiled_task, _ = _mk_task(env, env["draft"], is_live=False)
    mirror_task, _ = _mk_task(env, env["mirror"], is_live=False)
    env["db"].refresh(compiled_task)
    env["db"].refresh(mirror_task)

    assert resolve_task(env["db"], compiled_task)["workflow"]["is_mirror"] is False
    assert resolve_task(env["db"], mirror_task)["workflow"]["is_mirror"] is True


def test_is_mirror_matches_sweep_discriminator(env):
    """The UI's is_mirror and the sweep's §6 guard must key off the SAME field —
    if they diverged, the toggle could enable a trigger the sweep won't fire live."""
    from app.services.maps_of_content.schedule_sweep import _resolve_go_live

    trig = MoCTaskTrigger(id="x", task_catalog_id="t", kind="schedule", config={}, is_live=True)
    # is_mirror True  ⇔  _resolve_go_live False (for a promoted trigger)
    assert (env["mirror"].mirrored_from_workflow_id is not None) is True
    assert _resolve_go_live(trig, env["mirror"]) is False
    assert (env["draft"].mirrored_from_workflow_id is not None) is False
    assert _resolve_go_live(trig, env["draft"]) is True


# ── 2. list_schedule_runs trigger_id filter (the confirm's preview fetch) ─


def test_schedule_runs_filters_by_trigger(env):
    s = env["db"]
    task, trig = _mk_task(env, env["draft"], is_live=False)
    _, other_trig = _mk_task(env, env["draft"], is_live=False)

    wf = Workflow(id=str(uuid.uuid4()), company_id=env["company"].id, name="probe",
                  trigger_type="manual", scope="tenant", tier=4, is_active=True)
    s.add(wf)
    s.flush()
    step = WorkflowStep(id=str(uuid.uuid4()), workflow_id=wf.id, step_order=1,
                        step_key="s1", step_type="action", config={})
    s.add(step)
    s.flush()

    def _mk_run(trigger_id: str, when: datetime) -> WorkflowRun:
        r = WorkflowRun(id=str(uuid.uuid4()), workflow_id=wf.id, company_id=env["company"].id,
                        trigger_source="moc_task_schedule",
                        trigger_context={"moc_task_trigger_id": trigger_id,
                                         "intended_fire": when.isoformat(),
                                         "task_name": task.name},
                        status="completed", output_data={"__dry_run__": True},
                        started_at=when)
        s.add(r)
        s.flush()
        env["run_ids"].append(r.id)
        s.add(WorkflowRunStep(run_id=r.id, step_id=step.id, step_key="s1", status="completed",
                              output_data={"would": "would execute action:record_marker"}))
        s.flush()
        return r

    older = _mk_run(trig.id, datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc))
    newest = _mk_run(trig.id, datetime(2026, 7, 2, 10, 0, tzinfo=timezone.utc))
    _mk_run(other_trig.id, datetime(2026, 7, 3, 10, 0, tzinfo=timezone.utc))
    s.commit()

    # filtered to the trigger, newest first — limit=1 is the confirm's fetch
    rows = list_schedule_runs(s, limit=1, trigger_id=trig.id)
    assert len(rows) == 1
    assert rows[0]["run_id"] == newest.id
    assert rows[0]["moc_task_trigger_id"] == trig.id
    assert rows[0]["would_do"] == ["would execute action:record_marker"]

    # unfiltered still returns the other trigger's run too
    all_rows = list_schedule_runs(s, limit=50)
    assert {r["run_id"] for r in all_rows} >= {older.id, newest.id}
