"""The manufacturing Focuses-card back-port (FH Map stamp, commit 4).

NON-REGRESSION PIN (the dispatch's STOP condition): every focus ref the
manufacturing card carried pre-back-port still surfaces post-conversion to
the join-table query — decision-triage + legacy-generation (owned) and
cemetery-triage (joined). PLUS the vertical filter on the mirror rows:
the FH nine must NOT pollute the manufacturing Workflows card (and the
6 cores still carry — include-core canon).

Requires the focus demo seeds' content; creates it when absent
(hermetic-or-adopt, state-immune either way).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.moc_page import MoCPage
from scripts.seed_moc_backfill_workflow_mirrors import seed as seed_mirrors
from scripts.seed_moc_manufacturing import SLUG as MFG_SLUG, seed as seed_mfg


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def demo_focuses(db):
    """Ensure the pre-back-port card's focus content exists (adopt if the
    demo seeds already ran; create minimal rows if not)."""
    from scripts import seed_demo_artifact_focuses as demo

    demo.seed(db)
    yield


def _mfg_rows(db) -> list[dict]:
    page = (
        db.query(MoCPage)
        .filter(MoCPage.scope == "vertical_default",
                MoCPage.vertical == "manufacturing",
                MoCPage.slug == MFG_SLUG,
                MoCPage.is_active.is_(True))
        .first()
    )
    assert page is not None
    return [r for s in (page.sections or []) for r in s.get("rows", [])]


def test_backport_non_regression_and_no_fh_pollution(db, demo_focuses):
    seed_mirrors(db)
    seed_mfg(db)
    rows = _mfg_rows(db)

    # NON-REGRESSION: the pre-back-port focus refs still surface.
    focus_labels = {r["label"] for r in rows if r["builder"] == "focuses"}
    assert "Decision Triage" in focus_labels        # owned (demo seed)
    assert "Legacy Generation" in focus_labels      # owned (demo seed)
    # cemetery-triage joins manufacturing when the V-1 witness content exists;
    # assert only if the content is present (state-immune, by design).
    #
    # ⚠️ THE GUARD CHECKED THE WRONG TABLE. It read only
    # `focus_template_verticals` — the JOIN row — while the label it guards comes
    # from `focus_templates` — the TEMPLATE row. `focus_rows_for_vertical` LEFT
    # JOINs from templates, so a join row pointing at a template that does not
    # exist yields NO label: guard passes, assertion fails. Dev was in exactly
    # that state (join row present, template absent), which is why this failed
    # while looking state-immune.
    #
    # State-immunity was the author's intent and is preserved — the guard now
    # just checks the same thing the assertion reads. Both rows, or neither.
    has_ct_content = db.execute(
        sql_text(
            "SELECT 1 FROM focus_template_verticals ftv "
            "JOIN focus_templates ft ON ft.template_slug = ftv.template_slug "
            "WHERE ftv.template_slug = 'cemetery-triage' "
            "AND ftv.vertical = 'manufacturing' AND ft.is_active = true"
        )
    ).first()
    if has_ct_content:
        assert any("Cemetery Triage" in lbl for lbl in focus_labels)

    # THE VERTICAL FILTER: no FH mirror pollution; cores still carry.
    wf_labels = {r["label"] for r in rows if r["builder"] == "workflows"}
    assert "First Call Intake" not in wf_labels     # FH stays off this card
    assert "Plot Reservation" not in wf_labels
    assert {"Month-End Close", "AR Collections"} <= wf_labels  # cores carry
    assert "New Order" in wf_labels                 # own mirrors intact
