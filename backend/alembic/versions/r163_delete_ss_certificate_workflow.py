"""IOD — delete the Social Service Certificate workflow. Definition and rows, together.

ONE of the eight never-run unbuilt workflows. The other seven stay, and the reason
they stay is the finding this migration came out of.

⚠️ THESE EIGHT ARE NOT ORPHANS. THEY ARE DECLARATIONS.
r160, r161 and r162 all removed RESIDUE — step rows that outlived a superseded
definition, with no code behind them. That is not what these are. All eight are
defined in `app/data/default_workflows.py`, are tier 1–3 `scope=vertical`, and
appear in the workflow builder's Vertical tab. A tier-1 vertical workflow with no
implementation is the roadmap written where the builder shows it. Deleting one
erases the intent, not the leftovers.

Seven of the eight declare capabilities that are genuinely absent and genuinely
wanted — Legacy Print Proof/Final are Personalization Studio, Arrangement Scribe
is the FH vertical's headline feature, Vault Order Fulfillment is core
manufacturing. They cost nothing at runtime: zero runs, event- or manual-
triggered, and since WE-1 A-1 they fail loudly rather than silently if invoked.
**They stay.**

Social Service Certificate is the exception, and the distinction is narrow:
**it is the only one of the eight that duplicates a WORKING capability rather than
declaring an absent one.** `social_service_certificate_service.py` implements
generate → approve → send_to_funeral_home, and `ss_cert_triage` is the surface an
operator actually uses. The workflow row is a second, broken declaration of
something that already works — so it misleads rather than records intent.

WHY THE CODE EDIT SHIPS WITH THE MIGRATION
------------------------------------------
`seed_default_workflows` runs on every boot and INSERTS OR UPDATES; it never
deletes. So a migration alone would be undone by the next deploy — the row would
come straight back. The definition removal is what makes the deletion stick; the
migration is what clears the rows that already exist. Neither works alone.

This is the difference from r160–r162, which needed no code edit precisely because
their targets had no definition left to remove.

DELETION SAFETY — derived from `pg_constraint`, then measured
--------------------------------------------------------------
Thirteen FKs reference `workflows`. Four are `NO ACTION` and would block a delete;
all four are empty for this workflow:

    workflow_runs         0     (never invoked, platform-wide, ever)
    workflow_enrollments  0
    workflow_schedules    0
    saved_orders          0

Two cascade and go with it: `workflow_steps` (3 rows: `generate_cert`,
`store_cert`, `email_cert` — all carrying unrecognised action types) and
`workflow_step_params`. The remaining seven are `SET NULL` and hold no rows for
this id.

**No cadence card points at it.** `moc_job_ref` carries ZERO `automation` refs
with `ref_key = 'wf_sys_ss_certificate'` — checked for all eight, and none of them
is referenced by any card. So this deletion empties no Map surface. (That check
matters: deleting a workflow a card DOES reference is the Compliance Sync problem,
where removing the machinery leaves a card teaching a rhythm with nothing behind
it. Not the case here.)

The delete is guarded by `NOT EXISTS` on all four blocking tables at APPLY time
rather than trusting the counts above — they were true when taken, and this runs
later.
"""
from alembic import op
import sqlalchemy as sa

revision = "r163_delete_ss_certificate_workflow"
down_revision = "r162_finish_the_migrated_four"
branch_labels = None
depends_on = None

_WORKFLOW_ID = "wf_sys_ss_certificate"

#: Restored verbatim by `downgrade`, matching the definition removed from
#: `default_workflows.py` in the same commit.
_WORKFLOW = {
    "name": "Social Service Certificate",
    "description": "Generates, approves, and emails social service certificates.",
    "tier": 1,
    "scope": "vertical",
    "vertical": "manufacturing",
    "trigger_type": "manual",
}
_STEPS = [
    (1, "generate_cert", "action",
     '{"action_type": "system_job", "job": "generate_ss_certificate"}'),
    (2, "store_cert", "action",
     '{"action_type": "store_document", "document_type": "ss_certificate"}'),
    (3, "email_cert", "action",
     '{"action_type": "system_job", "job": "email_ss_certificate"}'),
]


def upgrade() -> None:
    conn = op.get_bind()

    blockers = {
        t: conn.execute(
            sa.text(f"SELECT count(*) FROM {t} WHERE workflow_id = :w"),
            {"w": _WORKFLOW_ID},
        ).scalar()
        for t in ("workflow_runs", "workflow_enrollments", "workflow_schedules", "saved_orders")
    }
    if any(blockers.values()):
        # Deliberately NOT a hard failure: if this workflow acquired a run or an
        # enrollment since this was written, that is new information — someone
        # invoked it — and the right response is to leave it and say so, not to
        # destroy history or to abort an otherwise-fine upgrade.
        print(
            f"[r163] SKIPPED — {_WORKFLOW_ID} now has references: "
            f"{ {k: v for k, v in blockers.items() if v} }. It was invoked since "
            f"this migration was written, which changes the disposition. Nothing "
            f"deleted; re-triage before retrying."
        )
        return

    steps = conn.execute(
        sa.text("DELETE FROM workflow_steps WHERE workflow_id = :w"), {"w": _WORKFLOW_ID}
    ).rowcount
    params = conn.execute(
        sa.text("DELETE FROM workflow_step_params WHERE workflow_id = :w"), {"w": _WORKFLOW_ID}
    ).rowcount
    rows = conn.execute(
        sa.text("DELETE FROM workflows WHERE id = :w"), {"w": _WORKFLOW_ID}
    ).rowcount

    print(
        f"[r163] deleted {rows} workflow, {steps} steps, {params} params. "
        f"The definition was removed from default_workflows.py in the same "
        f"commit — without that, the next boot would recreate this row."
    )


def downgrade() -> None:
    # A true reverse restores BOTH halves, but only this one is in scope here:
    # reverting the code edit is a git operation, not a migration. Restoring the
    # rows without restoring the definition leaves a state the seeder will not
    # maintain — which is exactly the orphan condition r160–r162 cleaned up, so
    # a downgrade should be paired with reverting the commit.
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO workflows (id, name, description, tier, scope, vertical, trigger_type) "
            "SELECT :w, :n, :d, :t, :s, :v, :tr "
            "WHERE NOT EXISTS (SELECT 1 FROM workflows WHERE id = :w)"
        ),
        {
            "w": _WORKFLOW_ID, "n": _WORKFLOW["name"], "d": _WORKFLOW["description"],
            "t": _WORKFLOW["tier"], "s": _WORKFLOW["scope"], "v": _WORKFLOW["vertical"],
            "tr": _WORKFLOW["trigger_type"],
        },
    )
    for order, key, step_type, cfg in _STEPS:
        conn.execute(
            sa.text(
                "INSERT INTO workflow_steps (id, workflow_id, step_order, step_key, step_type, config, is_core) "
                "SELECT gen_random_uuid()::text, :w, :o, :k, :t, CAST(:c AS jsonb), true "
                "WHERE NOT EXISTS (SELECT 1 FROM workflow_steps "
                "                  WHERE workflow_id = :w AND step_key = :k)"
            ),
            {"w": _WORKFLOW_ID, "o": order, "k": key, "t": step_type, "c": cfg},
        )
