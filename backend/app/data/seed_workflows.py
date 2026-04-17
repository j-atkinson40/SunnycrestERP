"""Seed default workflows — idempotent, safe to run on every startup."""

from sqlalchemy.orm import Session

from app.data.default_workflows import ALL_DEFAULT_WORKFLOWS
from app.models.workflow import Workflow, WorkflowStep


def seed_default_workflows(db: Session) -> dict:
    """Insert or update all default workflows + their steps.

    Returns a summary: {"inserted": int, "updated": int, "steps": int}
    Does not touch custom tenant workflows (tier 4).
    """
    inserted = 0
    updated = 0
    step_count = 0

    # Whitelist of columns allowed on the Workflow model. Anything else in the
    # seed dicts (e.g. documentation-only fields like `source_service` on
    # Tier 1 platform workflows) is silently dropped so we don't crash the
    # whole seed batch.
    allowed = {c.name for c in Workflow.__table__.columns}

    for raw in ALL_DEFAULT_WORKFLOWS:
        # Copy to avoid mutating the source data
        data = {k: v for k, v in raw.items() if k in allowed or k == "steps"}
        steps_data = data.pop("steps", [])

        existing = db.query(Workflow).filter(Workflow.id == data["id"]).first()
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            updated += 1
        else:
            db.add(Workflow(**data))
            inserted += 1

        db.flush()

        # Sync steps — upsert by (workflow_id, step_key)
        for step in steps_data:
            step_record = {"workflow_id": data["id"], **step}
            existing_step = (
                db.query(WorkflowStep)
                .filter(
                    WorkflowStep.workflow_id == data["id"],
                    WorkflowStep.step_key == step["step_key"],
                )
                .first()
            )
            if existing_step:
                for k, v in step_record.items():
                    setattr(existing_step, k, v)
            else:
                db.add(WorkflowStep(**step_record))
            step_count += 1

    db.commit()
    return {"inserted": inserted, "updated": updated, "steps": step_count}
