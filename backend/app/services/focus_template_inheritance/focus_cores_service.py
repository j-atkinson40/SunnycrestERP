"""Tier 1 — Focus core registry service.

Cores are platform-owned, code-implemented Focus operational surfaces
(dispatcher kanban, arrangement scribe, decision flow). Templates
(Tier 2) inherit one core each. The core itself is NOT composed in
the visual editor — it's React code; the registry surfaces it for
selection.

Versioning mirrors workflow_templates: every save deactivates the
prior active row + inserts a new active row at version+1. Partial
unique index on is_active=true enforces "at most one active row
per core_slug" — that constraint lives at the DB layer (migration
r96).

`core_slug` is immutable post-create. Changing it would amount to
inventing a new core; explicit `create_core` is the canonical path.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.models.focus_core import FocusCore
from app.models.focus_template import FocusTemplate
from app.services.focus_template_inheritance.chrome_validation import (
    InvalidChromeShape,
    validate_chrome_blob,
)


logger = logging.getLogger(__name__)


# ─── Exceptions ──────────────────────────────────────────────────


class FocusCoreError(Exception):
    """Base for Tier 1 core service errors."""


class CoreNotFound(FocusCoreError):
    pass


class InvalidCoreShape(FocusCoreError):
    pass


class CoreSlugImmutable(FocusCoreError):
    pass


# ─── Validation helpers ──────────────────────────────────────────


def _require_str(value: Any, field: str, *, max_len: int) -> str:
    if not isinstance(value, str) or not value:
        raise InvalidCoreShape(f"{field} must be a non-empty string")
    if len(value) > max_len:
        raise InvalidCoreShape(
            f"{field} exceeds {max_len} chars (got {len(value)})"
        )
    return value


def _require_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise InvalidCoreShape(f"{field} must be an integer")
    return value


def _validate_geometry(
    *,
    default_starting_column: int,
    default_column_span: int,
    default_row_index: int,
    min_column_span: int,
    max_column_span: int,
) -> None:
    if default_starting_column < 0 or default_starting_column >= 12:
        raise InvalidCoreShape(
            "default_starting_column must be in [0, 11]"
        )
    if default_column_span < 1 or default_column_span > 12:
        raise InvalidCoreShape("default_column_span must be in [1, 12]")
    if default_starting_column + default_column_span > 12:
        raise InvalidCoreShape(
            "default_starting_column + default_column_span must be <= 12"
        )
    if default_row_index < 0:
        raise InvalidCoreShape("default_row_index must be >= 0")
    if min_column_span < 1 or min_column_span > 12:
        raise InvalidCoreShape("min_column_span must be in [1, 12]")
    if max_column_span < min_column_span or max_column_span > 12:
        raise InvalidCoreShape(
            "max_column_span must be in [min_column_span, 12]"
        )
    if not (min_column_span <= default_column_span <= max_column_span):
        raise InvalidCoreShape(
            "default_column_span must be within [min_column_span, max_column_span]"
        )


# ─── Lookup ──────────────────────────────────────────────────────


def list_cores(db: Session, *, include_inactive: bool = False) -> list[FocusCore]:
    q = db.query(FocusCore)
    if not include_inactive:
        q = q.filter(FocusCore.is_active.is_(True))
    return q.order_by(FocusCore.created_at.asc()).all()


def get_core_by_id(db: Session, core_id: str) -> FocusCore | None:
    return db.query(FocusCore).filter(FocusCore.id == core_id).first()


def get_core_by_slug(db: Session, core_slug: str) -> FocusCore | None:
    """Active row only."""
    return (
        db.query(FocusCore)
        .filter(
            FocusCore.core_slug == core_slug,
            FocusCore.is_active.is_(True),
        )
        .first()
    )


def _find_active_by_slug(db: Session, core_slug: str) -> FocusCore | None:
    return get_core_by_slug(db, core_slug)


# ─── Mutation ────────────────────────────────────────────────────


def create_core(
    db: Session,
    *,
    core_slug: str,
    display_name: str,
    description: str | None = None,
    registered_component_kind: str,
    registered_component_name: str,
    default_starting_column: int = 0,
    default_column_span: int = 12,
    default_row_index: int = 0,
    min_column_span: int = 6,
    max_column_span: int = 12,
    canvas_config: Mapping[str, Any] | None = None,
    chrome: Mapping[str, Any] | None = None,
    created_by: str | None = None,
) -> FocusCore:
    """Create a new active core. If an active row already exists at
    `core_slug`, raise — use `update_core` to version an existing
    core. (Workflow precedent: same surface for "new" vs "version"
    via deactivate-prior; we keep them distinct here because core
    slug is meant to be stable.)"""
    _require_str(core_slug, "core_slug", max_len=96)
    _require_str(display_name, "display_name", max_len=160)
    _require_str(
        registered_component_kind, "registered_component_kind", max_len=32
    )
    _require_str(
        registered_component_name, "registered_component_name", max_len=96
    )

    _require_int(default_starting_column, "default_starting_column")
    _require_int(default_column_span, "default_column_span")
    _require_int(default_row_index, "default_row_index")
    _require_int(min_column_span, "min_column_span")
    _require_int(max_column_span, "max_column_span")
    _validate_geometry(
        default_starting_column=default_starting_column,
        default_column_span=default_column_span,
        default_row_index=default_row_index,
        min_column_span=min_column_span,
        max_column_span=max_column_span,
    )

    cfg = dict(canvas_config or {})
    if not isinstance(cfg, dict):
        raise InvalidCoreShape("canvas_config must be a dict")

    chrome_blob = dict(chrome or {})
    try:
        validate_chrome_blob(chrome_blob)
    except InvalidChromeShape as exc:
        raise InvalidCoreShape(str(exc)) from exc

    existing = _find_active_by_slug(db, core_slug)
    if existing is not None:
        raise FocusCoreError(
            f"active core with slug {core_slug!r} already exists; "
            f"use update_core to version it"
        )

    row = FocusCore(
        core_slug=core_slug,
        display_name=display_name,
        description=description,
        registered_component_kind=registered_component_kind,
        registered_component_name=registered_component_name,
        default_starting_column=default_starting_column,
        default_column_span=default_column_span,
        default_row_index=default_row_index,
        min_column_span=min_column_span,
        max_column_span=max_column_span,
        canvas_config=cfg,
        chrome=chrome_blob,
        version=1,
        is_active=True,
        created_by=created_by,
        updated_by=created_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_core(
    db: Session,
    core_id: str,
    *,
    updated_by: str | None = None,
    display_name: str | None = None,
    description: str | None = None,
    registered_component_kind: str | None = None,
    registered_component_name: str | None = None,
    default_starting_column: int | None = None,
    default_column_span: int | None = None,
    default_row_index: int | None = None,
    min_column_span: int | None = None,
    max_column_span: int | None = None,
    canvas_config: Mapping[str, Any] | None = None,
    chrome: Mapping[str, Any] | None = None,
    core_slug: str | None = None,
) -> FocusCore:
    """Version-bump the core. Deactivate the prior active row; insert a
    fresh active row at version+1. `core_slug` is immutable — passing
    a value other than the existing slug raises CoreSlugImmutable.
    """
    prior = get_core_by_id(db, core_id)
    if prior is None:
        raise CoreNotFound(core_id)
    if not prior.is_active:
        raise FocusCoreError(
            f"cannot update inactive core {core_id!r}; latest version "
            f"is active under slug {prior.core_slug!r}"
        )

    if core_slug is not None and core_slug != prior.core_slug:
        raise CoreSlugImmutable(
            f"core_slug is immutable; got {core_slug!r}, current "
            f"is {prior.core_slug!r}"
        )

    new_display_name = (
        display_name if display_name is not None else prior.display_name
    )
    _require_str(new_display_name, "display_name", max_len=160)
    new_description = description if description is not None else prior.description
    new_kind = (
        registered_component_kind
        if registered_component_kind is not None
        else prior.registered_component_kind
    )
    _require_str(new_kind, "registered_component_kind", max_len=32)
    new_name = (
        registered_component_name
        if registered_component_name is not None
        else prior.registered_component_name
    )
    _require_str(new_name, "registered_component_name", max_len=96)
    new_dsc = (
        default_starting_column
        if default_starting_column is not None
        else prior.default_starting_column
    )
    new_dcs = (
        default_column_span
        if default_column_span is not None
        else prior.default_column_span
    )
    new_dri = (
        default_row_index
        if default_row_index is not None
        else prior.default_row_index
    )
    new_min = (
        min_column_span if min_column_span is not None else prior.min_column_span
    )
    new_max = (
        max_column_span if max_column_span is not None else prior.max_column_span
    )
    _require_int(new_dsc, "default_starting_column")
    _require_int(new_dcs, "default_column_span")
    _require_int(new_dri, "default_row_index")
    _require_int(new_min, "min_column_span")
    _require_int(new_max, "max_column_span")
    _validate_geometry(
        default_starting_column=new_dsc,
        default_column_span=new_dcs,
        default_row_index=new_dri,
        min_column_span=new_min,
        max_column_span=new_max,
    )
    new_cfg = (
        dict(canvas_config) if canvas_config is not None else dict(prior.canvas_config or {})
    )
    if not isinstance(new_cfg, dict):
        raise InvalidCoreShape("canvas_config must be a dict")

    new_chrome = (
        dict(chrome) if chrome is not None else dict(prior.chrome or {})
    )
    try:
        validate_chrome_blob(new_chrome)
    except InvalidChromeShape as exc:
        raise InvalidCoreShape(str(exc)) from exc

    prior.is_active = False
    new_row = FocusCore(
        core_slug=prior.core_slug,
        display_name=new_display_name,
        description=new_description,
        registered_component_kind=new_kind,
        registered_component_name=new_name,
        default_starting_column=new_dsc,
        default_column_span=new_dcs,
        default_row_index=new_dri,
        min_column_span=new_min,
        max_column_span=new_max,
        canvas_config=new_cfg,
        chrome=new_chrome,
        version=prior.version + 1,
        is_active=True,
        created_by=prior.created_by,
        updated_by=updated_by,
    )
    db.add(new_row)
    db.commit()
    db.refresh(new_row)
    return new_row


def count_templates_referencing(db: Session, core_id: str) -> int:
    """Count active templates that reference this core_id (current
    active version only — older inactive versions aren't relevant
    because they share core_slug, not core_id).
    """
    return (
        db.query(FocusTemplate)
        .filter(
            FocusTemplate.inherits_from_core_id == core_id,
            FocusTemplate.is_active.is_(True),
        )
        .count()
    )
