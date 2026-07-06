"""MoC event-matcher sweep (Canvas↔Runtime Bridge T-2.2b) — match → fire →
dry-run-safe → idempotent, proven BEFORE any live event-fire.

Assembly claims (the dispatch's list):
  1. A seeded event (order.created, order_type=funeral) + a matching event-
     trigger → the sweep fires DRY-RUN → a WorkflowRun with "would do X" + the
     EVENT PROVENANCE (event_key/event_id in trigger_context), and NO real
     effect (the effect handler never invoked — T-2.0b holds through the
     event sweep).
  2. MATCH CORRECTNESS: retail ≠ funeral → no match; a condition field absent
     from the payload → no match; an event matching no trigger → processed,
     nothing fires.
  3. IDEMPOTENCY (the (trigger, event) pair): re-processing the same event
     does NOT re-fire; one event matching 2 triggers → 2 distinct dry-runs.
  4. FAIL-CLOSED: a malformed condition matches NOTHING.
  5. processed_at: a handled event is marked, not re-swept.
  6. OBSERVABILITY: the unified fires log shows the event fire with source +
     provenance.
  + conditions_match unit coverage (operators, numeric coercion, empty list).

State-immunity: assertions scoped to fixture trigger/event ids (the canon).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.company import Company
from app.models.moc_domain_event import MoCDomainEvent
from app.models.moc_task_catalog import MoCTaskCatalog
from app.models.moc_task_trigger import MoCTaskTrigger
from app.models.workflow import WorkflowRun
from app.models.workflow_template import WorkflowTemplate
from app.services.maps_of_content.event_matcher import (
    check_moc_domain_events,
    conditions_match,
)
from app.services.maps_of_content.schedule_sweep import list_schedule_runs

VERT = "manufacturing"


def _action_canvas() -> dict:
    return {
        "version": 1, "trigger": {"type": "manual"},
        "nodes": [
            {"id": "n_start", "type": "start", "config": {}},
            {"id": "n_act", "type": "action", "label": "Act",
             "config": {"action_type": "log_vault_item", "title": "event probe"}},
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
    company = Company(id=str(uuid.uuid4()), name="Match Co", slug=f"match-{suffix}",
                      vertical=VERT, timezone="America/New_York", is_active=True)
    s.add(company)
    tmpl = WorkflowTemplate(id=str(uuid.uuid4()), scope="vertical_default", vertical=VERT,
                            workflow_type=f"t22b_{suffix}", display_name="T-2.2b Probe",
                            canvas_state=_action_canvas(), version=1, is_active=True)
    s.add(tmpl)
    s.flush()
    ctx = {"db": s, "company": company, "tmpl": tmpl,
           "task_ids": [], "event_ids": []}
    s.commit()
    yield ctx
    s.rollback()
    cid = company.id
    s.execute(sql_text(
        "DELETE FROM workflow_run_steps WHERE run_id IN "
        "(SELECT id FROM workflow_runs WHERE company_id = :c)"), {"c": cid})
    s.execute(sql_text("DELETE FROM vault_items WHERE company_id = :c"), {"c": cid})
    s.execute(sql_text("DELETE FROM workflow_runs WHERE company_id = :c"), {"c": cid})
    s.refresh(tmpl)
    if tmpl.compiled_workflow_id:
        cw = tmpl.compiled_workflow_id
        s.execute(sql_text("UPDATE workflow_templates SET compiled_workflow_id=NULL WHERE id=:t"), {"t": tmpl.id})
        s.execute(sql_text("DELETE FROM workflow_steps WHERE workflow_id=:w"), {"w": cw})
        s.execute(sql_text("DELETE FROM workflows WHERE id=:w"), {"w": cw})
    s.execute(sql_text("DELETE FROM moc_task_trigger WHERE task_catalog_id = ANY(:t)"),
              {"t": ctx["task_ids"] or [""]})
    s.execute(sql_text("DELETE FROM moc_task_catalog WHERE id = ANY(:t)"),
              {"t": ctx["task_ids"] or [""]})
    s.execute(sql_text("DELETE FROM moc_domain_event WHERE company_id = :c"), {"c": cid})
    s.execute(sql_text("DELETE FROM workflow_templates WHERE id = :t"), {"t": tmpl.id})
    s.execute(sql_text("DELETE FROM companies WHERE id = :c"), {"c": cid})
    s.commit()
    s.close()


def _mk_trigger(env, *, conditions, event_key: str = "order.created") -> MoCTaskTrigger:
    s = env["db"]
    task = MoCTaskCatalog(id=str(uuid.uuid4()), scope="tenant_override", vertical=VERT,
                          tenant_id=env["company"].id, name=f"Ev Task {uuid.uuid4().hex[:6]}",
                          workflow_template_id=env["tmpl"].id, is_active=True)
    s.add(task)
    s.flush()
    env["task_ids"].append(task.id)
    trig = MoCTaskTrigger(id=str(uuid.uuid4()), task_catalog_id=task.id, kind="event",
                          config={"event": event_key, "conditions": conditions},
                          is_active=True)
    s.add(trig)
    s.flush()
    s.commit()
    return trig


def _mk_event(env, *, event_key: str = "order.created", payload: dict | None = None) -> MoCDomainEvent:
    s = env["db"]
    ev = MoCDomainEvent(id=str(uuid.uuid4()), company_id=env["company"].id,
                        event_key=event_key, entity_type="sales_order",
                        entity_id=str(uuid.uuid4()), payload=payload or {})
    s.add(ev)
    s.flush()
    env["event_ids"].append(ev.id)
    s.commit()
    return ev


def _runs_for_pair(db, trigger_id: str, event_id: str | None = None) -> list[WorkflowRun]:
    db.expire_all()
    q = db.query(WorkflowRun).filter(
        WorkflowRun.trigger_source == "moc_task_event",
        WorkflowRun.trigger_context["moc_task_trigger_id"].astext == trigger_id,
    )
    if event_id:
        q = q.filter(WorkflowRun.trigger_context["event_id"].astext == event_id)
    return q.all()


def _spy(monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr(
        "app.services.workflow_engine._execute_action",
        lambda *a, **k: (calls.append(1), {"type": "spy"})[1],
    )
    return calls


FUNERAL_COND = [{"field": "order_type", "operator": "==", "value": "funeral"}]


# ── 1. the match → dry-run fire, with provenance, no real effect ────────


def test_matching_event_fires_dry_run_with_provenance(env, monkeypatch):
    trig = _mk_trigger(env, conditions=FUNERAL_COND)
    ev = _mk_event(env, payload={"order_type": "funeral"})
    calls = _spy(monkeypatch)

    result = check_moc_domain_events()

    runs = _runs_for_pair(env["db"], trig.id, ev.id)
    assert len(runs) == 1
    r = runs[0]
    assert (r.output_data or {}).get("__dry_run__") is True     # DRY-RUN
    assert calls == []                                           # NO real effect
    ctx = r.trigger_context
    assert ctx["event_key"] == "order.created"                   # provenance
    assert ctx["event_id"] == ev.id
    assert result["fired_dry_run"] >= 1


# ── 2. match correctness ───────────────────────────────────────────────


def test_non_matching_payload_does_not_fire(env, monkeypatch):
    trig = _mk_trigger(env, conditions=FUNERAL_COND)
    ev = _mk_event(env, payload={"order_type": "retail"})   # retail ≠ funeral
    calls = _spy(monkeypatch)
    check_moc_domain_events()
    assert _runs_for_pair(env["db"], trig.id) == []
    assert calls == []
    env["db"].expire_all()
    assert env["db"].get(MoCDomainEvent, ev.id).processed_at is not None  # still consumed


def test_condition_field_absent_from_payload_no_match(env):
    trig = _mk_trigger(env, conditions=FUNERAL_COND)
    _mk_event(env, payload={"status": "confirmed"})   # no order_type key at all
    check_moc_domain_events()
    assert _runs_for_pair(env["db"], trig.id) == []


def test_event_matching_no_trigger_is_processed_quietly(env):
    ev = _mk_event(env, event_key="delivery.completed", payload={"status": "completed"})
    result = check_moc_domain_events()
    env["db"].expire_all()
    assert env["db"].get(MoCDomainEvent, ev.id).processed_at is not None
    assert result["processed"] >= 1


# ── 3. idempotency — the (trigger, event) pair ─────────────────────────


def test_reprocessed_event_does_not_refire(env):
    trig = _mk_trigger(env, conditions=FUNERAL_COND)
    ev = _mk_event(env, payload={"order_type": "funeral"})
    check_moc_domain_events()                      # fires once
    # simulate an at-least-once redelivery: force the event back to unprocessed
    env["db"].execute(sql_text(
        "UPDATE moc_domain_event SET processed_at = NULL WHERE id = :e"), {"e": ev.id})
    env["db"].commit()
    check_moc_domain_events()                      # re-processes the same event
    assert len(_runs_for_pair(env["db"], trig.id, ev.id)) == 1   # ONCE, not twice


def test_one_event_matching_two_triggers_fires_two_distinct_runs(env):
    trig_a = _mk_trigger(env, conditions=FUNERAL_COND)
    trig_b = _mk_trigger(env, conditions=[])       # unconditional on the event
    ev = _mk_event(env, payload={"order_type": "funeral"})
    check_moc_domain_events()
    assert len(_runs_for_pair(env["db"], trig_a.id, ev.id)) == 1
    assert len(_runs_for_pair(env["db"], trig_b.id, ev.id)) == 1  # distinct pairs


# ── 4. fail-closed ─────────────────────────────────────────────────────


def test_malformed_condition_matches_nothing(env, monkeypatch):
    """A broken condition fires NOTHING (never everything) — the blast-radius
    guard. Insert the malformed config directly (the validator would reject it
    at authoring; the matcher must still fail closed against drifted data)."""
    trig = _mk_trigger(env, conditions=FUNERAL_COND)
    env["db"].execute(sql_text(
        "UPDATE moc_task_trigger SET config = :c WHERE id = :t"),
        {"c": '{"event": "order.created", "conditions": "order_type==funeral"}',
         "t": trig.id})   # a FLAT STRING — the malformed shape
    env["db"].commit()
    calls = _spy(monkeypatch)
    _mk_event(env, payload={"order_type": "funeral"})
    check_moc_domain_events()
    assert _runs_for_pair(env["db"], trig.id) == []
    assert calls == []


# ── 5. processed marking ───────────────────────────────────────────────


def test_processed_event_is_not_reswept(env):
    trig = _mk_trigger(env, conditions=FUNERAL_COND)
    ev = _mk_event(env, payload={"order_type": "funeral"})
    check_moc_domain_events()
    env["db"].expire_all()
    first_processed = env["db"].get(MoCDomainEvent, ev.id).processed_at
    assert first_processed is not None
    result2 = check_moc_domain_events()             # second tick — nothing unprocessed of ours
    env["db"].expire_all()
    assert env["db"].get(MoCDomainEvent, ev.id).processed_at == first_processed
    assert len(_runs_for_pair(env["db"], trig.id, ev.id)) == 1
    assert isinstance(result2["processed"], int)


# ── 6. observability — the unified fires log ───────────────────────────


def test_event_fire_visible_with_provenance_in_fires_log(env):
    trig = _mk_trigger(env, conditions=FUNERAL_COND)
    ev = _mk_event(env, payload={"order_type": "funeral"})
    check_moc_domain_events()

    log = list_schedule_runs(env["db"], limit=100, trigger_id=trig.id)
    assert len(log) == 1
    entry = log[0]
    assert entry["source"] == "event"                            # the discriminator
    assert entry["event_key"] == "order.created"                 # provenance
    assert entry["event_id"] == ev.id
    assert entry["is_dry_run"] is True
    assert any("would execute action:log_vault_item" in w for w in entry["would_do"])


# ── unit: conditions_match (pure) ──────────────────────────────────────


def test_conditions_match_operators():
    p = {"order_type": "funeral", "total": 1200, "status": "confirmed"}
    m = conditions_match
    assert m([{"field": "order_type", "operator": "==", "value": "funeral"}], p)
    assert not m([{"field": "order_type", "operator": "==", "value": "retail"}], p)
    assert m([{"field": "order_type", "operator": "!=", "value": "retail"}], p)
    assert m([{"field": "order_type", "operator": "in", "value": ["funeral", "retail"]}], p)
    assert not m([{"field": "order_type", "operator": "in", "value": "funeral"}], p)  # non-list in
    assert m([{"field": "total", "operator": ">", "value": 1000}], p)
    assert m([{"field": "total", "operator": "<=", "value": "1200"}], p)   # string-number coerces
    assert not m([{"field": "status", "operator": ">", "value": 5}], p)    # non-numeric fails closed
    assert m([{"field": "status", "operator": "contains", "value": "firm"}], p)
    # AND across elements (rich-ready)
    assert m([{"field": "order_type", "operator": "==", "value": "funeral"},
              {"field": "total", "operator": ">", "value": 1000}], p)
    assert not m([{"field": "order_type", "operator": "==", "value": "funeral"},
                  {"field": "total", "operator": ">", "value": 9999}], p)
    # empty list = unconditional (event_key alone)
    assert m([], p)
    # malformed shapes fail closed
    assert not m("order_type==funeral", p)
    assert not m([{"field": "order_type"}], p)
    assert not m([{"field": "order_type", "operator": "~=", "value": "x"}], p)
    assert not m([42], p)
