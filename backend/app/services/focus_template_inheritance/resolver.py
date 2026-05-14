"""Focus Template Inheritance resolver.

Walks Tier 1 (focus_cores) → Tier 2 (focus_templates) → Tier 3
(focus_compositions, optional) and materializes the effective layout.

Composition order (per investigation §4):
    1. Locate Tier 2 template by (template_slug, vertical). Vertical
       wins when both vertical_default + platform_default exist.
    2. Resolve Tier 1 core via template's inherits_from_core_id. v1
       uses the active row (IGNORE inherits_from_core_version per
       locked decision 2). v2 Option B (versioned cascade) lands
       additively here.
    3. If tenant_id provided, look up Tier 3 composition at
       (tenant_id, template.id). Zero-or-one row; None ⇒ tenant
       hasn't customized (lazy fork pre-state).
    4. Compose:
         a. Start from template.rows (deep-copy)
         b. Inject core as a placement at the appropriate row with
            is_core=true (per locked decision 4: core-as-placement)
         c. Apply Tier 3 deltas in order:
            - hidden_placement_ids: drop matching placements
            - additional_placements: append to indicated rows
            - placement_geometry_overrides: update geometry
            - core_geometry_override: update core placement geometry
            - placement_order: reorder placements within rows

Orphan handling (locked decision per investigation §4): orphan IDs
(placements that no longer exist in template.rows after an upstream
edit) are silently dropped at debug log level. The composition
row's deltas are preserved verbatim; the resolver simply ignores
stale references at READ time.

Performance: three indexed queries (template lookup by slug+scope,
core by id, composition by (tenant_id, template_id)). No caching in
v1.

Live cascade (locked decision 2): the resolver always uses the
ACTIVE template + core rows for the tuple, regardless of what
version the composition row's inherits_from_*_version pointed at.
A tenant who customized template v1 will see their deltas applied
on top of template v2's structure after upstream edits land.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.focus_composition import FocusComposition
from app.models.focus_core import FocusCore
from app.models.focus_template import (
    SCOPE_PLATFORM_DEFAULT,
    SCOPE_VERTICAL_DEFAULT,
    FocusTemplate,
)


logger = logging.getLogger(__name__)


# ─── Exceptions + types ──────────────────────────────────────────


class FocusTemplateNotFound(Exception):
    """Raised when no Tier 2 template matches the requested
    (template_slug, vertical) tuple. Indicates a misconfiguration —
    the resolver expects every requested template to exist at
    platform_default at minimum."""


class ResolvedFocus(BaseModel):
    template_id: str
    template_slug: str
    template_version: int
    template_scope: str  # 'platform_default' | 'vertical_default'
    template_vertical: str | None
    core_id: str
    core_slug: str
    core_version: int
    core_registered_component: dict[str, str]
    rows: list[dict[str, Any]]
    canvas_config: dict[str, Any]
    sources: dict[str, Any]


# ─── Internal helpers ────────────────────────────────────────────


def _find_active_template(
    db: Session,
    *,
    template_slug: str,
    vertical: str | None,
) -> tuple[FocusTemplate, str] | None:
    """Try vertical_default first (when vertical is provided), then
    platform_default. Returns (row, scope_resolved) or None."""
    if vertical is not None:
        vrow = (
            db.query(FocusTemplate)
            .filter(
                FocusTemplate.template_slug == template_slug,
                FocusTemplate.scope == SCOPE_VERTICAL_DEFAULT,
                FocusTemplate.vertical == vertical,
                FocusTemplate.is_active.is_(True),
            )
            .first()
        )
        if vrow is not None:
            return vrow, SCOPE_VERTICAL_DEFAULT
    prow = (
        db.query(FocusTemplate)
        .filter(
            FocusTemplate.template_slug == template_slug,
            FocusTemplate.scope == SCOPE_PLATFORM_DEFAULT,
            FocusTemplate.vertical.is_(None),
            FocusTemplate.is_active.is_(True),
        )
        .first()
    )
    if prow is not None:
        return prow, SCOPE_PLATFORM_DEFAULT
    return None


def _build_core_placement(core: FocusCore, *, override: dict | None) -> dict:
    """Produce the synthetic placement for the core. Geometry comes
    from core defaults, unless `override` (from Tier 3
    core_geometry_override) supplies a replacement.
    """
    if override is not None:
        starting_column = override["starting_column"]
        column_span = override["column_span"]
    else:
        starting_column = core.default_starting_column
        column_span = core.default_column_span
    return {
        "placement_id": f"core:{core.core_slug}",
        "is_core": True,
        "component_kind": core.registered_component_kind,
        "component_name": core.registered_component_name,
        "starting_column": starting_column,
        "column_span": column_span,
        "prop_overrides": {},
        "display_config": {},
    }


def _ensure_row_index(rows: list[dict], row_index: int) -> int:
    """Clamp row_index to the current rows list. If rows is empty,
    synthesize a single 12-column row first. Returns the (possibly
    clamped) index that's now valid to insert at.
    """
    if not rows:
        rows.append(
            {
                "row_id": "synth-core-row",
                "column_count": 12,
                "column_widths": None,
                "placements": [],
            }
        )
        return 0
    if row_index < 0:
        return 0
    if row_index >= len(rows):
        return len(rows) - 1
    return row_index


def _inject_core_placement(
    rows: list[dict],
    core: FocusCore,
    *,
    override: dict | None,
) -> list[dict]:
    """Inject the core placement at the core's row_index (or
    override's). If a placement with `is_core=true` already exists
    in `rows` (Tier 2 author put it there explicitly), DO NOT
    duplicate — replace its geometry with the core's defaults +
    optional override and ensure component_kind/name match.

    The Tier 2 author MAY include a sentinel placement with
    is_core=true in their rows; that's the canonical way to position
    the core within a multi-row layout. When absent, the resolver
    injects at core.default_row_index.
    """
    # Find any existing core placement in rows.
    existing_row_idx = None
    existing_placement_idx = None
    for r_idx, row in enumerate(rows):
        for p_idx, p in enumerate(row.get("placements") or []):
            if p.get("is_core") is True:
                existing_row_idx = r_idx
                existing_placement_idx = p_idx
                break
        if existing_row_idx is not None:
            break

    core_placement = _build_core_placement(core, override=override)

    if existing_row_idx is not None:
        target_row_idx = existing_row_idx
        if override is not None:
            # Override carries row_index — clamp + relocate if needed.
            requested_row_idx = override.get("row_index", existing_row_idx)
            target_row_idx = _ensure_row_index(rows, requested_row_idx)
            if target_row_idx != existing_row_idx:
                # Remove from current row.
                rows[existing_row_idx]["placements"].pop(existing_placement_idx)
                rows[target_row_idx]["placements"].append(core_placement)
                return rows
        # Replace in place.
        rows[target_row_idx]["placements"][existing_placement_idx] = core_placement
        return rows

    # No existing core placement — inject at core.default_row_index
    # (or override.row_index if supplied).
    requested_row_idx = (
        override.get("row_index") if override is not None else core.default_row_index
    )
    target_row_idx = _ensure_row_index(rows, requested_row_idx)
    rows[target_row_idx]["placements"].append(core_placement)
    return rows


def _apply_hidden(rows: list[dict], hidden_ids: list[str]) -> list[dict]:
    if not hidden_ids:
        return rows
    hidden_set = set(hidden_ids)
    for row in rows:
        kept: list[dict] = []
        for p in row.get("placements") or []:
            pid = p.get("placement_id")
            if pid in hidden_set:
                # Don't hide the core via hidden_placement_ids (core
                # has its own override mechanism); only accessories.
                if p.get("is_core") is True:
                    logger.debug(
                        "[focus-resolver] refusing to hide core placement %s",
                        pid,
                    )
                    kept.append(p)
                    continue
                logger.debug(
                    "[focus-resolver] dropping hidden placement %s", pid
                )
                continue
            kept.append(p)
        row["placements"] = kept
    return rows


def _apply_additional(
    rows: list[dict], additional: list[dict]
) -> list[dict]:
    if not additional:
        return rows
    for add in additional:
        target_row_idx = add.get("row_index", 0)
        placement = {k: v for k, v in add.items() if k != "row_index"}
        if not rows:
            rows.append(
                {
                    "row_id": f"user-row-{placement.get('placement_id', 'unknown')}",
                    "column_count": 12,
                    "column_widths": None,
                    "placements": [placement],
                }
            )
            continue
        idx = max(0, min(target_row_idx, len(rows) - 1))
        rows[idx]["placements"].append(placement)
    return rows


def _apply_geometry_overrides(
    rows: list[dict], overrides: dict[str, dict]
) -> list[dict]:
    if not overrides:
        return rows
    seen_ids: set[str] = set()
    for row in rows:
        for p in row.get("placements") or []:
            pid = p.get("placement_id")
            if pid in overrides:
                # Don't override core geometry via the generic
                # accessory path; core has its own override.
                if p.get("is_core") is True:
                    logger.debug(
                        "[focus-resolver] refusing to apply accessory "
                        "geometry override to core placement %s",
                        pid,
                    )
                    continue
                geom = overrides[pid]
                p["starting_column"] = geom["starting_column"]
                p["column_span"] = geom["column_span"]
                seen_ids.add(pid)
    # Orphans: log and drop silently.
    orphans = set(overrides.keys()) - seen_ids
    for pid in orphans:
        logger.debug(
            "[focus-resolver] orphan placement_geometry_override for %s "
            "(placement no longer exists)",
            pid,
        )
    return rows


def _apply_reorder(rows: list[dict], order: list[str]) -> list[dict]:
    if not order:
        return rows
    order_index = {pid: i for i, pid in enumerate(order)}
    for row in rows:
        placements = row.get("placements") or []

        def sort_key(p: dict) -> tuple[int, int]:
            pid = p.get("placement_id")
            if pid in order_index:
                return (0, order_index[pid])
            return (1, placements.index(p))

        row["placements"] = sorted(placements, key=sort_key)
    return rows


# ─── Public resolver ─────────────────────────────────────────────


def resolve_focus(
    db: Session,
    *,
    template_slug: str,
    vertical: str | None = None,
    tenant_id: str | None = None,
) -> ResolvedFocus:
    """Resolve the effective Focus layout for the given context."""
    found = _find_active_template(
        db, template_slug=template_slug, vertical=vertical
    )
    if found is None:
        raise FocusTemplateNotFound(
            f"no active template at template_slug={template_slug!r} "
            f"vertical={vertical!r}"
        )
    template, scope_resolved = found

    core = (
        db.query(FocusCore)
        .filter(FocusCore.id == template.inherits_from_core_id)
        .first()
    )
    if core is None:
        raise FocusTemplateNotFound(
            f"template {template.id!r} points at missing core "
            f"{template.inherits_from_core_id!r}"
        )

    composition: FocusComposition | None = None
    if tenant_id is not None:
        composition = (
            db.query(FocusComposition)
            .filter(
                FocusComposition.tenant_id == tenant_id,
                FocusComposition.inherits_from_template_id == template.id,
                FocusComposition.is_active.is_(True),
            )
            .first()
        )

    # Deep-copy template rows so we never mutate the persisted JSONB
    # in place. Compose step proceeds against this fresh structure.
    rows = copy.deepcopy(template.rows or [])

    # Step 1: inject core (with potential core_geometry_override).
    core_override = None
    if composition is not None:
        core_override = (composition.deltas or {}).get("core_geometry_override")
    rows = _inject_core_placement(rows, core, override=core_override)

    # Step 2: apply Tier 3 deltas in canonical order.
    if composition is not None:
        deltas = composition.deltas or {}
        rows = _apply_hidden(rows, deltas.get("hidden_placement_ids", []))
        rows = _apply_additional(rows, deltas.get("additional_placements", []))
        rows = _apply_geometry_overrides(
            rows, deltas.get("placement_geometry_overrides", {}) or {}
        )
        rows = _apply_reorder(rows, deltas.get("placement_order", []))

    # Compose canvas_config: template's config + tenant overrides on top.
    canvas_config = dict(template.canvas_config or {})
    if composition is not None:
        canvas_config.update(dict(composition.canvas_config_overrides or {}))

    sources: dict[str, Any] = {
        "template": {
            "id": template.id,
            "version": template.version,
            "scope": template.scope,
            "vertical": template.vertical,
        },
        "core": {
            "id": core.id,
            "slug": core.core_slug,
            "version": core.version,
        },
        "tenant": (
            {
                "tenant_id": composition.tenant_id,
                "composition_id": composition.id,
                "version": composition.version,
            }
            if composition is not None
            else None
        ),
    }

    return ResolvedFocus(
        template_id=template.id,
        template_slug=template.template_slug,
        template_version=template.version,
        template_scope=scope_resolved,
        template_vertical=template.vertical,
        core_id=core.id,
        core_slug=core.core_slug,
        core_version=core.version,
        core_registered_component={
            "kind": core.registered_component_kind,
            "name": core.registered_component_name,
        },
        rows=rows,
        canvas_config=canvas_config,
        sources=sources,
    )
