"""Tier 3 — Edge Panel Composition service (sub-arc B-1.5).

Per-tenant lazy-fork delta over a chosen EdgePanelTemplate. The
substrate is greenfield: no rows exist for a tenant until they make
their first edit. Pre-edit, the resolver returns the bare Tier 2
template (with optional User overrides layered on top).

deltas vocabulary is recursive (page-keyed outer, placement-keyed
inner) and matches the R-5.0 + R-5.1 User-preference shape verbatim,
plus Tier 3's per-page `placement_geometry_overrides` addition (the
User layer doesn't carry geometry overrides today; Tier 3 does, per
the B-1.5 investigation §3).

Allowed top-level delta keys:
  - hidden_page_ids:        [str]
  - additional_pages:       [page]
  - page_order:             [page_id]
  - page_overrides:         { <page_id>: PageOverride }

Allowed page_overrides[<page_id>] keys (PageOverride):
  - hidden_placement_ids:        [placement_id]
  - additional_placements:       [placement with optional row_index]
  - placement_geometry_overrides: { <placement_id>: { starting_column, column_span } }
  - placement_order:             [placement_id]
  - canvas_config:               dict (full-replace if present)

Unknown keys at either level are REJECTED (forward-compat: new
delta capabilities require a service-layer bump here).

Lazy-fork lifecycle: `upsert_composition` is the only write surface
and handles both first-edit and subsequent-edit. `reset_composition`
clears all deltas (deactivates + replaces with empty delta row).
`reset_page` removes one entry from `deltas.page_overrides`.
`reset_placement` removes per-placement entries (hidden /
geometry-override / order) within one page's overrides.

`inherits_from_template_version` is captured from the live active
template at write time. v1 resolver IGNORES it (live cascade); v2
versioned cascade lands additively.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.edge_panel_composition import EdgePanelComposition
from app.services.edge_panel_inheritance.edge_panel_templates_service import (
    EdgePanelTemplateNotFound,
    InvalidEdgePanelShape,
    get_template_by_id,
)


logger = logging.getLogger(__name__)


# ─── Exceptions ──────────────────────────────────────────────────


class EdgePanelCompositionError(Exception):
    """Base for Tier 3 edge-panel composition service errors."""


class EdgePanelCompositionNotFound(EdgePanelCompositionError):
    pass


# ─── Validation helpers ──────────────────────────────────────────


_ALLOWED_TOP_KEYS: tuple[str, ...] = (
    "hidden_page_ids",
    "additional_pages",
    "page_order",
    "page_overrides",
)

_ALLOWED_PAGE_OVERRIDE_KEYS: tuple[str, ...] = (
    "hidden_placement_ids",
    "additional_placements",
    "placement_geometry_overrides",
    "placement_order",
    "canvas_config",
)


def _validate_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise InvalidEdgePanelShape(f"{field} must be an integer")
    return value


def _validate_str_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise InvalidEdgePanelShape(f"{field} must be a list of strings")
    out: list[str] = []
    for i, v in enumerate(value):
        if not isinstance(v, str) or not v:
            raise InvalidEdgePanelShape(
                f"{field}[{i}] must be a non-empty string"
            )
        out.append(v)
    return out


def _validate_additional_placement(p: Any, *, page_loc: str, index: int) -> dict:
    if not isinstance(p, dict):
        raise InvalidEdgePanelShape(
            f"{page_loc}.additional_placements[{index}] must be a dict"
        )
    pid = p.get("placement_id")
    if not isinstance(pid, str) or not pid:
        raise InvalidEdgePanelShape(
            f"{page_loc}.additional_placements[{index}].placement_id must be a non-empty string"
        )
    kind = p.get("component_kind")
    if not isinstance(kind, str) or not kind:
        raise InvalidEdgePanelShape(
            f"{page_loc}.additional_placements[{index}] {pid!r}: component_kind must be a non-empty string"
        )
    name = p.get("component_name")
    if not isinstance(name, str) or not name:
        raise InvalidEdgePanelShape(
            f"{page_loc}.additional_placements[{index}] {pid!r}: component_name must be a non-empty string"
        )
    starting_column = _validate_int(
        p.get("starting_column"),
        f"{page_loc}.additional_placements[{index}] {pid!r}.starting_column",
    )
    column_span = _validate_int(
        p.get("column_span"),
        f"{page_loc}.additional_placements[{index}] {pid!r}.column_span",
    )
    if starting_column < 0:
        raise InvalidEdgePanelShape(
            f"{page_loc}.additional_placements[{index}] {pid!r}: starting_column must be >= 0"
        )
    if column_span < 1:
        raise InvalidEdgePanelShape(
            f"{page_loc}.additional_placements[{index}] {pid!r}: column_span must be >= 1"
        )
    if starting_column + column_span > 12:
        raise InvalidEdgePanelShape(
            f"{page_loc}.additional_placements[{index}] {pid!r}: "
            f"starting_column + column_span exceeds 12-column canvas"
        )
    if "row_index" in p:
        row_index = p.get("row_index")
        if not isinstance(row_index, int) or isinstance(row_index, bool) or row_index < 0:
            raise InvalidEdgePanelShape(
                f"{page_loc}.additional_placements[{index}] {pid!r}: row_index "
                f"must be a non-negative integer"
            )
    if "prop_overrides" in p and not isinstance(p["prop_overrides"], dict):
        raise InvalidEdgePanelShape(
            f"{page_loc}.additional_placements[{index}] {pid!r}: prop_overrides must be a dict"
        )
    if "display_config" in p and not isinstance(p["display_config"], dict):
        raise InvalidEdgePanelShape(
            f"{page_loc}.additional_placements[{index}] {pid!r}: display_config must be a dict"
        )
    return dict(p)


def _validate_geometry_overrides(
    value: Any, *, page_loc: str
) -> dict[str, dict]:
    if not isinstance(value, dict):
        raise InvalidEdgePanelShape(
            f"{page_loc}.placement_geometry_overrides must be a dict"
        )
    out: dict[str, dict] = {}
    for pid, geom in value.items():
        if not isinstance(pid, str) or not pid:
            raise InvalidEdgePanelShape(
                f"{page_loc}.placement_geometry_overrides keys must be non-empty strings"
            )
        if not isinstance(geom, dict):
            raise InvalidEdgePanelShape(
                f"{page_loc}.placement_geometry_overrides[{pid!r}] must be a dict"
            )
        starting_column = _validate_int(
            geom.get("starting_column"),
            f"{page_loc}.placement_geometry_overrides[{pid!r}].starting_column",
        )
        column_span = _validate_int(
            geom.get("column_span"),
            f"{page_loc}.placement_geometry_overrides[{pid!r}].column_span",
        )
        if starting_column < 0:
            raise InvalidEdgePanelShape(
                f"{page_loc}.placement_geometry_overrides[{pid!r}]: starting_column must be >= 0"
            )
        if column_span < 1:
            raise InvalidEdgePanelShape(
                f"{page_loc}.placement_geometry_overrides[{pid!r}]: column_span must be >= 1"
            )
        if starting_column + column_span > 12:
            raise InvalidEdgePanelShape(
                f"{page_loc}.placement_geometry_overrides[{pid!r}]: "
                f"starting_column + column_span exceeds 12-column canvas"
            )
        out[pid] = {
            "starting_column": starting_column,
            "column_span": column_span,
        }
    return out


def _validate_page_override(po: Any, *, page_id: str) -> dict:
    page_loc = f"page_overrides[{page_id!r}]"
    if not isinstance(po, dict):
        raise InvalidEdgePanelShape(f"{page_loc} must be a dict")
    for key in po.keys():
        if key not in _ALLOWED_PAGE_OVERRIDE_KEYS:
            raise InvalidEdgePanelShape(
                f"{page_loc}: unknown key {key!r}; allowed: {_ALLOWED_PAGE_OVERRIDE_KEYS}"
            )

    hidden = _validate_str_list(
        po.get("hidden_placement_ids", []), f"{page_loc}.hidden_placement_ids"
    )
    additional_raw = po.get("additional_placements", [])
    if not isinstance(additional_raw, list):
        raise InvalidEdgePanelShape(
            f"{page_loc}.additional_placements must be a list"
        )
    additional: list[dict] = []
    seen_additional_ids: set[str] = set()
    for i, p in enumerate(additional_raw):
        validated = _validate_additional_placement(p, page_loc=page_loc, index=i)
        pid = validated["placement_id"]
        if pid in seen_additional_ids:
            raise InvalidEdgePanelShape(
                f"{page_loc}.additional_placements: duplicate placement_id {pid!r}"
            )
        seen_additional_ids.add(pid)
        additional.append(validated)
    geometry = _validate_geometry_overrides(
        po.get("placement_geometry_overrides", {}), page_loc=page_loc
    )
    order = _validate_str_list(
        po.get("placement_order", []), f"{page_loc}.placement_order"
    )
    out: dict[str, Any] = {
        "hidden_placement_ids": hidden,
        "additional_placements": additional,
        "placement_geometry_overrides": geometry,
        "placement_order": order,
    }
    if "canvas_config" in po:
        cc = po["canvas_config"]
        if cc is not None and not isinstance(cc, dict):
            raise InvalidEdgePanelShape(
                f"{page_loc}.canvas_config must be a dict or null"
            )
        out["canvas_config"] = dict(cc) if isinstance(cc, dict) else None
    return out


def _validate_additional_page(p: Any, *, index: int) -> dict:
    """Light validation of `additional_pages[*]` — same shape as a
    template page (page_id + name + rows + optional canvas_config),
    delegated to the template-side _validate_pages helper for row
    structure. Done locally to avoid the cyclic dependency on the
    templates service (the helper is shared via a private import in
    upsert)."""
    from app.services.edge_panel_inheritance.edge_panel_templates_service import (
        _validate_pages as _tpl_validate_pages,
    )

    if not isinstance(p, dict):
        raise InvalidEdgePanelShape(f"additional_pages[{index}] must be a dict")
    pid = p.get("page_id")
    if not isinstance(pid, str) or not pid:
        raise InvalidEdgePanelShape(
            f"additional_pages[{index}].page_id must be a non-empty string"
        )
    # Reuse template page validation by wrapping into a single-element list.
    _tpl_validate_pages([p])
    return dict(p)


def _validate_deltas(deltas: Any, *, template_page_ids: set[str]) -> dict:
    """Normalize + validate the deltas blob. Returns a fresh dict
    suitable for JSONB persistence. Unknown keys at either top-level
    or per-page level are rejected.

    Write-time orphan handling: deltas referencing page_ids not in
    the current template (`page_overrides` keys, `hidden_page_ids`
    entries) are REJECTED at the write boundary so authoring errors
    surface immediately. The resolver also drops orphan references
    silently at READ time as defense-in-depth for cross-version
    template drift.
    """
    if deltas is None:
        return {
            "hidden_page_ids": [],
            "additional_pages": [],
            "page_order": [],
            "page_overrides": {},
        }
    if not isinstance(deltas, dict):
        raise InvalidEdgePanelShape("deltas must be a dict or null")

    for key in deltas.keys():
        if key not in _ALLOWED_TOP_KEYS:
            raise InvalidEdgePanelShape(
                f"unknown delta key {key!r}; allowed: {_ALLOWED_TOP_KEYS}"
            )

    hidden_page_ids = _validate_str_list(
        deltas.get("hidden_page_ids", []), "hidden_page_ids"
    )
    additional_pages_raw = deltas.get("additional_pages", [])
    if not isinstance(additional_pages_raw, list):
        raise InvalidEdgePanelShape("additional_pages must be a list")
    additional_pages: list[dict] = []
    seen_add_page_ids: set[str] = set()
    for i, p in enumerate(additional_pages_raw):
        validated = _validate_additional_page(p, index=i)
        ap_id = validated["page_id"]
        if ap_id in seen_add_page_ids:
            raise InvalidEdgePanelShape(
                f"additional_pages: duplicate page_id {ap_id!r}"
            )
        seen_add_page_ids.add(ap_id)
        additional_pages.append(validated)

    page_order = _validate_str_list(
        deltas.get("page_order", []), "page_order"
    )

    page_overrides_raw = deltas.get("page_overrides", {})
    if not isinstance(page_overrides_raw, dict):
        raise InvalidEdgePanelShape("page_overrides must be a dict")
    page_overrides: dict[str, dict] = {}
    for page_id, po in page_overrides_raw.items():
        if not isinstance(page_id, str) or not page_id:
            raise InvalidEdgePanelShape(
                "page_overrides keys must be non-empty strings"
            )
        # Write-time orphan rejection: page_id must exist in template
        # pages OR in additional_pages we're about to persist.
        if (
            page_id not in template_page_ids
            and page_id not in seen_add_page_ids
        ):
            raise InvalidEdgePanelShape(
                f"page_overrides[{page_id!r}]: page_id is not present in "
                f"template pages or additional_pages"
            )
        page_overrides[page_id] = _validate_page_override(po, page_id=page_id)

    return {
        "hidden_page_ids": hidden_page_ids,
        "additional_pages": additional_pages,
        "page_order": page_order,
        "page_overrides": page_overrides,
    }


# ─── Lookup ──────────────────────────────────────────────────────


def get_composition_by_tenant_template(
    db: Session,
    tenant_id: str,
    template_id: str,
) -> EdgePanelComposition | None:
    """Active row at (tenant_id, template_id). None when no fork
    exists (pre-lazy-fork state)."""
    return (
        db.query(EdgePanelComposition)
        .filter(
            EdgePanelComposition.tenant_id == tenant_id,
            EdgePanelComposition.inherits_from_template_id == template_id,
            EdgePanelComposition.is_active.is_(True),
        )
        .first()
    )


def get_composition_by_id(
    db: Session, composition_id: str
) -> EdgePanelComposition | None:
    return (
        db.query(EdgePanelComposition)
        .filter(EdgePanelComposition.id == composition_id)
        .first()
    )


# ─── Mutation ────────────────────────────────────────────────────


def upsert_composition(
    db: Session,
    *,
    tenant_id: str,
    template_id: str,
    deltas: Mapping[str, Any] | None = None,
    canvas_config_overrides: Mapping[str, Any] | None = None,
    updated_by: str | None = None,
) -> EdgePanelComposition:
    """Lazy-fork write: create row if none exists at (tenant_id,
    template_id), otherwise version-bump the existing active row.
    """
    if not isinstance(tenant_id, str) or not tenant_id:
        raise InvalidEdgePanelShape(
            "tenant_id must be a non-empty string"
        )
    template = get_template_by_id(db, template_id)
    if template is None:
        raise EdgePanelTemplateNotFound(template_id)
    if not template.is_active:
        raise InvalidEdgePanelShape(
            f"template {template_id!r} is inactive; composition must "
            f"reference the active template version"
        )

    template_page_ids = {
        (p or {}).get("page_id")
        for p in (template.pages or [])
        if isinstance(p, dict)
    }
    template_page_ids.discard(None)

    deltas_validated = _validate_deltas(
        deltas, template_page_ids=template_page_ids  # type: ignore[arg-type]
    )

    cfg = dict(canvas_config_overrides or {})
    if not isinstance(cfg, dict):
        raise InvalidEdgePanelShape(
            "canvas_config_overrides must be a dict"
        )

    existing = get_composition_by_tenant_template(db, tenant_id, template_id)
    next_version = 1
    if existing is not None:
        existing.is_active = False
        next_version = existing.version + 1

    new_row = EdgePanelComposition(
        tenant_id=tenant_id,
        inherits_from_template_id=template.id,
        inherits_from_template_version=template.version,
        deltas=deltas_validated,
        canvas_config_overrides=cfg,
        version=next_version,
        is_active=True,
        created_by=updated_by,
        updated_by=updated_by,
    )
    db.add(new_row)
    db.commit()
    db.refresh(new_row)
    return new_row


def reset_composition(
    db: Session,
    tenant_id: str,
    template_id: str,
    updated_by: str | None = None,
) -> EdgePanelComposition:
    """Clear all deltas + canvas_config_overrides. The row stays
    (audit) but is a no-op delta at resolve time. Raises if no
    composition exists."""
    existing = get_composition_by_tenant_template(db, tenant_id, template_id)
    if existing is None:
        raise EdgePanelCompositionNotFound(
            f"no active composition for tenant={tenant_id} template={template_id}"
        )
    return upsert_composition(
        db,
        tenant_id=tenant_id,
        template_id=template_id,
        deltas=None,
        canvas_config_overrides={},
        updated_by=updated_by,
    )


def _reload_composition(db, composition_id: str) -> EdgePanelComposition:
    row = get_composition_by_id(db, composition_id)
    if row is None:
        raise EdgePanelCompositionNotFound(composition_id)
    return row


def reset_page(
    db: Session,
    composition_id: str,
    page_id: str,
    updated_by: str | None = None,
) -> EdgePanelComposition:
    """Remove one entry from `deltas.page_overrides[<page_id>]`. The
    composition row is version-bumped. If `page_overrides[<page_id>]`
    didn't exist, the call is a no-op write (still version-bumps —
    user pressed reset, treat as audit event)."""
    existing = _reload_composition(db, composition_id)
    deltas = dict(existing.deltas or {})
    page_overrides = dict(deltas.get("page_overrides") or {})
    page_overrides.pop(page_id, None)
    deltas["page_overrides"] = page_overrides

    return upsert_composition(
        db,
        tenant_id=existing.tenant_id,
        template_id=existing.inherits_from_template_id,
        deltas=deltas,
        canvas_config_overrides=dict(existing.canvas_config_overrides or {}),
        updated_by=updated_by,
    )


def reset_placement(
    db: Session,
    composition_id: str,
    page_id: str,
    placement_id: str,
    updated_by: str | None = None,
) -> EdgePanelComposition:
    """Remove per-placement entries within `deltas.page_overrides[<page_id>]`:
      - `hidden_placement_ids` removes matching entries
      - `placement_geometry_overrides` removes the key
      - `placement_order` removes matching entries

    `additional_placements` entries with the matching placement_id are
    NOT removed — those are tenant-authored content (distinct from
    "reset this inherited placement's tenant customization"). Mirrors
    the focus_compositions_service.reset_placement_to_default semantics.

    Version-bumps. If no matching entries existed, still version-bumps
    (treat as audit event).
    """
    existing = _reload_composition(db, composition_id)
    deltas = dict(existing.deltas or {})
    page_overrides = dict(deltas.get("page_overrides") or {})
    if page_id in page_overrides:
        po = dict(page_overrides[page_id] or {})
        po["hidden_placement_ids"] = [
            pid
            for pid in (po.get("hidden_placement_ids") or [])
            if pid != placement_id
        ]
        po["placement_geometry_overrides"] = {
            pid: g
            for pid, g in (po.get("placement_geometry_overrides") or {}).items()
            if pid != placement_id
        }
        po["placement_order"] = [
            pid
            for pid in (po.get("placement_order") or [])
            if pid != placement_id
        ]
        page_overrides[page_id] = po
    deltas["page_overrides"] = page_overrides
    flag_modified(existing, "deltas")

    return upsert_composition(
        db,
        tenant_id=existing.tenant_id,
        template_id=existing.inherits_from_template_id,
        deltas=deltas,
        canvas_config_overrides=dict(existing.canvas_config_overrides or {}),
        updated_by=updated_by,
    )
