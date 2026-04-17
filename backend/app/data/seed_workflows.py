"""Seed default workflows — idempotent, safe to run on every startup."""

from sqlalchemy.orm import Session

from app.data.default_workflows import ALL_DEFAULT_WORKFLOWS
from app.models.workflow import Workflow, WorkflowStep, WorkflowStepParam


def seed_default_workflows(db: Session) -> dict:
    """Insert or update all default workflows + their steps + step params.

    Returns a summary: {"inserted": int, "updated": int, "steps": int, "params": int}
    Does not touch custom tenant workflows (tier 4).
    """
    inserted = 0
    updated = 0
    step_count = 0
    param_count = 0

    # Whitelist of columns allowed on the Workflow model. Anything else in the
    # seed dicts (e.g. documentation-only fields like `source_service` on
    # Tier 1 platform workflows, or per-workflow "params" lists) is silently
    # dropped so we don't crash the whole seed batch.
    workflow_cols = {c.name for c in Workflow.__table__.columns}
    step_cols = {c.name for c in WorkflowStep.__table__.columns}

    for raw in ALL_DEFAULT_WORKFLOWS:
        # Copy and split out the pieces we don't hand to Workflow(**data)
        steps_data = raw.get("steps", [])
        params_data = raw.get("params", [])
        data = {k: v for k, v in raw.items() if k in workflow_cols}

        is_tier_1 = raw.get("tier") == 1

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
            # Tier 1 steps are "core" by default (locked) unless explicitly
            # marked otherwise. Tier 2/3/4 default to is_core=False.
            step_record = {
                "workflow_id": data["id"],
                **{k: v for k, v in step.items() if k in step_cols},
            }
            step_record.setdefault("is_core", True if is_tier_1 else False)

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

        # Sync platform defaults for step params (company_id NULL).
        # Tenant-specific overrides live as separate rows with company_id set.
        for param in params_data:
            existing_param = (
                db.query(WorkflowStepParam)
                .filter(
                    WorkflowStepParam.workflow_id == data["id"],
                    WorkflowStepParam.step_key == param["step_key"],
                    WorkflowStepParam.param_key == param["param_key"],
                    WorkflowStepParam.company_id.is_(None),
                )
                .first()
            )
            record = {
                "workflow_id": data["id"],
                "company_id": None,
                "step_key": param["step_key"],
                "param_key": param["param_key"],
                "label": param["label"],
                "description": param.get("description"),
                "param_type": param["param_type"],
                "default_value": param.get("default_value"),
                "is_configurable": param.get("is_configurable", True),
                "validation": param.get("validation"),
            }
            if existing_param:
                for k, v in record.items():
                    setattr(existing_param, k, v)
            else:
                db.add(WorkflowStepParam(**record))
            param_count += 1

    db.commit()
    return {
        "inserted": inserted,
        "updated": updated,
        "steps": step_count,
        "params": param_count,
    }
