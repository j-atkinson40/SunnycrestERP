"""IOD — wire Monthly Statement Run to its existing producer, and leave it DELIBERATELY PARTIAL.

⚠️ READ THIS FIRST IF YOU ARE LOOKING AT A FAILED `wf_sys_statement_run` RUN.
**A red run after the approval gate is the INTENDED state, not a regression.**
This workflow now genuinely generates statements and genuinely takes a human
review — and then fails at `send_statements`, because bulk dispatch of an approved
statement run **was never built**. The failure is the honest report of that.

    order 1  identify_customers    inert          (the producer does this internally)
    order 2  generate_statements   PRODUCER  →  invoice_statement.run_statement_run
    order 3  approval_gate         human review   (no park_when — deliberate, see below)
    order 4  send_statements       STILL BROKEN — bulk send does not exist

Generation is real. Review is real. Dispatch is declared and absent. Making the
run complete green by clearing step 4 would produce a workflow that generates
statements, collects an approval, and sends nothing — silently. That is precisely
the class WE-1 A-1 exists to end, and it would be worse than the red.

WHAT ALREADY EXISTED, WHICH IS WHY THIS IS WIRING AND NOT A BUILD
-----------------------------------------------------------------
`invoice_statement_adapter.run_statement_run` was written, delegates to
`statement_generation_service.generate_statement_run`, and is REGISTERED in
`workflow_engine._SERVICE_METHOD_REGISTRY` as `invoice_statement.run_statement_run`
with allowed kwargs `(period_start, period_end)` — both optional, defaulting to
the current month. The adapter existed and the workflow simply never pointed at
it. No adapter change, no registry change.

⚠️ THE PRODUCER REPLACES A STEP RATHER THAN BEING INSERTED, ON PURPOSE.
Adding a `run_statement_run` step at order 1 beside `identify_customers` would
have created a second step sharing a `step_order` — manufacturing the exact
pathology r161 and r162 were written to remove, in the same arc that removed it.
`_next_by_order` walks by list index, so the two would race under unspecified
Postgres ordering.

So `generate_statements` (order 2) BECOMES the producer in place. Its key already
describes what the producer does, the order sequence stays 1-2-3-4 with no
duplicates, and its four run-step history rows continue to reference a step whose
meaning is unchanged. `identify_customers` goes inert because customer selection
happens inside `generate_statement_run`.

⚠️ NO `park_when` ON THE GATE, AND THE ABSENCE IS RECORDED ON THE ROW.
Three sibling gates in this arc carry one; two now do not. The gate asks "Review
flagged statements", and the producer returns `statement_run_id`,
`total_customers`, `period_start`, `period_end` — **no flagged count**. Three
options were weighed:

  1. `total_customers > 0` — the WRONG QUESTION. It would park on a clean run of
     forty unflagged statements, which is not what the gate asks about.
  2. Extend the adapter to return `flagged_count`, then park on `> 0`. The honest
     exception-only gate, and `StatementRunItem` supports it — but it is an
     adapter change with its own scope, not a wiring.
  3. No predicate at all.

**(3), for Month-End Close's reason**: dispatching statements to every
charge-account customer is consequential and monthly, so a human confirming it is
not an empty question. Option 2 is recorded on the row as the upgrade path so that
whoever wants exception-only firing finds the change already identified rather
than re-deriving it.

DELETE-VS-NEUTRALISE IS PER STEP, MEASURED
-------------------------------------------
`identify_customers` 4 run-steps · `generate_statements` 4 · `approval_gate` 4 ·
`send_statements` 0. Only the last is deletable, and it is exactly the one being
kept. So nothing is deleted here.

Note also that `send_statements` carries three admin-configurable
`workflow_step_params` — `from_name`, `reply_to`, `include_zero_balance`. Those
reference the step by `step_key` STRING with no FK, so deleting the step would
have orphaned them silently rather than cascading. They stand as the spec for what
a future bulk-send step needs.

THE PATH TO A GREEN RUN, for whoever picks it up
--------------------------------------------------
Add a bulk send to `invoice_statement_adapter` and point step 4 at it. The recipe
is already proven in `wf_mfg_send_statement`, which is FULLY BUILT (all four steps
use recognised action types) but is manual and per-customer: "Which customer?" →
`generate_document` → `send_email` → confirm. Bulk dispatch of an approved run is
the missing piece. That is a build, and it is the only path to a green MSR.

NOTE ON FIRING: this workflow's `schedule_retired_at` is stamped (2026-07-17) —
per r129 its cron authority moved to a MoC trigger, so it fires via the MoC
schedule sweep rather than `workflow_scheduler`. Wiring the producer does not
change what fires it.
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "r165_wire_monthly_statement_run"
down_revision = "r164_mark_declared_but_unbuilt"
branch_labels = None
depends_on = None

_WORKFLOW_ID = "wf_sys_statement_run"

#: The step that becomes the producer, and what it held before.
_PRODUCER_STEP = "generate_statements"
_PRODUCER_WAS = {"description": "Generate statement PDFs"}
_PRODUCER_CONFIG = {
    "action_type": "call_service_method",
    "method_name": "invoice_statement.run_statement_run",
    # Both allowed kwargs are optional; the adapter defaults to the current
    # month (period_start = first of month, period_end = today).
    "kwargs": {},
    "_wired_by": {
        "by": "r165 (IOD)",
        "was": _PRODUCER_WAS,
        "why": (
            "The adapter and its registry entry already existed; this workflow "
            "never pointed at them. Replaced in place rather than inserting a "
            "new step, because a second step at an existing step_order would "
            "recreate the duplicate-order pathology r161/r162 removed."
        ),
    },
}

#: Goes inert — the producer selects customers internally.
_INERT_STEP = "identify_customers"
_INERT_WAS = {"description": "Find charge-account customers with activity"}

_NO_PARK_WHEN = {
    "by": "r165 (IOD)",
    "decision": "This gate has NO park_when, deliberately.",
    "why": (
        "The gate asks about FLAGGED statements; the producer returns "
        "statement_run_id / total_customers / period_start / period_end and no "
        "flagged count. total_customers > 0 would be the wrong question — it "
        "parks on a clean run of forty unflagged statements. Dispatching "
        "statements to every charge-account customer is consequential and "
        "monthly, so a human confirming it is not an empty question."
    ),
    "expect": (
        "THIS WORKFLOW PARKS AT THE GATE ON EVERY RUN, and then FAILS at "
        "send_statements. Both are intended. See the migration docstring: bulk "
        "dispatch was never built."
    ),
    "upgrade_path": (
        "For exception-only firing: extend invoice_statement_adapter."
        "run_statement_run to return flagged_count (StatementRunItem supports "
        "it), then set park_when {op: '>', field: "
        "'{output.generate_statements.flagged_count}', value: 0}."
    ),
}

#: Left broken on purpose. Named here so a reader of this migration does not have
#: to infer the omission.
_DELIBERATELY_BROKEN = {
    "by": "r165 (IOD)",
    "decision": "send_statements is LEFT BROKEN, deliberately.",
    # ⚠️ CORRECTED 2026-08-11 (BSS-1). This migration's data was superseded by the
    # port into `default_workflows.py`; what remains here is documentation, and
    # two of its claims were FALSE. Both are corrected below with the original
    # wording preserved, because a note that stops someone looking is worse than
    # no note.
    "why": (
        "Bulk dispatch EXISTS — statement_service.send_all_digital is a real "
        "per-item fan-out with per-item ledger writes — but is FILTERED TO ZERO "
        "ROWS for this producer's output (it requires delivery_method 'digital' "
        "+ status 'ready'; the producer writes 'email' + 'pending') and attaches "
        "no PDF. Clearing this step would still make the run complete green "
        "having sent nothing — the silent-success class WE-1 A-1 was built to end."
    ),
    "why_was_recorded_as": (
        "'Bulk dispatch of an approved statement run does not exist.' FALSE."
    ),
    "upgrade_path": (
        "Reconcile the two parallel statement subsystems' Customer column pair, "
        "then wire statement_pdf_service.generate_statement_document (ZERO "
        "callers today) so the email carries the statement. Per-item failure "
        "handling follows the Plaid sync shape: per-item try, commit the ledger "
        "INSIDE the loop, one terminal raise; 'customer has no email' is a SOFT "
        "outcome (a paper-statement customer), not an error."
    ),
    "upgrade_path_was_recorded_as": (
        "'The recipe is proven in wf_mfg_send_statement … which is fully built.' "
        "FALSE — that workflow's generate_document step omits template_key + "
        "title so the handler raises, its send_email step is a two-line stub "
        "that calls nothing, and it has ZERO runs platform-wide. 'Fully built' "
        "was asserted from step NAMES and recognised action types without "
        "reading the configs."
    ),
    "params_are_the_spec": ["from_name", "reply_to", "include_zero_balance"],
}


def upgrade() -> None:
    conn = op.get_bind()

    producer = conn.execute(
        sa.text(
            "UPDATE workflow_steps SET config = CAST(:c AS jsonb) "
            "WHERE workflow_id = :w AND step_key = :k "
            "  AND config->>'action_type' IS NULL"
        ),
        {"w": _WORKFLOW_ID, "k": _PRODUCER_STEP, "c": json.dumps(_PRODUCER_CONFIG)},
    ).rowcount

    inert = conn.execute(
        sa.text(
            "UPDATE workflow_steps SET config = CAST(:c AS jsonb) "
            "WHERE workflow_id = :w AND step_key = :k "
            "  AND config->'_retired' IS NULL"
        ),
        {
            "w": _WORKFLOW_ID, "k": _INERT_STEP,
            "c": json.dumps({
                "action_type": "show_confirmation",
                "message": "Retired step — see _retired. Does nothing.",
                "_retired": {
                    "by": "r165 (IOD)",
                    "was": _INERT_WAS,
                    "why": (
                        "Customer selection happens inside "
                        "statement_generation_service.generate_statement_run, "
                        "which the sibling step now invokes."
                    ),
                    "disposition": (
                        "DELETE once the run-step FK allows removal without "
                        "destroying history — 4 rows reference this."
                    ),
                },
            }),
        },
    ).rowcount

    gate = conn.execute(
        sa.text(
            "UPDATE workflow_steps SET config = config || CAST(:n AS jsonb) "
            "WHERE workflow_id = :w AND step_key = 'approval_gate' "
            "  AND config->'_no_park_when' IS NULL"
        ),
        {"w": _WORKFLOW_ID, "n": json.dumps({"_no_park_when": _NO_PARK_WHEN})},
    ).rowcount

    # The broken step is annotated, NOT repaired. The annotation is the whole
    # point: an unexplained broken step reads as an oversight, and the next
    # cleanup pass closes it.
    broken = conn.execute(
        sa.text(
            "UPDATE workflow_steps SET config = config || CAST(:n AS jsonb) "
            "WHERE workflow_id = :w AND step_key = 'send_statements' "
            "  AND config->'_deliberately_broken' IS NULL"
        ),
        {"w": _WORKFLOW_ID, "n": json.dumps({"_deliberately_broken": _DELIBERATELY_BROKEN})},
    ).rowcount

    print(
        f"[r165] producer wired: {producer}; step made inert: {inert}; gate "
        f"annotated: {gate}; broken step annotated: {broken}."
    )
    print(
        "[r165] MSR IS DELIBERATELY PARTIAL — generation real, review real, "
        "dispatch absent. A red run after the gate is intended."
    )


def downgrade() -> None:
    conn = op.get_bind()
    for key, note in (("send_statements", "_deliberately_broken"),
                      ("approval_gate", "_no_park_when")):
        conn.execute(
            sa.text(
                f"UPDATE workflow_steps SET config = config - '{note}' "
                "WHERE workflow_id = :w AND step_key = :k"
            ),
            {"w": _WORKFLOW_ID, "k": key},
        )
    for key, original in ((_PRODUCER_STEP, _PRODUCER_WAS), (_INERT_STEP, _INERT_WAS)):
        conn.execute(
            sa.text(
                "UPDATE workflow_steps SET config = CAST(:c AS jsonb) "
                "WHERE workflow_id = :w AND step_key = :k"
            ),
            {"w": _WORKFLOW_ID, "k": key, "c": json.dumps(original)},
        )
