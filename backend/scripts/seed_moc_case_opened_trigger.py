"""Demo Walk G-1 — the case.opened event trigger on First Call Intake.

The walk's Act II beat, made real: a director creates a case (any door —
the Cmd+K NL flow and the form route share the create_case chokepoint,
which has emitted `case.opened` same-transaction since T-2.2a) → within
the matcher's 1-minute cadence the trigger matches → the fires log shows
"case.opened … would run First Call Intake" with full provenance.

DRY-RUN IS THE SHOW: is_live=False, deliberately — nothing promotes for
the demo; the fires-log entry IS the theater. An operator promotion (the
T-2.1c toggle) is PRESERVED across re-runs, same as the witness seed.

The trigger hangs on the VERTICAL First Call Intake task (vertical_default
/ funeral_home — the FH mirror pass's thin task): fan-out membership means
ANY FH tenant's case.opened matches, and the fire is attributed to THAT
tenant — Hopkins' case lights up as Hopkins on the log. Condition-free
(`conditions: []` — event-key-alone) per the investigation's recommended
any-case semantics; the catalog's filterable set (`status`) stays available
for a future narrower condition.

G-6 RESET INTERFACE: the demo_reset script must delete the rehearsal's
CASES + RUNS + EVENTS — never this trigger (it deletes nothing here; this
seed is also idempotent + auto-runs on deploy via the canonical runner,
so even a destroyed trigger self-heals on the next deploy).

Idempotent: find-or-create by (task, kind=event, event key). Resolve-or-
skip: if the First Call Intake task is absent (mirror seed not yet run —
alphabetically it runs first: seed_moc_b… < seed_moc_c…), log + skip;
self-heals next run.

Usage:  cd backend && python -m scripts.seed_moc_case_opened_trigger
"""

from __future__ import annotations

import logging
import sys
import uuid
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models.moc_task_catalog import MoCTaskCatalog  # noqa: E402
from app.models.moc_task_trigger import MoCTaskTrigger  # noqa: E402

logger = logging.getLogger(__name__)

EVENT_KEY = "case.opened"
TASK_NAME = "First Call Intake"
TASK_VERTICAL = "funeral_home"


def seed(db) -> dict:
    task = (
        db.query(MoCTaskCatalog)
        .filter(
            MoCTaskCatalog.scope == "vertical_default",
            MoCTaskCatalog.vertical == TASK_VERTICAL,
            MoCTaskCatalog.name == TASK_NAME,
            MoCTaskCatalog.is_active.is_(True),
        )
        .first()
    )
    if task is None:
        logger.warning(
            "seed_moc_case_opened_trigger: task %r (%s) not found — run "
            "seed_moc_backfill_workflow_mirrors first. Skipping (self-heals "
            "next run).",
            TASK_NAME, TASK_VERTICAL,
        )
        return {"skipped": "task_absent"}

    trig = (
        db.query(MoCTaskTrigger)
        .filter(
            MoCTaskTrigger.task_catalog_id == task.id,
            MoCTaskTrigger.kind == "event",
            MoCTaskTrigger.config["event"].astext == EVENT_KEY,
        )
        .first()
    )
    if trig is not None:
        # PRESERVE is_live (an operator's T-2.1c promotion survives re-seeds).
        trig.config = {"event": EVENT_KEY, "conditions": []}
        trig.is_active = True
        db.commit()
        logger.info(
            "case.opened trigger already present on %r (id=%s, is_live=%s) — "
            "config refreshed",
            TASK_NAME, trig.id, trig.is_live,
        )
        return {"trigger_id": trig.id, "created": False, "is_live": trig.is_live}

    trig = MoCTaskTrigger(
        id=str(uuid.uuid4()),
        task_catalog_id=task.id,
        kind="event",
        config={"event": EVENT_KEY, "conditions": []},
        label="On case opened (demo walk G-1)",
        is_active=True,
        is_live=False,  # DRY-RUN IS THE SHOW — nothing promotes for the demo
    )
    db.add(trig)
    db.commit()
    logger.info(
        "case.opened trigger seeded on %r (id=%s, dry-run) — a new case in "
        "any FH tenant now lights the fires log within the matcher's minute.",
        TASK_NAME, trig.id,
    )
    return {"trigger_id": trig.id, "created": True, "is_live": False}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
