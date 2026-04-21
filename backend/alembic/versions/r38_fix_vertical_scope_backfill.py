"""Workflow Arc Phase 8d — fix r36 scope backfill for vertical
tier-1 workflows.

r36 shipped a CASE expression that assigned scope='core' to every
workflow with tier=1, without consulting the `vertical` column:

    WHEN tier = 1 THEN 'core'
    WHEN tier IN (2, 3) THEN 'vertical'
    WHEN tier = 4 OR company_id IS NOT NULL THEN 'tenant'

The audit surfaced 10 workflow rows that have tier=1 AND
vertical IS NOT NULL — they are system-shipped platform defaults,
but they're vertical-specific (only applicable to FH tenants OR
only applicable to manufacturing tenants). Those rows belong in
scope='vertical', not scope='core', so the three-tab workflow
builder's Vertical tab surfaces them to the right tenants and the
Core tab doesn't show them to tenants that don't have the vertical.

The correct classification rule:
    tier = 1 AND vertical IS NULL  →  scope = 'core'      (cross-vertical)
    tier = 1 AND vertical NOT NULL →  scope = 'vertical'  (this fix)
    tier IN (2, 3)                 →  scope = 'vertical'
    tier = 4 OR company_id NOT NULL→  scope = 'tenant'

Idempotent: updates rows where id is in the known-misclassified
set AND scope='core'. Safe to re-run after any scope correction,
and safe to run on fresh databases where r36 never misclassified
(no rows match the WHERE predicate, zero updates).

Affected workflows (surfaced by auditing tier=1 rows with non-null
`vertical` in app/data/default_workflows.py):

    Manufacturing:
    - wf_sys_legacy_print_proof
    - wf_sys_legacy_print_final
    - wf_sys_safety_program_gen
    - wf_sys_vault_order_fulfillment
    - wf_sys_document_review_reminder
    - wf_sys_auto_delivery
    - wf_sys_catalog_fetch
    - wf_sys_ss_certificate

    Funeral Home:
    - wf_sys_scribe_processing
    - wf_sys_plot_reservation

Invariant enforced going forward by tests/test_r38_scope_backfill_fix.py
(regression gate: tier=1 AND vertical IS NOT NULL IMPLIES
scope='vertical') — any future seed that adds a tier-1 vertical
workflow without setting scope='vertical' in its seed or via a
follow-up migration fails the test.

Revision ID: r38_fix_vertical_scope_backfill
Down Revision: r37_approval_gate_email_template
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "r38_fix_vertical_scope_backfill"
down_revision = "r37_approval_gate_email_template"
branch_labels = None
depends_on = None


# Canonical list of workflow IDs the r36 backfill misclassified as
# 'core' when they should have been 'vertical'. Derived from a
# one-time audit of app/data/default_workflows.py for rows with
# tier=1 AND vertical IS NOT NULL. If a future seed adds another
# such workflow, the regression test (test_r38_scope_backfill_fix.py)
# fails until a new migration brings scope into alignment.
MISCLASSIFIED_VERTICAL_WORKFLOWS: tuple[str, ...] = (
    # Manufacturing
    "wf_sys_legacy_print_proof",
    "wf_sys_legacy_print_final",
    "wf_sys_safety_program_gen",
    "wf_sys_vault_order_fulfillment",
    "wf_sys_document_review_reminder",
    "wf_sys_auto_delivery",
    "wf_sys_catalog_fetch",
    "wf_sys_ss_certificate",
    # Funeral Home
    "wf_sys_scribe_processing",
    "wf_sys_plot_reservation",
)


def upgrade() -> None:
    # Idempotent: scope-corrects only rows that still hold the
    # incorrect 'core' value. Re-running the migration after a
    # partial success (or after an admin has already hand-corrected
    # some rows) is a no-op for the corrected subset.
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE workflows
            SET scope = 'vertical'
            WHERE id = ANY(:ids)
              AND scope = 'core'
              AND vertical IS NOT NULL;
            """
        ),
        {"ids": list(MISCLASSIFIED_VERTICAL_WORKFLOWS)},
    )


def downgrade() -> None:
    # Revert to the r36 misclassification. Only touches the same
    # known set so a downgrade doesn't sweep vertical workflows
    # seeded correctly post-r38.
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE workflows
            SET scope = 'core'
            WHERE id = ANY(:ids)
              AND scope = 'vertical'
              AND vertical IS NOT NULL;
            """
        ),
        {"ids": list(MISCLASSIFIED_VERTICAL_WORKFLOWS)},
    )
