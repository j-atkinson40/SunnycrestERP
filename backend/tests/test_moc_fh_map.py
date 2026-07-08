"""The Funeral Home map seed (FH Map stamp, commit 3).

Pins: the page creates at (vertical_default, funeral_home, funeral-home-map)
with the four cards' refs query-built (FH mirrors + core mirrors on
Workflows — the include-core canon carrying to a SECOND vertical; the
Focuses card from the JOIN TABLE — Cemetery Triage surfaces because its
funeral_home join row exists, the V-1 log-skip made real); idempotent
(sections refresh, operator renames preserved); the join-query helper
returns both OWNED (vertical=fh) and JOINED (multi-vertical) lineages.

State-immunity: assertions fixture-scoped where fixtures exist; the seed
itself is content-agnostic so page-shape assertions key on stable slugs.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.focus_template import FocusTemplate
from app.models.focus_template_vertical import FocusTemplateVertical
from app.models.moc_page import MoCPage
from scripts.seed_moc_backfill_workflow_mirrors import seed as seed_mirrors
from scripts.seed_moc_funeral_home import (
    SLUG,
    focus_rows_for_vertical,
    seed as seed_fh_map,
)


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _page(db) -> MoCPage | None:
    return (
        db.query(MoCPage)
        .filter(MoCPage.scope == "vertical_default",
                MoCPage.vertical == "funeral_home",
                MoCPage.slug == SLUG,
                MoCPage.is_active.is_(True))
        .first()
    )


def _rows(page: MoCPage) -> list[dict]:
    return [r for s in (page.sections or []) for r in s.get("rows", [])]


def test_fh_map_seeds_with_all_four_cards(db):
    seed_mirrors(db)
    seed_fh_map(db)
    page = _page(db)
    assert page is not None
    rows = _rows(page)
    by_builder: dict[str, list[dict]] = {}
    for r in rows:
        by_builder.setdefault(r["builder"], []).append(r)

    # WORKFLOWS: the 9 FH mirrors + the 6 core mirrors (include-core canon
    # carrying to a second vertical — the STOP condition's negative).
    wf_labels = {r["label"] for r in by_builder.get("workflows", [])}
    assert {"First Call Intake", "Plot Reservation",
            "Arrangement Scribe Processing"} <= wf_labels     # FH mirrors
    assert {"Month-End Close", "AR Collections"} <= wf_labels  # cores carry
    assert len(by_builder.get("workflows", [])) >= 15

    # FOCUSES: query-built from the join table — Cemetery Triage's
    # funeral_home join row makes the V-1 log-skip real.
    focus_labels = {r["label"] for r in by_builder.get("focuses", [])}
    assert any("Cemetery Triage" in lbl for lbl in focus_labels)

    # DOCUMENTS + WIDGETS: the honest single refs (when present on this DB).
    assert len(by_builder.get("documents", [])) <= 1
    assert len(by_builder.get("widgets", [])) <= 1


def test_fh_map_idempotent_and_rename_preserved(db):
    seed_mirrors(db)
    seed_fh_map(db)
    page = _page(db)
    # Operator renames the map…
    page.title = "Hopkins Ops"
    db.add(page)
    db.commit()
    # …and a deploy re-run refreshes sections WITHOUT clobbering the rename.
    seed_fh_map(db)
    db.expire_all()
    pages = (
        db.query(MoCPage)
        .filter(MoCPage.scope == "vertical_default",
                MoCPage.vertical == "funeral_home",
                MoCPage.slug == SLUG,
                MoCPage.is_active.is_(True))
        .all()
    )
    assert len(pages) == 1                    # no duplicate page
    assert pages[0].title == "Hopkins Ops"    # rename preserved (H-2 pattern)
    assert len(_rows(pages[0])) >= 15         # sections refreshed
    # restore
    pages[0].title = "Funeral Home"
    db.add(pages[0])
    db.commit()


def test_focus_rows_query_returns_owned_and_joined(db):
    """The join-query helper: an OWNED (vertical=funeral_home) template and a
    JOINED (home elsewhere, funeral_home join row) lineage both surface."""
    suffix = uuid.uuid4().hex[:8]
    core_id = str(uuid.uuid4())
    db.execute(
        sql_text(
            "INSERT INTO focus_cores (id, core_slug, display_name, "
            "registered_component_kind, registered_component_name) "
            "VALUES (:id, :slug, 'FH Map Core', 'focus-core', "
            "'SchedulingKanbanCore')"
        ),
        {"id": core_id, "slug": f"fhmap-core-{suffix}"},
    )
    owned_id, joined_id = str(uuid.uuid4()), str(uuid.uuid4())
    for tid, slug, vert in (
        (owned_id, f"fhmap-owned-{suffix}", "funeral_home"),
        (joined_id, f"fhmap-joined-{suffix}", "manufacturing"),
    ):
        db.execute(
            sql_text(
                "INSERT INTO focus_templates (id, scope, template_slug, "
                "display_name, inherits_from_core_id, "
                "inherits_from_core_version, vertical, is_active) VALUES "
                "(:id, 'vertical_default', :slug, :dn, :c, 1, :v, true)"
            ),
            {"id": tid, "slug": slug, "dn": slug, "c": core_id, "v": vert},
        )
    db.add(FocusTemplateVertical(
        template_slug=f"fhmap-joined-{suffix}", vertical="funeral_home"
    ))
    db.flush()
    try:
        ids = {r["artifact_id"] for r in focus_rows_for_vertical(db, "funeral_home")}
        assert owned_id in ids       # owned by the vertical
        assert joined_id in ids      # joined via the multi-vertical table
        mfg_ids = {r["artifact_id"] for r in focus_rows_for_vertical(db, "manufacturing")}
        assert joined_id in mfg_ids  # home vertical still sees it
        assert owned_id not in mfg_ids
    finally:
        db.rollback()
