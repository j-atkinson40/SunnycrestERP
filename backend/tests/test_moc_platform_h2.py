"""MoC Hierarchy H-2 — the platform MoC (the tier existed; this authors into it).

Claims:
  1. The seed authors the platform_default page idempotently (find-or-create;
     sections refreshed; operator title edits survive re-seeds), and
     `resolve_for_context(vertical=None)` — the login landing's read — serves it.
  2. SCOPE COHERENCE on create_task: platform_default + vertical → rejected;
     platform_default + None → a vertical-less row; a vertical scope without a
     vertical → rejected.
  3. The platform task read: resolve_task_catalog(scope="platform_default",
     vertical=None) returns platform rows (and NOT vertical rows) — the
     platform page's table.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.services.maps_of_content.service import resolve_for_context
from app.services.maps_of_content.task_catalog import (
    TaskValidationError,
    create_task,
    resolve_task_catalog,
)
from scripts import seed_moc_platform as seed_mod


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def test_seed_is_idempotent_and_the_root_resolve_serves_it(db):
    r1 = seed_mod.seed(db)
    r2 = seed_mod.seed(db)
    assert r2["page_id"] == r1["page_id"]          # find-or-create, not duplicate
    assert r2["created"] is False

    page = resolve_for_context(db, vertical=None, tenant_id=None)
    assert page is not None
    assert page.scope == "platform_default"
    assert page.id == r1["page_id"]

    # operator renames survive a re-seed (only sections refresh)
    db.execute(sql_text("UPDATE moc_pages SET title = 'Renamed' WHERE id = :p"),
               {"p": r1["page_id"]})
    db.commit()
    seed_mod.seed(db)
    title = db.execute(sql_text("SELECT title FROM moc_pages WHERE id = :p"),
                       {"p": r1["page_id"]}).fetchone()[0]
    assert title == "Renamed"


def test_create_task_scope_coherence(db):
    suffix = uuid.uuid4().hex[:8]
    # platform + vertical → incoherent, rejected
    with pytest.raises(TaskValidationError):
        create_task(db, vertical="manufacturing", name=f"P bad {suffix}",
                    scope="platform_default")
    # a vertical scope without a vertical → rejected
    with pytest.raises(TaskValidationError):
        create_task(db, vertical=None, name=f"V bad {suffix}",
                    scope="vertical_default")
    # platform + None → a vertical-less row
    task = create_task(db, vertical=None, name=f"Platform Task {suffix}",
                       scope="platform_default")
    db.commit()
    try:
        assert task.scope == "platform_default"
        assert task.vertical is None
        # the platform read returns it; the manufacturing read does NOT
        plat = resolve_task_catalog(db, vertical=None, scope="platform_default")
        assert any(t["id"] == task.id for t in plat)
        mfg = resolve_task_catalog(db, vertical="manufacturing")
        assert not any(t["id"] == task.id for t in mfg)
    finally:
        db.execute(sql_text("DELETE FROM moc_task_catalog WHERE id = :t"), {"t": task.id})
        db.commit()
