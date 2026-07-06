"""MoC witness marker seed (Canvas↔Runtime Bridge T-2.1b-WITNESS).

Seeds the DEDICATED BENIGN marker-task — the safe target for the platform's first
autonomous real scheduled fire. It seeds:

  1. a COMPILED (single-owner, NOT a mirror) WorkflowTemplate whose canvas is
     `start → record_marker → end` — the only effect is one `moc_witness_marker`
     row (real, attributable, harmless);
  2. a MoCTaskCatalog row scoped `tenant_override` to TESTCO — so the sweep's
     `_fanout_companies` fires for EXACTLY ONE company (the T-2.1a death-spiral
     was a `vertical_default` fan-out; this is deliberately one tenant);
  3. a schedule trigger, cron `*/15 * * * *` — fires every 15-min sweep window,
     so it is witnessable within a sweep cycle (not a once-a-day wait), and
     is_live=FALSE (ships UNPROMOTED → fires DRY-RUN until the operator promotes).

WITNESS FLOW (operator, on staging, AFTER T-2.1b + this arc are pushed +
deployed so migration r117 + r118 are live):
  a. run this seed:  python -m scripts.seed_moc_witness_marker
  b. watch /schedule-runs — the task fires DRY-RUN ("would execute action:
     record_marker"); NO moc_witness_marker row is written yet.
  c. PROMOTE:  PATCH /api/platform/admin/moc/triggers/<TRIGGER_ID> {is_live:true}
  d. the next sweep tick fires it LIVE → a real moc_witness_marker row is written.
  e. de-promote (is_live:false) → the next tick fires DRY-RUN again (the OFF
     switch); deactivate the trigger to stop the dry-run previews entirely.

The seed PRESERVES an existing trigger's is_live on re-run (it never resets a
promotion the operator made) — idempotent + non-destructive. Refuses on
ENVIRONMENT=production (a witness artifact, never for prod).

Usage:  cd backend && python -m scripts.seed_moc_witness_marker
"""
from __future__ import annotations

import logging
import os
import sys
import uuid
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.moc_task_trigger import MoCTaskTrigger  # noqa: E402
from app.models.workflow_template import WorkflowTemplate  # noqa: E402
from app.services.maps_of_content.task_catalog import upsert_task  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

VERTICAL = "manufacturing"
WORKFLOW_TYPE = "moc_witness_marker"
TASK_NAME = "MoC Witness Marker (T-2.1b)"
TESTCO_SLUG = "testco"
CRON_EVERY_15 = "*/15 * * * *"


def _witness_canvas() -> dict:
    """`start → record_marker → end` — a LINEAR, compilable canvas whose only
    effect is one benign witness marker row."""
    return {
        "version": 1,
        "trigger": {"type": "manual"},  # the compiler forces manual anyway
        "nodes": [
            {"id": "n_start", "type": "start", "config": {}},
            {
                "id": "n_marker",
                "type": "record_marker",
                "label": "Record witness marker",
                "config": {
                    "note": "MoC witness marker — first autonomous scheduled fire (T-2.1b)"
                },
            },
            {"id": "n_end", "type": "end", "config": {}},
        ],
        "edges": [
            {"id": "e1", "source": "n_start", "target": "n_marker"},
            {"id": "e2", "source": "n_marker", "target": "n_end"},
        ],
    }


def _find_or_create_template(db) -> WorkflowTemplate:
    tmpl = (
        db.query(WorkflowTemplate)
        .filter(
            WorkflowTemplate.scope == "vertical_default",
            WorkflowTemplate.vertical == VERTICAL,
            WorkflowTemplate.workflow_type == WORKFLOW_TYPE,
        )
        .first()
    )
    if tmpl is not None:
        return tmpl
    tmpl = WorkflowTemplate(
        id=str(uuid.uuid4()),
        scope="vertical_default",
        vertical=VERTICAL,
        workflow_type=WORKFLOW_TYPE,
        display_name="MoC Witness Marker",
        description=(
            "T-2.1b-WITNESS benign marker task — the only effect is a "
            "moc_witness_marker row. A COMPILED (single-owner) template, not a "
            "mirror, so it is eligible for a live fire under the §6 guard."
        ),
        canvas_state=_witness_canvas(),
        version=1,
        is_active=True,
        # NOT a mirror — mirrored_from_workflow_id stays NULL (compiled-only path).
    )
    db.add(tmpl)
    db.flush()
    logger.info("  + created WorkflowTemplate %s (%s)", tmpl.id, WORKFLOW_TYPE)
    return tmpl


