"""Tier 2 — Focus Template service.

Templates inherit a single Tier 1 core and arrange accessory
placements around it on the canvas. Scope is `platform_default`
(vertical=None) or `vertical_default` (vertical=<slug>); the third
tier is per-tenant (Tier 3, focus_compositions).

`rows` JSONB shape is validated here (service-layer responsibility
per locked decision 4 — schema doesn't enforce). Each row carries
column_count (1..12) + a list of placements with 0-indexed
starting_column + column_span. Placements are unique by
`placement_id` within the template. At most one placement may carry
`is_core: true`; if any does, its component_kind + component_name
must match the inherited core's registered_component_kind +
registered_component_name.

Versioning mirrors workflow_templates: each save deactivates the
prior active row + inserts a fresh active row at version+1.
Partial unique index on is_active=true (migration r96) enforces "at
most one active row per (scope, vertical, template_slug)" tuple.

`inherits_from_core_version` is captured from the current active
core at create time. v1 resolver IGNORES it (live cascade per
locked decision 2); Option B versioned cascade lands additively at
the service layer when needed.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping

from sqlalchemy.orm import Session

from app.models.focus_composition import FocusComposition
from app.models.focus_core import FocusCore
from app.models.focus_template import (
    SCOPE_PLATFORM_DEFAULT,
    SCOPE_VERTICAL_DEFAULT,
    FocusTemplate,
)
from app.services.focus_template_inheritance.focus_cores_service import (
    CoreNotFound,
    get_core_by_id,
)
from app.services.focus_template_inheritance.chrome_validation import (
    InvalidChromeShape,
    validate_chrome_blob,
)


logger = logging.getLogger(__name__)


_VALID_SCOPES: tuple[str, ...] = (SCOPE_PLATFORM_DEFAULT, SCOPE_VERTICAL_DEFAULT)


# ─── Exceptions ──────────────────────────────────────────────────


class FocusTemplateError(Exception):
    """Base for Tier 2 template service errors."""


class TemplateNotFound(FocusTemplateError):
    pass


class InvalidTemplateShape(FocusTemplateError):
    pass


class TemplateScopeMismatch(FocusTemplateError):
    pass


# ─── Validation helpers ──────────────────────────────────────────


def _require_str(value: Any, field: str, *, max_len: int) -> str:
    if not isinstance(value, str) or not value:
        raise InvalidTemplateShape(f"{field} must be a non-empty string")
    if len(value) > max_len:
        raise InvalidTemplateShape(
            f"{field} exceeds {max_len} chars (got {len(value)})"
        )
    return value


def _validate_scope(scope: str, vertical: str | None) -> None:
    if scope not in _VALID_SCOPES:
        raise InvalidTemplateShape(f"scope must be one of {_VALID_SCOPES}")
    if scope == SCOPE_PLATFORM_DEFAULT and vertical is not None:
        raise TemplateScopeMismatch(
            "platform_default rows must have vertical=None"
        )
    if scope == SCOPE_VERTICAL_DEFAULT and vertical is None:
        raise TemplateScopeMismatch(
            "vertical_default rows must have vertical set"
        )


def _validate_placement(
    placement: Any,
    *,
    column_count: int,
    placement_ids_seen: set[str],
    core: FocusCore,
) -> None:
    if not isinstance(placement, dict):
        raise InvalidTemplateShape("each placement must be a dict")

    pid = placement.get("placement_id")
    if not isinstance(pid, str) or not pid:
        raise InvalidTemplateShape(
            "each placement must have a non-empty placement_id string"
        )
    if pid in placement_ids_seen:
        raise InvalidTemplateShape(
            f"duplicate placement_id within template: {pid!r}"
        )
    placement_ids_seen.add(pid)

    kind = placement.get("component_kind")
    name = placement.get("component_name")
    if not isinstance(kind, str) or not kind:
        raise InvalidTemplateShape(
            f"placement {pid!r}: component_kind must be a non-empty string"
        )
    if not isinstance(name, str) or not name:
        raise InvalidTemplateShape(
            f"placement {pid!r}: component_name must be a non-empty string"
        )

    starting_column = placement.get("starting_column")
    column_span = placement.get("column_span")
    if not isinstance(starting_column, int) or isinstance(starting_column, bool):
        raise InvalidTemplateShape(
            f"placement {pid!r}: starting_column must be an integer"
        )
    if not isinstance(column_span, int) or isinstance(column_span, bool):
        raise InvalidTemplateShape(
            f"placement {pid!r}: column_span must be an integer"
        )
    if starting_column < 0:
        raise InvalidTemplateShape(
            f"placement {pid!r}: starting_column must be >= 0"
        )
    if column_span < 1:
        raise InvalidTemplateShape(
            f"placement {pid!r}: column_span must be >= 1"
        )
    if starting_column + column_span > column_count:
        raise InvalidTemplateShape(
            f"placement {pid!r}: starting_column ({starting_column}) + "
            f"column_span ({column_span}) exceeds row column_count "
            f"({column_count})"
        )

    if "prop_overrides" in placement and not isinstance(
        placement["prop_overrides"], dict
    ):
        raise InvalidTemplateShape(
            f"placement {pid!r}: prop_overrides must be a dict"
        )
    if "display_config" in placement and not isinstance(
        placement["display_config"], dict
    ):
        raise InvalidTemplateShape(
            f"placement {pid!r}: display_config must be a dict"
        )

    if placement.get("is_core") is True:
        if kind != core.registered_component_kind or name != core.registered_component_name:
            raise InvalidTemplateShape(
                f"placement {pid!r} is marked is_core=true but its "
                f"component (kind={kind!r}, name={name!r}) does not "
                f"match the inherited core "
                f"(kind={core.registered_component_kind!r}, "
                f"name={core.registered_component_name!r})"
            )


def _validate_rows(rows: Any, *, core: FocusCore) -> list[dict]:
    """Validate `rows` JSONB shape. Returns the rows list (no
    structural mutation; deep-copy at the boundary if mutation is
    a concern at the call site).
    """
    if not isinstance(rows, list):
        raise InvalidTemplateShape("rows must be a list")

    placement_ids_seen: set[str] = set()
    core_placements_seen = 0

    for row_idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise InvalidTemplateShape(
                f"row {row_idx}: must be a dict"
            )
        column_count = row.get("column_count")
        if (
            not isinstance(column_count, int)
            or isinstance(column_count, bool)
            or column_count < 1
            or column_count > 12
        ):
            raise InvalidTemplateShape(
                f"row {row_idx}: column_count must be an integer in [1, 12]"
            )
        column_widths = row.get("column_widths")
        if column_widths is not None:
            if not isinstance(column_widths, list):
                raise InvalidTemplateShape(
                    f"row {row_idx}: column_widths must be a list or null"
                )
            if len(column_widths) != column_count:
                raise InvalidTemplateShape(
                    f"row {row_idx}: column_widths length "
                    f"({len(column_widths)}) must equal column_count "
                    f"({column_count})"
                )

        placements = row.get("placements", [])
        if not isinstance(placements, list):
            raise InvalidTemplateShape(
                f"row {row_idx}: placements must be a list"
            )
        for placement in placements:
            _validate_placement(
                placement,
                column_count=column_count,
                placement_ids_seen=placement_ids_seen,
                core=core,
            )
            if placement.get("is_core") is True:
                core_placements_seen += 1

    if core_placements_seen > 1:
        raise InvalidTemplateShape(
            f"at most one placement may have is_core=true; got "
            f"{core_placements_seen}"
        )

    return rows


# ─── Lookup ──────────────────────────────────────────────────────


def list_templates(
    db: Session,
    *,
    scope: str | None = None,
    vertical: str | None = None,
    include_inactive: bool = False,
) -> list[FocusTemplate]:
    q = db.query(FocusTemplate)
    if scope is not None:
        if scope not in _VALID_SCOPES:
            raise InvalidTemplateShape(f"scope filter invalid: {scope!r}")
        q = q.filter(FocusTemplate.scope == scope)
    if vertical is not None:
        q = q.filter(FocusTemplate.vertical == vertical)
    if not include_inactive:
        q = q.filter(FocusTemplate.is_active.is_(True))
    return q.order_by(FocusTemplate.created_at.asc()).all()


def get_template_by_id(
    db: Session, template_id: str
) -> FocusTemplate | None:
    return (
        db.query(FocusTemplate)
        .filter(FocusTemplate.id == template_id)
        .first()
    )


def get_template_by_slug(
    db: Session,
    template_slug: str,
    *,
    scope: str,
    vertical: str | None,
) -> FocusTemplate | None:
    """Active row only at the (scope, vertical, template_slug) tuple."""
    _validate_scope(scope, vertical)
    q = db.query(FocusTemplate).filter(
        FocusTemplate.template_slug == template_slug,
        FocusTemplate.scope == scope,
        FocusTemplate.is_active.is_(True),
    )
    if vertical is None:
        q = q.filter(FocusTemplate.vertical.is_(None))
    else:
        q = q.filter(FocusTemplate.vertical == vertical)
    return q.first()


def _find_active(
    db: Session,
    *,
    scope: str,
    vertical: str | None,
    template_slug: str,
) -> FocusTemplate | None:
    return get_template_by_slug(
        db, template_slug, scope=scope, vertical=vertical
    )


# ─── Mutation ────────────────────────────────────────────────────


def create_template(
    db: Session,
    *,
    scope: str,
    vertical: str | None = None,
    template_slug: str,
    display_name: str,
    description: str | None = None,
    inherits_from_core_id: str,
    rows: Iterable[Mapping[str, Any]] | None = None,
    canvas_config: Mapping[str, Any] | None = None,
    chrome_overrides: Mapping[str, Any] | None = None,
    created_by: str | None = None,
) -> FocusTemplate:
    """Create or version a template at (scope, vertical, template_slug).
    If an active row exists at the tuple, it's deactivated and the
    new row's version is prior.version + 1.

    `inherits_from_core_version` is captured from the live active
    core (NOT a parameter — service-layer captures so callers can't
    drift the FK against a stale value).
    """
    _validate_scope(scope, vertical)
    _require_str(template_slug, "template_slug", max_len=96)
    _require_str(display_name, "display_name", max_len=160)
    _require_str(inherits_from_core_id, "inherits_from_core_id", max_len=36)

    core = get_core_by_id(db, inherits_from_core_id)
    if core is None:
        raise CoreNotFound(inherits_from_core_id)
    if not core.is_active:
        raise InvalidTemplateShape(
            f"inherits_from_core_id {inherits_from_core_id!r} points at "
            f"an inactive core version; reference the active row"
        )

    if rows is None:
        rows_list: list[dict] = []
    elif not isinstance(rows, list):
        # Bare dict / scalar / other iterable shapes are not valid.
        # The validator below will catch list-of-dict-shape errors;
        # this guard catches "wasn't a list at all."
        raise InvalidTemplateShape("rows must be a list")
    else:
        rows_list = [dict(r) for r in rows]
    _validate_rows(rows_list, core=core)

    cfg = dict(canvas_config or {})
    if not isinstance(cfg, dict):
        raise InvalidTemplateShape("canvas_config must be a dict")

    chrome_blob = dict(chrome_overrides or {})
    try:
        validate_chrome_blob(chrome_blob)
    except InvalidChromeShape as exc:
        raise InvalidTemplateShape(str(exc)) from exc

    existing = _find_active(
        db, scope=scope, vertical=vertical, template_slug=template_slug
    )
    next_version = 1
    if existing is not None:
        existing.is_active = False
        next_version = existing.version + 1

    row = FocusTemplate(
        scope=scope,
        vertical=vertical,
        template_slug=template_slug,
        display_name=display_name,
        description=description,
        inherits_from_core_id=core.id,
        inherits_from_core_version=core.version,
        rows=rows_list,
        canvas_config=cfg,
        chrome_overrides=chrome_blob,
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
    rows: Iterable[Mapping[str, Any]] | None = None,
    canvas_config: Mapping[str, Any] | None = None,
    chrome_overrides: Mapping[str, Any] | None = None,
) -> FocusTemplate:
    """Version-bump the template. `scope`, `vertical`, `template_slug`,
    `inherits_from_core_id` are immutable through this surface —
    they identify the chain. Changing core = new template (caller
    should create a new template_slug)."""
    prior = get_template_by_id(db, template_id)
    if prior is None:
        raise TemplateNotFound(template_id)
    if not prior.is_active:
        raise FocusTemplateError(
            f"cannot update inactive template {template_id!r}"
        )

    new_display_name = (
        display_name if display_name is not None else prior.display_name
    )
    _require_str(new_display_name, "display_name", max_len=160)
    new_description = (
        description if description is not None else prior.description
    )

    core = get_core_by_id(db, prior.inherits_from_core_id)
    if core is None:
        raise CoreNotFound(prior.inherits_from_core_id)

    if rows is not None:
        if not isinstance(rows, list):
            raise InvalidTemplateShape("rows must be a list")
        new_rows = [dict(r) for r in rows]
        _validate_rows(new_rows, core=core)
    else:
        new_rows = list(prior.rows or [])

    new_cfg = (
        dict(canvas_config) if canvas_config is not None else dict(prior.canvas_config or {})
    )
    if not isinstance(new_cfg, dict):
        raise InvalidTemplateShape("canvas_config must be a dict")

    new_chrome = (
        dict(chrome_overrides)
        if chrome_overrides is not None
        else dict(prior.chrome_overrides or {})
    )
    try:
        validate_chrome_blob(new_chrome)
    except InvalidChromeShape as exc:
        raise InvalidTemplateShape(str(exc)) from exc

    prior.is_active = False
    new_row = FocusTemplate(
        scope=prior.scope,
        vertical=prior.vertical,
        template_slug=prior.template_slug,
        display_name=new_display_name,
        description=new_description,
        inherits_from_core_id=prior.inherits_from_core_id,
        inherits_from_core_version=prior.inherits_from_core_version,
        rows=new_rows,
        canvas_config=new_cfg,
        chrome_overrides=new_chrome,
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
        db.query(FocusComposition)
        .filter(
            FocusComposition.inherits_from_template_id == template_id,
            FocusComposition.is_active.is_(True),
        )
        .count()
    )
