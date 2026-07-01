"""Canvas↔Runtime Bridge T-2.0 — the SPINE, proven by a canvas that RUNS.

The witness for T-2.0 is not a UI — it's a canvas executing. Assembly tests (JCF-1
at the highest stakes):
  1. RE-POINT: a mirror → re-point → its runtime SOURCE runs → WorkflowRun completes.
  2. COMPILE: a linear canvas → compile → engine runs → WorkflowRun completes AND
     the run reflects the canvas's real shape (N steps, in order — not degenerate).
  3. REJECT: a parallel / forked canvas → compile → REJECTED loudly, nothing runs
     (no silent partial-compile that would run a DIFFERENT workflow than authored).
  4. GATE: execution without the explicit gate → ExecutionGatedError (T-2.0 has no
     engine dry-run yet; live runs are test-only until T-2.0b).
  5. LOUD FAILURE: a dangling mirror → RepointError; a run that raises mid-flight →
     WorkflowRun.status="failed" + error_message (recorded loudly, not swallowed).

All benign steps use `show_confirmation` (inline, no side effects) so the tests
prove EXECUTION without hitting real invoices/notifications.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.workflow import Workflow, WorkflowStep
from app.models.workflow_template import WorkflowTemplate
from app.services.workflows import execution_bridge as bridge
from app.services.workflows.canvas_compiler import (
    CanvasCompileError,
    compile_canvas_to_workflow,
)

VERT = "manufacturing"


def _benign_action(node_id: str, label: str) -> dict:
    """An inline, side-effect-free action node (show_confirmation)."""
    return {"id": node_id, "type": "action", "label": label,
            "config": {"action_type": "show_confirmation", "message": label}}


def _linear_canvas() -> dict:
    return {
        "version": 1, "trigger": {"type": "manual"},
        "nodes": [
            {"id": "n_start", "type": "start", "config": {}},
            _benign_action("n_a", "Step A"),
            _benign_action("n_b", "Step B"),
            {"id": "n_end", "type": "end", "config": {}},
        ],
        "edges": [
            {"id": "e1", "source": "n_start", "target": "n_a"},
            {"id": "e2", "source": "n_a", "target": "n_b"},
            {"id": "e3", "source": "n_b", "target": "n_end"},
        ],
    }


@pytest.fixture
def env():
    s = SessionLocal()
    company_id = s.execute(
        sql_text("SELECT id FROM companies WHERE is_active = true LIMIT 1")
    ).scalar()
    if not company_id:
        s.close()
        pytest.skip("no active company in the dev DB")
    templates: list[str] = []
    workflows: list[str] = []  # created sources + compiled outputs
    yield {"db": s, "company_id": company_id, "templates": templates, "workflows": workflows}
    s.rollback()
    if workflows:
        ids = tuple(workflows)
        s.execute(sql_text(
            "DELETE FROM workflow_run_steps WHERE run_id IN "
            "(SELECT id FROM workflow_runs WHERE workflow_id = ANY(:ids))"
        ), {"ids": list(ids)})
        s.execute(sql_text("DELETE FROM workflow_runs WHERE workflow_id = ANY(:ids)"), {"ids": list(ids)})
        s.execute(sql_text("DELETE FROM workflow_steps WHERE workflow_id = ANY(:ids)"), {"ids": list(ids)})
        s.execute(sql_text("DELETE FROM workflows WHERE id = ANY(:ids)"), {"ids": list(ids)})
    if templates:
        s.execute(sql_text("DELETE FROM workflow_templates WHERE id = ANY(:ids)"), {"ids": list(templates)})
    s.commit()
    s.close()


def _mk_template(env, *, canvas: dict, mirrored_from: str | None = None) -> WorkflowTemplate:
    s = env["db"]
    t = WorkflowTemplate(
        id=str(uuid.uuid4()), scope="vertical_default", vertical=VERT,
        workflow_type=f"t2test_{uuid.uuid4().hex[:8]}", display_name="T-2 Test Template",
        canvas_state=canvas, version=1, is_active=True,
        mirrored_from_workflow_id=mirrored_from,
    )
    s.add(t)
    s.flush()
    env["templates"].append(t.id)
    return t


def _mk_runtime_source(env) -> str:
    """A runnable runtime workflow (one benign step) — a mirror's source."""
    s = env["db"]
    wf = Workflow(
        id=str(uuid.uuid4()), company_id=None, name="T-2 Source",
        trigger_type="manual", scope="core", tier=1, is_active=True,
    )
    s.add(wf)
    s.flush()
    s.add(WorkflowStep(
        id=str(uuid.uuid4()), workflow_id=wf.id, step_order=1, step_key="s1",
        step_type="action", config={"action_type": "show_confirmation", "message": "ok"},
    ))
    s.flush()
    env["workflows"].append(wf.id)
    return wf.id


