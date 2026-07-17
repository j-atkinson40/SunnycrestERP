"""T-0 — the honesty guard pins.

Three claims, pinned:
  1. THE DISCRIMINATOR — `schedule_authority` keys on WHO fires, not on
     task-ness: an active runtime schedule (scheduled / time_of_day /
     time_after_event) on a mirror's source → "runtime_scheduler";
     everything else (manual mirrors, inactive runtimes, compiled tasks)
     → "moc". Runtime-scheduler tasks get the badged/blocked WHEN beat;
     compiled tasks are byte-untouched.
  2. THE TZ FIRE-FIX — time_of_day matches TENANT-LOCAL wall clock (the
     8b.5-flagged UTC latent bug, closed at the dispatch site).
  3. WHEN-SOURCE-IS-AUTHORITY — a runtime-scheduled mirror's WHEN beat
     derives from the RUNTIME config even when composed MoC triggers
     exist; the owned-fork path keeps its honest preview semantics.

Hermetic per the borrow-a-core lesson: every test builds its own rows,
teardown deletes by this file's own naming patterns.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.company import Company
from app.models.moc_task_catalog import MoCTaskCatalog
from app.models.workflow import Workflow, WorkflowStep
from app.models.workflow_template import WorkflowTemplate
from app.services.maps_of_content import triggers as triggers_svc
from app.services.maps_of_content.ponder import (
    build_ponder_script,
    schedule_authority,
)
from app.services.maps_of_content.task_catalog import resolve_task
from app.services.workflow_scheduler import (
    _matches_time_of_day,
    _resolve_tenant_tz,
)


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.execute(sql_text(
        "DELETE FROM moc_task_trigger WHERE task_catalog_id IN "
        "(SELECT id FROM moc_task_catalog WHERE name LIKE 'T0 Authority Task %')"
    ))
    s.execute(sql_text(
        "DELETE FROM moc_task_catalog WHERE name LIKE 'T0 Authority Task %'"
    ))
    s.execute(sql_text(
        "DELETE FROM workflow_templates WHERE workflow_type LIKE 'mirror_t0auth_%'"
    ))
    s.execute(sql_text("DELETE FROM workflow_steps WHERE workflow_id LIKE 'wf_t0auth_%'"))
    s.execute(sql_text("DELETE FROM workflows WHERE id LIKE 'wf_t0auth_%'"))
    s.execute(sql_text("DELETE FROM companies WHERE slug LIKE 't0auth-%'"))
    s.commit()
    s.close()


def _mk(db, *, trigger_type="time_of_day", trigger_config=None,
        scope="vertical_default", tenant_id=None, mirror=True):
    """Runtime workflow + (mirror|compiled) template + task row."""
    suffix = uuid.uuid4().hex[:6]
    wf = None
    if mirror:
        wf = Workflow(
            id=f"wf_t0auth_{suffix}", name=f"T0 Fixture {suffix}",
            company_id=None, tier=1, scope="core",
            trigger_type=trigger_type,
            trigger_config=trigger_config if trigger_config is not None
            else {"time": "23:30"},
        )
        db.add(wf)
        db.add(WorkflowStep(
            id=str(uuid.uuid4()), workflow_id=wf.id, step_key="do_the_thing",
            step_type="action", step_order=1,
            config={"description": "Match receipts"},
        ))
    nodes = [{
        "id": "do_the_thing", "type": "action", "label": "do_the_thing",
        "config": {"description": "Match receipts"},
        "position": {"x": 0, "y": 0},
    }]
    tpl = WorkflowTemplate(
        id=str(uuid.uuid4()), scope="platform_default", vertical=None,
        workflow_type=f"mirror_t0auth_{suffix}",
        display_name=f"T0 Mirror {suffix}", version=1, is_active=True,
        canvas_state={"version": 1, "nodes": nodes, "edges": []},
        mirrored_from_workflow_id=wf.id if mirror else None,
    )
    db.add(tpl)
    db.flush()
    task = MoCTaskCatalog(
        scope=scope, vertical="manufacturing", tenant_id=tenant_id,
        name=f"T0 Authority Task {suffix}", workflow_template_id=tpl.id,
    )
    db.add(task)
    db.commit()
    return task, tpl, wf


def _mk_company(db):
    suffix = uuid.uuid4().hex[:6]
    c = Company(
        id=str(uuid.uuid4()), name=f"T0Auth Co {suffix}",
        slug=f"t0auth-{suffix}", vertical="manufacturing",
    )
    db.add(c)
    db.commit()
    return c


class TestDiscriminator:
    """Authority keys on who fires — never on task-ness."""

    def _wf(self, trigger_type, is_active=True):
        return Workflow(
            id="x", name="x", tier=1, scope="core",
            trigger_type=trigger_type, is_active=is_active,
        )

    @pytest.mark.parametrize("tt", ["scheduled", "time_of_day", "time_after_event"])
    def test_active_runtime_schedules_are_runtime_authority(self, tt):
        assert schedule_authority(self._wf(tt)) == "runtime_scheduler"

    @pytest.mark.parametrize("tt", ["manual", "event", None])
    def test_non_schedule_triggers_are_moc(self, tt):
        assert schedule_authority(self._wf(tt)) == "moc"

    def test_inactive_runtime_is_moc(self):
        assert schedule_authority(self._wf("scheduled", is_active=False)) == "moc"

    def test_compiled_no_runtime_is_moc(self):
        assert schedule_authority(None) == "moc"


class TestPonderWhenAuthority:
    def test_runtime_scheduled_mirror_is_badged_and_blocked(self, db):
        task, _, _ = _mk(db, trigger_type="time_of_day",
                         trigger_config={"time": "23:30"})
        script = build_ponder_script(db, task.id)
        assert script["schedule_authority"] == "runtime_scheduler"
        when = script["beats"][0]
        assert when["key"] == "when"
        assert when["editable"] is False
        assert when["managed_by"] == "standard_scheduler"
        # The beat teaches the RUNTIME truth (11:30 PM tenant-local).
        assert "11:30 PM" in when["text"]

    def test_when_source_is_authority_not_composed_triggers(self, db):
        # A composed MoC trigger exists — the WHEN text STILL derives from
        # the runtime schedule (the authority), and the trigger rides the
        # payload so nothing is hidden.
        task, _, _ = _mk(db, trigger_type="time_of_day",
                         trigger_config={"time": "23:30"})
        triggers_svc.add_trigger(
            db, task_catalog_id=task.id, kind="schedule",
            config={"spec_kind": "time_of_day", "time": "09:00"},
        )
        script = build_ponder_script(db, task.id)
        when = script["beats"][0]
        assert "11:30 PM" in when["text"]
        assert "9:00" not in when["text"]
        assert when["editable"] is False
        assert len(when["triggers"]) == 1  # nothing hidden

    def test_manual_mirror_stays_editable(self, db):
        task, _, _ = _mk(db, trigger_type="manual", trigger_config={})
        script = build_ponder_script(db, task.id)
        assert script["schedule_authority"] == "moc"
        when = script["beats"][0]
        assert when["editable"] is True
        assert when.get("managed_by") is None

    def test_owned_fork_keeps_preview_semantics(self, db):
        # A tenant's fork of a runtime-scheduled mirror: THEIR composed
        # schedule previews (dry-run), so the composer stays open.
        company = _mk_company(db)
        task, _, _ = _mk(db, trigger_type="time_of_day",
                         trigger_config={"time": "23:30"},
                         scope="tenant_override", tenant_id=company.id)
        script = build_ponder_script(db, task.id, company_id=company.id)
        # Authority is still named honestly on the script...
        assert script["schedule_authority"] == "runtime_scheduler"
        # ...but the fork's WHEN beat is NOT blocked.
        when = script["beats"][0]
        assert when["editable"] is True
        assert when.get("managed_by") is None


class TestResolveTaskAuthority:
    def test_runtime_scheduled_mirror_carries_truth_summary(self, db):
        task, _, _ = _mk(db, trigger_type="time_of_day",
                         trigger_config={"time": "23:30"})
        row = resolve_task(db, task)
        assert row["schedule_authority"] == "runtime_scheduler"
        assert "11:30 PM" in row["runtime_schedule_summary"]

    def test_manual_mirror_and_compiled_are_moc(self, db):
        manual, _, _ = _mk(db, trigger_type="manual", trigger_config={})
        row = resolve_task(db, manual)
        assert row["schedule_authority"] == "moc"
        assert row["runtime_schedule_summary"] is None

        compiled, _, _ = _mk(db, mirror=False)
        row2 = resolve_task(db, compiled)
        assert row2["schedule_authority"] == "moc"
        assert row2["runtime_schedule_summary"] is None


class TestTimeOfDayTenantLocal:
    """The TZ fire-fix: the config's HH:MM means the tenant's wall clock."""

    def test_conversion_matches_tenant_wall_clock(self):
        # 04:30 UTC on Jan 15 == 23:30 the prior evening in New York (EST).
        now_utc = datetime(2026, 1, 15, 4, 30, tzinfo=timezone.utc)
        now_local = now_utc.astimezone(_resolve_tenant_tz("America/New_York"))
        assert _matches_time_of_day({"time": "23:30"}, now_local) is True
        # The pre-fix behavior (raw UTC comparison) must NOT match.
        assert _matches_time_of_day({"time": "23:30"}, now_utc) is False

    def test_dispatch_site_converts(self):
        # The call-site pin: check_time_based_workflows' time_of_day branch
        # converts to tenant-local before matching (not just the helper's
        # docstring promising it).
        import inspect
        from app.services import workflow_scheduler

        src = inspect.getsource(workflow_scheduler.check_time_based_workflows)
        assert "now.astimezone(_resolve_tenant_tz(company.timezone))" in src

    def test_fallback_tz_is_graceful(self):
        assert str(_resolve_tenant_tz("Not/AZone")) == "America/New_York"
        assert str(_resolve_tenant_tz(None)) == "America/New_York"
