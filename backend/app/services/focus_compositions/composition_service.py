"""Focus composition service — CRUD + resolution (R-3.0 rows shape).

Mirrors the architectural pattern of theme_service / config_service /
template_service: write-side versioning (each save deactivates the
prior active row + inserts a new active row at version+1), READ-time
resolution (walks platform_default → vertical_default →
tenant_override; first match wins per Focus type).

R-3.0 schema — composition is a sequence of rows. Each row declares its
own column_count and carries its own placements:

    rows: list[Row]
    Row = {
        "row_id": str,                # UUID; stable across edits
        "column_count": int 1..12,
        "row_height": "auto" | int,
        "column_widths": list[float] | None,   # extension point; null today
        "nested_rows": list[Row] | None,       # extension point; null today
        "placements": list[Placement],
    }
    Placement = {
        "placement_id": str,
        "component_kind": str,
        "component_name": str,
        "starting_column": int 0..(column_count-1),
        "column_span": int 1..(column_count - starting_column),
        "prop_overrides": dict,
        "display_config": {"show_header": bool?, "show_border": bool?, "z_index": int?},
        "nested_rows": list[Row] | None,       # extension point; null today
    }

Validation:
    - rows must be a list (may be empty)
    - each row has unique row_id; column_count in [1,12]; row_height
      either positive int or "auto"
    - placements within a row fit within column_count: starting_column
      in [0, column_count-1] AND starting_column + column_span <= column_count
    - placement_ids unique across the entire composition (prevents
      editor drag-drop reuse confusion)
    - nested_rows + column_widths accepted as null OR validated lists
      (logged warning when non-null in R-3.0 — extension points are
      schema-permitted but application logic ignores them)

Pre-R-3.0 flat-placements payload (no `rows` key, has top-level
`placements` array) is rejected at the API boundary with a clear
error directing the caller to the rows-shaped payload. The DB columns
remain (one-release grace) but the service layer authors via `rows`
exclusively.
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


_MIN_COLUMN_COUNT = 1
_MAX_COLUMN_COUNT = 12


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


class LegacyPayloadRejected(CompositionError):
    """Rejects pre-R-3.0 flat-placements payloads.

    Callers must now send `rows`. This helps the API surface a clear
    error rather than silently dropping the legacy payload during the
    R-3.0 → R-3.2 deprecation window.
    """

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


def _validate_rows(rows: list) -> list[str]:
    """Validate rows shape + return a list of warnings.

    Raises InvalidCompositionShape on hard errors (malformed records,
    out-of-bounds column_count or starting_column/column_span,
    duplicate row_ids OR duplicate placement_ids, references to
    unknown components).
    """
    if not isinstance(rows, list):
        raise InvalidCompositionShape("rows must be a list")

    warnings: list[str] = []
    seen_row_ids: set[str] = set()
    seen_placement_ids: set[str] = set()

    for r_idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise InvalidCompositionShape(
                f"rows[{r_idx}] must be an object"
            )
        row_id = row.get("row_id")
        if not isinstance(row_id, str) or not row_id:
            raise InvalidCompositionShape(
                f"rows[{r_idx}].row_id must be a non-empty string"
            )
        if row_id in seen_row_ids:
            raise InvalidCompositionShape(
                f"rows[{r_idx}].row_id '{row_id}' is duplicated"
            )
        seen_row_ids.add(row_id)

        column_count = row.get("column_count")
        if (
            not isinstance(column_count, int)
            or column_count < _MIN_COLUMN_COUNT
            or column_count > _MAX_COLUMN_COUNT
        ):
            raise InvalidCompositionShape(
                f"rows[{r_idx}].column_count must be an integer in "
                f"[{_MIN_COLUMN_COUNT}, {_MAX_COLUMN_COUNT}] (got {column_count!r})"
            )

        row_height = row.get("row_height", "auto")
        if not (
            row_height == "auto"
            or (isinstance(row_height, int) and row_height > 0)
        ):
            raise InvalidCompositionShape(
                f"rows[{r_idx}].row_height must be 'auto' or a positive integer "
                f"(got {row_height!r})"
            )

        # Variant B + nesting extension points — accept null OR valid
        # shape; in R-3.0 we warn when non-null (application ignores).
        column_widths = row.get("column_widths")
        if column_widths is not None and not isinstance(column_widths, list):
            raise InvalidCompositionShape(
                f"rows[{r_idx}].column_widths must be null or a list of numbers"
            )
        if column_widths is not None:
            warnings.append(
                f"rows[{r_idx}].column_widths is set but ignored in R-3.0 "
                f"(Variant B extension reserved for future activation)"
            )

        nested_rows = row.get("nested_rows")
        if nested_rows is not None and not isinstance(nested_rows, list):
            raise InvalidCompositionShape(
                f"rows[{r_idx}].nested_rows must be null or a list"
            )
        if nested_rows is not None:
            warnings.append(
                f"rows[{r_idx}].nested_rows is set but ignored in R-3.0 "
                f"(bounded-nesting extension reserved for future activation)"
            )

        placements = row.get("placements")
        if not isinstance(placements, list):
            raise InvalidCompositionShape(
                f"rows[{r_idx}].placements must be a list"
            )

        for p_idx, p in enumerate(placements):
            if not isinstance(p, dict):
                raise InvalidCompositionShape(
                    f"rows[{r_idx}].placements[{p_idx}] must be an object"
                )
            pid = p.get("placement_id")
            if not isinstance(pid, str) or not pid:
                raise InvalidCompositionShape(
                    f"rows[{r_idx}].placements[{p_idx}].placement_id "
                    f"must be a non-empty string"
                )
            if pid in seen_placement_ids:
                raise InvalidCompositionShape(
                    f"rows[{r_idx}].placements[{p_idx}].placement_id "
                    f"'{pid}' is duplicated within composition"
                )
            seen_placement_ids.add(pid)

            kind = p.get("component_kind")
            name = p.get("component_name")
            if not isinstance(kind, str) or not isinstance(name, str):
                raise InvalidCompositionShape(
                    f"rows[{r_idx}].placements[{p_idx}] must have string "
                    f"component_kind + component_name"
                )
            if (kind, name) not in REGISTRY_SNAPSHOT:
                # Warn-only: registry can evolve in step with composition
                # writes; we don't want to block.
                warnings.append(
                    f"rows[{r_idx}].placements[{p_idx}] references unknown "
                    f"component '{kind}:{name}'"
                )

            sc = p.get("starting_column")
            cspan = p.get("column_span")
            if not isinstance(sc, int) or sc < 0:
                raise InvalidCompositionShape(
                    f"rows[{r_idx}].placements[{p_idx}].starting_column "
                    f"must be a non-negative integer (0-indexed)"
                )
            if not isinstance(cspan, int) or cspan < 1:
                raise InvalidCompositionShape(
                    f"rows[{r_idx}].placements[{p_idx}].column_span "
                    f"must be a positive integer"
                )
            if sc + cspan > column_count:
                raise InvalidCompositionShape(
                    f"rows[{r_idx}].placements[{p_idx}]: starting_column "
                    f"+ column_span must be <= row.column_count "
                    f"({sc} + {cspan} > {column_count})"
                )

            # Per-placement nested_rows extension point — accept null only.
            p_nested = p.get("nested_rows")
            if p_nested is not None and not isinstance(p_nested, list):
                raise InvalidCompositionShape(
                    f"rows[{r_idx}].placements[{p_idx}].nested_rows "
                    f"must be null or a list"
                )
            if p_nested is not None:
                warnings.append(
                    f"rows[{r_idx}].placements[{p_idx}].nested_rows is set "
                    f"but ignored in R-3.0 (bounded-nesting extension)"
                )

    return warnings


def _normalize_rows(rows: list) -> list[dict]:
    """Defensive normalization — copy each row + each placement so the
    DB row never aliases the caller's mutable list. Auto-generates
    row_id when caller omits it (editor convenience). Auto-fills
    extension-point fields with null.
    """
    normalized: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        new_row: dict[str, Any] = {
            "row_id": row.get("row_id") or str(uuid.uuid4()),
            "column_count": row.get("column_count"),
            "row_height": row.get("row_height", "auto"),
            "column_widths": row.get("column_widths"),
            "nested_rows": row.get("nested_rows"),
            "placements": [],
        }
        for p in row.get("placements") or []:
            if not isinstance(p, dict):
                continue
            new_row["placements"].append(
                {
                    "placement_id": p.get("placement_id"),
                    "component_kind": p.get("component_kind"),
                    "component_name": p.get("component_name"),
                    "starting_column": p.get("starting_column"),
                    "column_span": p.get("column_span"),
                    "prop_overrides": dict(p.get("prop_overrides") or {}),
                    "display_config": dict(p.get("display_config") or {}),
                    "nested_rows": p.get("nested_rows"),
                }
            )
        normalized.append(new_row)
    return normalized


def reject_legacy_placements_payload(body: Any) -> None:
    """API-boundary helper — rejects pre-R-3.0 flat-placements payloads
    with a clear error pointing at the rows-shaped contract.

    A legacy payload is one that:
      - has a top-level `placements` key AND
      - does NOT have a top-level `rows` key.

    Bare `placements` array is non-canonical post-R-3.0 even if non-empty.
    """
    if not isinstance(body, dict):
        return
    if "rows" not in body and "placements" in body:
        raise LegacyPayloadRejected(
            "Pre-R-3.0 flat-placements payload is no longer accepted. "
            "Send a `rows` array instead. See R-3.0 architectural notes for "
            "the rows-based contract."
        )


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
    rows: list | None = None,
    canvas_config: dict | None = None,
    actor_user_id: str | None = None,
) -> FocusComposition:
    _validate_scope(scope, vertical=vertical, tenant_id=tenant_id)
    rows_list = _normalize_rows(list(rows or []))
    warnings = _validate_rows(rows_list)
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
        rows=rows_list,
        # `placements` is no longer authoritative; persist empty list
        # for column-not-null safety. R-3.2 drops the column.
        placements=[],
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
    rows: list | None = None,
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

    if rows is not None:
        new_rows = _normalize_rows(list(rows))
    else:
        new_rows = list(row.rows or [])
    new_canvas = (
        dict(canvas_config)
        if canvas_config is not None
        else dict(row.canvas_config or {})
    )
    warnings = _validate_rows(new_rows)
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
        rows=new_rows,
        placements=[],
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
            "rows": [...],
            "canvas_config": {...},
        }

    When no composition exists at any tier, source is None and
    rows/canvas_config are empty — caller falls back to the Focus's
    hard-coded layout.
    """
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
        "rows": [],
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
        "rows": list(row.rows or []),
        "canvas_config": dict(row.canvas_config or {}),
    }