# ── 1. RE-POINT ────────────────────────────────────────────────────────


def test_repoint_mirror_runs_the_source(env):
    s = env["db"]
    source_id = _mk_runtime_source(env)
    tmpl = _mk_template(env, canvas={"version": 1, "nodes": [], "edges": []},
                        mirrored_from=source_id)
    s.commit()

    # resolve returns the SOURCE (no compile, no new workflow)
    resolved = bridge.resolve_executable_workflow(
        s, template_id=tmpl.id, company_id=env["company_id"])
    assert resolved == source_id

    run = bridge.execute_template(
        s, template_id=tmpl.id, company_id=env["company_id"], allow_live_execution=True)
    assert run.workflow_id == source_id  # ran the source, not a compiled copy
    assert run.status == "completed"


# ── 2. COMPILE (linear) — runs AND reflects the canvas shape ───────────


def test_compile_linear_runs_and_reflects_shape(env):
    s = env["db"]
    tmpl = _mk_template(env, canvas=_linear_canvas())  # draft (no mirror)
    s.commit()

    run = bridge.execute_template(
        s, template_id=tmpl.id, company_id=env["company_id"], allow_live_execution=True)
    env["workflows"].append(run.workflow_id)  # the compiled workflow
    assert run.status == "completed"

    # shape fidelity: 2 real steps (start/end dropped), in canvas order.
    steps = (
        s.query(WorkflowStep)
        .filter(WorkflowStep.workflow_id == run.workflow_id)
        .order_by(WorkflowStep.step_order)
        .all()
    )
    assert [st.step_key for st in steps] == ["n_a", "n_b"]
    assert all(st.step_type == "action" for st in steps)
    # compiled workflow is scheduler-inert (trigger forced to manual)
    wf = s.get(Workflow, run.workflow_id)
    assert wf.trigger_type == "manual"


def test_compile_preserves_action_type_config(env):
    """A node.config carrying action_type is carried verbatim (variable refs +
    action dispatch survive the compile)."""
    s = env["db"]
    canvas = _linear_canvas()
    tmpl = _mk_template(env, canvas=canvas)
    wf = compile_canvas_to_workflow(
        s, canvas_state=canvas, company_id=env["company_id"], name="cfg")
    env["workflows"].append(wf.id)
    s.commit()
    step = (
        s.query(WorkflowStep)
        .filter(WorkflowStep.workflow_id == wf.id, WorkflowStep.step_key == "n_a")
        .one()
    )
    assert step.config["action_type"] == "show_confirmation"
    assert step.config["message"] == "Step A"


# ── 3. REJECT (out-of-subset) — loud, nothing runs ─────────────────────


def test_parallel_canvas_is_rejected(env):
    s = env["db"]
    canvas = {
        "version": 1,
        "nodes": [
            {"id": "n_start", "type": "start", "config": {}},
            {"id": "n_split", "type": "parallel_split", "config": {}},
            {"id": "n_end", "type": "end", "config": {}},
        ],
        "edges": [
            {"id": "e1", "source": "n_start", "target": "n_split"},
            {"id": "e2", "source": "n_split", "target": "n_end"},
        ],
    }
    with pytest.raises(CanvasCompileError, match="parallel_split"):
        compile_canvas_to_workflow(s, canvas_state=canvas, company_id=env["company_id"], name="p")


