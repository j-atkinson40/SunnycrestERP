"""Seed canonical Focus Template Inheritance content (sub-arc B-1).

Tier 1 — one core:
    core_slug = 'scheduling-kanban'
        Canonical decision-triage Focus core. Registered against the
        in-memory component registry as
        focus-core / SchedulingKanbanCore.

Tier 2 — one template:
    template_slug = 'scheduling-fh', scope = 'vertical_default',
    vertical = 'funeral_home'
        Default funeral scheduling Focus. Minimal accessory rows in
        v1; editor populates canonical accessories in sub-arc C.

Idempotent: re-running detects the active row by slug and skips when
present (does NOT version-bump). This is distinct from the service
layer's `create_template` "version on collision" behavior — seed
scripts must be safe to re-run without rotating the active row
unnecessarily.

Usage:
    PYTHONPATH=. python backend/scripts/seed_focus_template_inheritance.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure `backend` is on sys.path so this script runs from any cwd.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.services.focus_template_inheritance import (  # noqa: E402
    create_core,
    create_template,
    get_core_by_slug,
    get_template_by_slug,
    update_core,
    update_template,
)


logger = logging.getLogger(__name__)


SCHEDULING_KANBAN_CORE = {
    "core_slug": "scheduling-kanban",
    # Sub-arc F-1.1: display_name normalized "Scheduling Kanban" → "Kanban".
    # The kanban shape is canonical; "Scheduling" was a use-case framing
    # that conflated core with template. Slug stays unchanged (immutable
    # via update_core; renaming would break references). Templates layer
    # use-case framing ("Funeral Scheduling") on top.
    "display_name": "Kanban",
    "description": (
        "Canonical decision-triage Focus core: column-based scheduling "
        "kanban with drag-to-reorder."
    ),
    "registered_component_kind": "focus-core",
    "registered_component_name": "SchedulingKanbanCore",
    "default_starting_column": 0,
    "default_column_span": 12,
    "default_row_index": 0,
    "min_column_span": 8,
    "max_column_span": 12,
    "canvas_config": {},
    # Sub-arc E-1.1: full canonical mockup chrome state. E-1 shipped
    # delta updates (corner_radius / padding_token / backdrop_blur)
    # but preserved pre-E-1 preset / elevation / background / border
    # values that weren't mockup-canonical. E-1.1 specifies ALL 7
    # chrome fields explicitly so the Tier 1 core stamps the full
    # frosted-glass mockup chrome that Tier 2 templates inherit via
    # empty chrome_overrides.
    "chrome": {
        "preset": "frosted",
        "elevation": 50,
        "corner_radius": 70,
        "backdrop_blur": 44,
        "background_token": "surface-frosted",
        "border_token": "border-subtle",
        "padding_token": "space-3",
    },
}


# Sub-arc E-1: canonical mockup substrate + typography. Matches
# `defaults.py::DEFAULT_SUBSTRATE` + `DEFAULT_TYPOGRAPHY` so newly-
# created Tier 2 templates and the seeded scheduling-fh template have
# the same starting baseline. `chrome_overrides` is explicitly empty
# so the template cascades chrome (including the E-1 corner_radius /
# padding_token / backdrop_blur overrides) from the inherited core.
SCHEDULING_FH_TEMPLATE = {
    "scope": "vertical_default",
    # Sub-arc F-1.1: vertical flipped funeral_home → manufacturing.
    # James authored the template at Sunnycrest (precast manufacturer)
    # to schedule funeral vault deliveries. CONTENT involves funeral
    # homes (customer); OPERATOR is Manufacturing. Templates live in
    # the OPERATOR's vertical, not the customer's. Slug stays unchanged
    # (referenced externally; renaming would break links).
    "vertical": "manufacturing",
    "template_slug": "scheduling-fh",
    # Sub-arc F-1.1: display_name normalized "Funeral Home Scheduling"
    # → "Funeral Scheduling" (the use-case framing on top of the
    # canonical Kanban core).
    "display_name": "Funeral Scheduling",
    "description": (
        "Default funeral scheduling Focus with case overview + day-pane "
        "accessories. Sub-arc C ships the canonical accessory layout."
    ),
    "rows": [],  # Editor populates accessories in sub-arc C.
    "canvas_config": {},
    "chrome_overrides": {},
    "substrate": {
        "preset": "morning-warm",
        "intensity": 100,
        "base_token": "surface-base",
        "accent_token_1": "surface-elevated",
        "accent_token_2": None,
    },
    "typography": {
        "preset": "frosted-text",
        "heading_weight": 600,
        "body_weight": 500,
        "heading_color_token": "content-strong",
        "body_color_token": "content-base",
    },
}


def _seed_core(db) -> str:
    existing = get_core_by_slug(db, SCHEDULING_KANBAN_CORE["core_slug"])
    if existing is not None:
        # Sub-arc E-1: if seeded content drifted from the canonical
        # values (e.g. earlier seeds shipped `chrome: {"preset": "card"}`
        # without the corner_radius / padding_token / backdrop_blur
        # overrides), version-bump to align. Compare on the fields the
        # seed declares; non-declared fields are preserved by update.
        desired_chrome = dict(SCHEDULING_KANBAN_CORE["chrome"])
        desired_display_name = SCHEDULING_KANBAN_CORE["display_name"]
        current_chrome = dict(existing.chrome or {})
        current_display_name = existing.display_name
        chrome_drift = current_chrome != desired_chrome
        name_drift = current_display_name != desired_display_name
        if chrome_drift or name_drift:
            # Sub-arc F-1.1: include display_name in drift detection so
            # "Scheduling Kanban" → "Kanban" rename actually propagates.
            update_kwargs = {}
            if chrome_drift:
                update_kwargs["chrome"] = desired_chrome
            if name_drift:
                update_kwargs["display_name"] = desired_display_name
            row = update_core(db, existing.id, **update_kwargs)
            logger.info(
                "Updated Tier 1 core %r to canonical mockup values "
                "(id=%s, version=%d → %d, drift: chrome=%s, name=%s)",
                existing.core_slug,
                row.id,
                existing.version,
                row.version,
                chrome_drift,
                name_drift,
            )
            return row.id
        logger.info(
            "Tier 1 core %r already active + canonical "
            "(id=%s, version=%d) — skip",
            existing.core_slug,
            existing.id,
            existing.version,
        )
        return existing.id
    row = create_core(db, **SCHEDULING_KANBAN_CORE)
    logger.info(
        "Seeded Tier 1 core %r (id=%s, version=%d)",
        row.core_slug,
        row.id,
        row.version,
    )
    return row.id


def _seed_template(db, *, inherits_from_core_id: str) -> str:
    # Sub-arc F-1.1: vertical migration. The template previously lived
    # at vertical=funeral_home; F-1.1 reclassifies to vertical=manufacturing
    # (operator-vertical canon). update_template treats `vertical` as
    # immutable, so the migration is two-step: deactivate any prior
    # funeral_home row, then create/update at the new manufacturing row.
    # Idempotent: once the funeral_home row is deactivated, subsequent
    # runs find nothing at the old location and continue at the new one.
    legacy_existing = get_template_by_slug(
        db,
        SCHEDULING_FH_TEMPLATE["template_slug"],
        scope=SCHEDULING_FH_TEMPLATE["scope"],
        vertical="funeral_home",
    )
    if legacy_existing is not None and SCHEDULING_FH_TEMPLATE["vertical"] != "funeral_home":
        legacy_existing.is_active = False
        db.add(legacy_existing)
        db.commit()
        logger.info(
            "Deactivated legacy Tier 2 template %r at vertical=funeral_home "
            "(id=%s, version=%d) per F-1.1 vertical migration",
            legacy_existing.template_slug,
            legacy_existing.id,
            legacy_existing.version,
        )

    existing = get_template_by_slug(
        db,
        SCHEDULING_FH_TEMPLATE["template_slug"],
        scope=SCHEDULING_FH_TEMPLATE["scope"],
        vertical=SCHEDULING_FH_TEMPLATE["vertical"],
    )
    # Sub-arc E-1.1: force a version-bump via create_template when the
    # template's recorded `inherits_from_core_version` lags behind the
    # active core's version. `update_template` preserves the prior
    # version pin (immutable through that surface — service-layer
    # captures from the live active core only on create). The resolver
    # already uses the active core regardless (locked decision 2), but
    # C-2.3's lineage chrome reads `template.inherits_from_core_version`
    # directly, so a stale stamp displays as "v1" in the editor even
    # after the core moves to v9.
    if existing is not None:
        from app.services.focus_template_inheritance import get_core_by_id

        active_core = get_core_by_id(db, inherits_from_core_id)
        active_core_version = (
            active_core.version if active_core is not None else None
        )
        if (
            active_core_version is not None
            and existing.inherits_from_core_version != active_core_version
        ):
            row = create_template(
                db,
                scope=SCHEDULING_FH_TEMPLATE["scope"],
                vertical=SCHEDULING_FH_TEMPLATE["vertical"],
                template_slug=SCHEDULING_FH_TEMPLATE["template_slug"],
                display_name=SCHEDULING_FH_TEMPLATE["display_name"],
                description=SCHEDULING_FH_TEMPLATE["description"],
                inherits_from_core_id=inherits_from_core_id,
                rows=SCHEDULING_FH_TEMPLATE["rows"],
                canvas_config=SCHEDULING_FH_TEMPLATE["canvas_config"],
                chrome_overrides=SCHEDULING_FH_TEMPLATE["chrome_overrides"],
                substrate=SCHEDULING_FH_TEMPLATE["substrate"],
                typography=SCHEDULING_FH_TEMPLATE["typography"],
            )
            logger.info(
                "Version-bumped Tier 2 template %r so "
                "inherits_from_core_version restamps to live core v%d "
                "(id=%s, vertical=%s, version=%d → %d)",
                row.template_slug,
                row.inherits_from_core_version,
                row.id,
                row.vertical,
                existing.version,
                row.version,
            )
            return row.id
    if existing is not None:
        # Sub-arc E-1: align previously-seeded substrate / typography /
        # chrome_overrides to the canonical mockup baseline. Earlier
        # seeds shipped `substrate: {"preset": "morning-warm"}` (no
        # intensity / tokens) and `typography: {"preset":
        # "frosted-text"}` (no weights / color tokens); the canonical
        # blobs are explicit so the resolver sees the same values
        # regardless of preset-cascade evolution.
        desired_substrate = dict(SCHEDULING_FH_TEMPLATE["substrate"])
        desired_typography = dict(SCHEDULING_FH_TEMPLATE["typography"])
        desired_chrome = dict(SCHEDULING_FH_TEMPLATE["chrome_overrides"])
        desired_display_name = SCHEDULING_FH_TEMPLATE["display_name"]
        current_substrate = dict(existing.substrate or {})
        current_typography = dict(getattr(existing, "typography", None) or {})
        current_chrome = dict(existing.chrome_overrides or {})
        current_display_name = existing.display_name
        if (
            current_substrate != desired_substrate
            or current_typography != desired_typography
            or current_chrome != desired_chrome
            or current_display_name != desired_display_name
        ):
            # Sub-arc F-1.1: include display_name in drift detection so
            # "Funeral Home Scheduling" → "Funeral Scheduling" rename
            # propagates on re-seed.
            row = update_template(
                db,
                existing.id,
                display_name=desired_display_name,
                substrate=desired_substrate,
                typography=desired_typography,
                chrome_overrides=desired_chrome,
            )
            logger.info(
                "Updated Tier 2 template %r to canonical mockup values "
                "(id=%s, vertical=%s, version=%d → %d)",
                existing.template_slug,
                row.id,
                existing.vertical,
                existing.version,
                row.version,
            )
            return row.id
        logger.info(
            "Tier 2 template %r already active + canonical "
            "(id=%s, scope=%s, vertical=%s, version=%d) — skip",
            existing.template_slug,
            existing.id,
            existing.scope,
            existing.vertical,
            existing.version,
        )
        return existing.id
    row = create_template(
        db,
        scope=SCHEDULING_FH_TEMPLATE["scope"],
        vertical=SCHEDULING_FH_TEMPLATE["vertical"],
        template_slug=SCHEDULING_FH_TEMPLATE["template_slug"],
        display_name=SCHEDULING_FH_TEMPLATE["display_name"],
        description=SCHEDULING_FH_TEMPLATE["description"],
        inherits_from_core_id=inherits_from_core_id,
        rows=SCHEDULING_FH_TEMPLATE["rows"],
        canvas_config=SCHEDULING_FH_TEMPLATE["canvas_config"],
        chrome_overrides=SCHEDULING_FH_TEMPLATE["chrome_overrides"],
        substrate=SCHEDULING_FH_TEMPLATE["substrate"],
        typography=SCHEDULING_FH_TEMPLATE["typography"],
    )
    logger.info(
        "Seeded Tier 2 template %r (id=%s, vertical=%s, version=%d)",
        row.template_slug,
        row.id,
        row.vertical,
        row.version,
    )
    return row.id


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    db = SessionLocal()
    try:
        core_id = _seed_core(db)
        _seed_template(db, inherits_from_core_id=core_id)
    finally:
        db.close()


if __name__ == "__main__":
    main()
