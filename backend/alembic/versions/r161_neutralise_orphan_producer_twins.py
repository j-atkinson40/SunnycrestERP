"""WE-1 A-1 follow-up — neutralise the FOUR orphaned twins that suppress a working producer.

r160 fixed ONE instance of a pathology it did not know was a class. This is the
derived full set.

THE PATHOLOGY
-------------
Two steps share a `step_order`. `_next_by_order` walks by LIST INDEX rather than
by order value, so which one runs is decided by unspecified Postgres ordering.
Before A-1 both were harmless — the broken one returned `unknown_action_type`
and the engine recorded it as completed. After A-1 it HALTS the run, and if it
is picked first the working twin never executes.

In each of these four, the working twin is a `call_service_method` step that
does the substantive job:

    wf_sys_ar_collections     order 1  ar_snapshot        ← inert, halts
                              order 1  run_collections    ← DOES THE WORK
    wf_sys_month_end_close    order 1  invoice_coverage   ← inert, halts
                              order 1  run_analysis       ← DOES THE WORK
    wf_sys_safety_program_gen order 1  scrape_osha        ← inert, halts
                              order 1  run_monthly_safety_program ← DOES THE WORK
    wf_sys_catalog_fetch      order 1  fetch_catalog      ← inert, halts
                              order 1  stage_catalog_fetch ← DOES THE WORK

AR Collections and Wilbert Catalog were ACTIVELY regressed by A-1 — both failed
twice in the deploy window. Month-End Close and Safety Program Generation are
LATENT: zero runs, so the break has not fired yet. They are included precisely
because a workflow that has not run since the deploy carries the same break.

DERIVED, NOT ENUMERATED. The recognised `action_type` set was parsed from
`workflow_engine.py` and every `workflow_steps` row classified against it. The
hand-found set was two of four; the two latent ones came from the derivation.

⚠️ WHAT THIS DELIBERATELY DOES NOT TOUCH — AND WHY
--------------------------------------------------
**Seven other workflows have a broken step ahead of a working one. Neutralising
those would be WRONG, and it is worth stating why rather than leaving it to look
like an oversight.**

r160's justification was that the engine fix "would silently disable the one
piece that currently works." That justification holds ONLY where a working
sibling does the substantive job. In the excluded group the broken step IS the
job, and what survives behind it is a gate or a notification, never a producer:

    Arrangement Scribe      → confidence_review   (INPUT — parks on nothing)
    Legacy Print — Proof    → await_approval      (INPUT — parks on nothing)
    Monthly Statement Run   → approval_gate       (INPUT — parks on nothing)
    Document Review Reminder→ notify_admin        (notifies with no scan behind it)
    Flag Pre-Need Policy    → notify_if_found     (CONSUMES check_preneed's output)

Neutralising those would trade a loud failure for a silent empty park — undoing
WE-1 A-2, which exists to stop gates asking about nothing, and re-creating the
condition A-3 cleared 610 runs of. Failing loudly is the correct behaviour and
the honest input to the implement-or-delete pass.

**The order-2 twins are excluded by the same argument one level down.**
`tier_classification` (AR Collections) and `payment_reconciliation` (Month-End
Close) each share order 2 with an `approval_gate`. Neutralising them would let
the gate run — and a gate whose producer is inert parks on nothing.

⚠️ THIS DOES NOT FIX THE DUPLICATE `step_order` PATHOLOGY. IT UNBLOCKS FOUR
PRODUCERS.
--------------------------------------------------------------------------
Anyone reading "fixed the duplicate step_order pathology" would reasonably
believe more than happened. At order 2 the engine still chooses between failing
and parking-empty under unspecified Postgres ordering — a coin flip that remains
in place after this migration. Removing it means renumbering `step_order` or
changing how `_next_by_order` walks. That is a design act, and it belongs with
the implement-or-delete pass where the whole step inventory is on the table.

⚠️ NEUTRALISED, NOT DELETED — SAME FK AS r160.
`workflow_run_steps.step_id → workflow_steps.id` has NO `ON DELETE`, and history
rows reference these steps. Deleting them means destroying the evidence of the
silent failure or altering a history table's FK; neither belongs in a bug fix.
`WorkflowStep` has no `is_active` column, and adding one is the general answer
for all 46 remaining broken steps — a design decision for implement-or-delete,
not a side effect of unblocking four.

`show_confirmation` is the only recognised action type that is genuinely
side-effect free: it returns `{"type": "confirmation", ...}` with no `status`
key, so A-1 completes it and the run proceeds to the next step. (`record_marker`
was rejected in r160 for writing a real row on every fire; that reasoning is
unchanged here.)

ORPHANS OF SUPERSEDED DEFINITIONS — verified, not assumed. None of these four
step keys appears in `app/data/default_workflows.py` (1,802 lines, searched;
a control key in the same file returns hits, so the absence is a real search
result rather than an empty one). `seed_default_workflows` inserts and updates
but never deletes, which is how the rows outlived their definitions. So no code
edit accompanies this, and on a fresh database it updates nothing.

Note the shape of three of the four: `{"description": "Snapshot overdue AR"}` —
a step that names its intent in prose and carries no `action_type` at all. It
never did anything. The description is the only evidence it was ever meant to.
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "r161_neutralise_orphan_producer_twins"
down_revision = "r160_neutralise_orphan_categorize_step"
branch_labels = None
depends_on = None


#: (workflow_id, step_key, original_config, working_twin, why)
#:
#: The original config is carried so `downgrade` is a TRUE reverse rather than a
#: guess, and so `_retired.was` records what the row actually held rather than
#: what someone remembered it holding.
_TARGETS = [
    (
        "wf_sys_ar_collections",
        "ar_snapshot",
        {"description": "Snapshot overdue AR"},
        "run_collections",
        "ACTIVELY REGRESSED — failed twice post-A-1. Suppresses the AR "
        "collections pipeline (drafts, tiering, anomaly staging).",
    ),
    (
        "wf_sys_month_end_close",
        "invoice_coverage",
        {"description": "Verify all delivered orders are invoiced"},
        "run_analysis",
        "LATENT — zero runs, manual trigger. Suppresses the month-end close "
        "analysis on the first invocation that ever happens.",
    ),
    (
        "wf_sys_safety_program_gen",
        "scrape_osha",
        {"description": "Scrape OSHA standard pages"},
        "run_monthly_safety_program",
        "LATENT — zero runs. Suppresses the Phase 8d.1 safety program "
        "generation adapter.",
    ),
    (
        "wf_sys_catalog_fetch",
        "fetch_catalog",
        {"job": "wilbert_catalog_fetch", "action_type": "system_job"},
        "stage_catalog_fetch",
        "ACTIVELY REGRESSED — failed twice post-A-1. Suppresses the Phase 8d "
        "staged Wilbert catalog fetch.",
    ),
]


def _retired_note(step_key: str, original: dict, twin: str, why: str) -> dict:
    """Carried in the step's own config so implement-or-delete FINDS this.

    A neutralised orphan that looks like an ordinary step is how a cleanup pass
    skips the thing it exists to clean.
    """
    return {
        "by": "r161 (WE-1 A-1 follow-up)",
        "was": original,
        "why": (
            f"Orphan of a superseded definition sharing step_order with "
            f"'{twin}', which does the actual work. Never executed anything. "
            f"{why}"
        ),
        "disposition": (
            "DELETE this row once WorkflowStep gains an is_active column, or "
            "once the run-step FK allows removal without destroying history. "
            "It exists in no version of default_workflows.py."
        ),
        "not_fixed": (
            "The duplicate step_order itself. _next_by_order walks by list "
            "index, so sibling selection is still decided by unspecified "
            "Postgres ordering."
        ),
    }


def upgrade() -> None:
    conn = op.get_bind()
    total = 0

    for workflow_id, step_key, original, twin, why in _TARGETS:
        # Targeted by (workflow_id, step_key) plus the ORIGINAL action_type
        # shape, never by id — ids are per-environment. Including the shape in
        # the predicate means a future legitimate step reusing the key is not
        # neutralised by this migration, and makes the statement idempotent:
        # after it runs, action_type is 'show_confirmation' and neither branch
        # matches again.
        if original.get("action_type") is None:
            # Three of the four carry no action_type at all — a prose
            # description and nothing else.
            shape_predicate = "config->>'action_type' IS NULL"
            params = {"w": workflow_id, "k": step_key}
        else:
            shape_predicate = "config->>'action_type' = :at"
            params = {"w": workflow_id, "k": step_key, "at": original["action_type"]}

        params["cfg"] = json.dumps({
            "action_type": "show_confirmation",
            "message": "Retired step — see _retired. Does nothing.",
            "_retired": _retired_note(step_key, original, twin, why),
        })

        result = conn.execute(
            sa.text(
                "UPDATE workflow_steps SET config = CAST(:cfg AS jsonb) "
                "WHERE workflow_id = :w AND step_key = :k "
                f"  AND {shape_predicate}"
            ),
            params,
        )
        total += result.rowcount
        print(f"[r161] {workflow_id}.{step_key}: neutralised {result.rowcount} row(s)")

    print(
        f"[r161] {total} orphaned twin(s) neutralised. Four producers unblocked. "
        f"The duplicate step_order pathology itself is NOT fixed — see the "
        f"module docstring."
    )


def downgrade() -> None:
    # Restores each ORIGINAL config exactly, so the reverse is a true reverse:
    # every step goes back to halting the run under A-1. Paired with reverting
    # the engine fix that is harmless again (these were swallowed before);
    # without that revert it re-breaks four workflows, which is correct — this
    # migration exists only to serve the fix, and rolling one back without the
    # other should restore the state they were both written against.
    conn = op.get_bind()
    for workflow_id, step_key, original, _twin, _why in _TARGETS:
        conn.execute(
            sa.text(
                "UPDATE workflow_steps SET config = CAST(:cfg AS jsonb) "
                "WHERE workflow_id = :w AND step_key = :k "
                "  AND config->'_retired' IS NOT NULL"
            ),
            {"w": workflow_id, "k": step_key, "cfg": json.dumps(original)},
        )
