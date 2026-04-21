"""Workflow Arc Phase 8d — regression gate for r38 scope backfill fix.

r36 misclassified 10 tier-1 vertical workflows as scope='core'.
r38 corrects them by ID. This test asserts the post-r38 invariant:

    tier = 1 AND vertical IS NOT NULL  IMPLIES  scope = 'vertical'

Any seed that adds a new tier-1 vertical-specific workflow going
forward must either (a) set scope='vertical' in the seed path OR
(b) ship a follow-up migration that promotes it. If neither happens,
this test fails loudly rather than letting the misclassification
leak into the three-tab workflow builder.

Also cross-checks the companion invariant:

    tier = 1 AND vertical IS NULL  IMPLIES  scope = 'core'

so that the "tightened" classification rule stays symmetric. Any
future r36-style blanket-backfill mistake is caught by one of the
two gates below.

A third smoke test confirms the 10 canonical IDs that r38 targeted
are present with scope='vertical' — guards against someone
re-running r36 after r38 and silently reverting the fix.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


# Mirrors the canonical list in
# alembic/versions/r38_fix_vertical_scope_backfill.py::MISCLASSIFIED_VERTICAL_WORKFLOWS.
# Any drift between the migration's target list and the gate below
# is itself a bug — keep both in sync in future phases.
EXPECTED_VERTICAL_WORKFLOW_IDS: frozenset[str] = frozenset({
    "wf_sys_legacy_print_proof",
    "wf_sys_legacy_print_final",
    "wf_sys_safety_program_gen",
    "wf_sys_vault_order_fulfillment",
    "wf_sys_document_review_reminder",
    "wf_sys_auto_delivery",
    "wf_sys_catalog_fetch",
    "wf_sys_ss_certificate",
    "wf_sys_scribe_processing",
    "wf_sys_plot_reservation",
})


class TestR38ScopeBackfillFix:
    def test_invariant_tier1_vertical_implies_vertical_scope(self, db_session):
        """The primary post-r38 invariant: any tier-1 workflow with a
        non-null `vertical` is scope='vertical', not scope='core'."""
        from app.models.workflow import Workflow

        offenders = (
            db_session.query(Workflow)
            .filter(
                Workflow.tier == 1,
                Workflow.vertical.isnot(None),
                Workflow.scope != "vertical",
            )
            .all()
        )
        if offenders:
            ids = sorted(w.id for w in offenders)
            pytest.fail(
                "tier=1 AND vertical IS NOT NULL workflows must have "
                "scope='vertical' (post-r38). Misclassified: "
                + ", ".join(ids)
                + ". Fix via a follow-up migration matching the r38 "
                "pattern, or set scope='vertical' in the seed."
            )

    def test_invariant_tier1_null_vertical_implies_core_scope(self, db_session):
        """Companion invariant for the other half of the classification
        rule: tier-1 with NULL vertical is cross-vertical core."""
        from app.models.workflow import Workflow

        offenders = (
            db_session.query(Workflow)
            .filter(
                Workflow.tier == 1,
                Workflow.vertical.is_(None),
                Workflow.scope != "core",
            )
            .all()
        )
        if offenders:
            ids = sorted(w.id for w in offenders)
            pytest.fail(
                "tier=1 AND vertical IS NULL workflows must have "
                "scope='core' (post-r38). Offenders: " + ", ".join(ids)
            )

    def test_canonical_misclassified_ids_now_vertical(self, db_session):
        """Smoke gate for the specific 10 IDs r38 corrected. Guards
        against accidental r36 re-runs or manual rescoping that
        silently reverts the fix."""
        from app.models.workflow import Workflow

        rows = (
            db_session.query(Workflow.id, Workflow.scope, Workflow.vertical)
            .filter(Workflow.id.in_(tuple(EXPECTED_VERTICAL_WORKFLOW_IDS)))
            .all()
        )
        # Build a dict for targeted error messages.
        actual = {row.id: (row.scope, row.vertical) for row in rows}
        missing = EXPECTED_VERTICAL_WORKFLOW_IDS - set(actual.keys())
        bad_scope = {
            wf_id: scope_vert
            for wf_id, scope_vert in actual.items()
            if scope_vert[0] != "vertical"
        }
        null_vertical = {
            wf_id: scope_vert
            for wf_id, scope_vert in actual.items()
            if scope_vert[1] is None
        }
        msg_parts = []
        if missing:
            msg_parts.append(
                f"r38-target workflows missing from DB: {sorted(missing)}"
            )
        if bad_scope:
            msg_parts.append(
                "r38-target workflows with non-'vertical' scope: "
                + ", ".join(
                    f"{wf}={scope}" for wf, (scope, _) in bad_scope.items()
                )
            )
        if null_vertical:
            msg_parts.append(
                "r38-target workflows with NULL vertical (invariant violation): "
                + ", ".join(null_vertical.keys())
            )
        if msg_parts:
            pytest.fail("; ".join(msg_parts))
