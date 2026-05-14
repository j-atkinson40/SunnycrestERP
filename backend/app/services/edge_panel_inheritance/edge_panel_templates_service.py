"""Tier 2 — Edge Panel Template service (sub-arc B-1.5).

Templates are platform-owned (`platform_default`, vertical=None) or
per-vertical-default (`vertical_default`, vertical=<slug>). The third
tier is per-tenant lazy fork (Tier 3, edge_panel_compositions).

`pages` JSONB shape is validated here (service-layer responsibility —
schema doesn't enforce JSONB-internal structure). Each page carries
page_id (unique within template) + name + rows (same shape as Focus
rows) + optional per-page canvas_config. Each row's placements are
unique by placement_id within the page.

Versioning mirrors r96 / focus_templates: each save deactivates the
prior active row + inserts a fresh active row at version+1. Partial
unique index on is_active=true enforces "at most one active row per
(scope, vertical, panel_key) tuple."

The `_validate_pages` helper is copy-verbatim of the R-5.0
composition_service `_validate_pages` (with exceptions retypeed to
InvalidEdgePanelShape) per build report decision: direct import of
the legacy helper introduces a cyclic substrate dependency (sub-arc
B-2 rewrites composition_service against the Focus inheritance model).
A small, focused copy keeps B-1.5 self-contained; the shapes are
structurally identical and any drift in either direction is
test-covered.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping

from sqlalchemy.orm import Session

from app.models.edge_panel_composition import EdgePanelComposition
from app.models.edge_panel_template import (
    SCOPE_PLATFORM_DEFAULT,
    SCOPE_VERTICAL_DEFAULT,
    EdgePanelTemplate,
)


logger = logging.getLogger(__name__)


_VALID_SCOPES: tuple[str, ...] = (SCOPE_PLATFORM_DEFAULT, SCOPE_VERTICAL_DEFAULT)


# ─── Exceptions ──────────────────────────────────────────────────


class EdgePanelTemplateError(Exception):
    """Base for Tier 2 edge-panel template service errors."""


class EdgePanelTemplateNotFound(EdgePanelTemplateError):
    pass


class InvalidEdgePanelShape(EdgePanelTemplateError):
    """Raised when a template's pages / canvas_config / metadata
    shape fails validation. Also raised by the composition service
    + resolver for matching errors on the deltas side; centralizing
    the exception class makes route-layer translation a one-isinstance
    check."""


class EdgePanelTemplateScopeMismatch(EdgePanelTemplateError):
    pass


# ─── Validation helpers ──────────────────────────────────────────


def _require_str(value: Any, field: str, *, max_len: int) -> str:
    if not isinstance(value, str) or not value:
        raise InvalidEdgePanelShape(f"{field} must be a non-empty string")
    if len(value) > max_len:
        raise InvalidEdgePanelShape(
            f"{field} exceeds {max_len} chars (got {len(value)})"
        )
    return value


def _validate_scope(scope: str, vertical: str | None) -> None:
    if scope not in _VALID_SCOPES:
        raise InvalidEdgePanelShape(f"scope must be one of {_VALID_SCOPES}")
    if scope == SCOPE_PLATFORM_DEFAULT and vertical is not None:
        raise EdgePanelTemplateScopeMismatch(
            "platform_default rows must have vertical=None"
        )
    if scope == SCOPE_VERTICAL_DEFAULT and vertical is None:
        raise EdgePanelTemplateScopeMismatch(
            "vertical_default rows must have vertical set"
        )


def _validate_placement(
    placement: Any,
    *,
    column_count: int,
    placement_ids_seen: set[str],
    location: str,
) -> None:
    """Validate a single placement within a page row. Mirrors the
    R-5.0 composition_service._validate_rows inner-loop placement
    validation."""
    if not isinstance(placement, dict):
        raise InvalidEdgePanelShape(f"{location}: each placement must be a dict")

    pid = placement.get("placement_id")
    if not isinstance(pid, str) or not pid:
        raise InvalidEdgePanelShape(
            f"{location}: placement_id must be a non-empty string"
        )
    if pid in placement_ids_seen:
        raise InvalidEdgePanelShape(
            f"{location}: duplicate placement_id within page: {pid!r}"
        )
    placement_ids_seen.add(pid)

    kind = placement.get("component_kind")
    name = placement.get("component_name")
    if not isinstance(kind, str) or not kind:
        raise InvalidEdgePanelShape(
            f"{location} placement {pid!r}: component_kind must be a non-empty string"
        )
    if not isinstance(name, str) or not name:
        raise InvalidEdgePanelShape(
            f"{location} placement {pid!r}: component_name must be a non-empty string"
        )

    starting_column = placement.get("starting_column")
    column_span = placement.get("column_span")
    if not isinstance(starting_column, int) or isinstance(starting_column, bool):
        raise InvalidEdgePanelShape(
            f"{location} placement {pid!r}: starting_column must be an integer"
        )
    if not isinstance(column_span, int) or isinstance(column_span, bool):
        raise InvalidEdgePanelShape(
            f"{location} placement {pid!r}: column_span must be an integer"
        )
    if starting_column < 0:
        raise InvalidEdgePanelShape(
            f"{location} placement {pid!r}: starting_column must be >= 0"
        )
    if column_span < 1:
        raise InvalidEdgePanelShape(
            f"{location} placement {pid!r}: column_span must be >= 1"
        )
    if starting_column + column_span > column_count:
        raise InvalidEdgePanelShape(
            f"{location} placement {pid!r}: starting_column ({starting_column}) "
            f"+ column_span ({column_span}) exceeds row column_count "
            f"({column_count})"
        )

    if "prop_overrides" in placement and not isinstance(
        placement["prop_overrides"], dict
    ):
        raise InvalidEdgePanelShape(
            f"{location} placement {pid!r}: prop_overrides must be a dict"
        )
    if "display_config" in placement and not isinstance(
        placement["display_config"], dict
    ):
        raise InvalidEdgePanelShape(
            f"{location} placement {pid!r}: display_config must be a dict"
        )


def _validate_rows_of_page(rows: Any, *, page_location: str) -> None:
    if not isinstance(rows, list):
        raise InvalidEdgePanelShape(f"{page_location}.rows must be a list")
    placement_ids_seen: set[str] = set()
    for row_idx, row in enumerate(rows):
        loc = f"{page_location}.rows[{row_idx}]"
        if not isinstance(row, dict):
            raise InvalidEdgePanelShape(f"{loc}: must be a dict")
        column_count = row.get("column_count")
        if (
            not isinstance(column_count, int)
            or isinstance(column_count, bool)
            or column_count < 1
            or column_count > 12
        ):
            raise InvalidEdgePanelShape(
                f"{loc}: column_count must be an integer in [1, 12]"
            )
        column_widths = row.get("column_widths")
        if column_widths is not None and not isinstance(column_widths, list):
            raise InvalidEdgePanelShape(
                f"{loc}: column_widths must be a list or null"
            )
        placements = row.get("placements", [])
        if not isinstance(placements, list):
            raise InvalidEdgePanelShape(f"{loc}: placements must be a list")
        for placement in placements:
            _validate_placement(
                placement,
                column_count=column_count,
                placement_ids_seen=placement_ids_seen,
                location=loc,
            )


def _validate_pages(pages: Any) -> list[dict]:
    """Validate the `pages` JSONB structure. Pages may be empty list
    (a template with no pages is structurally valid; resolves to an
    empty edge-panel).

    Mirrors the R-5.0 composition_service._validate_pages contract
    except: empty list is allowed (R-5.0 required at least one page;
    Tier 2 templates may legitimately ship zero pages for placeholders
    + tenant fork-and-add scenarios).
    """
    if not isinstance(pages, list):
        raise InvalidEdgePanelShape("pages must be a list")

    seen_page_ids: set[str] = set()
    for idx, page in enumerate(pages):
        loc = f"pages[{idx}]"
        if not isinstance(page, dict):
            raise InvalidEdgePanelShape(f"{loc}: must be a dict")
        page_id = page.get("page_id")
        if not isinstance(page_id, str) or not page_id:
            raise InvalidEdgePanelShape(
                f"{loc}.page_id must be a non-empty string"
            )
        if page_id in seen_page_ids:
            raise InvalidEdgePanelShape(
                f"{loc}.page_id {page_id!r} duplicated within template"
            )
        seen_page_ids.add(page_id)

        name = page.get("name")
        if not isinstance(name, str):
            raise InvalidEdgePanelShape(f"{loc}.name must be a string")

        _validate_rows_of_page(page.get("rows", []), page_location=loc)

        canvas_config = page.get("canvas_config")
        if canvas_config is not None and not isinstance(canvas_config, dict):
            raise InvalidEdgePanelShape(
                f"{loc}.canvas_config must be a dict or null"
            )

    return pages


# ─── Lookup ──────────────────────────────────────────────────────


def list_templates(
    db: Session,
    *,
    scope: str | None = None,
    vertical: str | None = None,
    include_inactive: bool = False,
) -> list[EdgePanelTemplate]:
    q = db.query(EdgePanelTemplate)
    if scope is not None:
        if scope not in _VALID_SCOPES:
            raise InvalidEdgePanelShape(f"scope filter invalid: {scope!r}")
        q = q.filter(EdgePanelTemplate.scope == scope)
    if vertical is not None:
        q = q.filter(EdgePanelTemplate.vertical == vertical)
    if not include_inactive:
        q = q.filter(EdgePanelTemplate.is_active.is_(True))
    return q.order_by(EdgePanelTemplate.created_at.asc()).all()


def get_template_by_id(
    db: Session, template_id: str
) -> EdgePanelTemplate | None:
    return (
        db.query(EdgePanelTemplate)
        .filter(EdgePanelTemplate.id == template_id)
        .first()
    )


def get_template_by_key(
    db: Session,
    panel_key: str,
    *,
    scope: str,
    vertical: str | None,
) -> EdgePanelTemplate | None:
    """Active row only at the (scope, vertical, panel_key) tuple."""
    _validate_scope(scope, vertical)
    q = db.query(EdgePanelTemplate).filter(
        EdgePanelTemplate.panel_key == panel_key,
        EdgePanelTemplate.scope == scope,
        EdgePanelTemplate.is_active.is_(True),
    )
    if vertical is None:
        q = q.filter(EdgePanelTemplate.vertical.is_(None))
    else:
        q = q.filter(EdgePanelTemplate.vertical == vertical)
    return q.first()


# ─── Mutation ────────────────────────────────────────────────────


def create_template(
    db: Session,
    *,
    scope: str,
    vertical: str | None = None,
    panel_key: str,
    display_name: str,
    description: str | None = None,
    pages: Iterable[Mapping[str, Any]] | None = None,
    canvas_config: Mapping[str, Any] | None = None,
    created_by: str | None = None,
) -> EdgePanelTemplate:
    """Create or version a template at (scope, vertical, panel_key).
    If an active row exists at the tuple, it's deactivated and the
    new row's version is prior.version + 1.
    """
    _validate_scope(scope, vertical)
    _require_str(panel_key, "panel_key", max_len=96)
    _require_str(display_name, "display_name", max_len=160)

    if pages is None:
        pages_list: list[dict] = []
    elif not isinstance(pages, list):
        raise InvalidEdgePanelShape("pages must be a list")
    else:
        pages_list = [dict(p) for p in pages]
    _validate_pages(pages_list)

    cfg = dict(canvas_config or {})
    if not isinstance(cfg, dict):
        raise InvalidEdgePanelShape("canvas_config must be a dict")

    existing = get_template_by_key(
        db, panel_key, scope=scope, vertical=vertical
    )
    next_version = 1
    if existing is not None:
        existing.is_active = False
        next_version = existing.version + 1

    row = EdgePanelTemplate(
        scope=scope,
        vertical=vertical,
        panel_key=panel_key,
        display_name=display_name,
        description=description,
        pages=pages_list,
        canvas_config=cfg,
        version=next_version,
        is_active=True,
        created_by=created_by,
        updated_by=created_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_template(
    db: Session,
    template_id: str,
    *,
    updated_by: str | None = None,
    display_name: str | None = None,
    description: str | None = None,
    pages: Iterable[Mapping[str, Any]] | None = None,
    canvas_config: Mapping[str, Any] | None = None,
) -> EdgePanelTemplate:
    """Version-bump the template. `scope`, `vertical`, `panel_key`
    are immutable through this surface — they identify the chain.
    Changing them = new template (caller should create a new
    panel_key)."""
    prior = get_template_by_id(db, template_id)
    if prior is None:
        raise EdgePanelTemplateNotFound(template_id)
    if not prior.is_active:
        raise EdgePanelTemplateError(
            f"cannot update inactive template {template_id!r}"
        )

    new_display_name = (
        display_name if display_name is not None else prior.display_name
    )
    _require_str(new_display_name, "display_name", max_len=160)
    new_description = (
        description if description is not None else prior.description
    )

    if pages is not None:
        if not isinstance(pages, list):
            raise InvalidEdgePanelShape("pages must be a list")
        new_pages = [dict(p) for p in pages]
        _validate_pages(new_pages)
    else:
        new_pages = list(prior.pages or [])

    new_cfg = (
        dict(canvas_config)
        if canvas_config is not None
        else dict(prior.canvas_config or {})
    )
    if not isinstance(new_cfg, dict):
        raise InvalidEdgePanelShape("canvas_config must be a dict")

    prior.is_active = False
    new_row = EdgePanelTemplate(
        scope=prior.scope,
        vertical=prior.vertical,
        panel_key=prior.panel_key,
        display_name=new_display_name,
        description=new_description,
        pages=new_pages,
        canvas_config=new_cfg,
        version=prior.version + 1,
        is_active=True,
        created_by=prior.created_by,
        updated_by=updated_by,
    )
    db.add(new_row)
    db.commit()
    db.refresh(new_row)
    return new_row


def count_compositions_referencing(db: Session, template_id: str) -> int:
    """Count active per-tenant compositions (Tier 3) referencing
    this template_id."""
    return (
        db.query(EdgePanelComposition)
        .filter(
            EdgePanelComposition.inherits_from_template_id == template_id,
            EdgePanelComposition.is_active.is_(True),
        )
        .count()
    )
