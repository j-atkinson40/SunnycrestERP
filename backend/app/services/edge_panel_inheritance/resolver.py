"""Edge Panel Inheritance resolver (sub-arc B-1.5).

Walks Tier 2 (edge_panel_templates) → Tier 3 (edge_panel_compositions,
optional lazy fork) → User overrides (User.preferences) and produces
the effective edge-panel layout.

Composition order (per investigation §4):

    1. Tier 2 lookup: try (vertical_default, vertical, panel_key) →
       fall back to (platform_default, None, panel_key). Raises
       EdgePanelTemplateResolveError on miss.
    2. Tier 3 lookup: (tenant_id, template.id) active row. None means
       lazy pre-edit; resolution proceeds with bare Tier 2.
    3. User overrides: read `User.preferences.edge_panel_overrides[panel_key]`.
       Resolver reads `User.preferences` directly (rather than accepting
       overrides as a kwarg) so the caller boundary stays simple — pass
       user identity, resolver owns the read.
    4. Compose:
         a. Start from template.pages deep-copied.
         b. Apply Tier 3 deltas: hide pages → add pages → reorder pages
            → per-page placement deltas (hide → add → geometry → reorder).
         c. Apply User overrides on top: same vocabulary, same
            composition order. The User layer doesn't carry
            placement_geometry_overrides today (Tier 3 does); the resolver
            silently no-ops that key at the User layer if present.

Orphan handling (silent debug-log + drop):
    - Tier 3 references page_id not in template (write-time check
      catches; resolver also defends).
    - Tier 3 page_overrides references placement_id not in page.
    - User overrides reference page_id not in post-Tier-3-compose pages.
    - User overrides page_overrides references placement_id not in page.

canvas_config merge (per investigation §4 + §9 R8):
    template top-level canvas_config (deep-copied) + tenant
    canvas_config_overrides on top (dict.update) + per-page canvas_config
    merging is handled inline on each page record.

`_apply_placement_overrides` is copied verbatim from the legacy
composition_service to keep B-1.5 self-contained (B-2 rewrites the
legacy module; pinning to its private helper would couple substrates).
The behavior is identical; tests verify equivalence.

Live cascade (v1): the resolver always uses the ACTIVE Tier 2 + Tier 3
rows. `inherits_from_template_version` is captured at write time but
ignored at read time. Option B versioned cascade lands additively.

Performance: indexed lookups on (panel_key, scope, vertical) + on
(tenant_id, template_id) + a User.preferences read. Single-digit-ms
expected; no caching in v1.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.edge_panel_composition import EdgePanelComposition
from app.models.edge_panel_template import (
    SCOPE_PLATFORM_DEFAULT,
    SCOPE_VERTICAL_DEFAULT,
    EdgePanelTemplate,
)
from app.models.user import User


logger = logging.getLogger(__name__)


# ─── Exceptions + types ──────────────────────────────────────────


class EdgePanelTemplateResolveError(Exception):
    """Raised when no Tier 2 template matches the requested
    (panel_key, vertical) tuple. Indicates a misconfiguration —
    the resolver expects every requested panel to have at least a
    platform_default template."""


class ResolvedEdgePanel(BaseModel):
    panel_key: str
    template_id: str
    template_version: int
    template_scope: str  # 'platform_default' | 'vertical_default'
    template_vertical: str | None
    pages: list[dict[str, Any]]
    canvas_config: dict[str, Any]
    sources: dict[str, Any]


# ─── Internal helpers ────────────────────────────────────────────


def _find_active_template(
    db: Session,
    *,
    panel_key: str,
    vertical: str | None,
) -> tuple[EdgePanelTemplate, str] | None:
    """Try vertical_default first (when vertical is provided), then
    platform_default. Returns (row, scope_resolved) or None."""
    if vertical is not None:
        vrow = (
            db.query(EdgePanelTemplate)
            .filter(
                EdgePanelTemplate.panel_key == panel_key,
                EdgePanelTemplate.scope == SCOPE_VERTICAL_DEFAULT,
                EdgePanelTemplate.vertical == vertical,
                EdgePanelTemplate.is_active.is_(True),
            )
            .first()
        )
        if vrow is not None:
            return vrow, SCOPE_VERTICAL_DEFAULT
    prow = (
        db.query(EdgePanelTemplate)
        .filter(
            EdgePanelTemplate.panel_key == panel_key,
            EdgePanelTemplate.scope == SCOPE_PLATFORM_DEFAULT,
            EdgePanelTemplate.vertical.is_(None),
            EdgePanelTemplate.is_active.is_(True),
        )
        .first()
    )
    if prow is not None:
        return prow, SCOPE_PLATFORM_DEFAULT
    return None


def _apply_placement_overrides(
    rows: list[dict],
    *,
    hidden_ids: list[str],
    additional: list[dict],
    order: list[str] | None,
) -> list[dict]:
    """Copy-verbatim of composition_service._apply_placement_overrides
    (sub-arc B-2 rewrites the legacy module; B-1.5 keeps a local copy
    to avoid coupling substrates). Shape contract: hide → add → reorder.

    1. Filter placements: drop those whose placement_id is in
       hidden_ids (orphan IDs in hidden_ids logged at debug + dropped
       silently).
    2. Append additional placements: each carries optional row_index
       (default 0, clamped to last row; if rows empty, append as a new
       row containing the single placement).
    3. Reorder placements within each row by order if provided. Orphan
       IDs in order silently dropped. Placements not mentioned in order
       keep relative position appended at end.

    Returns a new rows list (does not mutate input).
    """
    hidden_set = set(hidden_ids or [])

    new_rows: list[dict] = []
    for row in rows:
        new_row = dict(row)
        kept_placements = []
        for p in row.get("placements") or []:
            if p.get("placement_id") in hidden_set:
                logger.debug(
                    "[edge-panel-resolver] dropped hidden placement %s",
                    p.get("placement_id"),
                )
                continue
            kept_placements.append(dict(p))
        new_row["placements"] = kept_placements
        new_rows.append(new_row)

    for add in additional or []:
        if not isinstance(add, dict):
            continue
        placement = {k: v for k, v in add.items() if k != "row_index"}
        target_row_idx = add.get("row_index", 0)
        if not isinstance(target_row_idx, int) or target_row_idx < 0:
            target_row_idx = 0

        if not new_rows:
            new_rows.append(
                {
                    "row_id": f"user-row-{placement.get('placement_id', 'unknown')}",
                    "column_count": 12,
                    "row_height": "auto",
                    "column_widths": None,
                    "nested_rows": None,
                    "placements": [placement],
                }
            )
        else:
            clamped_idx = min(target_row_idx, len(new_rows) - 1)
            new_rows[clamped_idx]["placements"].append(placement)

    if order:
        order_index = {pid: i for i, pid in enumerate(order)}
        for row in new_rows:
            placements = row["placements"]

            def sort_key(p: dict) -> tuple[int, int]:
                pid = p.get("placement_id")
                if pid in order_index:
                    return (0, order_index[pid])
                return (1, placements.index(p))

            row["placements"] = sorted(placements, key=sort_key)

    return new_rows


def _apply_geometry_overrides_on_page(
    page: dict, geometry_overrides: dict[str, dict]
) -> dict:
    """Walk a page's rows + apply per-placement geometry overrides
    (starting_column + column_span). Orphan placement_ids are
    silently dropped at debug log level. Returns the same page dict
    (mutates in place — caller passes a fresh copy)."""
    if not geometry_overrides:
        return page
    seen_ids: set[str] = set()
    for row in page.get("rows") or []:
        for p in row.get("placements") or []:
            pid = p.get("placement_id")
            if pid in geometry_overrides:
                geom = geometry_overrides[pid]
                p["starting_column"] = geom["starting_column"]
                p["column_span"] = geom["column_span"]
                seen_ids.add(pid)
    orphans = set(geometry_overrides.keys()) - seen_ids
    for pid in orphans:
        logger.debug(
            "[edge-panel-resolver] orphan placement_geometry_overrides[%s] "
            "(placement no longer exists on page %s)",
            pid,
            page.get("page_id"),
        )
    return page


def _apply_page_overrides(
    pages: list[dict],
    page_overrides: dict[str, dict],
    *,
    layer_label: str,
) -> list[dict]:
    """Walk pages + apply per-page deltas. Orphan page_ids are
    silently dropped at debug log level.

    Per-page deltas (canonical order, mirrors R-5.0 composition_service):
      1. hide → 2. add → 3. geometry → 4. reorder, then optionally
      canvas_config (full-replace if present).
    """
    if not page_overrides:
        return pages
    by_id = {p.get("page_id"): idx for idx, p in enumerate(pages)}
    for page_id, override in page_overrides.items():
        idx = by_id.get(page_id)
        if idx is None:
            logger.debug(
                "[edge-panel-resolver] orphan page_overrides[%s] from %s layer",
                page_id,
                layer_label,
            )
            continue
        if not isinstance(override, dict):
            continue
        new_page = copy.deepcopy(pages[idx])

        hidden_ids = override.get("hidden_placement_ids") or []
        additional = override.get("additional_placements") or []
        placement_order = override.get("placement_order")

        if (
            hidden_ids
            or additional
            or (placement_order is not None and len(placement_order) > 0)
        ):
            new_page["rows"] = _apply_placement_overrides(
                list(new_page.get("rows") or []),
                hidden_ids=hidden_ids if isinstance(hidden_ids, list) else [],
                additional=additional if isinstance(additional, list) else [],
                order=placement_order if isinstance(placement_order, list) else None,
            )

        geometry_overrides = override.get("placement_geometry_overrides")
        if isinstance(geometry_overrides, dict) and geometry_overrides:
            _apply_geometry_overrides_on_page(new_page, geometry_overrides)

        if "canvas_config" in override:
            cc = override["canvas_config"]
            new_page["canvas_config"] = (
                dict(cc) if isinstance(cc, dict) else None
            )

        pages[idx] = new_page
    return pages


def _apply_top_level_deltas(
    pages: list[dict],
    *,
    hidden_page_ids: list[str],
    additional_pages: list[dict],
    page_order: list[str],
) -> list[dict]:
    """Hide → add → reorder at the top-level pages layer."""
    # Hide.
    if hidden_page_ids:
        hidden_set = set(hidden_page_ids)
        pages = [p for p in pages if p.get("page_id") not in hidden_set]

    # Add (collision: tenant/template page wins; silently drop the
    # additional page).
    if additional_pages:
        existing_ids = {p.get("page_id") for p in pages}
        for ap in additional_pages:
            if not isinstance(ap, dict):
                continue
            ap_id = ap.get("page_id")
            if ap_id in existing_ids:
                logger.debug(
                    "[edge-panel-resolver] additional_pages[%s] collides "
                    "with existing page; dropping personal/tenant page",
                    ap_id,
                )
                continue
            pages.append(copy.deepcopy(ap))
            existing_ids.add(ap_id)

    # Reorder (any not mentioned keep position appended at end).
    if page_order:
        by_id = {p.get("page_id"): p for p in pages}
        reordered: list[dict] = []
        for pid in page_order:
            if pid in by_id:
                reordered.append(by_id.pop(pid))
        reordered.extend(by_id.values())
        pages = reordered

    return pages


def _user_overrides_for(db: Session, user_id: str, panel_key: str) -> dict | None:
    """Read `User.preferences.edge_panel_overrides[panel_key]` for the
    given user. Returns None if no overrides are present (legitimate
    state) or if the user can't be found (defensive; caller likely
    passed an invalid id which the API layer would catch first)."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        return None
    prefs = user.preferences or {}
    overrides_root = prefs.get("edge_panel_overrides")
    if not isinstance(overrides_root, dict):
        return None
    blob = overrides_root.get(panel_key)
    if not isinstance(blob, dict):
        return None
    return blob


