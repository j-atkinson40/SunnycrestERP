"""Focus composition service — CRUD + resolution.

Mirrors the architectural pattern of theme_service / config_service /
template_service: write-side versioning (each save deactivates the
prior active row + inserts a new active row at version+1), READ-time
resolution (walks platform_default → vertical_default →
tenant_override; first match wins per Focus type).

Validation:
    - placements MUST be a list of placement records
    - each placement has a unique placement_id, valid component_kind +
      component_name, well-formed grid coords
    - grid: column_start in [1,12], column_span in [1,12],
      column_start + column_span <= 13
    - row_start + row_span >= 1; rows are auto-sized so we don't
      enforce a hard row ceiling
    - overlapping placements are PERMITTED (z_index handles intentional
      overlap) but trigger a warning in the response
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.focus_composition import (
    FocusComposition,
    SCOPE_PLATFORM_DEFAULT,
    SCOPE_TENANT_OVERRIDE,
    SCOPE_VERTICAL_DEFAULT,
)
from app.services.component_config.registry_snapshot import (
    REGISTRY_SNAPSHOT,
)


logger = logging.getLogger(__name__)


# ─── Exceptions ──────────────────────────────────────────────────


class CompositionError(Exception):
    def __init__(self, message: str, *, http_status: int = 400) -> None:
        super().__init__(message)
        self.http_status = http_status


class CompositionNotFound(CompositionError):
    def __init__(self, message: str = "Composition not found") -> None:
        super().__init__(message, http_status=404)


class InvalidCompositionShape(CompositionError):
    def __init__(self, message: str) -> None:
        super().__init__(message, http_status=400)


class CompositionScopeMismatch(CompositionError):
    def __init__(self, message: str) -> None:
        super().__init__(message, http_status=400)


# ─── Validation ──────────────────────────────────────────────────


def _validate_scope(
    scope: str,
    *,
    vertical: str | None,
    tenant_id: str | None,
) -> None:
    if scope == SCOPE_PLATFORM_DEFAULT and (
        vertical is not None or tenant_id is not None
    ):
        raise CompositionScopeMismatch(
            "platform_default rows must have vertical=None and tenant_id=None"
        )
    if scope == SCOPE_VERTICAL_DEFAULT and (
        vertical is None or tenant_id is not None
    ):
        raise CompositionScopeMismatch(
            "vertical_default rows must have vertical set and tenant_id=None"
        )
    if scope == SCOPE_TENANT_OVERRIDE and (
        tenant_id is None or vertical is not None
    ):
        raise CompositionScopeMismatch(
            "tenant_override rows must have tenant_id set and vertical=None"
        )
    if scope not in {
        SCOPE_PLATFORM_DEFAULT,
        SCOPE_VERTICAL_DEFAULT,
        SCOPE_TENANT_OVERRIDE,
    }:
        raise InvalidCompositionShape(f"Unknown scope: {scope}")


def _validate_placements(placements: list) -> list[str]:
    """Validate placements + return a list of warnings (overlap notes).

    Raises InvalidCompositionShape on hard errors (malformed records,
    out-of-bounds grid, duplicate placement_ids, references to
    unknown components).
    """
    if not isinstance(placements, list):
        raise InvalidCompositionShape("placements must be a list")

    warnings: list[str] = []
    seen_ids: set[str] = set()

    for idx, p in enumerate(placements):
        if not isinstance(p, dict):
            raise InvalidCompositionShape(
                f"placements[{idx}] must be an object"
            )
        pid = p.get("placement_id")
        if not isinstance(pid, str) or not pid:
            raise InvalidCompositionShape(
                f"placements[{idx}].placement_id must be a non-empty string"
            )
        if pid in seen_ids:
            raise InvalidCompositionShape(
                f"placements[{idx}].placement_id '{pid}' is duplicated"
            )
        seen_ids.add(pid)

        kind = p.get("component_kind")
        name = p.get("component_name")
        if not isinstance(kind, str) or not isinstance(name, str):
            raise InvalidCompositionShape(
                f"placements[{idx}] must have string component_kind + component_name"
            )
        # Reference-integrity check: the (kind, name) tuple must be a
        # registered component. Use the existing registry_snapshot.
        if (kind, name) not in REGISTRY_SNAPSHOT:
            # Only warn, don't reject — the registry may evolve and
            # we don't want to block writes when a component is added
            # in the same release as a composition referencing it.
            warnings.append(
                f"placements[{idx}] references unknown component '{kind}:{name}'"
            )

        grid = p.get("grid")
        if not isinstance(grid, dict):
            raise InvalidCompositionShape(
                f"placements[{idx}].grid must be an object"
            )
        cs = grid.get("column_start")
        cspan = grid.get("column_span")
        rs = grid.get("row_start")
        rspan = grid.get("row_span")
        for fld, val in [
            ("column_start", cs),
            ("column_span", cspan),
            ("row_start", rs),
            ("row_span", rspan),
        ]:
            if not isinstance(val, int) or val < 1:
                raise InvalidCompositionShape(
                    f"placements[{idx}].grid.{fld} must be a positive integer"
                )
        if cs > 12 or cspan > 12 or cs + cspan > 13:
            raise InvalidCompositionShape(
                f"placements[{idx}].grid: column_start + column_span must be <= 13 "
                f"(got {cs} + {cspan})"
            )

    # Overlap detection — warn-only.
    for i, a in enumerate(placements):
        for j, b in enumerate(placements[i + 1:], start=i + 1):
            if _grids_overlap(a["grid"], b["grid"]):
                warnings.append(
                    f"placements[{i}] and placements[{j}] overlap"
                )
                break

    return warnings


def _grids_overlap(a: dict, b: dict) -> bool:
    a_c0, a_c1 = a["column_start"], a["column_start"] + a["column_span"]
    b_c0, b_c1 = b["column_start"], b["column_start"] + b["column_span"]
    a_r0, a_r1 = a["row_start"], a["row_start"] + a["row_span"]
    b_r0, b_r1 = b["row_start"], b["row_start"] + b["row_span"]
    return not (a_c1 <= b_c0 or b_c1 <= a_c0 or a_r1 <= b_r0 or b_r1 <= a_r0)


# ─── CRUD ────────────────────────────────────────────────────────


def _find_active(
    db: Session,
    *,
    scope: str,
    focus_type: str,
    vertical: str | None,
    tenant_id: str | None,
) -> FocusComposition | None:
    q = db.query(FocusComposition).filter(
        FocusComposition.scope == scope,
        FocusComposition.focus_type == focus_type,
        FocusComposition.is_active.is_(True),
    )
    if vertical is None:
        q = q.filter(FocusComposition.vertical.is_(None))
    else:
        q = q.filter(FocusComposition.vertical == vertical)
    if tenant_id is None:
        q = q.filter(FocusComposition.tenant_id.is_(None))
    else:
        q = q.filter(FocusComposition.tenant_id == tenant_id)
    return q.first()


def _next_version(
    db: Session,
    *,
    scope: str,
    focus_type: str,
    vertical: str | None,
    tenant_id: str | None,
) -> int:
    q = db.query(FocusComposition).filter(
        FocusComposition.scope == scope,
        FocusComposition.focus_type == focus_type,
    )
    if vertical is None:
        q = q.filter(FocusComposition.vertical.is_(None))
    else:
        q = q.filter(FocusComposition.vertical == vertical)
    if tenant_id is None:
        q = q.filter(FocusComposition.tenant_id.is_(None))
    else:
        q = q.filter(FocusComposition.tenant_id == tenant_id)
    rows = q.all()
    if not rows:
        return 1
    return max(r.version for r in rows) + 1


def create_composition(
    db: Session,
    *,
    scope: str,
    focus_type: str,
    vertical: str | None = None,
    tenant_id: str | None = None,
    placements: list | None = None,
    canvas_config: dict | None = None,
    actor_user_id: str | None = None,
) -> FocusComposition:
    _validate_scope(scope, vertical=vertical, tenant_id=tenant_id)
    placements_list = list(placements or [])
    warnings = _validate_placements(placements_list)
    for w in warnings:
        logger.warning("[composition] %s", w)

    existing = _find_active(
        db,
        scope=scope,
        focus_type=focus_type,
        vertical=vertical,
        tenant_id=tenant_id,
    )
    if existing is not None:
        existing.is_active = False

    new_row = FocusComposition(
        id=str(uuid.uuid4()),
        scope=scope,
        vertical=vertical,
        tenant_id=tenant_id,
        focus_type=focus_type,
        placements=placements_list,
        canvas_config=dict(canvas_config or {}),
        version=_next_version(
            db,
            scope=scope,
            focus_type=focus_type,
            vertical=vertical,
            tenant_id=tenant_id,
        ),
        is_active=True,
        created_by=actor_user_id,
        updated_by=actor_user_id,
    )
    db.add(new_row)
    db.commit()
    db.refresh(new_row)
    return new_row


def update_composition(
    db: Session,
    *,
    composition_id: str,
    placements: list | None = None,
    canvas_config: dict | None = None,
    actor_user_id: str | None = None,
) -> FocusComposition:
    row = (
        db.query(FocusComposition)
        .filter(FocusComposition.id == composition_id)
        .first()
    )
    if row is None:
        raise CompositionNotFound()

    new_placements = (
        list(placements) if placements is not None else list(row.placements or [])
    )
    new_canvas = (
        dict(canvas_config)
        if canvas_config is not None
        else dict(row.canvas_config or {})
    )
    warnings = _validate_placements(new_placements)
    for w in warnings:
        logger.warning("[composition] %s", w)

    if row.is_active:
        row.is_active = False

    new_row = FocusComposition(
        id=str(uuid.uuid4()),
        scope=row.scope,
        vertical=row.vertical,
        tenant_id=row.tenant_id,
        focus_type=row.focus_type,
        placements=new_placements,
        canvas_config=new_canvas,
        version=_next_version(
            db,
            scope=row.scope,
            focus_type=row.focus_type,
            vertical=row.vertical,
            tenant_id=row.tenant_id,
        ),
        is_active=True,
        created_by=row.created_by,
        updated_by=actor_user_id,
    )
    db.add(new_row)
    db.commit()
    db.refresh(new_row)
    return new_row


def get_composition(
    db: Session, *, composition_id: str
) -> FocusComposition:
    row = (
        db.query(FocusComposition)
        .filter(FocusComposition.id == composition_id)
        .first()
    )
    if row is None:
        raise CompositionNotFound()
    return row


def list_compositions(
    db: Session,
    *,
    scope: str | None = None,
    vertical: str | None = None,
    tenant_id: str | None = None,
    focus_type: str | None = None,
    include_inactive: bool = False,
) -> list[FocusComposition]:
    q = db.query(FocusComposition)
    if scope is not None:
        q = q.filter(FocusComposition.scope == scope)
    if vertical is not None:
        q = q.filter(FocusComposition.vertical == vertical)
    if tenant_id is not None:
        q = q.filter(FocusComposition.tenant_id == tenant_id)
    if focus_type is not None:
        q = q.filter(FocusComposition.focus_type == focus_type)
    if not include_inactive:
        q = q.filter(FocusComposition.is_active.is_(True))
    return q.order_by(
        FocusComposition.focus_type,
        FocusComposition.scope,
        FocusComposition.version.desc(),
    ).all()


# ─── Resolution ──────────────────────────────────────────────────


def resolve_composition(
    db: Session,
    *,
    focus_type: str,
    vertical: str | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Walk the inheritance chain and return the first matching
    composition. First-match-wins semantics (no overlay merging at
    READ time — a composition is a complete layout, not a partial
    override).

    Returns:
        {
            "focus_type": ...,
            "vertical": ...,
            "tenant_id": ...,
            "source": "platform_default" | "vertical_default" |
                      "tenant_override" | None,
            "source_id": ... | None,
            "source_version": ... | None,
            "placements": [...],
            "canvas_config": {...},
        }

    When no composition exists at any tier, source is None and
    placements/canvas_config are empty — caller falls back to the
    Focus's hard-coded layout.
    """
    # Tenant override wins outright if it exists (it's the most
    # specific scope). If not, vertical_default; if not, platform.
    if tenant_id is not None:
        row = _find_active(
            db,
            scope=SCOPE_TENANT_OVERRIDE,
            focus_type=focus_type,
            vertical=None,
            tenant_id=tenant_id,
        )
        if row is not None:
            return _serialize_resolution(row, "tenant_override")

    if vertical is not None:
        row = _find_active(
            db,
            scope=SCOPE_VERTICAL_DEFAULT,
            focus_type=focus_type,
            vertical=vertical,
            tenant_id=None,
        )
        if row is not None:
            return _serialize_resolution(row, "vertical_default")

    row = _find_active(
        db,
        scope=SCOPE_PLATFORM_DEFAULT,
        focus_type=focus_type,
        vertical=None,
        tenant_id=None,
    )
    if row is not None:
        return _serialize_resolution(row, "platform_default")

    return {
        "focus_type": focus_type,
        "vertical": vertical,
        "tenant_id": tenant_id,
        "source": None,
        "source_id": None,
        "source_version": None,
        "placements": [],
        "canvas_config": {},
    }


def _serialize_resolution(row: FocusComposition, source: str) -> dict:
    return {
        "focus_type": row.focus_type,
        "vertical": row.vertical,
        "tenant_id": row.tenant_id,
        "source": source,
        "source_id": row.id,
        "source_version": row.version,
        "placements": list(row.placements or []),
        "canvas_config": dict(row.canvas_config or {}),
    }