def test_conditional_canvas_is_rejected(env):
    """condition/decision deferred to T-2.0b (no true/false edge convention)."""
    s = env["db"]
    canvas = {
        "version": 1,
        "nodes": [
            {"id": "n_start", "type": "start", "config": {}},
            {"id": "n_cond", "type": "condition", "config": {}},
            {"id": "n_end", "type": "end", "config": {}},
        ],
        "edges": [
            {"id": "e1", "source": "n_start", "target": "n_cond"},
            {"id": "e2", "source": "n_cond", "target": "n_end"},
        ],
    }
    with pytest.raises(CanvasCompileError, match="condition"):
        compile_canvas_to_workflow(s, canvas_state=canvas, company_id=env["company_id"], name="c")


def test_forked_canvas_is_rejected(env):
    """A node with >1 outgoing edge is non-linear → rejected (no silent drop)."""
    s = env["db"]
    canvas = {
        "version": 1,
        "nodes": [
            {"id": "n_start", "type": "start", "config": {}},
            _benign_action("n_a", "A"),
            _benign_action("n_b", "B"),
            _benign_action("n_c", "C"),
        ],
        "edges": [
            {"id": "e1", "source": "n_start", "target": "n_a"},
            {"id": "e2", "source": "n_a", "target": "n_b"},  # fork:
            {"id": "e3", "source": "n_a", "target": "n_c"},  # n_a → two targets
        ],
    }
    with pytest.raises(CanvasCompileError, match="outgoing edges"):
        compile_canvas_to_workflow(s, canvas_state=canvas, company_id=env["company_id"], name="f")


# ── 4. GATE — execution is off by default ──────────────────────────────


def test_execution_is_gated_by_default(env):
    s = env["db"]
    tmpl = _mk_template(env, canvas=_linear_canvas())
    s.commit()
    with pytest.raises(bridge.ExecutionGatedError):
        bridge.execute_template(s, template_id=tmpl.id, company_id=env["company_id"])
    # nothing compiled/ran
    assert s.execute(
        sql_text("SELECT COUNT(*) FROM workflow_runs WHERE trigger_source = 'manual' "
                 "AND company_id = :c AND workflow_id IN "
                 "(SELECT id FROM workflows WHERE name = 'T-2 Test Template')"),
        {"c": env["company_id"]},
    ).scalar() == 0


# ── 5. LOUD FAILURE ────────────────────────────────────────────────────


def test_not_a_mirror_repoint_raises_loudly(env):
    """repoint on a non-mirror template (no source) raises loudly."""
    s = env["db"]
    tmpl = _mk_template(env, canvas=_linear_canvas())  # mirrored_from=None
    s.commit()
    with pytest.raises(bridge.RepointError, match="not a mirror"):
        bridge.repoint_mirror(s, tmpl)


def test_dangling_mirror_raises_loudly(env):
    """A mirror whose runtime source is gone → RepointError. The FK is ON DELETE
    SET NULL, so a persisted dangling ref can't exist — exercise the defensive
    branch on a transient template pointing at a vanished source."""
    s = env["db"]
    transient = WorkflowTemplate(
        id=str(uuid.uuid4()), scope="vertical_default", vertical=VERT,
        workflow_type="t2_dangling", display_name="Dangling",
        canvas_state={"version": 1, "nodes": [], "edges": []}, version=1,
        is_active=True, mirrored_from_workflow_id="vanished-" + uuid.uuid4().hex,
    )
    with pytest.raises(bridge.RepointError, match="dangling"):
        bridge.repoint_mirror(s, transient)


def test_run_failure_is_recorded_loudly(env, monkeypatch):
    s = env["db"]
    tmpl = _mk_template(env, canvas=_linear_canvas())
    s.commit()

    def _boom(*a, **k):
        raise RuntimeError("boom in a step")

    # Inject a raise at the action dispatch (inside _execute_step's try → _fail_run).
    monkeypatch.setattr("app.services.workflow_engine._execute_action", _boom)

    run = bridge.execute_template(
        s, template_id=tmpl.id, company_id=env["company_id"], allow_live_execution=True)
    env["workflows"].append(run.workflow_id)
    assert run.status == "failed"  # recorded loudly, not swallowed
    assert run.error_message and "boom in a step" in run.error_message


def test_missing_template_raises_loudly(env):
    s = env["db"]
    with pytest.raises(bridge.ExecutionBridgeError, match="not found"):
        bridge.resolve_executable_workflow(
            s, template_id="no-such-template", company_id=env["company_id"])
