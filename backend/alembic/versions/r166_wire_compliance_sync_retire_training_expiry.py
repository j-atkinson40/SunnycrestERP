"""IOD — wire Compliance Sync to the service it already names; retire Training Expiry as redundant.

TWO WORKFLOWS, ONE SERVICE, AND THE CARD WAS TELLING THE TRUTH ALL ALONG
------------------------------------------------------------------------
`wf_sys_compliance_sync` has carried `"source_service": "vault_compliance_sync.py"`
in `default_workflows.py` since it was written. Its four steps name the four
things that service already does:

    scan_inspections    → _sync_inspection_expiries
    scan_training       → _sync_training_expiries
    scan_regulatory     → _sync_regulatory_deadlines
    upsert_vault_items  → the VaultItem upsert the function performs

`sync_compliance_expiries` is live — called from `app/api/routes/vault.py:296` —
and covered by `tests/test_vault_v1d_notifications.py`. The workflow never pointed
at it. **This is unwired work, not unbuilt work.**

That distinction resolved a decision that had been framed as a loss either way.
The "Compliance & records upkeep" cadence card claims compliance data is synced
and documents reviewed, and the options on the table were (a) build four scanners,
or (b) make the card honest — which meant deleting its only members and losing the
Weekly grain from the accounting area entirely. **Wiring is the third option: the
card becomes TRUE rather than built-out or walked back.** No Map change.

⚠️ TRAINING EXPIRY IS RETIRED AS REDUNDANT — NOT MARKED `is_coming_soon`.
`wf_sys_training_expiry`'s whole declared job (find expiring certs → notify admins)
is a strict SUBSET of `sync_compliance_expiries`, INCLUDING the notification:
`_notify_admins_compliance_expiry` fires from three call sites inside the service
and de-dupes on `(company_id, category, source_reference_id)`.

Compliance Sync runs daily at 03:00; Training Expiry weekly Monday 07:00. So once
Compliance Sync is wired, Training Expiry's job has already been done — daily —
and the de-dupe means wiring it too would produce **green runs that did nothing
because something else already did it.** That is a new instance of the exact
pathology this arc has spent five migrations removing, and it would have been
created by the arc itself.

`is_coming_soon` is the WRONG WORD here and the distinction is load-bearing. That
flag means "declared, never built" (r164). Training Expiry's capability IS built
and IS running — it is covered, not missing. Overloading the flag with a second
meaning is how a later investigation gets a wrong answer from a true value, which
is the same reason r164 rejected `schedule_retired_at` as an off switch.

So: `is_active = False`, and the reason goes in `description`, which is the
human-readable field the builder already renders. No field is given a second job.

⚠️ THE "ONE RENAME FROM WORKING" CLAIM WAS FALSE, and it is worth recording where
it came from. An earlier IOD report said `notify_admins` was one rename from
working because `send_notification` is a recognised action type. But the step's
config is prose only — `{"description": "Send notification to safety trainers"}` —
with no title, body or recipient, and `_handle_send_notification` DEFAULTS all of
them. Adding the action type would not have errored; it would have created a
VaultItem titled "Notification", empty, with no recipients, weekly, on three
tenants. Green and useless. **The claim was made from the step's NAME rather than
its CONFIG**, which is how several "one small fix away" claims have gone this week.

THE PRODUCER REPLACES A STEP, NOT INSERTED — r165's reasoning, unchanged.
Adding a step at an occupied `step_order` would manufacture the duplicate-order
race r161/r162 removed. `scan_inspections` (order 1) becomes the producer; the
other three go inert because the one call does all four things.

DELETE-VS-NEUTRALISE, measured per step: scan_inspections 134 run-steps,
scan_training 133, scan_regulatory 133, upsert_vault_items 133; find_expiring 20,
notify_admins 19. Every one carries history, so nothing here is deletable and
nothing is deleted.
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "r166_wire_compliance_sync_retire_training_expiry"
down_revision = "r165_wire_monthly_statement_run"
branch_labels = None
depends_on = None

_COMPLIANCE = "wf_sys_compliance_sync"
_TRAINING = "wf_sys_training_expiry"

_PRODUCER_STEP = "scan_inspections"
_PRODUCER_WAS = {"description": "Find overdue inspections"}
_PRODUCER_CONFIG = {
    "action_type": "call_service_method",
    "method_name": "compliance_sync.run_compliance_sync",
    "kwargs": {},
    "_wired_by": {
        "by": "r166 (IOD)",
        "was": _PRODUCER_WAS,
        "why": (
            "The definition has always declared source_service "
            "vault_compliance_sync.py; the workflow never called it. One "
            "invocation covers all four declared steps. Replaced in place "
            "rather than inserted, so no second step shares a step_order."
        ),
    },
}

#: The other three: one call does all of it.
_INERT = [
    ("scan_training", {"description": "Find expiring training certs"},
     "_sync_training_expiries runs inside the sibling producer's one call."),
    ("scan_regulatory", {"description": "Find regulatory deadlines (OSHA 300A)"},
     "_sync_regulatory_deadlines runs inside the sibling producer's one call."),
    ("upsert_vault_items",
     {"description": "Create/update vault items (dedupe by source_entity_id)"},
     "The VaultItem upsert is what sync_compliance_expiries does; it is not a "
     "separate phase."),
]

_TRAINING_WAS_DESC = "Notify admins when employee training certifications are expiring."
_TRAINING_NEW_DESC = (
    "RETIRED (r166) — superseded by Compliance Sync. "
    "vault_compliance_sync.sync_compliance_expiries already finds expiring "
    "training certs and notifies admins (de-duped), daily at 03:00. This "
    "workflow's weekly run would find nothing left to report. Not 'unbuilt' — "
    "covered. Original: " + _TRAINING_WAS_DESC
)


def upgrade() -> None:
    conn = op.get_bind()

    producer = conn.execute(
        sa.text(
            "UPDATE workflow_steps SET config = CAST(:c AS jsonb) "
            "WHERE workflow_id = :w AND step_key = :k "
            "  AND config->>'action_type' IS NULL"
        ),
        {"w": _COMPLIANCE, "k": _PRODUCER_STEP, "c": json.dumps(_PRODUCER_CONFIG)},
    ).rowcount

    inert = 0
    for step_key, original, why in _INERT:
        inert += conn.execute(
            sa.text(
                "UPDATE workflow_steps SET config = CAST(:c AS jsonb) "
                "WHERE workflow_id = :w AND step_key = :k "
                "  AND config->'_retired' IS NULL"
            ),
            {
                "w": _COMPLIANCE, "k": step_key,
                "c": json.dumps({
                    "action_type": "show_confirmation",
                    "message": "Retired step — see _retired. Does nothing.",
                    "_retired": {
                        "by": "r166 (IOD)",
                        "was": original,
                        "why": why,
                        "disposition": (
                            "DELETE once the run-step FK allows removal without "
                            "destroying history — 133 rows reference this."
                        ),
                    },
                }),
            },
        ).rowcount

    # Training Expiry: OFF because it is covered, not because it is unbuilt.
    # is_coming_soon is deliberately NOT set — see the module docstring.
    retired = conn.execute(
        sa.text(
            "UPDATE workflows SET is_active = false, description = :d "
            "WHERE id = :w AND is_active = true"
        ),
        {"w": _TRAINING, "d": _TRAINING_NEW_DESC},
    ).rowcount

    print(
        f"[r166] compliance producer wired: {producer}; steps made inert: {inert}; "
        f"training expiry retired as redundant: {retired}."
    )
    print(
        "[r166] The 'Compliance & records upkeep' cadence card is now TRUE — "
        "compliance data is synced by the workflow the card points at."
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE workflows SET is_active = true, description = :d WHERE id = :w"
        ),
        {"w": _TRAINING, "d": _TRAINING_WAS_DESC},
    )
    for step_key, original, _why in _INERT:
        conn.execute(
            sa.text(
                "UPDATE workflow_steps SET config = CAST(:c AS jsonb) "
                "WHERE workflow_id = :w AND step_key = :k"
            ),
            {"w": _COMPLIANCE, "k": step_key, "c": json.dumps(original)},
        )
    conn.execute(
        sa.text(
            "UPDATE workflow_steps SET config = CAST(:c AS jsonb) "
            "WHERE workflow_id = :w AND step_key = :k"
        ),
        {"w": _COMPLIANCE, "k": _PRODUCER_STEP, "c": json.dumps(_PRODUCER_WAS)},
    )
