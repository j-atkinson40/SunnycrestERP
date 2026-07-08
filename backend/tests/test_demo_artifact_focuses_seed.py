"""Demo artifacts 3a/3b — the two focus seeds + the live MoC light-up keystone.

1. Idempotency: seed twice → exactly the 2 focus_cores + 2 focus_templates,
   no dup, pointing at the registered core components.
2. KEYSTONE: after the focus seed + the MoC seed, the manufacturing MoC LIGHTS
   UP with zero frontend change — the task-table focus cells populate (Funeral
   Home Billing → Decision Triage; New Legacy Order → Legacy Generation +
   Decision Triage) AND the Focuses card gains both entries. This is the live
   proof the dynamic resolver (proven in 2a) fires for real when an artifact
   is seeded.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.services import maps_of_content as moc
from app.services.maps_of_content.task_catalog import resolve_task_catalog

from scripts.seed_demo_artifact_focuses import seed as seed_focuses
from scripts.seed_moc_manufacturing import seed as seed_moc

VERT = "manufacturing"
TEMPLATE_SLUGS = ("decision-triage", "legacy-generation")
CORE_SLUGS = ("decision-triage-core", "legacy-generation-core")
TASK_NAMES = ("Funeral Home Billing", "New Legacy Order")


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    # teardown: tasks (cascade joins) → templates → cores. Leave the page (its
    # now-orphaned focus refs resolve muted; a later seed re-resolves).
    for name in TASK_NAMES:
        s.execute(
            sql_text("DELETE FROM moc_task_catalog WHERE vertical = :v AND name = :n"),
            {"v": VERT, "n": name},
        )
    for slug in TEMPLATE_SLUGS:
        s.execute(
            sql_text(
                "DELETE FROM focus_templates WHERE template_slug = :s AND vertical = :v"
            ),
            {"s": slug, "v": VERT},
        )
    for slug in CORE_SLUGS:
        # FK-safe (FH stamp): OTHER lineages' templates may pin retained
        # version rows of these cores (e.g. a V-1 variation created from
        # decision-triage-core). Delete only the unreferenced rows; the
        # referenced snapshots stay and the seed re-adopts by slug.
        s.execute(
            sql_text(
                "DELETE FROM focus_cores WHERE core_slug = :s AND id NOT IN "
                "(SELECT inherits_from_core_id FROM focus_templates)"
            ),
            {"s": slug},
        )
    s.commit()
    s.close()


def _count(db, table: str, col: str, val: str, vertical: bool = False) -> int:
    # ACTIVE rows only (post-V-2 world: version bumps retain prior rows
    # is_active=false — the dup-check invariant is one ACTIVE row per slug).
    q = f"SELECT COUNT(*) FROM {table} WHERE {col} = :v AND is_active = true"
    params = {"v": val}
    if vertical:
        q += " AND vertical = :vt"
        params["vt"] = VERT
    return db.execute(sql_text(q), params).scalar()


def test_focus_seed_idempotent(db):
    seed_focuses(db)
    seed_focuses(db)  # re-run must not dup

    for slug in TEMPLATE_SLUGS:
        assert _count(db, "focus_templates", "template_slug", slug, vertical=True) == 1
    for slug in CORE_SLUGS:
        assert _count(db, "focus_cores", "core_slug", slug) == 1

    # The cores point at the registered components (per the investigation).
    comp = db.execute(
        sql_text(
            "SELECT registered_component_name FROM focus_cores "
            "WHERE core_slug = 'decision-triage-core' AND is_active = true"
        )
    ).scalar()
    assert comp == "TriageQueueCore"
    comp2 = db.execute(
        sql_text(
            "SELECT registered_component_name FROM focus_cores "
            "WHERE core_slug = 'legacy-generation-core' AND is_active = true"
        )
    ).scalar()
    assert comp2 == "EditCanvasCore"


def test_keystone_moc_lights_up(db):
    seed_focuses(db)   # 3a/3b: the focuses now exist
    seed_moc(db)       # the MoC seed re-resolves them (card refs + task joins)

    # 1) Task-table focus cells POPULATE (deep-linkable).
    tasks = {t["name"]: t for t in resolve_task_catalog(db, vertical=VERT)}
    fhb = tasks["Funeral Home Billing"]
    nlo = tasks["New Legacy Order"]
    assert [f["label"] for f in fhb["focuses"]] == ["Decision Triage"]
    assert {f["label"] for f in nlo["focuses"]} == {"Legacy Generation", "Decision Triage"}
    # deep-linkable: available + a template_slug route (what mocDeepLink consumes)
    assert fhb["focuses"][0]["available"] is True
    assert fhb["focuses"][0]["routing"]["template_slug"] == "decision-triage"
    assert all(f["available"] for f in nlo["focuses"])

    # 2) The Focuses CARD gains both entries (the authored page refs).
    view = moc.read_for_context(db, vertical=VERT)
    card_focuses = [
        r["resolution"]["label"]
        for s in view["sections"]
        for r in s["rows"]
        if r["builder"] == "focuses"
    ]
    assert "Decision Triage" in card_focuses
    assert "Legacy Generation" in card_focuses
