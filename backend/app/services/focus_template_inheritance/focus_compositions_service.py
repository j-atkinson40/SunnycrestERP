"""Tier 3 — Focus Composition service.

Per-tenant delta over a chosen Tier 2 FocusTemplate. Greenfield
repurpose of the May 2026 focus_compositions table.

Storage shape: DELTAS only — hidden_placement_ids,
additional_placements, placement_order, placement_geometry_overrides,
core_geometry_override. The composition does NOT redeclare the
template; the resolver walks template → composition and materializes
the effective layout at READ time.

Lazy-fork lifecycle (locked decision 3): no row exists for a tenant
until they first edit. `create_or_update_composition` is the only
write surface and handles both first-edit and subsequent-edit. The
resolver gracefully handles "tenant has no row" by falling back to
the Tier 2 template directly.

`inherits_from_template_version` is captured from the live active
template at write time. v1 resolver IGNORES it (live cascade); v2
versioned cascade lands additively.

Core geometry override clamps to core's min_column_span /
max_column_span (out-of-bounds raises). Accessory geometry overrides
clamp to "starting_column + column_span <= 12" (the canvas is always
12-column at the composition level; per-row column_count constraints
live at Tier 2's row metadata).
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping

from sqlalchemy.orm import Session

from app.models.focus_composition import FocusComposition
from app.models.focus_core import FocusCore
from app.models.focus_template import FocusTemplate
from app.services.focus_template_inheritance.focus_cores_service import (
    CoreNotFound,
)
from app.services.focus_template_inheritance.focus_templates_service import (
    TemplateNotFound,
    get_template_by_id,
)


logger = logging.getLogger(__name__)


# ─── Exceptions ──────────────────────────────────────────────────


class FocusCompositionError(Exception):
    """Base for Tier 3 composition service errors."""


class CompositionNotFound(FocusCompositionError):
    pass


class InvalidCompositionShape(FocusCompositionError):
    pass


# ─── Validation helpers ──────────────────────────────────────────


_ALLOWED_DELTA_KEYS: tuple[str, ...] = (
    "hidden_placement_ids",
    "additional_placements",
    "placement_order",
    "placement_geometry_overrides",
    "core_geometry_override",
)


def _validate_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise InvalidCompositionShape(f"{field} must be an integer")
    return value


def _validate_str_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise InvalidCompositionShape(f"{field} must be a list of strings")
    out: list[str] = []
    for i, v in enumerate(value):
        if not isinstance(v, str) or not v:
            raise InvalidCompositionShape(
                f"{field}[{i}] must be a non-empty string"
            )
        out.append(v)
    return out


def _validate_additional_placement(p: Any, *, index: int) -> dict:
    if not isinstance(p, dict):
        raise InvalidCompositionShape(
            f"additional_placements[{index}] must be a dict"
        )
    pid = p.get("placement_id")
    if not isinstance(pid, str) or not pid:
        raise InvalidCompositionShape(
            f"additional_placements[{index}]: placement_id must be a "
            f"non-empty string"
        )
    kind = p.get("component_kind")
    if not isinstance(kind, str) or not kind:
        raise InvalidCompositionShape(
            f"additional_placements[{index}] {pid!r}: component_kind "
            f"must be a non-empty string"
        )
    name = p.get("component_name")
    if not isinstance(name, str) or not name:
        raise InvalidCompositionShape(
            f"additional_placements[{index}] {pid!r}: component_name "
            f"must be a non-empty string"
        )
    starting_column = _validate_int(
        p.get("starting_column"),
        f"additional_placements[{index}] {pid!r}.starting_column",
    )
    column_span = _validate_int(
        p.get("column_span"),
        f"additional_placements[{index}] {pid!r}.column_span",
    )
    if starting_column < 0:
        raise InvalidCompositionShape(
            f"additional_placements[{index}] {pid!r}: starting_column "
            f"must be >= 0"
        )
    if column_span < 1:
        raise InvalidCompositionShape(
            f"additional_placements[{index}] {pid!r}: column_span must be >= 1"
        )
    if starting_column + column_span > 12:
        raise InvalidCompositionShape(
            f"additional_placements[{index}] {pid!r}: starting_column + "
            f"column_span exceeds 12-column canvas"
        )
    if "row_index" in p:
        row_index = p.get("row_index")
        if not isinstance(row_index, int) or isinstance(row_index, bool) or row_index < 0:
            raise InvalidCompositionShape(
                f"additional_placements[{index}] {pid!r}: row_index must "
                f"be a non-negative integer"
            )
    if "prop_overrides" in p and not isinstance(p["prop_overrides"], dict):
        raise InvalidCompositionShape(
            f"additional_placements[{index}] {pid!r}: prop_overrides "
            f"must be a dict"
        )
    if "display_config" in p and not isinstance(p["display_config"], dict):
        raise InvalidCompositionShape(
            f"additional_placements[{index}] {pid!r}: display_config "
            f"must be a dict"
        )
    return dict(p)


def _validate_geometry_overrides(value: Any) -> dict[str, dict]:
    if not isinstance(value, dict):
        raise InvalidCompositionShape(
            "placement_geometry_overrides must be a dict"
        )
    out: dict[str, dict] = {}
    for pid, geom in value.items():
        if not isinstance(pid, str) or not pid:
            raise InvalidCompositionShape(
                "placement_geometry_overrides keys must be non-empty strings"
            )
        if not isinstance(geom, dict):
            raise InvalidCompositionShape(
                f"placement_geometry_overrides[{pid!r}] must be a dict"
            )
        starting_column = _validate_int(
            geom.get("starting_column"),
            f"placement_geometry_overrides[{pid!r}].starting_column",
        )
        column_span = _validate_int(
            geom.get("column_span"),
            f"placement_geometry_overrides[{pid!r}].column_span",
        )
        if starting_column < 0:
            raise InvalidCompositionShape(
                f"placement_geometry_overrides[{pid!r}]: starting_column "
                f"must be >= 0"
            )
        if column_span < 1:
            raise InvalidCompositionShape(
                f"placement_geometry_overrides[{pid!r}]: column_span "
                f"must be >= 1"
            )
        if starting_column + column_span > 12:
            raise InvalidCompositionShape(
                f"placement_geometry_overrides[{pid!r}]: starting_column "
                f"+ column_span exceeds 12-column canvas"
            )
        out[pid] = {
            "starting_column": starting_column,
            "column_span": column_span,
        }
    return out


def _validate_core_geometry_override(value: Any, *, core: FocusCore) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise InvalidCompositionShape(
            "core_geometry_override must be a dict or null"
        )
    starting_column = _validate_int(
        value.get("starting_column"),
        "core_geometry_override.starting_column",
    )
    column_span = _validate_int(
        value.get("column_span"),
        "core_geometry_override.column_span",
    )
    row_index = _validate_int(
        value.get("row_index"),
        "core_geometry_override.row_index",
    )
    if starting_column < 0:
        raise InvalidCompositionShape(
            "core_geometry_override.starting_column must be >= 0"
        )
    if row_index < 0:
        raise InvalidCompositionShape(
            "core_geometry_override.row_index must be >= 0"
        )
    if column_span < core.min_column_span or column_span > core.max_column_span:
        raise InvalidCompositionShape(
            f"core_geometry_override.column_span ({column_span}) must be "
            f"within core's [min_column_span={core.min_column_span}, "
            f"max_column_span={core.max_column_span}]"
        )
    if starting_column + column_span > 12:
        raise InvalidCompositionShape(
            "core_geometry_override: starting_column + column_span exceeds "
            "12-column canvas"
        )
    return {
        "starting_column": starting_column,
        "column_span": column_span,
        "row_index": row_index,
    }


def _validate_deltas(deltas: Any, *, core: FocusCore) -> dict:
    """Normalize + validate the deltas blob. Returns a fresh dict
    suitable for JSONB persistence. Unknown keys are rejected
    (forward-compat: new delta capabilities require schema bumps
    here)."""
    if deltas is None:
        return {
            "hidden_placement_ids": [],
            "additional_placements": [],
            "placement_order": [],
            "placement_geometry_overrides": {},
            "core_geometry_override": None,
        }
    if not isinstance(deltas, dict):
        raise InvalidCompositionShape("deltas must be a dict or null")

    for key in deltas.keys():
        if key not in _ALLOWED_DELTA_KEYS:
            raise InvalidCompositionShape(
                f"unknown delta key {key!r}; allowed: {_ALLOWED_DELTA_KEYS}"
            )

    hidden = _validate_str_list(
        deltas.get("hidden_placement_ids", []), "hidden_placement_ids"
    )
    additional_raw = deltas.get("additional_placements", [])
    if not isinstance(additional_raw, list):
        raise InvalidCompositionShape(
            "additional_placements must be a list"
        )
    additional: list[dict] = []
    seen_additional_ids: set[str] = set()
    for i, p in enumerate(additional_raw):
        validated = _validate_additional_placement(p, index=i)
        pid = validated["placement_id"]
        if pid in seen_additional_ids:
            raise InvalidCompositionShape(
                f"additional_placements: duplicate placement_id {pid!r}"
            )
        seen_additional_ids.add(pid)
        additional.append(validated)
    order = _validate_str_list(
        deltas.get("placement_order", []), "placement_order"
    )
    geometry_overrides = _validate_geometry_overrides(
        deltas.get("placement_geometry_overrides", {})
    )
    core_override = _validate_core_geometry_override(
        deltas.get("core_geometry_override"), core=core
    )

    return {
        "hidden_placement_ids": hidden,
        "additional_placements": additional,
        "placement_order": order,
        "placement_geometry_overrides": geometry_overrides,
        "core_geometry_override": core_override,
    }


# ─── Lookup ──────────────────────────────────────────────────────


def get_composition_by_tenant_template(
    db: Session,
    tenant_id: str,
    template_id: str,
) -> FocusComposition | None:
    """Active row at (tenant_id, template_id). None when no fork
    exists (pre-lazy-fork state)."""
    return (
        db.query(FocusComposition)
        .filter(
            FocusComposition.tenant_id == tenant_id,
            FocusComposition.inherits_from_template_id == template_id,
            FocusComposition.is_active.is_(True),
        )
        .first()
    )


def get_composition_by_id(
    db: Session, composition_id: str
) -> FocusComposition | None:
    return (
        db.query(FocusComposition)
        .filter(FocusComposition.id == composition_id)
        .first()
    )


# ─── Mutation ────────────────────────────────────────────────────


def create_or_update_composition(
    db: Session,
    *,
    tenant_id: str,
    template_id: str,
    deltas: Mapping[str, Any] | None = None,
    canvas_config_overrides: Mapping[str, Any] | None = None,
    updated_by: str | None = None,
) -> FocusComposition:
    """Lazy-fork write: create row if none exists at (tenant_id,
    template_id), otherwise version-bump the existing active row.
    """
    if not isinstance(tenant_id, str) or not tenant_id:
        raise InvalidCompositionShape(
            "tenant_id must be a non-empty string"
        )
    template = get_template_by_id(db, template_id)
    if template is None:
        raise TemplateNotFound(template_id)
    if not template.is_active:
        raise InvalidCompositionShape(
            f"template {template_id!r} is inactive; composition must "
            f"reference the active template version"
        )

    core = (
        db.query(FocusCore)
        .filter(FocusCore.id == template.inherits_from_core_id)
        .first()
    )
    if core is None:
        raise CoreNotFound(template.inherits_from_core_id)

    deltas_validated = _validate_deltas(deltas, core=core)

    cfg = dict(canvas_config_overrides or {})
    if not isinstance(cfg, dict):
        raise InvalidCompositionShape(
            "canvas_config_overrides must be a dict"
        )

    existing = get_composition_by_tenant_template(db, tenant_id, template_id)
    next_version = 1
    if existing is not None:
        existing.is_active = False
        next_version = existing.version + 1

    new_row = FocusComposition(
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


def reset_composition_to_default(
    db: Session,
    tenant_id: str,
    template_id: str,
    updated_by: str | None = None,
) -> FocusComposition:
    """Clear all deltas + canvas_config_overrides. The row stays
    (audit) but is a no-op delta at resolve time. Raises if no
    composition exists — caller should check + handle the "tenant
    never customized" case."""
    existing = get_composition_by_tenant_template(db, tenant_id, template_id)
    if existing is None:
        raise CompositionNotFound(
            f"no active composition for tenant={tenant_id} template={template_id}"
        )
    return create_or_update_composition(
        db,
        tenant_id=tenant_id,
        template_id=template_id,
        deltas=None,
        canvas_config_overrides={},
        updated_by=updated_by,
    )


