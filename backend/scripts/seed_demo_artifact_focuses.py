"""Demo artifacts (MoC option-3) — 3a-seed + 3b-seed: the two focus configs.

Seeds "Decision Triage" + "Legacy Generation" as CONFIG over existing focus
substrate (per docs/investigations/moc_demo_artifacts_investigation.md). Each =
a focus_cores row (pointing at an ALREADY-REGISTERED core component) + a
focus_templates row. NO new React core, NO migration.

  - Decision Triage  → core component TriageQueueCore (mode triageQueue;
    renders placeholders today — fleshing the stub is 3a.1, deferred).
  - Legacy Generation → core component EditCanvasCore (the canvas-authoring
    core, a stand-in for the generation surface; the headless-dispatch wrapper +
    real Personalization-Studio generation surface are 3b.1, deferred).

WHY THIS LIGHTS UP THE MoC: seed_moc_manufacturing references these focuses by
display_name; it runs AFTER this seed (alphabetical: seed_demo_… < seed_moc_…),
so its _resolve_focus_ids finds them + creates the focus-join rows in the SAME
deploy → the MoC task table's focus cells + the Focuses card populate, zero
frontend change. Names MUST match the MoC refs exactly.

Vertical-scoped (vertical_default/manufacturing) per the
ck_focus_templates_scope_vertical_correlation constraint. Idempotent:
find-or-create by core_slug (cores) and (scope, vertical, template_slug)
(templates). Platform-canonical (real artifacts; no demo guard).

Usage:  cd backend && python -m scripts.seed_demo_artifact_focuses
"""
from __future__ import annotations

import logging
import sys
import uuid
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import text as sql_text  # noqa: E402

from app.database import SessionLocal  # noqa: E402

logger = logging.getLogger(__name__)

VERTICAL = "manufacturing"

# display_name MUST match seed_moc_manufacturing's focus refs exactly.
FOCUSES = [
    {
        "core_slug": "decision-triage-core",
        "core_display": "Decision Triage Core",
        "core_component": "TriageQueueCore",
        "core_icon": "scale",
        "template_slug": "decision-triage",
        "display_name": "Decision Triage",
        "description": (
            "Bounded approve/reject decisions over the triage substrate "
            "(the Decide primitive). Core renders the triage queue."
        ),
    },
    {
        "core_slug": "legacy-generation-core",
        "core_display": "Legacy Generation Core",
        # Canvas-authoring core as the generation-surface stand-in; the real
        # legacy-proof generation surface + headless dispatch are 3b.1.
        "core_component": "EditCanvasCore",
        "core_icon": "sparkles",
        "template_slug": "legacy-generation",
        "display_name": "Legacy Generation",
        "description": (
            "Generates a legacy proof (the generation Focus, headless-capable). "
            "Headless dispatch wiring is 3b.1."
        ),
    },
]


def _upsert_core(
    db, *, slug: str, display: str, component: str, icon: str | None = None
) -> tuple[str, int]:
    """find-or-create a focus_cores row by core_slug → (id, version)."""
    # Prefer the ACTIVE row; fall back to the newest snapshot only when the
    # whole lineage is deactivated (FH-stamp fix: version bumps retain prior
    # rows is_active=false — an unordered SELECT grabbed one and the
    # is_active=true update tripped the one-active-per-slug partial unique).
    row = db.execute(
        sql_text(
            "SELECT id, version FROM focus_cores WHERE core_slug = :s "
            "ORDER BY is_active DESC, version DESC LIMIT 1"
        ),
        {"s": slug},
    ).first()
    if row:
        db.execute(
            sql_text(
                "UPDATE focus_cores SET display_name = :d, "
                "registered_component_kind = 'focus-core', "
                "registered_component_name = :c, is_active = true, "
                # r122 family icon: assign-if-NULL only — an operator's
                # later choice is never clobbered by a deploy re-seed.
                "icon = COALESCE(icon, :i), "
                "updated_at = now() WHERE id = :id"
            ),
            {"d": display, "c": component, "i": icon, "id": row.id},
        )
        return row.id, row.version
    cid = str(uuid.uuid4())
    db.execute(
        sql_text(
            "INSERT INTO focus_cores (id, core_slug, display_name, "
            "registered_component_kind, registered_component_name, icon, "
            "version, is_active, created_at, updated_at) VALUES (:id, :s, :d, "
            "'focus-core', :c, :i, 1, true, now(), now())"
        ),
        {"id": cid, "s": slug, "d": display, "c": component, "i": icon},
    )
    return cid, 1


def _upsert_template(
    db, *, template_slug: str, display_name: str, description: str,
    core_id: str, core_version: int,
) -> str:
    """find-or-create a focus_templates row by (scope, vertical, slug)."""
    # Same active-first discipline as _upsert_core (version rows retained).
    row = db.execute(
        sql_text(
            "SELECT id FROM focus_templates WHERE scope = 'vertical_default' "
            "AND vertical = :v AND template_slug = :ts "
            "ORDER BY is_active DESC, version DESC LIMIT 1"
        ),
        {"v": VERTICAL, "ts": template_slug},
    ).first()
    if row:
        db.execute(
            sql_text(
                "UPDATE focus_templates SET display_name = :d, description = :desc, "
                "inherits_from_core_id = :cid, inherits_from_core_version = :cv, "
                "is_active = true, updated_at = now() WHERE id = :id"
            ),
            {"d": display_name, "desc": description, "cid": core_id,
             "cv": core_version, "id": row.id},
        )
        return row.id
    tid = str(uuid.uuid4())
    db.execute(
        sql_text(
            "INSERT INTO focus_templates (id, scope, vertical, template_slug, "
            "display_name, description, inherits_from_core_id, "
            "inherits_from_core_version, is_active, created_at, updated_at) "
            "VALUES (:id, 'vertical_default', :v, :ts, :d, :desc, :cid, :cv, "
            "true, now(), now())"
        ),
        {"id": tid, "v": VERTICAL, "ts": template_slug, "d": display_name,
         "desc": description, "cid": core_id, "cv": core_version},
    )
    return tid


def seed(db) -> str:
    for f in FOCUSES:
        core_id, core_ver = _upsert_core(
            db, slug=f["core_slug"], display=f["core_display"],
            component=f["core_component"], icon=f.get("core_icon"),
        )
        _upsert_template(
            db, template_slug=f["template_slug"], display_name=f["display_name"],
            description=f["description"], core_id=core_id, core_version=core_ver,
        )
        logger.info("[demo-focus-seed] %r ready (core=%s)", f["display_name"],
                    f["core_component"])
    db.commit()
    return f"{len(FOCUSES)} focuses"


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        print(f"[seed_demo_artifact_focuses] {seed(db)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
