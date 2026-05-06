"""Component class configuration service — CRUD + resolution.

Mirrors the architectural pattern of theme_service + component
config_service: write-side versioning (each save deactivates the
prior active row + inserts a new active row with version+1),
READ-time resolution (the active row's prop_overrides ARE the
class default; no merging at the class layer because there's only
one scope).

Public API:
    create_class_config(db, *, component_class, prop_overrides, ...)
    update_class_config(db, *, config_id, prop_overrides, ...)
    get_class_config(db, *, config_id)
    list_class_configs(db, *, component_class=None)
    resolve_class_config(db, *, component_class)
        → returns the active row's prop_overrides as a dict + the
          row itself for source tracking. Empty dict when no class
          default exists for the class.

Validation:
    Class config writes are validated against
    `class_registry_snapshot.CLASS_REGISTRY_SNAPSHOT` — unknown
    prop names + out-of-bounds values reject with
    InvalidClassConfigShape (HTTP 400).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.component_class_configuration import ComponentClassConfiguration
from app.services.component_class_config.class_registry_snapshot import (
    CLASS_REGISTRY_SNAPSHOT,
    lookup_class,
)


# ─── Exceptions ──────────────────────────────────────────────────


class ClassConfigError(Exception):
    """Base error for class config operations. http_status drives the
    API translation (4xx vs 5xx)."""

    def __init__(self, message: str, *, http_status: int = 400) -> None:
        super().__init__(message)
        self.http_status = http_status


class ClassConfigNotFound(ClassConfigError):
    def __init__(self, message: str = "Class configuration not found") -> None:
        super().__init__(message, http_status=404)


class UnknownClass(ClassConfigError):
    def __init__(self, class_name: str) -> None:
        super().__init__(
            f"Unknown component class: {class_name}", http_status=400
        )


class InvalidClassConfigShape(ClassConfigError):
    def __init__(self, message: str) -> None:
        super().__init__(message, http_status=400)


# ─── Validation ──────────────────────────────────────────────────


def _validate_class(class_name: str) -> dict:
    """Confirm the class is registered. Returns the class's prop
    schema map for write-time validation."""
    schema = lookup_class(class_name)
    if schema is None:
        raise UnknownClass(class_name)
    return schema


def _validate_prop_overrides(class_name: str, overrides: dict) -> None:
    """Reject writes that don't conform to the class's prop schema.

    - Unknown keys → InvalidClassConfigShape.
    - Out-of-bounds enum / numeric values → InvalidClassConfigShape.
    - Wrong-type values (e.g., bool-typed prop receives a string)
      → InvalidClassConfigShape.
    """
    schema = _validate_class(class_name)
    for key, value in overrides.items():
        prop_schema = schema.get(key)
        if prop_schema is None:
            raise InvalidClassConfigShape(
                f"Unknown prop '{key}' for class '{class_name}'."
            )
        prop_type = prop_schema.get("type")
        bounds = prop_schema.get("bounds")
        if prop_type == "boolean":
            if not isinstance(value, bool):
                raise InvalidClassConfigShape(
                    f"Prop '{key}' expects boolean, got {type(value).__name__}."
                )
        elif prop_type == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise InvalidClassConfigShape(
                    f"Prop '{key}' expects number, got {type(value).__name__}."
                )
            if isinstance(bounds, list) and len(bounds) == 2:
                lo, hi = bounds
                if value < lo or value > hi:
                    raise InvalidClassConfigShape(
                        f"Prop '{key}' value {value} out of bounds [{lo}, {hi}]."
                    )
        elif prop_type == "enum":
            if not isinstance(bounds, list):
                continue
            if value not in bounds:
                raise InvalidClassConfigShape(
                    f"Prop '{key}' value '{value}' not in enum {bounds}."
                )
        elif prop_type == "tokenReference":
            if not isinstance(value, str):
                raise InvalidClassConfigShape(
                    f"Prop '{key}' expects string token name, got {type(value).__name__}."
                )
        elif prop_type == "string":
            if not isinstance(value, str):
                raise InvalidClassConfigShape(
                    f"Prop '{key}' expects string, got {type(value).__name__}."
                )
        # Other types (componentReference, array, object) skip
        # detailed validation at v1 — schemas don't yet declare them
        # at class level.


# ─── CRUD ────────────────────────────────────────────────────────


def _find_active(
    db: Session, *, component_class: str
) -> ComponentClassConfiguration | None:
    return (
        db.query(ComponentClassConfiguration)
        .filter(
            ComponentClassConfiguration.component_class == component_class,
            ComponentClassConfiguration.is_active.is_(True),
        )
        .first()
    )


def _next_version(db: Session, *, component_class: str) -> int:
    rows = (
        db.query(ComponentClassConfiguration)
        .filter(ComponentClassConfiguration.component_class == component_class)
        .all()
    )
    if not rows:
        return 1
    return max(r.version for r in rows) + 1


def create_class_config(
    db: Session,
    *,
    component_class: str,
    prop_overrides: dict | None = None,
    actor_user_id: str | None = None,
) -> ComponentClassConfiguration:
    """Create or version a class configuration.

    If an active row exists for this class, deactivates it and
    inserts a new active row with version+1. Otherwise inserts a
    fresh v1 row.
    """
    overrides = dict(prop_overrides or {})
    _validate_prop_overrides(component_class, overrides)

    existing = _find_active(db, component_class=component_class)
    if existing is not None:
        existing.is_active = False

    new_row = ComponentClassConfiguration(
        id=str(uuid.uuid4()),
        component_class=component_class,
        prop_overrides=overrides,
        version=_next_version(db, component_class=component_class),
        is_active=True,
        created_by=actor_user_id,
        updated_by=actor_user_id,
    )
    db.add(new_row)
    db.commit()
    db.refresh(new_row)
    return new_row


def update_class_config(
    db: Session,
    *,
    config_id: str,
    prop_overrides: dict,
    actor_user_id: str | None = None,
) -> ComponentClassConfiguration:
    """Replace prop_overrides on the row identified by config_id by
    deactivating it and inserting a new active row at version+1."""
    row = (
        db.query(ComponentClassConfiguration)
        .filter(ComponentClassConfiguration.id == config_id)
        .first()
    )
    if row is None:
        raise ClassConfigNotFound()

    overrides = dict(prop_overrides or {})
    _validate_prop_overrides(row.component_class, overrides)

    if row.is_active:
        row.is_active = False

    new_row = ComponentClassConfiguration(
        id=str(uuid.uuid4()),
        component_class=row.component_class,
        prop_overrides=overrides,
        version=_next_version(db, component_class=row.component_class),
        is_active=True,
        created_by=row.created_by,
        updated_by=actor_user_id,
    )
    db.add(new_row)
    db.commit()
    db.refresh(new_row)
    return new_row


def get_class_config(
    db: Session, *, config_id: str
) -> ComponentClassConfiguration:
    row = (
        db.query(ComponentClassConfiguration)
        .filter(ComponentClassConfiguration.id == config_id)
        .first()
    )
    if row is None:
        raise ClassConfigNotFound()
    return row


def list_class_configs(
    db: Session, *, component_class: str | None = None, include_inactive: bool = False
) -> list[ComponentClassConfiguration]:
    q = db.query(ComponentClassConfiguration)
    if component_class is not None:
        q = q.filter(ComponentClassConfiguration.component_class == component_class)
    if not include_inactive:
        q = q.filter(ComponentClassConfiguration.is_active.is_(True))
    return q.order_by(
        ComponentClassConfiguration.component_class,
        ComponentClassConfiguration.version.desc(),
    ).all()


# ─── Resolution ──────────────────────────────────────────────────


def resolve_class_config(
    db: Session, *, component_class: str
) -> dict[str, Any]:
    """Return the resolved class default for a class.

    Output:
        {
            "component_class": ...,
            "props": { name: value, ... },
            "source": {scope, id, version, applied_keys} | None,
            "orphaned_keys": [...],
        }

    Class layer has only one scope (class_default), so resolution
    is a single lookup. Orphaned keys (present in storage but
    missing from the class registry snapshot) are dropped from
    `props` and surfaced via `orphaned_keys`.
    """
    if component_class not in CLASS_REGISTRY_SNAPSHOT:
        raise UnknownClass(component_class)

    schema = CLASS_REGISTRY_SNAPSHOT[component_class]
    known_keys = set(schema.keys())

    row = _find_active(db, component_class=component_class)
    if row is None:
        return {
            "component_class": component_class,
            "props": {},
            "source": None,
            "orphaned_keys": [],
        }

    overrides = dict(row.prop_overrides or {})
    orphaned: list[str] = []
    for k in list(overrides.keys()):
        if k not in known_keys:
            orphaned.append(k)
            del overrides[k]

    return {
        "component_class": component_class,
        "props": overrides,
        "source": {
            "scope": "class_default",
            "id": row.id,
            "version": row.version,
            "applied_keys": list(overrides.keys()),
        },
        "orphaned_keys": sorted(set(orphaned)),
    }
