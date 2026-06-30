"""MoC workflow backfill (Build 1+1b) — faithful runtime→canvas mirrors.

Assembly tests (load-bearing, the JCF-1 bar): a runtime workflow ROUND-TRIPS to a
faithful, VALID template (node count = step count, config carried, provenance set)
that the resolver surfaces; the thin task is pre-wired (its workflow cell resolves
the mirror pill); the whole set (all 18) validates; idempotent.
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
    _MANUFACTURING,
    seed,
)


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    names = [t[0] for t in TARGETS]
    s.execute(
        sql_text(
            "DELETE FROM moc_task_catalog WHERE vertical = 'manufacturing' "
            "AND name = ANY(:n)"
        ),
        {"n": names},
    )
    s.execute(
        sql_text(
            "DELETE FROM workflow_templates WHERE mirrored_from_workflow_id IS NOT NULL"
        )
    )
    s.commit()
    s.close()


def test_set_is_exactly_18():
    assert len(_MANUFACTURING) == 12
    assert len(_CORE) == 6
    assert len(TARGETS) == 18


def test_all_18_mirrors_valid_and_faithful(db):
    seed(db)
    mirrors = db.execute(
        sql_text(
            "SELECT id, display_name, canvas_state, mirrored_from_workflow_id "
            "FROM workflow_templates WHERE mirrored_from_workflow_id IS NOT NULL"
        )
    ).fetchall()
    assert len(mirrors) == 18

    # The whole set validates (a single bad mirror would fail on publish).
    for m in mirrors:
        cs = m.canvas_state if isinstance(m.canvas_state, dict) else json.loads(m.canvas_state)
        validate_canvas_state(cs)  # raises on invalid
        assert m.mirrored_from_workflow_id  # provenance recorded

    # Faithful: a mirror's node count == its runtime workflow's step count.
    no = next(m for m in mirrors if m.display_name == "New Order")
    cs = no.canvas_state if isinstance(no.canvas_state, dict) else json.loads(no.canvas_state)
    nsteps = db.execute(
        sql_text("SELECT COUNT(*) FROM workflow_steps WHERE workflow_id = :w"),
        {"w": no.mirrored_from_workflow_id},
    ).scalar()
    assert len(cs["nodes"]) == nsteps  # node-per-step
    assert len(cs["edges"]) == max(0, nsteps - 1)  # consecutive linear edges
    assert any(n["config"] for n in cs["nodes"])  # config carried verbatim


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


def test_idempotent_no_dups(db):
    seed(db)
    seed(db)  # re-run (runs on every deploy)
    n_templates = db.execute(
        sql_text(
            "SELECT COUNT(*) FROM workflow_templates WHERE mirrored_from_workflow_id IS NOT NULL"
        )
    ).scalar()
    assert n_templates == 18  # no duplicate templates
    n_tasks = db.execute(
        sql_text(
            "SELECT COUNT(*) FROM moc_task_catalog WHERE vertical = 'manufacturing' "
            "AND name = ANY(:n)"
        ),
        {"n": [t[0] for t in TARGETS]},
    ).scalar()
    assert n_tasks == 18  # no duplicate tasks


def test_core_mirrors_are_platform_scope_but_surface_on_mfg_card(db):
    seed(db)
    # The 6 core mirrors are platform_default/None-vertical; they reach the
    # manufacturing card via explicit ref (resolver reads by id).
    core = db.execute(
        sql_text(
            "SELECT scope, vertical FROM workflow_templates "
            "WHERE mirrored_from_workflow_id IS NOT NULL AND display_name = 'Month-End Close'"
        )
    ).first()
    assert core.scope == "platform_default"
    assert core.vertical is None
