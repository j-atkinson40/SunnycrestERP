"""Transfer T-1 — THE ATOMIC ADOPT (schedule authority moves in one transaction).

`adopt_schedule(db, task_id)` moves a mirror task's schedule authority from the
runtime scheduler to the MoC trigger — ALL ONE TRANSACTION:

  1. the runtime schedule is read and FAITHFULLY carried into the task's MoC
     schedule trigger (create-or-update). The adopt changes WHO fires, never
     WHEN — schedule-equivalence is ASSERTED inside the operation (a translation
     that would shift a fire time fails the whole adopt, never silently).
  2. the MoC trigger PROMOTES (is_live=True) — adopting a firing schedule
     preserves firing. The confirm surface gates this operator-side.
  3. the runtime schedule RETIRES (`workflows.schedule_retired_at` stamped —
     r129). The runtime scheduler's query skips retired rows permanently.

Any failure → full rollback. There is never a state with BOTH authorities live
or NEITHER: pre-adopt the runtime fires and the §6 guard forces the mirror's
MoC fires dry-run; post-adopt the runtime is retired and the MoC trigger is the
single authority; a failed adopt rolls back to exactly the pre state. The
in-window boundary is closed by the sweep's `_runtime_fired_same_window` guard
(a fire the runtime already made this window is not re-made).

ONE-WAY (the one-way-heal precedent): there is NO un-adopt. Post-adopt,
de-promoting the MoC trigger (is_live=False) is THE off switch — the task stops
firing live and previews dry-run; the runtime entry does not resurrect. The
confirm says so.

SHAPE COVERAGE: `scheduled` (cron) and `time_of_day` carry faithfully — both
authorities evaluate them with the SAME helpers against the SAME tenant-local
clock (`_intended_scheduled_fire` / `_matches_time_of_day` + company timezone;
the runtime ignores any trigger_config "timezone" field, and so does the
sweep). `time_after_event` is REFUSED loudly: the MoC sweep defers that spec
(it would validate but never fire — a silent drop, the one thing the adopt must
never do). None of the transfer plan's six accounting mirrors carry it.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.moc_task_catalog import MoCTaskCatalog
from app.models.moc_task_trigger import MoCTaskTrigger
from app.models.workflow import Workflow
from app.models.workflow_template import WorkflowTemplate
from app.services.maps_of_content import triggers as triggers_svc
from app.services.maps_of_content.ponder import schedule_authority

logger = logging.getLogger(__name__)


class AdoptError(ValueError):
    """A refused or failed adopt — surfaced, never silent."""


def _moc_config_from_runtime(runtime: Workflow) -> dict[str, Any]:
    """Translate the runtime schedule into the MoC trigger's config shape —
    the 1:1 mirror the trigger substrate was designed for (its spec shapes
    deliberately mirror workflow_scheduler's trigger_config)."""
    cfg = runtime.trigger_config or {}
    if runtime.trigger_type == "scheduled":
        cron = cfg.get("cron")
        if not cron:
            raise AdoptError(
                f"workflow {runtime.id!r} is 'scheduled' but has no cron "
                "expression — nothing faithful to carry"
            )
        return {"spec_kind": "cron", "cron": cron}
    if runtime.trigger_type == "time_of_day":
        t = cfg.get("time")
        if not t:
            raise AdoptError(
                f"workflow {runtime.id!r} is 'time_of_day' but has no time — "
                "nothing faithful to carry"
            )
        out: dict[str, Any] = {"spec_kind": "time_of_day", "time": t}
        if cfg.get("days"):
            out["days"] = list(cfg["days"])
        return out
    if runtime.trigger_type == "time_after_event":
        raise AdoptError(
            "time_after_event schedules cannot be adopted yet — the MoC sweep "
            "defers that spec (it would never fire: a silent drop). The "
            "runtime scheduler keeps this one until the sweep supports it."
        )
    raise AdoptError(
        f"workflow {runtime.id!r} has trigger_type {runtime.trigger_type!r} — "
        "no runtime schedule to adopt"
    )


def _assert_schedule_equivalence(runtime: Workflow, moc_config: dict) -> None:
    """The in-operation faithfulness gate: the carried MoC config must denote
    the SAME fires as the runtime schedule. Field-by-field on the canonical
    firing inputs (both dispatchers share the matcher helpers + the company
    timezone, so equal inputs ⇒ equal fire instants). Raises AdoptError on any
    mismatch — the adopt must never change a fire time silently."""
    cfg = runtime.trigger_config or {}
    if runtime.trigger_type == "scheduled":
        if moc_config.get("spec_kind") != "cron" or moc_config.get("cron") != cfg.get("cron"):
            raise AdoptError(
                f"schedule-equivalence violated: runtime cron {cfg.get('cron')!r} "
                f"vs carried {moc_config!r}"
            )
    elif runtime.trigger_type == "time_of_day":
        runtime_days = sorted(cfg.get("days") or [])
        carried_days = sorted(moc_config.get("days") or [])
        if (
            moc_config.get("spec_kind") != "time_of_day"
            or str(moc_config.get("time")) != str(cfg.get("time"))
            or runtime_days != carried_days
        ):
            raise AdoptError(
                f"schedule-equivalence violated: runtime time_of_day {cfg!r} "
                f"vs carried {moc_config!r}"
            )
    else:
        raise AdoptError(
            f"schedule-equivalence cannot be asserted for trigger_type "
            f"{runtime.trigger_type!r}"
        )


def _final_verify(runtime: Workflow, trig: MoCTaskTrigger) -> None:
    """The post-state check inside the transaction: exactly ONE authority.
    Separate function so the rollback path is testable (a patched failure
    here must leave the pre state byte-intact)."""
    if schedule_authority(runtime) != "moc":
        raise AdoptError(
            "post-adopt verification failed: the runtime schedule still "
            "reads as the firing authority"
        )
    if not (trig.is_live and trig.is_active):
        raise AdoptError(
            "post-adopt verification failed: the MoC trigger is not live"
        )


def adopt_schedule(
    db: Session, *, task_id: str, actor_id: str | None = None
) -> dict[str, Any]:
    """THE ADOPT — one transaction, all or nothing. Returns the carried trigger
    payload + the retired workflow id. Raises AdoptError (nothing written) on
    any refusal or failure."""
    task = db.get(MoCTaskCatalog, task_id)
    if task is None or not task.is_active:
        raise AdoptError("task not found")
    if not task.workflow_template_id:
        raise AdoptError("this task has no workflow — nothing to adopt")
    template = db.get(WorkflowTemplate, task.workflow_template_id)
    if template is None or not template.mirrored_from_workflow_id:
        raise AdoptError(
            "this task's workflow is not a mirror — its schedule already "
            "lives in the map"
        )
    runtime = db.get(Workflow, template.mirrored_from_workflow_id)
    if runtime is None:
        raise AdoptError("the mirror's runtime source workflow is gone")
    if schedule_authority(runtime) != "runtime_scheduler":
        raise AdoptError(
            "the runtime scheduler does not own this task's schedule — "
            "nothing to adopt (already adopted, or the workflow is manual)"
        )

    try:
        # (1) the schedule, faithfully carried — asserted, never assumed.
        moc_config = _moc_config_from_runtime(runtime)
        _assert_schedule_equivalence(runtime, moc_config)

        existing = [
            t for t in triggers_svc.list_triggers(db, task_catalog_id=task.id)
            if t.kind == "schedule" and t.is_active
        ]
        if existing:
            # A composed preview existed — the adopt carries the FIRING truth
            # over it (the preview was dry-run-only display; the authority
            # transfer is what the operator confirmed).
            trig = triggers_svc.patch_trigger(
                db, trigger_id=existing[0].id, config=moc_config,
                is_live=True, actor_id=actor_id,
            )
            for extra in existing[1:]:
                # Never leave a second active schedule trigger teaching a
                # different clock — deactivate (not delete: authored history).
                triggers_svc.patch_trigger(
                    db, trigger_id=extra.id, is_active=False, actor_id=actor_id
                )
        else:
            trig = triggers_svc.add_trigger(
                db, task_catalog_id=task.id, kind="schedule",
                config=moc_config, actor_id=actor_id,
            )
            # (2) promote — adopting a firing schedule preserves firing.
            trig = triggers_svc.patch_trigger(
                db, trigger_id=trig.id, is_live=True, actor_id=actor_id
            )

        # (3) the runtime schedule retires — one-way, stamped.
        runtime.schedule_retired_at = datetime.now(timezone.utc)
        db.flush()

        _final_verify(runtime, trig)
        db.commit()
    except Exception:
        db.rollback()
        raise

    summary = triggers_svc.summarize_trigger("schedule", moc_config)
    logger.info(
        "ADOPTED: task %s (%s) schedule authority moved runtime→moc — "
        "trigger %s live (%s), workflow %s schedule retired.",
        task.id, task.name, trig.id, summary, runtime.id,
    )
    return {
        "task_id": task.id,
        "trigger_id": trig.id,
        "carried_config": moc_config,
        "carried_summary": summary,
        "retired_workflow_id": runtime.id,
        "schedule_retired_at": runtime.schedule_retired_at.isoformat(),
    }
