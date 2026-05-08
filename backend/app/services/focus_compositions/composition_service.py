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
    CANONICAL_KINDS,
    FocusComposition,
    KIND_EDGE_PANEL,
    KIND_FOCUS,
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


def _validate_kind(kind: str) -> None:
    """Validate kind discriminator (R-5.0)."""
    if kind not in CANONICAL_KINDS:
        raise InvalidCompositionShape(
            f"kind must be one of {CANONICAL_KINDS} (got {kind!r})"
        )


def _validate_pages(pages: Any) -> list[str]:
    """Validate the `pages` JSONB shape for kind=edge_panel (R-5.0).

    pages must be a non-empty list. Each entry:
        {
            "page_id": str (non-empty),
            "name": str,
            "rows": [...] (validated via _validate_rows),
            "canvas_config": dict (optional, default {}),
        }

    Returns the warnings collected from validating each page's rows.
    """
    if not isinstance(pages, list):
        raise InvalidCompositionShape("pages must be a list")
    if len(pages) == 0:
        raise InvalidCompositionShape(
            "kind=edge_panel requires at least one page"
        )

    warnings: list[str] = []
    seen_page_ids: set[str] = set()
    for idx, page in enumerate(pages):
        if not isinstance(page, dict):
            raise InvalidCompositionShape(
                f"pages[{idx}] must be an object"
            )
        page_id = page.get("page_id")
        if not isinstance(page_id, str) or not page_id:
            raise InvalidCompositionShape(
                f"pages[{idx}].page_id must be a non-empty string"
            )
        if page_id in seen_page_ids:
            raise InvalidCompositionShape(
                f"pages[{idx}].page_id '{page_id}' is duplicated"
            )
        seen_page_ids.add(page_id)

        name = page.get("name")
        if not isinstance(name, str):
            raise InvalidCompositionShape(
                f"pages[{idx}].name must be a string"
            )

        rows = page.get("rows")
        if rows is None:
            raise InvalidCompositionShape(
                f"pages[{idx}].rows must be a list (got null)"
            )
        # Recursively validate each page's rows.
        page_warnings = _validate_rows(rows)
        for w in page_warnings:
            warnings.append(f"pages[{idx}]: {w}")

        canvas_config = page.get("canvas_config")
        if canvas_config is not None and not isinstance(canvas_config, dict):
            raise InvalidCompositionShape(
                f"pages[{idx}].canvas_config must be an object or null"
            )

    return warnings