def reset_placement_to_default(
    db: Session,
    tenant_id: str,
    template_id: str,
    placement_id: str,
    updated_by: str | None = None,
) -> FocusComposition:
    """Clear matching entries from `deltas.hidden_placement_ids` +
    `deltas.placement_geometry_overrides` + `deltas.placement_order`.
    `additional_placements` entries with this placement_id are NOT
    removed — those are tenant-authored content, distinct from "reset
    this inherited placement's tenant customization."""
    existing = get_composition_by_tenant_template(db, tenant_id, template_id)
    if existing is None:
        raise CompositionNotFound(
            f"no active composition for tenant={tenant_id} template={template_id}"
        )

    deltas = dict(existing.deltas or {})
    hidden = [
        pid
        for pid in deltas.get("hidden_placement_ids", [])
        if pid != placement_id
    ]
    overrides = {
        pid: geom
        for pid, geom in (deltas.get("placement_geometry_overrides") or {}).items()
        if pid != placement_id
    }
    order = [pid for pid in deltas.get("placement_order", []) if pid != placement_id]
    deltas["hidden_placement_ids"] = hidden
    deltas["placement_geometry_overrides"] = overrides
    deltas["placement_order"] = order

    return create_or_update_composition(
        db,
        tenant_id=tenant_id,
        template_id=template_id,
        deltas=deltas,
        canvas_config_overrides=dict(existing.canvas_config_overrides or {}),
        updated_by=updated_by,
    )