# ─── Public resolver ─────────────────────────────────────────────


def resolve_edge_panel(
    db: Session,
    *,
    panel_key: str,
    vertical: str | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
) -> ResolvedEdgePanel:
    """Resolve the effective edge-panel layout for (panel_key, vertical,
    tenant, user). Raises EdgePanelTemplateResolveError when no Tier 2
    template matches."""
    found = _find_active_template(db, panel_key=panel_key, vertical=vertical)
    if found is None:
        raise EdgePanelTemplateResolveError(
            f"no active edge-panel template at panel_key={panel_key!r} "
            f"vertical={vertical!r}"
        )
    template, scope_resolved = found

    composition: EdgePanelComposition | None = None
    if tenant_id is not None:
        composition = (
            db.query(EdgePanelComposition)
            .filter(
                EdgePanelComposition.tenant_id == tenant_id,
                EdgePanelComposition.inherits_from_template_id == template.id,
                EdgePanelComposition.is_active.is_(True),
            )
            .first()
        )

    # Start from a deep copy of template pages so we never mutate
    # persisted JSONB in place.
    pages: list[dict] = copy.deepcopy(template.pages or [])

    # ── Tier 3 deltas ────────────────────────────────────────
    tenant_overrides_applied = False
    if composition is not None:
        deltas = composition.deltas or {}
        tenant_overrides_applied = True

        pages = _apply_top_level_deltas(
            pages,
            hidden_page_ids=list(deltas.get("hidden_page_ids") or []),
            additional_pages=list(deltas.get("additional_pages") or []),
            page_order=list(deltas.get("page_order") or []),
        )

        page_overrides = deltas.get("page_overrides") or {}
        if isinstance(page_overrides, dict):
            pages = _apply_page_overrides(
                pages, page_overrides, layer_label="tenant"
            )

    # ── User overrides ──────────────────────────────────────
    user_overrides_applied = False
    if user_id is not None:
        user_blob = _user_overrides_for(db, user_id, panel_key)
        if user_blob is not None:
            user_overrides_applied = True

            pages = _apply_top_level_deltas(
                pages,
                hidden_page_ids=list(user_blob.get("hidden_page_ids") or []),
                additional_pages=list(user_blob.get("additional_pages") or []),
                page_order=list(
                    user_blob.get("page_order_override")
                    or user_blob.get("page_order")
                    or []
                ),
            )
            po = user_blob.get("page_overrides") or {}
            if isinstance(po, dict):
                pages = _apply_page_overrides(
                    pages, po, layer_label="user"
                )

    # ── canvas_config compose ───────────────────────────────
    canvas_config: dict[str, Any] = dict(template.canvas_config or {})
    if composition is not None:
        canvas_config.update(dict(composition.canvas_config_overrides or {}))
    # v1 User layer does not carry top-level canvas_config; reserved.

    sources: dict[str, Any] = {
        "template": {
            "id": template.id,
            "version": template.version,
            "scope": template.scope,
            "vertical": template.vertical,
        },
        "composition": (
            {
                "tenant_id": composition.tenant_id,
                "composition_id": composition.id,
                "version": composition.version,
            }
            if composition is not None
            else None
        ),
        "user_override": {"applied": user_overrides_applied},
    }
    # Forward-compat marker for telemetry consumers.
    sources["composition_applied"] = tenant_overrides_applied

    return ResolvedEdgePanel(
        panel_key=panel_key,
        template_id=template.id,
        template_version=template.version,
        template_scope=scope_resolved,
        template_vertical=template.vertical,
        pages=pages,
        canvas_config=canvas_config,
        sources=sources,
    )
