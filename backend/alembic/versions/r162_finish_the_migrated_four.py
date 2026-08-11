"""WE-1 — finish the four migrated workflows: clear the residue, gate the one gate that needed it.

r161 unblocked the producer at order 1 in four workflows. It did not finish the
job: twelve more orphan steps sit at LATER orders, so post-r161 the producer runs
and the run still goes red behind it. This clears those, and — in the same change,
deliberately — sets the gate behaviour that clearing the path exposes.

⚠️ THE MIGRATION AND THE GATE PREDICATE ARE ONE CHANGE, NOT TWO.
Clearing the path to a gate that has no `park_when` produces a workflow that runs
its producer and then parks on nothing. That is the 12,367-run pathology WE-1 A-2
exists to prevent, and shipping the step cleanup alone would recreate it in four
places. Splitting them across two migrations would leave a window where the fix
is the defect.

WHAT CHANGED SINCE r161, AND A CORRECTION TO IT
-----------------------------------------------
r161's docstring says these steps cannot be deleted because "history rows
reference these steps." That is true PER STEP, not per workflow, and r161 did not
check per step. Measured now:

    ar_snapshot          121 run-steps   neutralise was required
    fetch_catalog          2 run-steps   neutralise was required
    invoice_coverage       0 run-steps   COULD HAVE BEEN DELETED
    scrape_osha            0 run-steps   COULD HAVE BEEN DELETED

So two of r161's four were neutralised when a clean delete was available. Nothing
broke — an inert row and an absent row behave identically — but the justification
was over-general, and this migration deletes those two rather than leaving them as
permanent residue with a misleading `_retired` note.

**The FK is the whole predicate, and it was derived rather than assumed.**
`pg_constraint` reports exactly ONE foreign key referencing `workflow_steps`:
`workflow_run_steps.step_id ON DELETE NO ACTION`. No DAG-edge table exists.
`workflow_step_params` references steps by `step_key` STRING with no FK, and
carries zero rows for any key deleted here. Platform-wide, ZERO steps set
`next_step_id` / `condition_true_step_id` / `condition_false_step_id`, so the
engine walks by order alone and removing a row dangles nothing.

Therefore: **a step with no run-step history is a clean DELETE; a step with
history is a NEUTRALISE.** Per step, not per workflow. Every DELETE below is
additionally guarded by `NOT EXISTS` at apply time — a count taken today is not a
guarantee about the database this runs against.

THE FOUR WORKFLOWS AFTER THIS
------------------------------
    wf_sys_ar_collections      ar_snapshot(inert) + run_collections → approval_gate(park_when)
    wf_sys_month_end_close     run_analysis → approval_gate (NO park_when — see below)
    wf_sys_safety_program_gen  run_monthly_safety_program            (gate REMOVED)
    wf_sys_catalog_fetch       fetch_catalog(inert) + stage_catalog_fetch + notify_if_updated(inert)

⚠️ MONTH-END CLOSE GETS NO `park_when`, AND THAT ABSENCE IS DELIBERATE.
Three sibling gates carry one; this one does not, and without saying so the gap
reads as an oversight — so it is recorded on the row itself as `_no_park_when`,
not only here.

Its gate asks *"Review the analysis report and approve to generate the statement
run + lock the period."* That is a real decision on EVERY run: it approves a
**period lock**, not a review of findings. The producer returns `anomaly_count`,
and writing `anomaly_count > 0` by analogy with its siblings would be
pattern-matching a shape rather than reading what the gate does — zero anomalies
means a clean close that still wants a human, not an empty question. The workflow
is manual-trigger, so whoever invokes it wants the gate.

**This is the case A-2's dispatch anticipated and could not find: a gate that
legitimately asks on empty.** First Call Intake was considered and was not it.

⚠️ CONSEQUENCE, NAMED HERE BECAUSE IT WILL LOOK LIKE A REGRESSION LATER.
After this migration Month-End Close PARKS ON EVERY RUN. That is correct for a
manual close whose gate approves a period lock. Someone reading run states in six
months will see a workflow parking every time and recognise the A-2 pathology —
it is not that. The same sentence is carried in the `_retired` note of the row
whose deletion exposes the gate, because the row is what gets queried.

⚠️ SAFETY PROGRAM'S GATE IS REMOVED, NOT PREDICATED.
`wf_sys_safety_program_gen` had THREE review surfaces for one artifact: this
workflow's `approval_gate`, the `safety_program_triage` queue (which Phase 8d.1
named canonical), and the bespoke `/safety/programs` UI. Its producer at order 1
already leaves a `SafetyProgramGeneration` in `pending_review` for those two.

A predicate would make the redundant surface fire less often, which is worse than
removing it: the gate stays in the definition, still competes for the same
decision, and now does so intermittently. It has zero run-steps, so a clean delete
is available. Removed.

AR COLLECTIONS' PREDICATE — derived the way `needs_review > 0` was.
The gate asks *"Review drafts and dispatch one customer's email at a time via the
triage queue."* The producer returns `drafts_generated` explicitly. A-3 measured
`drafts_generated: 0` on all 127 runs across three months. Gate text names the
thing, producer emits the field, production confirms it has always been zero:
`{output.run_collections.drafts_generated} > 0`.
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "r162_finish_the_migrated_four"
down_revision = "r161_neutralise_orphan_producer_twins"
branch_labels = None
depends_on = None


#: (workflow_id, step_order, step_key, step_type, config, is_core, display_name)
#: Read off production so `downgrade` recreates the real rows. For the two
#: r161-neutralised entries the ORIGINAL config is restored (from `_retired.was`),
#: not the inert shape — a downgrade to the inert shape would not be a reverse.
_DELETE = [
    ("wf_sys_ar_collections", 3, "draft_emails", "action",
     {"description": "Claude-drafted emails with template fallback"}, True, None),
    ("wf_sys_month_end_close", 2, "payment_reconciliation", "action",
     {"description": "Reconcile customer payments"}, True, None),
    ("wf_sys_month_end_close", 3, "ar_aging_snapshot", "action",
     {"description": "Snapshot AR aging buckets"}, True, None),
    ("wf_sys_month_end_close", 4, "revenue_summary", "action",
     {"description": "Summarize revenue with outlier detection"}, True, None),
    ("wf_sys_month_end_close", 5, "statement_flags", "action",
     {"description": "Detect per-customer statement flags"}, True, None),
    ("wf_sys_month_end_close", 6, "anomaly_checks", "action",
     {"description": "Cross-step anomaly checks"}, True, None),
    ("wf_sys_month_end_close", 7, "prior_period_compare", "action",
     {"description": "Compare against prior period"}, True, None),
    ("wf_sys_month_end_close", 9, "statement_run", "action",
     {"description": "Generate statement run, auto-approve unflagged, lock period"}, True, None),
    # r161-neutralised, zero history — deleted rather than left as residue.
    ("wf_sys_month_end_close", 1, "invoice_coverage", "action",
     {"description": "Verify all delivered orders are invoiced"}, True, None),
    ("wf_sys_safety_program_gen", 2, "generate_program", "action",
     {"description": "Claude generates 7-section program"}, True, None),
    ("wf_sys_safety_program_gen", 3, "render_pdf", "action",
     {"description": "WeasyPrint renders PDF with cover page"}, True, None),
    ("wf_sys_safety_program_gen", 1, "scrape_osha", "action",
     {"description": "Scrape OSHA standard pages"}, True, None),
    # The redundant third review surface. See the docstring.
    ("wf_sys_safety_program_gen", 4, "approval_gate", "input",
     {"prompt": "Review + approve program"}, True, None),
]

#: (workflow_id, step_key, original_config, why) — history exists, so inert.
_NEUTRALISE = [
    ("wf_sys_ar_collections", "tier_classification",
     {"description": "Classify customers into collection tiers"},
     "120 run-steps reference this. The tiering it names is done inside "
     "ar_collections.run_collections_pipeline."),
    ("wf_sys_catalog_fetch", "notify_if_updated",
     {"description": "Notify admins if catalog changed"},
     "2 run-steps reference this. The staged-fetch triage queue is where a "
     "changed catalog surfaces for review."),
]

#: The one predicate. Field is a template resolved by `resolve_variables` before
#: `_evaluate_park_when` sees it — same grammar as the A-2 reference instance.
_AR_PARK_WHEN = {
    "op": ">",
    "field": "{output.run_collections.drafts_generated}",
    "value": 0,
}

#: The deliberate absence, recorded on the row because the row is what gets
#: queried when someone asks why this gate differs from its three siblings.
_MEC_NO_PARK_WHEN = {
    "by": "r162 (WE-1)",
    "decision": "This gate has NO park_when, deliberately.",
    "why": (
        "It approves a PERIOD LOCK, not a review of findings. Zero anomalies "
        "means a clean close that still wants a human — not an empty question. "
        "Writing anomaly_count > 0 by analogy with the sibling gates would "
        "suppress a decision rather than an empty prompt."
    ),
    "expect": (
        "THIS WORKFLOW PARKS ON EVERY RUN. That is correct and is not the A-2 "
        "empty-park pathology. Manual trigger — whoever invokes it wants the gate."
    ),
}


def _retired_note(original: dict, why: str, extra: str | None = None) -> dict:
    note = {
        "by": "r162 (WE-1)",
        "was": original,
        "why": why,
        "disposition": (
            "DELETE once the run-step FK allows removal without destroying "
            "history. Kept inert only because history references it — its "
            "zero-history siblings were deleted outright by this migration."
        ),
    }
    if extra:
        note["expect"] = extra
    return note


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. DELETE the steps with no history ──────────────────────────────
    # Guarded by NOT EXISTS at APPLY time rather than trusting the counts this
    # was written against. If history appeared since, the row is left alone and
    # the mismatch is printed rather than silently skipped.
    deleted = 0
    for workflow_id, _order, step_key, _st, _cfg, _core, _dn in _DELETE:
        result = conn.execute(
            sa.text(
                "DELETE FROM workflow_steps s "
                "WHERE s.workflow_id = :w AND s.step_key = :k "
                "  AND NOT EXISTS (SELECT 1 FROM workflow_run_steps rs "
                "                  WHERE rs.step_id = s.id)"
            ),
            {"w": workflow_id, "k": step_key},
        )
        deleted += result.rowcount
        if result.rowcount == 0:
            print(
                f"[r162] {workflow_id}.{step_key}: NOT deleted — either already "
                f"gone (re-run) or run-step history appeared since this was "
                f"written. Left intact; no data destroyed."
            )
    print(f"[r162] deleted {deleted}/{len(_DELETE)} zero-history steps")

    # ── 2. NEUTRALISE the two that carry history ─────────────────────────
    for workflow_id, step_key, original, why in _NEUTRALISE:
        extra = None
        result = conn.execute(
            sa.text(
                "UPDATE workflow_steps SET config = CAST(:cfg AS jsonb) "
                "WHERE workflow_id = :w AND step_key = :k "
                "  AND config->'_retired' IS NULL"
            ),
            {
                "w": workflow_id, "k": step_key,
                "cfg": json.dumps({
                    "action_type": "show_confirmation",
                    "message": "Retired step — see _retired. Does nothing.",
                    "_retired": _retired_note(original, why, extra),
                }),
            },
        )
        print(f"[r162] {workflow_id}.{step_key}: neutralised {result.rowcount} row(s)")

    # ── 3. THE GATE PREDICATE — the half of this change that is not cleanup ──
    result = conn.execute(
        sa.text(
            "UPDATE workflow_steps "
            "SET config = config || CAST(:pw AS jsonb) "
            "WHERE workflow_id = 'wf_sys_ar_collections' AND step_key = 'approval_gate' "
            "  AND config->'park_when' IS NULL"
        ),
        {"pw": json.dumps({"park_when": _AR_PARK_WHEN})},
    )
    print(f"[r162] ar_collections gate: park_when set on {result.rowcount} row(s)")

    # ── 4. THE DELIBERATE ABSENCE, written down ──────────────────────────
    result = conn.execute(
        sa.text(
            "UPDATE workflow_steps "
            "SET config = config || CAST(:n AS jsonb) "
            "WHERE workflow_id = 'wf_sys_month_end_close' AND step_key = 'approval_gate' "
            "  AND config->'_no_park_when' IS NULL"
        ),
        {"n": json.dumps({"_no_park_when": _MEC_NO_PARK_WHEN})},
    )
    print(
        f"[r162] month_end_close gate: intentional-absence note on "
        f"{result.rowcount} row(s). THIS WORKFLOW NOW PARKS EVERY RUN, BY DESIGN."
    )


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text(
        "UPDATE workflow_steps SET config = config - '_no_park_when' "
        "WHERE workflow_id = 'wf_sys_month_end_close' AND step_key = 'approval_gate'"
    ))
    conn.execute(sa.text(
        "UPDATE workflow_steps SET config = config - 'park_when' "
        "WHERE workflow_id = 'wf_sys_ar_collections' AND step_key = 'approval_gate'"
    ))

    for workflow_id, step_key, original, _why in _NEUTRALISE:
        conn.execute(
            sa.text(
                "UPDATE workflow_steps SET config = CAST(:cfg AS jsonb) "
                "WHERE workflow_id = :w AND step_key = :k "
                "  AND config->'_retired' IS NOT NULL"
            ),
            {"w": workflow_id, "k": step_key, "cfg": json.dumps(original)},
        )

    # Re-inserted with fresh ids. Nothing referenced them (that is why they were
    # deletable), so identity is not part of what a reverse has to restore —
    # order, key, type and config are.
    for workflow_id, order, step_key, step_type, cfg, is_core, display_name in _DELETE:
        conn.execute(
            sa.text(
                "INSERT INTO workflow_steps "
                "  (id, workflow_id, step_order, step_key, step_type, config, is_core, display_name) "
                "SELECT gen_random_uuid()::text, :w, :o, :k, :t, CAST(:c AS jsonb), :core, :dn "
                "WHERE NOT EXISTS (SELECT 1 FROM workflow_steps "
                "                  WHERE workflow_id = :w AND step_key = :k)"
            ),
            {
                "w": workflow_id, "o": order, "k": step_key, "t": step_type,
                "c": json.dumps(cfg), "core": is_core, "dn": display_name,
            },
        )
