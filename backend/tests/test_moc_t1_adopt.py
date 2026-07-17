"""Transfer T-1 — THE ATOMIC ADOPT pins.

THE INVARIANT (the arc's non-negotiable): at no point — before, during,
after, or across a FAILED adopt — can both authorities fire the same task.
Proven as an invariant over the transaction's reachable states via
`_authorities()` (the same discriminator + go_live derivation production
uses), not as scenario tests alone.

Also pinned: schedule-equivalence asserted IN the operation; the adopt-moment
boundary both ways per schedule shape (time_of_day, daily cron, monthly cron);
§6 narrowed precisely (the hazard-shaped condition); the scheduler's retired
skip; the T-0 badge/composer flip; the one-way off switch.

Hermetic per the borrow-a-core lesson; teardown deletes by this file's own
naming patterns.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.company import Company
from app.models.moc_task_catalog import MoCTaskCatalog
from app.models.moc_task_trigger import MoCTaskTrigger
from app.models.workflow import Workflow, WorkflowRun, WorkflowStep
from app.models.workflow_template import WorkflowTemplate
from app.services.maps_of_content import adopt as adopt_mod
from app.services.maps_of_content import triggers as triggers_svc
from app.services.maps_of_content.adopt import AdoptError, adopt_schedule
from app.services.maps_of_content.ponder import build_ponder_script, schedule_authority
from app.services.maps_of_content.schedule_sweep import (
    _fire,
    _already_fired,
    _resolve_go_live,
    _runtime_fired_same_window,
)
from app.services.maps_of_content.task_catalog import resolve_task


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.execute(sql_text(
        "DELETE FROM moc_task_trigger WHERE task_catalog_id IN "
        "(SELECT id FROM moc_task_catalog WHERE name LIKE 'T1 Adopt Task %')"
    ))
    s.execute(sql_text(
        "DELETE FROM moc_task_catalog WHERE name LIKE 'T1 Adopt Task %'"
    ))
    s.execute(sql_text(
        "DELETE FROM workflow_templates WHERE workflow_type LIKE 'mirror_t1adopt_%'"
    ))
    s.execute(sql_text(
        "DELETE FROM workflow_run_steps WHERE run_id IN "
        "(SELECT id FROM workflow_runs WHERE workflow_id LIKE 'wf_t1adopt_%')"
    ))
    s.execute(sql_text("DELETE FROM workflow_runs WHERE workflow_id LIKE 'wf_t1adopt_%'"))
    s.execute(sql_text("DELETE FROM workflow_steps WHERE workflow_id LIKE 'wf_t1adopt_%'"))
    s.execute(sql_text("DELETE FROM workflows WHERE id LIKE 'wf_t1adopt_%'"))
    s.execute(sql_text("DELETE FROM companies WHERE slug LIKE 't1adopt-%'"))
    s.commit()
    s.close()


def _mk(db, *, trigger_type="time_of_day", trigger_config=None):
    """Runtime workflow + faithful mirror + tenant-scoped task + its company
    (tenant_override scope → the sweep fan-out is exactly this company)."""
    suffix = uuid.uuid4().hex[:6]
    company = Company(
        id=str(uuid.uuid4()), name=f"T1Adopt Co {suffix}",
        slug=f"t1adopt-{suffix}", vertical="manufacturing",
    )
    db.add(company)
    wf = Workflow(
        id=f"wf_t1adopt_{suffix}", name=f"T1 Adopt Fixture {suffix}",
        company_id=None, tier=1, scope="core",
        trigger_type=trigger_type,
        trigger_config=trigger_config if trigger_config is not None
        else {"time": "23:30"},
    )
    db.add(wf)
    db.add(WorkflowStep(
        id=str(uuid.uuid4()), workflow_id=wf.id, step_key="do_the_thing",
        step_type="action", step_order=1,
        config={"description": "A harmless witness step"},
    ))
    nodes = [{
        "id": "do_the_thing", "type": "action", "label": "do_the_thing",
        "config": {"description": "A harmless witness step"},
        "position": {"x": 0, "y": 0},
    }]
    tpl = WorkflowTemplate(
        id=str(uuid.uuid4()), scope="platform_default", vertical=None,
        workflow_type=f"mirror_t1adopt_{suffix}",
        display_name=f"T1 Mirror {suffix}", version=1, is_active=True,
        canvas_state={"version": 1, "nodes": nodes, "edges": []},
        mirrored_from_workflow_id=wf.id,
    )
    db.add(tpl)
    db.flush()
    task = MoCTaskCatalog(
        scope="tenant_override", vertical="manufacturing", tenant_id=company.id,
        name=f"T1 Adopt Task {suffix}", workflow_template_id=tpl.id,
    )
    db.add(task)
    db.commit()
    return task, tpl, wf, company


def _authorities(db, runtime, task, tpl) -> set[str]:
    """WHICH authorities could fire this task LIVE right now — computed from
    the SAME production derivations (the T-0 discriminator for the runtime;
    _resolve_go_live for the MoC side)."""
    out = set()
    db.refresh(runtime)
    if schedule_authority(runtime) == "runtime_scheduler":
        out.add("runtime")
    trigs = [
        t for t in triggers_svc.list_triggers(db, task_catalog_id=task.id)
        if t.kind == "schedule" and t.is_active
    ]
    if any(_resolve_go_live(t, tpl, db) for t in trigs):
        out.add("moc")
    return out


# ── 1. THE INVARIANT — both authorities live is impossible ──────────────


class TestInvariant:
    def test_pre_adopt_runtime_is_sole_authority_even_with_promoted_trigger(self, db):
        task, tpl, wf, _ = _mk(db)
        assert _authorities(db, wf, task, tpl) == {"runtime"}
        # A composed trigger promoted by hand does NOT add an authority —
        # §6 (narrowed) forces it dry-run while the runtime schedule lives.
        trig = triggers_svc.add_trigger(
            db, task_catalog_id=task.id, kind="schedule",
            config={"spec_kind": "time_of_day", "time": "09:00"},
        )
        triggers_svc.patch_trigger(db, trigger_id=trig.id, is_live=True)
        db.commit()
        assert _authorities(db, wf, task, tpl) == {"runtime"}

    def test_post_adopt_moc_is_sole_authority(self, db):
        task, tpl, wf, _ = _mk(db)
        adopt_schedule(db, task_id=task.id)
        assert _authorities(db, wf, task, tpl) == {"moc"}
        assert wf.schedule_retired_at is not None

    def test_failed_adopt_rolls_back_to_exactly_the_pre_state(self, db):
        task, tpl, wf, _ = _mk(db)
        with patch.object(adopt_mod, "_final_verify",
                          side_effect=AdoptError("injected failure")):
            with pytest.raises(AdoptError):
                adopt_schedule(db, task_id=task.id)
        db.expire_all()
        # Nothing written: no trigger row, no retire stamp — the runtime is
        # still the sole authority. Never BOTH, never NEITHER.
        assert triggers_svc.list_triggers(db, task_catalog_id=task.id) == []
        assert db.get(Workflow, wf.id).schedule_retired_at is None
        assert _authorities(db, wf, task, tpl) == {"runtime"}

    def test_failed_adopt_restores_a_preexisting_trigger(self, db):
        task, tpl, wf, _ = _mk(db)
        trig = triggers_svc.add_trigger(
            db, task_catalog_id=task.id, kind="schedule",
            config={"spec_kind": "time_of_day", "time": "09:00"},
        )
        db.commit()
        with patch.object(adopt_mod, "_final_verify",
                          side_effect=AdoptError("injected failure")):
            with pytest.raises(AdoptError):
                adopt_schedule(db, task_id=task.id)
        db.expire_all()
        fresh = db.get(MoCTaskTrigger, trig.id)
        assert fresh.config == {"spec_kind": "time_of_day", "time": "09:00"}
        assert fresh.is_live is False
        assert _authorities(db, wf, task, tpl) == {"runtime"}

    def test_every_reachable_state_has_at_most_one_authority(self, db):
        # The invariant swept across the full lifecycle: pre → adopted →
        # de-promoted (off) → re-promoted. Never 2; NEITHER only when the
        # operator deliberately switched it off.
        task, tpl, wf, _ = _mk(db)
        states = [_authorities(db, wf, task, tpl)]
        result = adopt_schedule(db, task_id=task.id)
        states.append(_authorities(db, wf, task, tpl))
        triggers_svc.patch_trigger(db, trigger_id=result["trigger_id"], is_live=False)
        db.commit()
        states.append(_authorities(db, wf, task, tpl))  # the off switch
        triggers_svc.patch_trigger(db, trigger_id=result["trigger_id"], is_live=True)
        db.commit()
        states.append(_authorities(db, wf, task, tpl))
        assert all(len(s) <= 1 for s in states)
        assert states == [{"runtime"}, {"moc"}, set(), {"moc"}]


# ── 2. Schedule-equivalence — asserted in-operation ─────────────────────


class TestEquivalence:
    def test_time_of_day_carries_faithfully(self, db):
        task, _, wf, _ = _mk(db, trigger_config={"time": "23:30", "days": ["mon", "fri"]})
        result = adopt_schedule(db, task_id=task.id)
        assert result["carried_config"] == {
            "spec_kind": "time_of_day", "time": "23:30", "days": ["mon", "fri"],
        }

    def test_cron_carries_faithfully(self, db):
        task, _, wf, _ = _mk(
            db, trigger_type="scheduled",
            trigger_config={"cron": "0 6 1 * *", "timezone": "America/New_York"},
        )
        result = adopt_schedule(db, task_id=task.id)
        assert result["carried_config"] == {"spec_kind": "cron", "cron": "0 6 1 * *"}
        assert "6:00 AM" in result["carried_summary"] or "0 6 1" in result["carried_summary"]

    def test_translation_drift_fails_the_whole_adopt(self, db):
        # The in-operation gate: a translation that would shift a fire time
        # fails the adopt — nothing written, never a silent change.
        task, tpl, wf, _ = _mk(db)
        with patch.object(
            adopt_mod, "_moc_config_from_runtime",
            return_value={"spec_kind": "time_of_day", "time": "09:00"},
        ):
            with pytest.raises(AdoptError, match="equivalence"):
                adopt_schedule(db, task_id=task.id)
        db.expire_all()
        assert triggers_svc.list_triggers(db, task_catalog_id=task.id) == []
        assert db.get(Workflow, wf.id).schedule_retired_at is None

    def test_time_after_event_is_refused_loudly(self, db):
        task, _, _, _ = _mk(
            db, trigger_type="time_after_event",
            trigger_config={"record_type": "funeral_case", "field": "service_date",
                            "offset_days": 7},
        )
        with pytest.raises(AdoptError, match="time_after_event"):
            adopt_schedule(db, task_id=task.id)

    def test_manual_runtime_has_nothing_to_adopt(self, db):
        task, _, _, _ = _mk(db, trigger_type="manual", trigger_config={})
        with pytest.raises(AdoptError, match="nothing to adopt"):
            adopt_schedule(db, task_id=task.id)

    def test_adopt_updates_an_existing_composed_trigger_in_place(self, db):
        task, _, wf, _ = _mk(db)
        trig = triggers_svc.add_trigger(
            db, task_catalog_id=task.id, kind="schedule",
            config={"spec_kind": "time_of_day", "time": "09:00"},
        )
        db.commit()
        result = adopt_schedule(db, task_id=task.id)
        assert result["trigger_id"] == trig.id  # updated, not duplicated
        db.refresh(trig)
        assert trig.config["time"] == "23:30"
        assert trig.is_live is True
        actives = [
            t for t in triggers_svc.list_triggers(db, task_catalog_id=task.id)
            if t.kind == "schedule" and t.is_active
        ]
        assert len(actives) == 1  # never two clocks


# ── 3. The adopt-moment boundary — no doubles, no drops, per shape ──────


_SHAPES = [
    ("time_of_day", {"time": "23:30"},
     {"spec_kind": "time_of_day", "time": "23:30"},
     datetime(2026, 1, 15, 4, 30, tzinfo=timezone.utc)),   # 23:30 EST
    ("scheduled", {"cron": "0 23 * * *"},
     {"spec_kind": "cron", "cron": "0 23 * * *"},
     datetime(2026, 1, 15, 4, 0, tzinfo=timezone.utc)),    # daily 23:00 EST
    ("scheduled", {"cron": "0 6 1 * *"},
     {"spec_kind": "cron", "cron": "0 6 1 * *"},
     datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc)),    # monthly, 6:00 EST
]


class TestBoundary:
    @pytest.mark.parametrize("ttype,tcfg,mcfg,intended_utc", _SHAPES)
    def test_adopt_after_runtime_fired_no_second_fire(
        self, db, ttype, tcfg, mcfg, intended_utc
    ):
        """The runtime already served this window LIVE → the freshly-adopted
        trigger's fire SKIPS (the cross-authority boundary guard — its own
        idempotency space is empty, verified, and closed)."""
        task, tpl, wf, company = _mk(db, trigger_type=ttype, trigger_config=tcfg)
        # The runtime's fire, 2 minutes into the window (sweep-tick shaped).
        db.add(WorkflowRun(
            workflow_id=wf.id, company_id=company.id, status="completed",
            trigger_source="schedule",
            trigger_context={"fired_at": (intended_utc + timedelta(minutes=2)).isoformat()},
            started_at=intended_utc + timedelta(minutes=2),
        ))
        db.commit()
        result = adopt_schedule(db, task_id=task.id)
        trig = db.get(MoCTaskTrigger, result["trigger_id"])
        run = _fire(db, trig=trig, task=task, company=company, intended_fire=intended_utc)
        assert run is None  # skipped — the window is already served
        moc_runs = db.query(WorkflowRun).filter(
            WorkflowRun.trigger_source == "moc_task_schedule",
            WorkflowRun.trigger_context["moc_task_trigger_id"].astext == trig.id,
        ).count()
        assert moc_runs == 0

    @pytest.mark.parametrize("ttype,tcfg,mcfg,intended_utc", _SHAPES)
    def test_adopt_before_the_fire_exactly_one_via_moc(
        self, db, ttype, tcfg, mcfg, intended_utc
    ):
        """Adopt lands before the window's runtime tick → the runtime entry is
        retired (never fires) and the MoC trigger picks the window up —
        exactly one fire, then idempotent across further ticks."""
        task, tpl, wf, company = _mk(db, trigger_type=ttype, trigger_config=tcfg)
        result = adopt_schedule(db, task_id=task.id)
        trig = db.get(MoCTaskTrigger, result["trigger_id"])
        run = _fire(db, trig=trig, task=task, company=company, intended_fire=intended_utc)
        assert run is not None  # the window is picked up
        # The next sweep tick in the same window: idempotency holds.
        assert _already_fired(
            db, trigger_id=trig.id, company_id=company.id, intended_fire=intended_utc
        ) is True

    def test_dry_run_previews_stay_unscoped_by_the_boundary_guard(self, db):
        """The cross-authority guard is LIVE-only: dry-run previews are the
        confirm's evidence and keep firing even when the runtime served the
        window (harmless duplicates, deliberate)."""
        task, tpl, wf, company = _mk(db)
        intended = datetime(2026, 1, 15, 4, 30, tzinfo=timezone.utc)
        db.add(WorkflowRun(
            workflow_id=wf.id, company_id=company.id, status="completed",
            trigger_source="schedule", trigger_context={},
            started_at=intended + timedelta(minutes=2),
        ))
        # An UNPROMOTED composed trigger (pre-adopt preview path).
        trig = triggers_svc.add_trigger(
            db, task_catalog_id=task.id, kind="schedule",
            config={"spec_kind": "time_of_day", "time": "23:30"},
        )
        db.commit()
        run = _fire(db, trig=trig, task=task, company=company, intended_fire=intended)
        assert run is not None  # dry-run preview fired despite the runtime run

    def test_window_membership_is_exact(self, db):
        task, tpl, wf, company = _mk(db)
        intended = datetime(2026, 1, 15, 4, 30, tzinfo=timezone.utc)
        # A runtime fire OUTSIDE the window (the previous day) doesn't shield.
        db.add(WorkflowRun(
            workflow_id=wf.id, company_id=company.id, status="completed",
            trigger_source="schedule", trigger_context={},
            started_at=intended - timedelta(days=1),
        ))
        db.commit()
        assert _runtime_fired_same_window(
            db, source_workflow_id=wf.id, company_id=company.id,
            intended_fire=intended,
        ) is False
        # In-window → shields.
        db.add(WorkflowRun(
            workflow_id=wf.id, company_id=company.id, status="completed",
            trigger_source="schedule", trigger_context={},
            started_at=intended + timedelta(minutes=14),
        ))
        db.commit()
        assert _runtime_fired_same_window(
            db, source_workflow_id=wf.id, company_id=company.id,
            intended_fire=intended,
        ) is True


# ── 4. §6 narrowed precisely — the hazard-shaped condition ──────────────


class TestSixNarrowed:
    def test_mirror_with_live_runtime_schedule_never_fires_live(self, db):
        task, tpl, wf, _ = _mk(db)
        trig = MoCTaskTrigger(
            id="x", task_catalog_id=task.id, kind="schedule",
            config={}, is_live=True,
        )
        assert _resolve_go_live(trig, tpl, db) is False

    def test_adopted_mirror_fires_live(self, db):
        task, tpl, wf, _ = _mk(db)
        wf.schedule_retired_at = datetime.now(timezone.utc)
        db.commit()
        trig = MoCTaskTrigger(
            id="x", task_catalog_id=task.id, kind="schedule",
            config={}, is_live=True,
        )
        assert _resolve_go_live(trig, tpl, db) is True

    def test_mirror_of_manual_runtime_fires_live(self, db):
        # The narrowing: no competing schedule authority → no hazard.
        task, tpl, wf, _ = _mk(db, trigger_type="manual", trigger_config={})
        trig = MoCTaskTrigger(
            id="x", task_catalog_id=task.id, kind="schedule",
            config={}, is_live=True,
        )
        assert _resolve_go_live(trig, tpl, db) is True

    def test_unpromoted_never_fires_live_regardless(self, db):
        task, tpl, wf, _ = _mk(db)
        wf.schedule_retired_at = datetime.now(timezone.utc)
        db.commit()
        trig = MoCTaskTrigger(
            id="x", task_catalog_id=task.id, kind="schedule",
            config={}, is_live=False,
        )
        assert _resolve_go_live(trig, tpl, db) is False


# ── 5. The runtime scheduler skips retired schedules ────────────────────
#
# Pinned at the DISPATCH-POPULATION level: `_active_time_based_workflows` is
# the single query `check_time_based_workflows` iterates (dispatch mechanics
# are covered by test_workflow_scheduler_scheduled_dispatch). A full-sweep
# invocation here would fire every due dev workflow (expense-cat's */15
# agent pipeline included) — deliberately avoided; hermetic > theatrical.


class TestSchedulerSkip:
    def test_retired_workflow_leaves_the_dispatch_population(self, db):
        from app.services.workflow_scheduler import _active_time_based_workflows

        task, tpl, wf, company = _mk(db)
        assert wf.id in {w.id for w in _active_time_based_workflows(db)}
        wf.schedule_retired_at = datetime.now(timezone.utc)
        db.commit()
        assert wf.id not in {w.id for w in _active_time_based_workflows(db)}

    def test_adopt_removes_the_workflow_from_the_dispatch_population(self, db):
        from app.services.workflow_scheduler import _active_time_based_workflows

        task, tpl, wf, company = _mk(db)
        adopt_schedule(db, task_id=task.id)
        assert wf.id not in {w.id for w in _active_time_based_workflows(db)}


# ── 6. The honesty guard reflects the transfer (T-0 flip) ───────────────


class TestHonestyFlip:
    def test_ponder_badge_flips_and_composer_unblocks(self, db):
        task, tpl, wf, _ = _mk(db)
        pre = build_ponder_script(db, task.id)
        assert pre["schedule_authority"] == "runtime_scheduler"
        assert pre["beats"][0]["editable"] is False

        adopt_schedule(db, task_id=task.id)

        post = build_ponder_script(db, task.id)
        assert post["schedule_authority"] == "moc"
        when = post["beats"][0]
        assert when["editable"] is True
        assert when.get("managed_by") is None
        # The clock is UNCHANGED — same 11:30 PM, taught from the carried
        # trigger now (the adopt changes who fires, never when).
        assert "11:30 PM" in when["text"]

    def test_resolve_task_authority_flips(self, db):
        task, tpl, wf, _ = _mk(db)
        adopt_schedule(db, task_id=task.id)
        db.expire_all()
        row = resolve_task(db, db.get(MoCTaskCatalog, task.id))
        assert row["schedule_authority"] == "moc"
        assert row["runtime_schedule_summary"] is None
        assert "11:30" in (row["derived_frequency"] or "")


# ── 7. The one-way off switch ───────────────────────────────────────────


class TestOffSwitch:
    def test_depromote_stops_live_and_runtime_does_not_resurrect(self, db):
        task, tpl, wf, _ = _mk(db)
        result = adopt_schedule(db, task_id=task.id)
        trig = db.get(MoCTaskTrigger, result["trigger_id"])
        assert _resolve_go_live(trig, tpl, db) is True

        triggers_svc.patch_trigger(db, trigger_id=trig.id, is_live=False)
        db.commit()
        db.refresh(trig)
        assert _resolve_go_live(trig, tpl, db) is False  # the off switch
        db.refresh(wf)
        assert wf.schedule_retired_at is not None  # one-way: no resurrection
        assert schedule_authority(wf) == "moc"

        triggers_svc.patch_trigger(db, trigger_id=trig.id, is_live=True)
        db.commit()
        db.refresh(trig)
        assert _resolve_go_live(trig, tpl, db) is True  # and back on

    def test_adopting_twice_is_refused(self, db):
        task, _, _, _ = _mk(db)
        adopt_schedule(db, task_id=task.id)
        with pytest.raises(AdoptError, match="nothing to adopt"):
            adopt_schedule(db, task_id=task.id)