def _find_or_create_trigger(db, task_id: str) -> tuple[MoCTaskTrigger, bool]:
    """Find-or-create the schedule trigger. On an existing row, PRESERVE is_live
    (never reset an operator promotion). Returns (trigger, created)."""
    trig = (
        db.query(MoCTaskTrigger)
        .filter(
            MoCTaskTrigger.task_catalog_id == task_id,
            MoCTaskTrigger.kind == "schedule",
        )
        .first()
    )
    if trig is not None:
        # Ensure the schedule shape + active; leave is_live ALONE (non-destructive).
        trig.config = {"spec_kind": "cron", "cron": CRON_EVERY_15}
        trig.is_active = True
        db.flush()
        return trig, False
    trig = MoCTaskTrigger(
        id=str(uuid.uuid4()),
        task_catalog_id=task_id,
        kind="schedule",
        config={"spec_kind": "cron", "cron": CRON_EVERY_15},
        label="Every 15 minutes (witness)",
        is_active=True,
        is_live=False,  # ships UNPROMOTED — dry-run until the operator promotes
    )
    db.add(trig)
    db.flush()
    return trig, True


# T-2.2c: the benign EVENT→marker path. A SYNTHETIC event key nothing organic
# ever emits — the witness emits it deliberately (fully controlled), the
# matcher fires the marker task. Unconditional (conditions: []) — the key
# alone is the match.
WITNESS_EVENT_KEY = "witness.marker_requested"


def _find_or_create_event_trigger(db, task_id: str) -> tuple[MoCTaskTrigger, bool]:
    """Find-or-create the EVENT trigger (T-2.2c witness). PRESERVES is_live on
    re-run, same as the schedule trigger."""
    trig = (
        db.query(MoCTaskTrigger)
        .filter(
            MoCTaskTrigger.task_catalog_id == task_id,
            MoCTaskTrigger.kind == "event",
        )
        .first()
    )
    if trig is not None:
        trig.config = {"event": WITNESS_EVENT_KEY, "conditions": []}
        trig.is_active = True
        db.flush()
        return trig, False
    trig = MoCTaskTrigger(
        id=str(uuid.uuid4()),
        task_catalog_id=task_id,
        kind="event",
        config={"event": WITNESS_EVENT_KEY, "conditions": []},
        label="On witness event (T-2.2c)",
        is_active=True,
        is_live=False,  # ships UNPROMOTED — a matching event fires dry-run
    )
    db.add(trig)
    db.flush()
    return trig, True


def seed(db, *, company_slug: str = TESTCO_SLUG) -> dict:
    if os.getenv("ENVIRONMENT", "dev") == "production":
        logger.info("ENVIRONMENT=production — refusing to seed a witness artifact.")
        return {"skipped": "production"}

    testco = db.query(Company).filter(Company.slug == company_slug).first()
    if testco is None:
        logger.info(
            "tenant (%s) not found — run seed_staging first. Skipping witness seed.",
            company_slug,
        )
        return {"skipped": "no_testco"}

    tmpl = _find_or_create_template(db)
    task = upsert_task(
        db,
        scope="tenant_override",
        vertical=VERTICAL,
        tenant_id=testco.id,
        name=TASK_NAME,
        icon="flag",
        frequency="Every 15 minutes",
        task_type="witness",
        description="Benign marker task for the T-2.1b live-fire witness.",
        workflow_template_id=tmpl.id,
    )
    trig, created = _find_or_create_trigger(db, task.id)
    ev_trig, ev_created = _find_or_create_event_trigger(db, task.id)
    db.commit()

    logger.info("")
    logger.info("MoC witness marker seeded (tenant_override → testco %s):", testco.id)
    logger.info("  task_id       = %s", task.id)
    logger.info("  template_id   = %s (compiled — NOT a mirror)", tmpl.id)
    logger.info("  sched trigger = %s  (is_live=%s, cron=%s)", trig.id, trig.is_live, CRON_EVERY_15)
    logger.info("  event trigger = %s  (is_live=%s, event=%s)", ev_trig.id, ev_trig.is_live, WITNESS_EVENT_KEY)
    logger.info("")
    logger.info("  PROMOTE to witness a REAL fire (schedule or event):")
    logger.info("    PATCH /api/platform/admin/moc/triggers/<id>  {\"is_live\": true}")
    logger.info("  EVENT witness: emit %s for testco (emit_event) → the 1-min matcher fires it.", WITNESS_EVENT_KEY)
    logger.info("  then watch /api/platform/admin/moc/schedule-runs + query moc_witness_marker.")
    return {
        "task_id": task.id,
        "template_id": tmpl.id,
        "trigger_id": trig.id,
        "is_live": trig.is_live,
        "trigger_created": created,
        "event_trigger_id": ev_trig.id,
        "event_trigger_is_live": ev_trig.is_live,
        "event_trigger_created": ev_created,
        "witness_event_key": WITNESS_EVENT_KEY,
    }


def main() -> None:
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