def _normalize_pages(pages: list) -> list[dict]:
    """Defensive normalization for the `pages` JSONB array (R-5.0).

    Each page's rows pass through _normalize_rows so placement_ids
    + row_ids get auto-filled.
    """
    normalized: list[dict] = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        new_page: dict[str, Any] = {
            "page_id": page.get("page_id") or str(uuid.uuid4()),
            "name": page.get("name") or "Untitled page",
            "rows": _normalize_rows(list(page.get("rows") or [])),
            "canvas_config": dict(page.get("canvas_config") or {}),
        }
        normalized.append(new_page)
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
    kind: str = KIND_FOCUS,
) -> FocusComposition | None:
    q = db.query(FocusComposition).filter(
        FocusComposition.scope == scope,
        FocusComposition.focus_type == focus_type,
        FocusComposition.kind == kind,
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
    kind: str = KIND_FOCUS,
) -> int:
    q = db.query(FocusComposition).filter(
        FocusComposition.scope == scope,
        FocusComposition.focus_type == focus_type,
        FocusComposition.kind == kind,
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
    kind: str = KIND_FOCUS,
    pages: list | None = None,
    actor_user_id: str | None = None,
) -> FocusComposition:
    _validate_scope(scope, vertical=vertical, tenant_id=tenant_id)
    _validate_kind(kind)

    if kind == KIND_EDGE_PANEL:
        # Edge panel: pages REQUIRED; rows must be empty.
        if pages is None:
            raise InvalidCompositionShape(
                "kind=edge_panel requires `pages` (a non-empty list of page records)"
            )
        normalized_pages = _normalize_pages(list(pages))
        page_warnings = _validate_pages(normalized_pages)
        for w in page_warnings:
            logger.warning("[composition] %s", w)
        rows_list: list = []
    else:
        # Focus: rows is canonical; pages must be None.
        if pages is not None:
            raise InvalidCompositionShape(
                "kind=focus must not include `pages` (use `rows` instead)"
            )
        rows_list = _normalize_rows(list(rows or []))
        warnings = _validate_rows(rows_list)
        for w in warnings:
            logger.warning("[composition] %s", w)
        normalized_pages = None

    existing = _find_active(
        db,
        scope=scope,
        focus_type=focus_type,
        vertical=vertical,
        tenant_id=tenant_id,
        kind=kind,
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
        canvas_config=dict(canvas_config or {}),
        kind=kind,
        pages=normalized_pages,
        version=_next_version(
            db,
            scope=scope,
            focus_type=focus_type,
            vertical=vertical,
            tenant_id=tenant_id,
            kind=kind,
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
    pages: list | None = None,
    actor_user_id: str | None = None,
) -> FocusComposition:
    row = (
        db.query(FocusComposition)
        .filter(FocusComposition.id == composition_id)
        .first()
    )
    if row is None:
        raise CompositionNotFound()

    kind = row.kind
    if kind == KIND_EDGE_PANEL:
        if pages is not None:
            new_pages = _normalize_pages(list(pages))
            page_warnings = _validate_pages(new_pages)
            for w in page_warnings:
                logger.warning("[composition] %s", w)
        else:
            new_pages = list(row.pages or [])
        new_rows: list = []
    else:
        if rows is not None:
            new_rows = _normalize_rows(list(rows))
        else:
            new_rows = list(row.rows or [])
        warnings = _validate_rows(new_rows)
        for w in warnings:
            logger.warning("[composition] %s", w)
        new_pages = None

    new_canvas = (
        dict(canvas_config)
        if canvas_config is not None
        else dict(row.canvas_config or {})
    )

    if row.is_active:
        row.is_active = False

    new_row = FocusComposition(
        id=str(uuid.uuid4()),
        scope=row.scope,
        vertical=row.vertical,
        tenant_id=row.tenant_id,
        focus_type=row.focus_type,
        rows=new_rows,
        canvas_config=new_canvas,
        kind=kind,
        pages=new_pages,
        version=_next_version(
            db,
            scope=row.scope,
            focus_type=row.focus_type,
            vertical=row.vertical,
            tenant_id=row.tenant_id,
            kind=kind,
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
    kind: str | None = None,
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
    if kind is not None:
        q = q.filter(FocusComposition.kind == kind)
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
    kind: str = KIND_FOCUS,
) -> dict[str, Any]:
    """Walk the inheritance chain and return the first matching
    composition. First-match-wins semantics (no overlay merging at
    READ time — a composition is a complete layout, not a partial
    override).

    `kind` (R-5.0) selects which composition family to resolve. The
    inheritance chain is identical for both kinds — platform_default
    → vertical_default → tenant_override.

    Returns:
        {
            "focus_type": ...,
            "vertical": ...,
            "tenant_id": ...,
            "kind": "focus" | "edge_panel",
            "source": "platform_default" | "vertical_default" |
                      "tenant_override" | None,
            "source_id": ... | None,
            "source_version": ... | None,
            "rows": [...],          # populated when kind=focus
            "canvas_config": {...},
            "pages": [...] | None,  # populated when kind=edge_panel
        }

    When no composition exists at any tier, source is None and
    rows/pages/canvas_config carry empty defaults — caller falls back
    to its hard-coded shape.
    """
    if tenant_id is not None:
        row = _find_active(
            db,
            scope=SCOPE_TENANT_OVERRIDE,
            focus_type=focus_type,
            vertical=None,
            tenant_id=tenant_id,
            kind=kind,
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
            kind=kind,
        )
        if row is not None:
            return _serialize_resolution(row, "vertical_default")

    row = _find_active(
        db,
        scope=SCOPE_PLATFORM_DEFAULT,
        focus_type=focus_type,
        vertical=None,
        tenant_id=None,
        kind=kind,
    )
    if row is not None:
        return _serialize_resolution(row, "platform_default")

    return {
        "focus_type": focus_type,
        "vertical": vertical,
        "tenant_id": tenant_id,
        "kind": kind,
        "source": None,
        "source_id": None,
        "source_version": None,
        "rows": [],
        "canvas_config": {},
        "pages": [] if kind == KIND_EDGE_PANEL else None,
    }


def _apply_placement_overrides(
    rows: list[dict],
    *,
    hidden_ids: list[str],
    additional: list[dict],
    order: list[str] | None,
) -> list[dict]:
    """R-5.1 — apply per-placement overrides to a tenant page's rows.

    1. Filter tenant placements: drop those whose placement_id is in
       hidden_ids (orphan IDs in hidden_ids logged at debug + dropped
       silently — they reference placements that were removed from the
       tenant default since the user authored their override).
    2. Append additional placements: each carries optional row_index
       (default 0, clamped to len(rows)-1; if rows empty, append as a
       new row containing the single placement so the result stays
       structurally valid).
    3. Reorder placements within each row by placement_order if
       provided. Orphan IDs in order silently dropped. Placements not
       mentioned in order keep relative position appended at end.

    Returns a new rows list (does not mutate input).
    """
    hidden_set = set(hidden_ids or [])

    # Step 1: deep-copy + filter hidden.
    new_rows: list[dict] = []
    for row in rows:
        new_row = dict(row)
        kept_placements = []
        for p in row.get("placements") or []:
            if p.get("placement_id") in hidden_set:
                logger.debug(
                    "[edge-panel] dropped hidden placement %s",
                    p.get("placement_id"),
                )
                continue
            kept_placements.append(dict(p))
        new_row["placements"] = kept_placements
        new_rows.append(new_row)

    # Step 2: append additional placements.
    for add in additional or []:
        if not isinstance(add, dict):
            continue
        # Strip row_index from the persisted placement shape — it's a
        # placement-resolution hint, not a placement attribute.
        placement = {k: v for k, v in add.items() if k != "row_index"}
        target_row_idx = add.get("row_index", 0)
        if not isinstance(target_row_idx, int) or target_row_idx < 0:
            target_row_idx = 0

        if not new_rows:
            # Empty rows: synthesize a new row containing this single
            # placement so the structure stays valid.
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
            # Clamp to last row.
            clamped_idx = min(target_row_idx, len(new_rows) - 1)
            new_rows[clamped_idx]["placements"].append(placement)

    # Step 3: reorder placements within each row.
    if order:
        order_index = {pid: i for i, pid in enumerate(order)}
        for row in new_rows:
            placements = row["placements"]

            def sort_key(p: dict) -> tuple[int, int]:
                pid = p.get("placement_id")
                # In-order placements: (0, order_index) — sorts first
                # by their declared position. Orphan-from-row
                # placements: (1, original_idx) — appended after.
                if pid in order_index:
                    return (0, order_index[pid])
                return (1, placements.index(p))

            row["placements"] = sorted(placements, key=sort_key)

    return new_rows


def resolve_edge_panel(
    db: Session,
    *,
    panel_key: str,
    vertical: str | None = None,
    tenant_id: str | None = None,
    user_overrides: dict | None = None,
) -> dict[str, Any]:
    """R-5.0 — resolve an edge panel composition with optional
    per-user override layer applied on top of the tenant resolution.

    R-5.1 — extends the override schema with per-placement granularity
    (hidden_placement_ids, additional_placements, placement_order)
    plus top-level additional_pages (user's personal pages).

    `panel_key` is the canonical slug for an edge panel (carried in
    the `focus_type` column). `user_overrides` is the
    `User.preferences.edge_panel_overrides[panel_key]` JSONB blob,
    if present.

    Per-user override semantics:

      Per-page (`page_overrides[page_id]`):
        - If `rows` set → use it (R-5.0 full-replace escape hatch);
          per-placement fields ignored for this page.
        - Else apply per-placement overrides (R-5.1):
            - `hidden_placement_ids` → drop placements (orphan IDs
              silently logged at debug)
            - `additional_placements` → append; each carries optional
              row_index (default 0, clamped to last row; empty rows
              synthesizes a new row)
            - `placement_order` → reorder within each row; orphan IDs
              silently dropped
        - `canvas_config` always replaces if set.

      Top-level `additional_pages` (R-5.1) — user's personal pages
      appended AFTER per-page overrides applied. Personal pages can
      themselves be hidden via `hidden_page_ids` (rare but consistent
      semantics) and participate in `page_order_override`. If a
      personal page's page_id collides with a tenant page_id, the
      tenant page wins (personal page silently dropped).

      `hidden_page_ids` drops those pages from the final list.

      `page_order_override` reorders pages by page_id.

    Pages outside `page_overrides` and `hidden_page_ids` fall through
    to the tenant default unmodified.
    """
    base = resolve_composition(
        db,
        focus_type=panel_key,
        vertical=vertical,
        tenant_id=tenant_id,
        kind=KIND_EDGE_PANEL,
    )
    pages = list(base.get("pages") or [])

    if not user_overrides:
        return base

    # Step 1: per-page overrides.
    page_overrides = user_overrides.get("page_overrides") or {}
    if isinstance(page_overrides, dict):
        for idx, page in enumerate(pages):
            pid = page.get("page_id")
            if pid not in page_overrides:
                continue
            override = page_overrides[pid]
            if not isinstance(override, dict):
                continue

            new_page = dict(page)

            if "rows" in override:
                # R-5.0 full-replace escape hatch — per-placement
                # fields ignored when rows is set.
                new_page["rows"] = override["rows"]
            else:
                # R-5.1 per-placement overrides.
                hidden_ids = override.get("hidden_placement_ids") or []
                additional = override.get("additional_placements") or []
                placement_order = override.get("placement_order")
                if (
                    hidden_ids
                    or additional
                    or (placement_order is not None)
                ):
                    new_page["rows"] = _apply_placement_overrides(
                        list(page.get("rows") or []),
                        hidden_ids=hidden_ids if isinstance(hidden_ids, list) else [],
                        additional=additional if isinstance(additional, list) else [],
                        order=placement_order if isinstance(placement_order, list) else None,
                    )

            if "canvas_config" in override:
                new_page["canvas_config"] = override["canvas_config"]

            pages[idx] = new_page

    # Step 2: append additional_pages (R-5.1) — user's personal pages.
    additional_pages = user_overrides.get("additional_pages") or []
    if isinstance(additional_pages, list) and additional_pages:
        existing_ids = {p.get("page_id") for p in pages}
        for ap in additional_pages:
            if not isinstance(ap, dict):
                continue
            ap_id = ap.get("page_id")
            if ap_id in existing_ids:
                # Collision: tenant page wins; drop personal page.
                logger.debug(
                    "[edge-panel] additional_page %s collides with tenant page; dropping personal page",
                    ap_id,
                )
                continue
            pages.append(ap)
            existing_ids.add(ap_id)

    # Step 3: drop hidden pages.
    hidden = user_overrides.get("hidden_page_ids") or []
    if isinstance(hidden, list) and hidden:
        hidden_set = set(hidden)
        pages = [p for p in pages if p.get("page_id") not in hidden_set]

    # Step 4: reorder per page_order_override.
    order = user_overrides.get("page_order_override")
    if isinstance(order, list) and order:
        by_id = {p.get("page_id"): p for p in pages}
        reordered: list[dict] = []
        for pid in order:
            if pid in by_id:
                reordered.append(by_id.pop(pid))
        # Append any pages not mentioned in the override list.
        reordered.extend(by_id.values())
        pages = reordered

    base["pages"] = pages
    return base


def _serialize_resolution(row: FocusComposition, source: str) -> dict:
    return {
        "focus_type": row.focus_type,
        "vertical": row.vertical,
        "tenant_id": row.tenant_id,
        "kind": row.kind,
        "source": source,
        "source_id": row.id,
        "source_version": row.version,
        "rows": list(row.rows or []),
        "canvas_config": dict(row.canvas_config or {}),
        "pages": list(row.pages) if row.pages is not None else (
            [] if row.kind == KIND_EDGE_PANEL else None
        ),
    }
