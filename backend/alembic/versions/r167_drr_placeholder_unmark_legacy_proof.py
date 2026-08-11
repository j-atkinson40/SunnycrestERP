"""IOD — Document Review Reminder is a placeholder; Legacy Print — Proof is NOT, and r164 said otherwise.

`source_service` turned out to be a CONVENTION — 17 of 36 workflows declare the
service their definition was meant to call — and checking those declarations
against the filesystem answered in seconds what this arc spent several passes
deriving. It also falsified one of r164's eight.

DOCUMENT REVIEW REMINDER — genuinely unbuilt
---------------------------------------------
Declares `document_review_service.py`. **The file does not exist.** `scan_documents`
is prose only, and the surviving `notify_admin` is a `send_notification` with no
producer behind it — it would notify about nothing. Same shape as Training Expiry's
`notify_admins`, and the same reason not to "just rename it".

`is_coming_soon = True` (declared, never built) **AND** `is_active = False`. Both,
because it is `scheduled` and fires: `is_coming_soon` governs the tenant catalog
query while the scheduler sweep filters `is_active` + `schedule_retired_at`.
Marking alone labels it correctly and leaves the cron running — the near-miss r164
caught, applied deliberately here rather than rediscovered.

⚠️ LEGACY PRINT — PROOF IS UNMARKED. r164 WAS WRONG ABOUT IT.
r164 marked eight workflows `is_coming_soon`, which asserts "declared, never
built." For this one, **both declared capabilities exist**:

    generate_proof    → _legacy_generate_proof, registered in HEADLESS_DISPATCH
                        under focus_id "legacy_proof_generation"
    send_proof_email  → legacy_email_service.send_proof_email

That makes it UNWIRED work, not unbuilt work — the exact distinction r166 turned
on when it refused `is_coming_soon` for Training Expiry, made wrongly one
migration later in the other direction. A marked-but-actually-built workflow
misleads the next reader precisely as much as an unmarked-but-unbuilt one.

⚠️ IT IS UNMARKED BUT NOT WIRED, AND THE REASON IS THAT THE TWO CAPABILITIES DO
NOT COMPOSE.
Wiring was attempted and stopped at a real gap rather than a missing template:

  1. **The generation step does not persist a proof.** `_legacy_generate_proof`
     is deliberately pure — its docstring says *"no R2, no persisted instance, no
     schema"* and names the missing piece itself: *"Refinements (NOT 3b.1): …
     persisting the proof to a Document so 3d's email step can attach it."*
  2. **The email step requires a persisted row.** `send_proof_email(db,
     company_id, legacy_proof_id, …)` loads a `LegacyProof` by id and raises if
     absent. Step 1 produces metadata; step 2 needs an id step 1 never creates.
  3. **Its trigger does not exist.** `trigger_type="event"`,
     `trigger_config={"event": "legacy_order.submitted"}` — and there is no event
     subscription registry or publish hook in the platform (the same gap Phase 8c
     worked around by switching Expense Categorization to a cron). Zero runs is a
     consequence, not a coincidence.

So the honest state is declared-and-unwired, which is what removing the flag says.
Wiring it needs the persistence refinement its own author already identified, plus
an event system. Both are builds.

LEGACY PRINT — FINAL STAYS MARKED. `finalize_artwork` has no verified capability;
`send_to_production` carries a `notify_roles` param that suggests a notification
shape but proves nothing. Claiming either way without checking is the error this
migration exists to correct, in one direction or the other.

⚠️ FILENAME EXISTENCE IS NOT CAPABILITY EXISTENCE — the caveat that kept the other
six of r164's eight correct. `cemetery_service.py` and `sales_service.py` both
EXIST and contain none of their declared capability: zero `plot`/`reserv`/`deed`
occurrences in the former, and the single `fulfil` hit in the latter is inside a
comment string. `source_service` is a shortcut to the right QUESTION, not to the
answer.
"""
from alembic import op
import sqlalchemy as sa

revision = "r167_drr_placeholder_unmark_legacy_proof"
down_revision = "r166_wire_compliance_sync_retire_training_expiry"
branch_labels = None
depends_on = None

_DRR = "wf_sys_document_review_reminder"
_LEGACY_PROOF = "wf_sys_legacy_print_proof"

#: Read off the definition, not reconstructed — a downgrade to an invented
#: description is not a reverse.
_DRR_WAS_DESC = "Flags written programs not reviewed in 11 months and notifies admin."
_DRR_NEW_DESC = (
    "NOT BUILT (r167) — declares source_service document_review_service.py, "
    "which does not exist. scan_documents is a prose-only step and notify_admin "
    "would notify about nothing. Deactivated so it stops failing on its weekly "
    "cron. Original: " + _DRR_WAS_DESC
)

_LEGACY_NEW_DESC = (
    "UNWIRED, NOT UNBUILT (r167) — corrects r164, which marked this "
    "is_coming_soon. Both capabilities exist: _legacy_generate_proof "
    "(HEADLESS_DISPATCH, focus_id 'legacy_proof_generation') and "
    "legacy_email_service.send_proof_email. They do not compose yet — the "
    "generation is deliberately pure and persists no LegacyProof, while the "
    "email step loads one by id. Its 'legacy_order.submitted' trigger also has "
    "no event system. Wiring needs both builds. "
    "Generate print proof, email to funeral home for approval."
)


def upgrade() -> None:
    conn = op.get_bind()

    # DRR: BOTH flags. is_coming_soon labels it; is_active stops the cron. See
    # the docstring — one without the other is a fix that changes nothing.
    drr = conn.execute(
        sa.text(
            "UPDATE workflows SET is_coming_soon = true, is_active = false, "
            "description = :d WHERE id = :w AND is_active = true"
        ),
        {"w": _DRR, "d": _DRR_NEW_DESC},
    ).rowcount

    # Legacy Print — Proof: unmark ONLY. Left active and declared, which is what
    # "unwired" means. It cannot fire (no event system), so unmarking restores
    # visibility without restoring a failure.
    legacy = conn.execute(
        sa.text(
            "UPDATE workflows SET is_coming_soon = false, description = :d "
            "WHERE id = :w AND is_coming_soon = true"
        ),
        {"w": _LEGACY_PROOF, "d": _LEGACY_NEW_DESC},
    ).rowcount

    print(f"[r167] DRR marked + deactivated: {drr}; legacy proof unmarked: {legacy}")
    print(
        "[r167] r164 asserted 'declared, never built' for Legacy Print — Proof. "
        "Both its capabilities exist; it is unwired. Corrected."
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE workflows SET is_coming_soon = true, "
            "description = 'Generate print proof, email to funeral home for approval.' "
            "WHERE id = :w"
        ),
        {"w": _LEGACY_PROOF},
    )
    conn.execute(
        sa.text(
            "UPDATE workflows SET is_coming_soon = false, is_active = true, "
            "description = :d WHERE id = :w"
        ),
        {"w": _DRR, "d": _DRR_WAS_DESC},
    )
