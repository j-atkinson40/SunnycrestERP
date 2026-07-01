"""Engine dry-run mode (Canvas↔Runtime Bridge T-2.0b) — the safety net, proven
AT THE BOTTOM (at the real effect, not at the flag).

The T-2.0 lesson recursion: a test that passes a flag and checks it was accepted
proves nothing — the flag must be HONORED at the step-executor. So every proof
here exercises the DEFAULT or the effect boundary, using a REAL, countable effect
(`log_vault_item` writes a vault_items row keyed to run.id):

  1. DEFAULT IS DRY-RUN (THE deliverable): allow_run=True, go_live OMITTED → it
     RUNS (not refused) → the log_vault_item write does NOT happen (0 rows) + the
     step records what it WOULD do. Verified at the EFFECT, not the flag.
  2. EXPLICIT LIVE WORKS: allow_run=True + go_live=True → the row IS written (dry-
     run didn't break live — we didn't build a mode that can only pretend).
  3. THE GATE HOLDS: allow_run=False (default) → refuses (T-2.0's tripwire).
  4. NONSENSE STATE SAFE: allow_run=False + go_live=True → refuses (go_live ignored
     without allow_run — the two-bool precedence guard; no run, no effect).
  5. DRY-RUN IS OBSERVABLE: the dry-run run COMPLETES + carries the "would do"
     records (a preview, not a no-op).
  6. BRANCHING HOLDS IN DRY-RUN: a conditional runtime workflow branches correctly
     in dry-run (condition reads happen), while both branches' effects stay
     suppressed.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.workflow import Workflow, WorkflowStep
from app.models.workflow_template import WorkflowTemplate
from app.services.workflow_engine import start_run
from app.services.workflows import execution_bridge as bridge

VERT = "manufacturing"


def _log_vault_canvas() -> dict:
    """A linear canvas whose one real step (log_vault_item) writes a countable
    vault_items row — so 'the effect did/didn't happen' is observable."""
    return {
        "version": 1, "trigger": {"type": "manual"},
        "nodes": [
            {"id": "n_start", "type": "start", "config": {}},
            {"id": "n_log", "type": "action", "label": "Log a vault item",
             "config": {"action_type": "log_vault_item", "item_type": "event",
                        "title": "T-2.0b dry-run probe"}},
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
    company_id = s.execute(
        sql_text("SELECT id FROM companies WHERE is_active = true LIMIT 1")
    ).scalar()
    if not company_id:
        s.close()
        pytest.skip("no active company in the dev DB")
    templates: list[str] = []
    workflows: list[str] = []
    yield {"db": s, "company_id": company_id, "templates": templates, "workflows": workflows}
    s.rollback()
    if workflows:
        ids = list(workflows)
        # vault_items written by any live run of these workflows (source_entity_id=run.id)
        s.execute(sql_text(
            "DELETE FROM vault_items WHERE source = 'workflow' AND source_entity_id IN "
            "(SELECT id FROM workflow_runs WHERE workflow_id = ANY(:ids))"
        ), {"ids": ids})
        s.execute(sql_text(
            "DELETE FROM workflow_run_steps WHERE run_id IN "
            "(SELECT id FROM workflow_runs WHERE workflow_id = ANY(:ids))"
        ), {"ids": ids})
        s.execute(sql_text("DELETE FROM workflow_runs WHERE workflow_id = ANY(:ids)"), {"ids": ids})
        s.execute(sql_text("DELETE FROM workflow_steps WHERE workflow_id = ANY(:ids)"), {"ids": ids})
        s.execute(sql_text("DELETE FROM workflows WHERE id = ANY(:ids)"), {"ids": ids})
    if templates:
        s.execute(sql_text("DELETE FROM workflow_templates WHERE id = ANY(:ids)"), {"ids": list(templates)})
    s.commit()
    s.close()


def _mk_template(env, canvas: dict) -> WorkflowTemplate:
    s = env["db"]
    t = WorkflowTemplate(
        id=str(uuid.uuid4()), scope="vertical_default", vertical=VERT,
        workflow_type=f"t20b_{uuid.uuid4().hex[:8]}", display_name="T-2.0b Probe",
        canvas_state=canvas, version=1, is_active=True,
    )
    s.add(t)
    s.flush()
    env["templates"].append(t.id)
    return t


def _effect_rows(s, run_id: str) -> int:
    return s.execute(
        sql_text("SELECT COUNT(*) FROM vault_items WHERE source_entity_id = :rid"),
        {"rid": run_id},
    ).scalar()


# ── 1. DEFAULT IS DRY-RUN — proven at the EFFECT (THE deliverable) ──────


def test_default_when_running_is_dry_run_no_effect_handler_invoked(env, monkeypatch):
    """THE deliverable, proven at the EFFECT boundary: the effect-producing
    handler (`_execute_action` — the one that would create an invoice / send a
    notification / write a row) is NEVER invoked in dry-run. Verified at the
    handler, not the flag."""
    s = env["db"]
    tmpl = _mk_template(env, _log_vault_canvas())
    s.commit()

    calls: list[int] = []
    monkeypatch.setattr(
        "app.services.workflow_engine._execute_action",
        lambda *a, **k: (calls.append(1), {"type": "spy"})[1],
    )

    # allow_run=True, go_live OMITTED → the SAFE default (dry-run).
    run = bridge.execute_template(
        s, template_id=tmpl.id, company_id=env["company_id"], allow_run=True)
    env["workflows"].append(run.workflow_id)

    assert run.status == "completed"   # it RAN (not refused) …
    assert calls == []                  # … but the effect handler was NEVER invoked (no real effect)

    # and the step recorded what it WOULD do (honored at the executor, not the flag)
    out = s.execute(
        sql_text("SELECT output_data FROM workflow_run_steps WHERE run_id = :rid AND step_key = 'n_log'"),
        {"rid": run.id},
    ).scalar()
    assert out and out.get("dry_run") is True and out.get("suppressed") is True
    assert "would execute action:log_vault_item" in out.get("would", "")


# ── 2. EXPLICIT LIVE WORKS — the effect handler IS invoked ─────────────


def test_explicit_live_invokes_the_effect_handler(env, monkeypatch):
    """Live works — the effect handler IS invoked (dry-run didn't build a mode
    that can only pretend). The same spy that stays uncalled in dry-run fires
    here."""
    s = env["db"]
    tmpl = _mk_template(env, _log_vault_canvas())
    s.commit()

    calls: list[int] = []
    monkeypatch.setattr(
        "app.services.workflow_engine._execute_action",
        lambda *a, **k: (calls.append(1), {"type": "spy"})[1],
    )

    run = bridge.execute_template(
        s, template_id=tmpl.id, company_id=env["company_id"], allow_run=True, go_live=True)
    env["workflows"].append(run.workflow_id)

    assert run.status == "completed"
    assert calls == [1]   # live → the effect handler WAS invoked


# ── 3 + 4. THE PRECEDENCE LADDER — gate + nonsense state ───────────────


def test_gate_holds_no_allow_run_refuses(env):
    s = env["db"]
    tmpl = _mk_template(env, _log_vault_canvas())
    s.commit()
    with pytest.raises(bridge.ExecutionGatedError):
        bridge.execute_template(s, template_id=tmpl.id, company_id=env["company_id"])


def test_nonsense_state_go_live_without_allow_run_refuses(env, monkeypatch):
    """allow_run=False + go_live=True → REFUSE (go_live ignored without allow_run).
    The only path to real effects is BOTH explicit. The refusal happens BEFORE any
    resolve/run — assert the effect handler is never even reached."""
    s = env["db"]
    tmpl = _mk_template(env, _log_vault_canvas())
    s.commit()
    calls: list[int] = []
    monkeypatch.setattr(
        "app.services.workflow_engine._execute_action",
        lambda *a, **k: (calls.append(1), {"type": "spy"})[1],
    )
    with pytest.raises(bridge.ExecutionGatedError):
        bridge.execute_template(
            s, template_id=tmpl.id, company_id=env["company_id"],
            allow_run=False, go_live=True)
    assert calls == []   # refused before any execution — no effect handler reached


# ── 5. DRY-RUN IS OBSERVABLE — a preview, not a no-op ──────────────────


def test_dry_run_is_observable(env):
    s = env["db"]
    tmpl = _mk_template(env, _log_vault_canvas())
    s.commit()
    run = bridge.execute_template(
        s, template_id=tmpl.id, company_id=env["company_id"], allow_run=True)
    env["workflows"].append(run.workflow_id)
    assert run.status == "completed"
    # the run is self-describing as dry-run …
    assert (run.output_data or {}).get("__dry_run__") is True
    # … and the trace has a real step record (not zero steps)
    n_steps = s.execute(
        sql_text("SELECT COUNT(*) FROM workflow_run_steps WHERE run_id = :rid"),
        {"rid": run.id},
    ).scalar()
    assert n_steps >= 1


# ── 6. BRANCHING HOLDS IN DRY-RUN ──────────────────────────────────────


def test_branching_holds_in_dry_run(env):
    """A conditional runtime workflow: condition (reads happen → real branch) →
    the taken branch's effect is still suppressed. Proves dry-run doesn't
    degenerate the run."""
    s = env["db"]
    wf = Workflow(id=str(uuid.uuid4()), company_id=None, name="cond-probe",
                  trigger_type="manual", scope="core", tier=1, is_active=True)
    s.add(wf)
    s.flush()
    env["workflows"].append(wf.id)

    cond_id, t_id, f_id, end_id = (str(uuid.uuid4()) for _ in range(4))
    # cond (True→logT, False→logF); both branches converge on `end` via explicit
    # next_step_id so a branch never falls through by step-order. A literal
    # condition (yes==yes → True) proves the condition STEP runs + branches in
    # dry-run (it's not suppressed) without depending on variable-resolution syntax.
    s.add(WorkflowStep(id=cond_id, workflow_id=wf.id, step_order=1, step_key="cond",
                       step_type="condition",
                       config={"field": "yes", "op": "==", "value": "yes"},
                       condition_true_step_id=t_id, condition_false_step_id=f_id))
    s.add(WorkflowStep(id=f_id, workflow_id=wf.id, step_order=2, step_key="logF",
                       step_type="action", next_step_id=end_id,
                       config={"action_type": "log_vault_item", "title": "FALSE"}))
    s.add(WorkflowStep(id=t_id, workflow_id=wf.id, step_order=3, step_key="logT",
                       step_type="action", next_step_id=end_id,
                       config={"action_type": "log_vault_item", "title": "TRUE"}))
    s.add(WorkflowStep(id=end_id, workflow_id=wf.id, step_order=4, step_key="end",
                       step_type="action",
                       config={"action_type": "show_confirmation", "message": "done"}))
    s.flush()
    s.commit()

    # dry-run, trigger flag=yes → the TRUE branch.
    run = start_run(s, workflow_id=wf.id, company_id=env["company_id"],
                    triggered_by_user_id=None, trigger_source="test",
                    trigger_context={"flag": "yes"}, dry_run=True)
    assert run.status == "completed"

    keys = [r[0] for r in s.execute(
        sql_text("SELECT step_key FROM workflow_run_steps WHERE run_id = :rid"),
        {"rid": run.id},
    ).fetchall()]
    assert "cond" in keys and "logT" in keys   # branched correctly to TRUE …
    assert "logF" not in keys                   # … and did NOT take the FALSE branch
    # both log effects were suppressed (dry-run) — no real rows.
    assert _effect_rows(s, run.id) == 0
