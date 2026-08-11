"""Seed default workflows — idempotent, safe to run on every startup.

⚠️ OVERWRITE-AWARE, AND THE OPPOSITE OF ITS SIBLING SEEDER. STATED EXPLICITLY
BECAUSE THE SILENCE HERE COST FOUR MIGRATIONS.

For every workflow and every step DECLARED in `default_workflows.py`, this does
an unconditional `setattr` over each declared column — **including a step's
`config`**. There is no preserve rule, no `force` flag, no user-modified check.
Anything a migration or an operator writes into a declared row is **overwritten
on the next boot**.

Contrast `scripts/seed_accounting_jobs.py`, which is explicitly PRESERVE-AWARE:
*"an existing job's FIELDS are never touched — the operator's words survive every
boot. Only wholly-missing jobs are created."* Two seeders, same codebase,
opposite policies. This file previously said nothing, and silence beside an
explicit contract reads as the same contract — which is exactly why r162, r165
and r166 wrote step config in migrations and were silently reverted in production
on the next deploy.

**THE DEFINITION OWNS STEP CONFIG.** To change a step's behaviour, edit
`app/data/default_workflows.py` — not a migration. Once the definition is right
this seeder stops being an eraser and becomes the repair mechanism: every drifted
row heals itself on the next boot, no data migration required. Enforced by
`tests/test_workflow_definition_ownership_ratchet.py`.

WHAT SURVIVES, precisely — it is DECLAREDNESS, not table:

    workflows.description     declared by 36/36  → overwritten every boot
    workflows.is_active       declared by  0/36  → never written, survives
    workflows.is_coming_soon  declared by  3/36  → overwritten for those 3 only
    a step present in the definition             → its config is overwritten
    an ORPHAN step (absent from the definition)  → untouched, survives

The orphan case is not protection, only distance: declaring one of those keys
would silently revert whatever neutralised it.
"""

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
