"""MoC workflow backfill (Build 1+1b; FH stamp) — faithful runtime→canvas mirrors.

Assembly tests (load-bearing, the JCF-1 bar): a runtime workflow ROUND-TRIPS to a
faithful, VALID template (node count = step count, config carried, provenance set)
that the resolver surfaces; the thin task is pre-wired (its workflow cell resolves
the mirror pill); the whole set (27 = 12 manufacturing + 9 funeral_home + 6 core)
validates; idempotent. The FH nine ride the SAME parameterized transform —
`task_vertical` lands each thin task on its own vertical's map.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.services.maps_of_content.task_catalog import resolve_task_catalog
from app.services.workflow_templates.canvas_validator import validate_canvas_state

from scripts.seed_moc_backfill_workflow_mirrors import (
    TARGETS,
    _CORE,
    _FUNERAL_HOME,
    _MANUFACTURING,
    seed,
)

TOTAL = 28  # Ponder P0: +mirror_cash_receipts_matching  # 12 mfg + 9 fh + 6 core


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    names = [t[0] for t in TARGETS]
    s.execute(
        sql_text(
            "DELETE FROM moc_task_catalog WHERE vertical IN "
            "('manufacturing', 'funeral_home') AND name = ANY(:n)"
        ),
        {"n": names},
    )
    s.execute(
        sql_text(
            "DELETE FROM workflow_templates WHERE mirrored_from_workflow_id IS NOT NULL"
        )
    )
    # RESTORE THE FLEET (P2): the delete above is hermetic on a fresh CI DB
    # but on dev it nukes the STANDING 28-mirror fleet (the documented
    # global-wipe incident — the accounting map went "no longer available"
    # mid-witness). Re-seed so the teardown's end state IS the standing
    # fleet; the backfill is preserve-aware + idempotent.
    seed(s)
    s.commit()
    s.close()


def test_set_is_exactly_27():
    assert len(_MANUFACTURING) == 12
    assert len(_FUNERAL_HOME) == 9      # the triaged bring-in set; shells excluded
    assert len(_CORE) == 7  # +Cash Receipts Matching (Ponder P0 — the audit's B-1 gap)
    assert len(TARGETS) == TOTAL


def test_all_27_mirrors_valid_and_faithful(db):
    seed(db)
    mirrors = db.execute(
        sql_text(
            "SELECT id, display_name, canvas_state, mirrored_from_workflow_id "
            "FROM workflow_templates WHERE mirrored_from_workflow_id IS NOT NULL"
        )
    ).fetchall()
    assert len(mirrors) == TOTAL

    # The whole set validates (a single bad mirror would fail on publish).
    for m in mirrors:
        cs = m.canvas_state if isinstance(m.canvas_state, dict) else json.loads(m.canvas_state)
        validate_canvas_state(cs)  # raises on invalid
        assert m.mirrored_from_workflow_id  # provenance recorded

    # Faithful, one exemplar per vertical: node count == runtime step count.
    for exemplar in ("New Order", "First Call Intake"):
        row = next(m for m in mirrors if m.display_name == exemplar)
        cs = row.canvas_state if isinstance(row.canvas_state, dict) else json.loads(row.canvas_state)
        nsteps = db.execute(
            sql_text("SELECT COUNT(*) FROM workflow_steps WHERE workflow_id = :w"),
            {"w": row.mirrored_from_workflow_id},
        ).scalar()
        assert len(cs["nodes"]) == nsteps  # node-per-step
        assert len(cs["edges"]) == max(0, nsteps - 1)  # consecutive linear edges
        assert any(n["config"] for n in cs["nodes"])  # config carried verbatim


def test_fh_mirrors_are_fh_vertical_scope(db):
    seed(db)
    rows = db.execute(
        sql_text(
            "SELECT display_name, scope, vertical FROM workflow_templates "
            "WHERE mirrored_from_workflow_id IS NOT NULL "
            "AND display_name = ANY(:n)"
        ),
        {"n": _FUNERAL_HOME},
    ).fetchall()
    assert len(rows) == 9
    assert all(r.scope == "vertical_default" and r.vertical == "funeral_home"
               for r in rows)


def test_thin_task_wired_resolves_the_mirror_pill(db):
    seed(db)
    by = {t["name"]: t for t in resolve_task_catalog(db, vertical="manufacturing")}
    no = by.get("New Order")
    assert no is not None
    # The auto-populate keystone, for a mirror: the workflow cell resolves.
    assert no["workflow"] and no["workflow"]["available"]
    assert no["workflow"]["label"] == "New Order"
    # Thin: descriptive cells blank (em-dash in the UI).
    assert no["frequency"] is None and no["task_type"] is None


def test_fh_thin_tasks_land_on_the_fh_map(db):
    seed(db)
    by = {t["name"]: t for t in resolve_task_catalog(db, vertical="funeral_home")}
    fc = by.get("First Call Intake")
    assert fc is not None                                # task_vertical honored
    assert fc["workflow"] and fc["workflow"]["available"]
    assert fc["workflow"]["label"] == "First Call Intake"
    assert fc["frequency"] is None and fc["task_type"] is None
    # And NOT cross-wired onto the manufacturing table.
    mfg = {t["name"] for t in resolve_task_catalog(db, vertical="manufacturing")}
    assert "First Call Intake" not in mfg


def test_idempotent_no_dups(db):
    seed(db)
    seed(db)  # re-run (runs on every deploy)
    n_templates = db.execute(
        sql_text(
            "SELECT COUNT(*) FROM workflow_templates WHERE mirrored_from_workflow_id IS NOT NULL"
        )
    ).scalar()
    assert n_templates == TOTAL  # no duplicate templates
    n_tasks = db.execute(
        sql_text(
            "SELECT COUNT(*) FROM moc_task_catalog WHERE vertical IN "
            "('manufacturing', 'funeral_home') AND name = ANY(:n)"
        ),
        {"n": [t[0] for t in TARGETS]},
    ).scalar()
    assert n_tasks == TOTAL  # no duplicate tasks


def test_core_mirrors_are_platform_scope_but_surface_on_mfg_card(db):
    seed(db)
    # The 6 core mirrors are platform_default/None-vertical; they reach each
    # vertical's card via explicit ref (resolver reads by id).
    core = db.execute(
        sql_text(
            "SELECT scope, vertical FROM workflow_templates "
            "WHERE mirrored_from_workflow_id IS NOT NULL AND display_name = 'Month-End Close'"
        )
    ).first()
    assert core.scope == "platform_default"
    assert core.vertical is None
