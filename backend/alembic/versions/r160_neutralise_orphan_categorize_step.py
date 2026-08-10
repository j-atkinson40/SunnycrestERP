"""WE-1 A-1 — neutralise the orphaned `categorize` step on wf_sys_expense_categorization.

REQUIRED BY THE ENGINE FIX IN THE SAME COMMIT, not bundled with it.

`workflow_engine` now marks a step failed when its output reports a failure
shape, rather than recording it as completed. `categorize` carries
`action_type: "system_job"`, which the engine does not recognise, so it returns
`unknown_action_type` — previously swallowed, now a failure that HALTS the run.

That matters here because of a second defect underneath it:

    order=1  categorize          action  ← unrecognised, no-op
    order=1  run_categorization  action  ← call_service_method, DOES THE WORK
    order=2  approval_gate       input

TWO STEPS SHARE step_order=1, and `_next_by_order` walks by LIST INDEX rather
than by order value, so both execute today in an order Postgres does not
guarantee. After the engine fix, whichever is picked first decides the outcome:
if `categorize` runs first the run halts and `run_categorization` — the only
step that does anything — never executes. The fix would silently disable the one
piece of expense categorization that currently works. Hence this migration.

⚠️ NEUTRALISED, NOT DELETED, AND THE REASON IS AN FK.
`workflow_run_steps.step_id → workflow_steps.id` has NO `ON DELETE`, and 12,365
run-step history rows reference this step. Deleting it therefore requires either
destroying that history — which is the evidence of the three-month silent
failure, i.e. the thing that made this findable — or altering a history table's
FK so a definition row can be removed. Neither belongs in a bug fix.

`WorkflowStep` has no `is_active` column, so there is no deactivate idiom here
the way `focus_templates` has one. Adding one is the general answer for all 47
broken steps and belongs to the implement-or-delete pass, not to this migration:
a new column the engine must honour is a design decision, and it should not
arrive as a side effect of unblocking one step.

So the step stays and is made INERT. `show_confirmation` is the only recognised
action type that is genuinely side-effect free — it returns a payload with no
`status` key and writes nothing. (`record_marker` was considered and rejected: it
writes a real `moc_witness_marker` row on every fire, which at this workflow's
15-minute cadence is 96 junk rows a day.)

THE DEFINITION ALREADY DROPPED THIS STEP. `app/data/default_workflows.py`
defines exactly two steps here (`run_categorization`, `approval_gate`) — the
Phase 8c rewrite replaced the `system_job` step with `call_service_method` and
never removed the old row, because `seed_default_workflows` INSERTS OR UPDATES
and never deletes. This is orphaned data, so no code edit accompanies it: a
fresh database has never had this step and this migration will delete nothing
there.

⚠️ SCOPE. One step. 46 others across 17 workflows carry an unrecognised
`action_type` and will now fail loudly — that is the intent. This one is singled
out ONLY because its failure would suppress working behaviour behind it.
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "r160_neutralise_orphan_categorize_step"
down_revision = "r159_moc_job_ref_kind_drop_focus"
branch_labels = None
depends_on = None

_WORKFLOW_ID = "wf_sys_expense_categorization"
_STEP_KEY = "categorize"

#: Carried in the step's own config so the implement-or-delete pass FINDS this
#: rather than rediscovering it. A neutralised orphan that looks like an
#: ordinary step is how a cleanup pass skips the thing it exists to clean.
_RETIRED_NOTE = {
    "by": "r160 (WE-1 A-1)",
    "was": {"action_type": "system_job", "job": "expense_categorization"},
    "why": (
        "Orphan of a superseded definition. Never executed anything — "
        "'system_job' is not a recognised action_type. Neutralised rather than "
        "deleted because workflow_run_steps.step_id has no ON DELETE and 12,365 "
        "history rows reference it."
    ),
    "disposition": (
        "DELETE this row once WorkflowStep gains an is_active column, or once "
        "the run-step FK allows removal without destroying history. It exists "
        "in no version of default_workflows.py."
    ),
}


def upgrade() -> None:
    conn = op.get_bind()

    # Targeted by (workflow, step_key, action_type) rather than by id — ids are
    # per-environment. The action_type is part of the predicate so a future
    # legitimate step reusing the key is not neutralised by this migration.
    result = conn.execute(
        sa.text(
            "UPDATE workflow_steps "
            "SET config = CAST(:cfg AS jsonb) "
            "WHERE workflow_id = :w AND step_key = :k "
            "  AND config->>'action_type' = 'system_job'"
        ),
        {
            "w": _WORKFLOW_ID,
            "k": _STEP_KEY,
            "cfg": json.dumps({
                "action_type": "show_confirmation",
                "message": "Retired step — see _retired. Does nothing.",
                "_retired": _RETIRED_NOTE,
            }),
        },
    )
    # Idempotent by construction: the predicate requires action_type
    # 'system_job', which no longer matches after this runs, and a fresh
    # database never had the row.
    print(f"[r160] neutralised {result.rowcount} orphaned '{_STEP_KEY}' step(s)")


def downgrade() -> None:
    # Restores the ORIGINAL config, so the reverse is a true reverse — the step
    # goes back to returning unknown_action_type. Paired with reverting the
    # engine fix that is harmless again (it was swallowed before); without that
    # revert it re-breaks the workflow, which is correct: this migration exists
    # only to serve the fix, and rolling one back without the other should
    # restore the state they were both written against.
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE workflow_steps "
            "SET config = CAST(:cfg AS jsonb) "
            "WHERE workflow_id = :w AND step_key = :k "
            "  AND config->'_retired' IS NOT NULL"
        ),
        {
            "w": _WORKFLOW_ID,
            "k": _STEP_KEY,
            "cfg": json.dumps({"action_type": "system_job", "job": "expense_categorization"}),
        },
    )
