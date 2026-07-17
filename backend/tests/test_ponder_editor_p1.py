"""The ponder's editing grammar (Tenant Ponder-Editor P1, commit sets 2+3).

WRITE-WHAT-YOU-READ symmetry, pinned per editor:
  * WHEN beat — prefers the task's OWN triggers (the T-1b rows the editor
    writes); saving a trigger re-derives the beat's sentence from the same
    grammar the editor's live readback mirrors. Runtime fallback preserved
    for tasks with no declared triggers.
  * step beats — carry the DECLARED params (the same describe shape the
    tenant route serves); a saved platform live value shows up in BOTH the
    beat's params and the audience/artifact derivation (the derivation reads
    merged config — the same effective values fire time uses).
  * script-level is_live — the live-edit confirm's gravity.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.moc_task_catalog import MoCTaskCatalog
from app.models.workflow import Workflow, WorkflowStep, WorkflowStepParam
from app.models.workflow_template import WorkflowTemplate
from app.services.maps_of_content import triggers as triggers_svc
from app.services.maps_of_content.ponder import build_ponder_script


@pytest.fixture
def db():
    s = SessionLocal()
    created = {"tasks": [], "templates": [], "workflows": []}
    s._ponder_created = created  # type: ignore[attr-defined]
    yield s
    s.rollback()
    for tid in created["tasks"]:
        s.execute(sql_text("DELETE FROM moc_task_trigger WHERE task_catalog_id = :t"), {"t": tid})
        s.execute(sql_text("DELETE FROM moc_task_catalog_focuses WHERE task_catalog_id = :t"), {"t": tid})
        s.execute(sql_text("DELETE FROM moc_task_catalog WHERE id = :t"), {"t": tid})
    for tpl in created["templates"]:
        s.execute(sql_text("DELETE FROM workflow_templates WHERE id = :t"), {"t": tpl})
    for wid in created["workflows"]:
        s.execute(sql_text("DELETE FROM workflow_step_params WHERE workflow_id = :w"), {"w": wid})
        s.execute(sql_text("DELETE FROM workflow_steps WHERE workflow_id = :w"), {"w": wid})
        s.execute(sql_text("DELETE FROM workflows WHERE id = :w"), {"w": wid})
    s.commit()
    s.close()


def _mk_task(db, *, steps=None, params=None, trigger_type="scheduled"):
    """A mirror task over a small runtime workflow (statement-run shaped).

    T-0 note: trigger_type="scheduled" (default) makes the runtime the
    schedule AUTHORITY — the WHEN beat is badged + blocked. Composer-grammar
    tests pass trigger_type="manual" (MoC authority — composed triggers own
    the beat honestly; the block is pinned in test_moc_t0_authority.py)."""
    created = db._ponder_created
    suffix = uuid.uuid4().hex[:8]
    wf_id = f"wf_test_ponder_{suffix}"
    steps = steps or [
        ("identify", "action", {"description": "Find charge-account customers"}),
        ("send_statements", "action",
         {"description": "Email approved statements", "action_type": "send_email"}),
    ]
    db.add(Workflow(
        id=wf_id, company_id=None, name=f"Ponder P1 {suffix}", tier=1,
        scope="core", trigger_type=trigger_type,
        trigger_config=(
            {"cron": "0 6 1 * *", "timezone": "America/New_York"}
            if trigger_type == "scheduled" else {}
        ),
        is_active=True,
    ))
    nodes = []
    for i, (k, t, c) in enumerate(steps):
        db.add(WorkflowStep(
            workflow_id=wf_id, step_order=i + 1, step_key=k, step_type=t, config=c,
        ))
        nodes.append({"id": k, "type": t, "label": k, "config": c})
    edges = [
        {"id": f"e{i}", "source": steps[i - 1][0], "target": steps[i][0]}
        for i in range(1, len(steps))
    ]
    for p in params or []:
        db.add(WorkflowStepParam(
            workflow_id=wf_id, company_id=None, step_key=p["step_key"],
            param_key=p["param_key"], label=p.get("label", p["param_key"]),
            param_type=p.get("param_type", "text"),
            default_value=p.get("default_value"),
            current_value=p.get("current_value"),
            is_configurable=p.get("is_configurable", True),
            validation=p.get("validation"),
        ))
    tpl = WorkflowTemplate(
        id=str(uuid.uuid4()), scope="platform_default", vertical=None,
        workflow_type=f"ponder_p1_{suffix}", display_name=f"Ponder P1 {suffix}",
        version=1, is_active=True,
        canvas_state={"version": 1, "nodes": nodes, "edges": edges},
        mirrored_from_workflow_id=wf_id,
    )
    db.add(tpl)
    db.flush()
    task = MoCTaskCatalog(
        scope="vertical_default", vertical="manufacturing",
        name=f"Ponder P1 Task {suffix}", workflow_template_id=tpl.id,
    )
    db.add(task)
    db.commit()
    created["workflows"].append(wf_id)
    created["templates"].append(tpl.id)
    created["tasks"].append(task.id)
    return task, wf_id


class TestWhenBeatTriggers:
    def test_runtime_scheduled_mirror_reads_authority_and_blocks(self, db):
        # T-0: the runtime scheduler is the firing truth for a scheduled
        # mirror — the beat teaches ITS schedule and the composer blocks.
        task, _ = _mk_task(db)
        script = build_ponder_script(db, task.id)
        when = script["beats"][0]
        assert when["key"] == "when"
        assert "1st of each month at 6:00 AM" in when["text"]
        assert when["editable"] is False
        assert when["managed_by"] == "standard_scheduler"
        assert when["triggers"] == []

    def test_task_schedule_trigger_owns_the_beat(self, db):
        """The editing loop's read half: an ordinal trigger on the task row →
        the beat speaks ITS sentence (the readback grammar), not the runtime
        fallback."""
        task, _ = _mk_task(db, trigger_type="manual")
        trig = triggers_svc.add_trigger(
            db, task_catalog_id=task.id, kind="schedule",
            config={"spec_kind": "ordinal_weekday", "ordinal": 1,
                    "weekday": "mon", "time": "16:00"},
        )
        db.commit()
        script = build_ponder_script(db, task.id)
        when = script["beats"][0]
        assert when["text"] == "The first Monday of every month at 4:00 PM."
        assert when["motif"] == {"kind": "clock"}
        assert when["editable"] is True
        assert [t["id"] for t in when["triggers"]] == [trig.id]
        assert when["triggers"][0]["summary"] == "Monthly · 1st Mon, 4:00 PM"

    def test_edit_then_rederive_closes_the_loop(self, db):
        """The witness in miniature: patch the trigger through the T-1b
        machinery → the beat's derived sentence changes to match."""
        task, _ = _mk_task(db, trigger_type="manual")
        trig = triggers_svc.add_trigger(
            db, task_catalog_id=task.id, kind="schedule",
            config={"spec_kind": "ordinal_weekday", "ordinal": 1,
                    "weekday": "mon", "time": "16:00"},
        )
        db.commit()
        triggers_svc.patch_trigger(
            db, trigger_id=trig.id,
            config={"spec_kind": "ordinal_weekday", "ordinal": "last",
                    "weekday": "fri", "time": "09:30"},
        )
        db.commit()
        when = build_ponder_script(db, task.id)["beats"][0]
        assert when["text"] == "The last Friday of every month at 9:30 AM."

    def test_event_trigger_prose_with_condition(self, db):
        task, _ = _mk_task(db, trigger_type="manual")
        # Bypass catalog validation (no synthetic catalog event needed) — the
        # prose path is what's under test; write the row directly.
        from app.models.moc_task_trigger import MoCTaskTrigger
        db.add(MoCTaskTrigger(
            task_catalog_id=task.id, kind="event",
            config={"event": "order.created",
                    "conditions": [{"field": "order_type", "operator": "==",
                                    "value": "vault"}]},
        ))
        db.commit()
        when = build_ponder_script(db, task.id)["beats"][0]
        assert "Whenever order created occurs" in when["text"]
        assert "(where order_type == vault)" in when["text"]
        assert when["motif"] == {"kind": "signal"}

    def test_inactive_triggers_do_not_speak(self, db):
        task, _ = _mk_task(db)
        trig = triggers_svc.add_trigger(
            db, task_catalog_id=task.id, kind="schedule",
            config={"spec_kind": "time_of_day", "time": "18:00", "days": []},
        )
        db.commit()
        triggers_svc.patch_trigger(db, trigger_id=trig.id, is_active=False)
        db.commit()
        when = build_ponder_script(db, task.id)["beats"][0]
        # Falls back to runtime prose; the inactive row still rides the
        # payload (the editor shows it), it just doesn't own the sentence.
        assert "1st of each month" in when["text"]
        assert len(when["triggers"]) == 1

    def test_script_is_live_flag(self, db):
        task, _ = _mk_task(db)
        assert build_ponder_script(db, task.id)["is_live"] is False
        trig = triggers_svc.add_trigger(
            db, task_catalog_id=task.id, kind="schedule",
            config={"spec_kind": "time_of_day", "time": "18:00", "days": []},
        )
        db.commit()
        triggers_svc.patch_trigger(db, trigger_id=trig.id, is_live=True)
        db.commit()
        script = build_ponder_script(db, task.id)
        assert script["is_live"] is True
        assert script["vertical"] == "manufacturing"
        assert script["workflow_id"] is not None

    def test_step_beats_carry_declared_params(self, db):
        """The editing grammar's fields: a step with declared params carries
        them on its beat (describe shape); undeclared steps carry none."""
        task, _ = _mk_task(db, params=[
            {"step_key": "send_statements", "param_key": "reply_to",
             "param_type": "email", "default_value": None},
            {"step_key": "send_statements", "param_key": "notify_roles",
             "param_type": "role_multi_select", "default_value": ["admin"]},
        ])
        script = build_ponder_script(db, task.id)
        by_key = {b["key"]: b for b in script["beats"]}
        send = by_key["step:send_statements"]
        assert {p["param_key"] for p in send["params"]} == {"reply_to", "notify_roles"}
        assert send["editable"] is True
        assert "params" not in by_key["step:identify"]

    def test_param_write_rederives_beat_and_audience(self, db):
        """WRITE-WHAT-YOU-READ, witnessed server-side: set the platform live
        value of notify_roles → the beat's params show it live AND the
        audience line re-derives from the merged config — the same effective
        values fire time merges."""
        task, wf_id = _mk_task(db, params=[
            {"step_key": "send_statements", "param_key": "notify_roles",
             "param_type": "role_multi_select", "default_value": ["admin"]},
        ])
        before = build_ponder_script(db, task.id)
        send_before = next(b for b in before["beats"] if b["key"] == "step:send_statements")
        assert send_before.get("audience") is None  # default never merges — no guessed line

        row = (
            db.query(WorkflowStepParam)
            .filter(WorkflowStepParam.workflow_id == wf_id,
                    WorkflowStepParam.param_key == "notify_roles",
                    WorkflowStepParam.company_id.is_(None))
            .one()
        )
        row.current_value = ["office", "accountant"]
        db.commit()

        after = build_ponder_script(db, task.id)
        send = next(b for b in after["beats"] if b["key"] == "step:send_statements")
        p = next(x for x in send["params"] if x["param_key"] == "notify_roles")
        assert p["live"] is True and p["effective_value"] == ["office", "accountant"]
        # The audience derivation reads the SAME merged config:
        assert send["audience"]["text"] == "the office, accountant roles"

    def test_specific_people_join_the_audience(self, db):
        """The fringe-case escape hatch: a user_multi_select param's live
        value composes into the audience line as REAL NAMES (roles +
        people); unresolvable ids are skipped, never guessed; the beat's
        param carries value_labels for the chips."""
        from app.models.user import User

        users = db.query(User).filter(User.is_active.is_(True)).limit(2).all()
        if len(users) < 2:
            pytest.skip("dev DB has fewer than 2 active users")
        u1, u2 = users
        task, wf_id = _mk_task(db, params=[
            {"step_key": "send_statements", "param_key": "notify_roles",
             "param_type": "role_multi_select", "default_value": ["admin"]},
            {"step_key": "send_statements", "param_key": "notify_user_ids",
             "param_type": "user_multi_select", "default_value": []},
        ])
        row = (
            db.query(WorkflowStepParam)
            .filter(WorkflowStepParam.workflow_id == wf_id,
                    WorkflowStepParam.param_key == "notify_user_ids",
                    WorkflowStepParam.company_id.is_(None))
            .one()
        )
        row.current_value = [u1.id, u2.id, "not-a-real-user-id"]
        db.commit()

        # Roles also need a live value for the composed line (defaults never
        # merge — the parity rule).
        roles_row = (
            db.query(WorkflowStepParam)
            .filter(WorkflowStepParam.workflow_id == wf_id,
                    WorkflowStepParam.param_key == "notify_roles",
                    WorkflowStepParam.company_id.is_(None))
            .one()
        )
        roles_row.current_value = ["office"]
        db.commit()

        script = build_ponder_script(db, task.id)
        send = next(b for b in script["beats"] if b["key"] == "step:send_statements")
        n1 = f"{u1.first_name} {u1.last_name}".strip() or u1.email
        n2 = f"{u2.first_name} {u2.last_name}".strip() or u2.email
        assert send["audience"]["text"] == f"the office role + {n1}, {n2}"
        p = next(x for x in send["params"] if x["param_key"] == "notify_user_ids")
        assert p["value_labels"] == {u1.id: n1, u2.id: n2}  # ghost id absent

    def test_users_only_audience_needs_no_roles(self, db):
        from app.models.user import User

        u = db.query(User).filter(User.is_active.is_(True)).first()
        if u is None:
            pytest.skip("dev DB has no active users")
        task, wf_id = _mk_task(db, params=[
            {"step_key": "send_statements", "param_key": "notify_user_ids",
             "param_type": "user_multi_select", "default_value": []},
        ])
        row = (
            db.query(WorkflowStepParam)
            .filter(WorkflowStepParam.workflow_id == wf_id,
                    WorkflowStepParam.company_id.is_(None))
            .one()
        )
        row.current_value = [u.id]
        db.commit()
        script = build_ponder_script(db, task.id)
        send = next(b for b in script["beats"] if b["key"] == "step:send_statements")
        expected = f"{u.first_name} {u.last_name}".strip() or u.email
        assert send["audience"]["text"] == expected

    def test_user_multi_select_shape_validation(self, db):
        from app.services.workflows.step_params import (
            StepParamValidationError, validate_param_value,
        )

        validate_param_value(param_type="user_multi_select", validation=None,
                             value=["some-id"], label="t")
        validate_param_value(param_type="user_multi_select", validation=None,
                             value=None, label="t")
        with pytest.raises(StepParamValidationError):
            validate_param_value(param_type="user_multi_select", validation=None,
                                 value="flat-string", label="t")
        with pytest.raises(StepParamValidationError):
            validate_param_value(param_type="user_multi_select", validation=None,
                                 value=["ok", ""], label="t")

    def test_when_caption_still_overlays(self, db):
        """Authored captions keep winning over derived text — keying intact."""
        from app.services.maps_of_content.ponder import save_caption
        task, _ = _mk_task(db, trigger_type="manual")
        triggers_svc.add_trigger(
            db, task_catalog_id=task.id, kind="schedule",
            config={"spec_kind": "ordinal_weekday", "ordinal": 1,
                    "weekday": "mon", "time": "16:00"},
        )
        db.commit()
        save_caption(db, task.id, "when", "Our statements go out monthly.")
        when = build_ponder_script(db, task.id)["beats"][0]
        assert when["text"] == "Our statements go out monthly."
        assert when["derived_text"] == "The first Monday of every month at 4:00 PM."
