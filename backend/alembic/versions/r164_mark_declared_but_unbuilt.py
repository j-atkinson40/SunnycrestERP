"""IOD — mark the eight declared-but-unbuilt workflows as placeholders, using the platform's own word for it.

r163 deleted one of the eight and kept seven on the grounds that they are
declarations rather than residue. That ruling was right and INCOMPLETE: the kept
seven stayed `is_coming_soon=False, is_active=True`, indistinguishable in every
surface from workflows that actually work. The declaration was preserved and not
made visible.

THE PLATFORM ALREADY HAS A WORD FOR THIS, AND THREE WORKFLOWS ALREADY CARRY IT.
`Workflow.is_coming_soon` is filtered at `workflow_engine.py:203` — *"placeholders
aren't runnable"* — and Obituary Draft Generation, Insurance Assignment and EDRS
Death Certificate Submission are already marked. They are the same category:
declared vertical capabilities that were never built. So this is applying an
established convention, not inventing a disposition.

⚠️ `is_coming_soon` ALONE DOES NOT STOP A CRON. THIS IS THE WHOLE REASON THE TWO
FLAGS DIFFER BELOW.
The scheduler's sweep query (`workflow_scheduler.py:250-263`) filters on
`is_active` and `schedule_retired_at`. It does NOT filter `is_coming_soon` —
that flag governs the tenant-facing CATALOG query, which is a different question
from what fires on a timer. Marking Auto-Delivery as a placeholder and stopping
there would have labelled it correctly and left it failing at 06:00 every morning.

    Auto-Delivery Eligibility Check   is_coming_soon=True  AND  is_active=False
    the other seven                   is_coming_soon=True

The seven are event- or manual-triggered and the scheduler dispatches only
`time_of_day` / `time_after_event` / `scheduled`, so they never fire and need no
second flag. Leaving them `is_active=True` keeps them present in the builder,
labelled, rather than disabled and gone — which is what "preserve the declaration"
meant.

⚠️ `schedule_retired_at` WAS CONSIDERED AND REJECTED for Auto-Delivery. It would
also stop the firing, but it means something specific: per r129 / Transfer T-1 it
marks a schedule ADOPTED by a MoC trigger, where the MoC entry is now the firing
authority. Stamping it here would assert an adoption that never happened, and the
next reader of Monthly Statement Run (genuinely adopted, `schedule_retired_at`
stamped 2026-07-17) would have no way to tell the two apart.

WHY MARK RATHER THAN DELETE — the ruling this reverses, and why
----------------------------------------------------------------
Auto-Delivery was ruled for deletion on the grounds that a daily red trains people
to ignore failed runs, which is the thing A-1 exists to make meaningful. That
reasoning holds; the deletion was the wrong instrument for it.

  * Marking stops the daily red just as effectively (`is_active=False`).
  * It preserves the declaration where the product already renders it, so the
    intent does not have to be exiled to a roadmap document.
  * **The deletion was not clean anyway.** Auto-Delivery has 8 runs and
    `workflow_runs.workflow_id` is `ON DELETE NO ACTION`, so deleting the row
    requires destroying its run history first — seven silent completions and the
    one honest failure A-1 produced. That history is the evidence of the silent
    period, and the argument for keeping it is the argument that kept the 12,365
    `categorize` run-steps in r160.
  * It is reversible. Deletion is not, and both remain available.

Social Service Certificate is not in this list because r163 deleted it, on a
distinction that still holds: it duplicated a WORKING capability rather than
declaring an absent one.

WHAT AUTO-DELIVERY ACTUALLY IS — measured, since "8 sunnycrest runs" looked like
activity worth protecting.
One step: `check_eligibility` → `system_job: auto_delivery_eligibility`,
unrecognised, so the workflow is a single no-op. `auto_delivery_eligibility`
appears in exactly ONE place in the repository — the workflow definition itself.
`legacy_delivery.run_auto_delivery` was checked and is a different domain (it
takes a `legacy_proof_id` — Legacy Print proof delivery, not vault scheduling).
The seven "completed" runs completed nothing; the eighth failed honestly post-A-1.

NO CODE EDIT. Unlike r163, the definitions stay in `default_workflows.py` — these
workflows continue to exist and to be declared. `seed_default_workflows` inserts
or updates and does not reset these flags on rows it already knows, so the marking
survives a boot.
"""
from alembic import op
import sqlalchemy as sa

revision = "r164_mark_declared_but_unbuilt"
down_revision = "r163_delete_ss_certificate_workflow"
branch_labels = None
depends_on = None

#: Fires on a cron, so it needs BOTH flags — see the docstring.
_DEACTIVATE = ["wf_sys_auto_delivery"]

#: Event- or manual-triggered; the scheduler never touches them. Marked only.
_MARK_ONLY = [
    "wf_sys_scribe_processing",
    "wf_tpl_fh_preneed_flag",
    "wf_sys_legacy_print_final",
    "wf_sys_legacy_print_proof",
    "wf_sys_plot_reservation",
    "wf_tpl_fh_send_info_form",
    "wf_sys_vault_order_fulfillment",
]


def upgrade() -> None:
    conn = op.get_bind()

    marked = conn.execute(
        sa.text(
            "UPDATE workflows SET is_coming_soon = true "
            "WHERE id = ANY(:ids) AND is_coming_soon = false"
        ),
        {"ids": _MARK_ONLY + _DEACTIVATE},
    ).rowcount

    # The flag that actually stops the 06:00 firing. Separate statement because
    # it is a separate claim: "not built" and "do not fire this" are different
    # facts, and only one of them is true of the other seven.
    stopped = conn.execute(
        sa.text(
            "UPDATE workflows SET is_active = false "
            "WHERE id = ANY(:ids) AND is_active = true"
        ),
        {"ids": _DEACTIVATE},
    ).rowcount

    print(
        f"[r164] marked {marked} workflow(s) is_coming_soon; deactivated {stopped} "
        f"cron-firing placeholder(s). Auto-Delivery stops failing at 06:00 daily; "
        f"its 8 runs of history are kept."
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE workflows SET is_active = true WHERE id = ANY(:ids)"),
        {"ids": _DEACTIVATE},
    )
    conn.execute(
        sa.text("UPDATE workflows SET is_coming_soon = false WHERE id = ANY(:ids)"),
        {"ids": _MARK_ONLY + _DEACTIVATE},
    )
