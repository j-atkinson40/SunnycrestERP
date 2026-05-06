"""Component Configuration service — CRUD + inheritance resolution
+ per-prop validation against the registry snapshot.

Mirrors `platform_themes.theme_service` design verbatim:
  - READ-time inheritance walk in `resolve_configuration`
  - Write-side versioning (every save deactivates prior + inserts
    a new active row with version + 1)
  - Empty `prop_overrides: {}` is valid ("inherit fully from parent")

Validation discipline: writes are validated against the registry
snapshot at the boundary. Out-of-bounds entries are rejected
with `PropValidationError` → API 400.

Orphaned overrides: when a component's registration changes (a
prop is removed in code), pre-existing override values for that
prop become orphaned. Resolution IGNORES orphaned keys (logs a
warning) but the API surfaces them in a `warnings` field so the
admin UI can flag them for cleanup.
"""

from __future__ import annotations

import logging
from typing import Any, Literal, Mapping
from sqlalchemy.orm import Session

from app.models.component_configuration import (
    ComponentConfiguration,
    SCOPE_PLATFORM_DEFAULT,
    SCOPE_TENANT_OVERRIDE,
    SCOPE_VERTICAL_DEFAULT,
)
from app.services.component_config.registry_snapshot import (
    REGISTRY_SNAPSHOT,
    lookup_component,
)


logger = logging.getLogger(__name__)


Scope = Literal["platform_default", "vertical_default", "tenant_override"]

_VALID_SCOPES: tuple[str, ...] = (
    SCOPE_PLATFORM_DEFAULT,
    SCOPE_VERTICAL_DEFAULT,
    SCOPE_TENANT_OVERRIDE,
)


# ─── Exceptions ──────────────────────────────────────────────────


class ComponentConfigError(Exception):
    """Base for the component-config service."""


class ComponentConfigNotFound(ComponentConfigError):
    pass


class ConfigScopeMismatch(ComponentConfigError):
    pass


class InvalidConfigShape(ComponentConfigError):
    pass


class UnknownComponent(ComponentConfigError):
    """The (component_kind, component_name) tuple isn't in the
    registry snapshot. Either the registration was removed or the
    backend snapshot is out of sync with the frontend."""


class PropValidationError(ComponentConfigError):
    """An override value violates the prop's declared bounds."""


# ─── Validation ──────────────────────────────────────────────────


def _validate_scope_keys(
    scope: str,
    vertical: str | None,
    tenant_id: str | None,
) -> None:
    if scope not in _VALID_SCOPES:
        raise InvalidConfigShape(f"scope must be one of {_VALID_SCOPES}")
    if scope == SCOPE_PLATFORM_DEFAULT and (vertical is not None or tenant_id is not None):
        raise ConfigScopeMismatch(
            "platform_default rows must have vertical=None and tenant_id=None"
        )
    if scope == SCOPE_VERTICAL_DEFAULT and (vertical is None or tenant_id is not None):
        raise ConfigScopeMismatch(
            "vertical_default rows must have vertical set and tenant_id=None"
        )
    if scope == SCOPE_TENANT_OVERRIDE and (tenant_id is None or vertical is not None):
        raise ConfigScopeMismatch(
            "tenant_override rows must have tenant_id set and vertical=None"
        )


def _validate_kind(kind: str) -> None:
    valid = {
        "widget",
        "focus",
        "focus-template",
        "document-block",
        "pulse-widget",
        "workflow-node",
        "layout",
        "composite",
        # Class-configuration phase (May 2026):
        "entity-card",
        "button",
        "form-input",
        "surface-card",
    }
    if kind not in valid:
        raise InvalidConfigShape(
            f"component_kind must be one of {sorted(valid)}, got {kind!r}"
        )


def validate_overrides(
    component_kind: str,
    component_name: str,
    prop_overrides: Mapping[str, Any],
    *,
    strict: bool = True,
) -> dict[str, Any]:
    """Validate + clean an overrides map against the registry
    snapshot. Returns the cleaned dict (drops None values =
    "remove this override").

    `strict=True` (default): unknown components raise
    UnknownComponent; unknown prop keys + out-of-bounds values
    raise PropValidationError.

    `strict=False`: orphaned + unknown keys are silently dropped
    (used by the read path so old override rows don't crash
    resolution after a registration change).
    """
    if not isinstance(prop_overrides, dict):
        raise InvalidConfigShape(
            "prop_overrides must be a mapping of prop name → value"
        )

    snapshot = lookup_component(component_kind, component_name)
    if snapshot is None:
        if strict:
            raise UnknownComponent(
                f"Component {component_kind!r}:{component_name!r} not in "
                f"backend registry snapshot. Either the registration was "
                f"removed in the frontend or the snapshot needs an update."
            )
        # Lenient mode: pass through without validation.
        return {k: v for k, v in prop_overrides.items() if v is not None}

    cleaned: dict[str, Any] = {}
    for key, value in prop_overrides.items():
        if not isinstance(key, str) or not key:
            raise PropValidationError(
                f"prop names must be non-empty strings, got {key!r}"
            )
        if value is None:
            continue
        prop = snapshot.get(key)
        if prop is None:
            if strict:
                raise PropValidationError(
                    f"Unknown prop {key!r} for {component_kind}:"
                    f"{component_name}. Known props: "
                    f"{sorted(snapshot.keys())}"
                )
            # Lenient: skip orphaned keys silently.
            logger.warning(
                "[component_config] dropping orphaned prop override "
                "%s on %s:%s",
                key, component_kind, component_name,
            )
            continue
        _validate_value(component_kind, component_name, key, prop, value)
        cleaned[key] = value
    return cleaned


def _validate_value(
    kind: str, name: str, prop_key: str, prop: Mapping[str, Any], value: Any
) -> None:
    """Validate a single value against its declared schema.
    Raises PropValidationError on shape or bound violations."""
    ptype = prop.get("type")
    bounds = prop.get("bounds")

    if ptype == "boolean":
        if not isinstance(value, bool):
            raise PropValidationError(
                f"{kind}:{name}.{prop_key}: expected boolean, got {type(value).__name__}"
            )
    elif ptype == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise PropValidationError(
                f"{kind}:{name}.{prop_key}: expected number, got {type(value).__name__}"
            )
        if isinstance(bounds, list) and len(bounds) == 2:
            lo, hi = bounds
            if value < lo or value > hi:
                raise PropValidationError(
                    f"{kind}:{name}.{prop_key}: value {value} out of bounds "
                    f"[{lo}, {hi}]"
                )
    elif ptype == "string":
        if not isinstance(value, str):
            raise PropValidationError(
                f"{kind}:{name}.{prop_key}: expected string, got {type(value).__name__}"
            )
        if isinstance(bounds, dict):
            max_len = bounds.get("maxLength")
            if isinstance(max_len, int) and len(value) > max_len:
                raise PropValidationError(
                    f"{kind}:{name}.{prop_key}: string exceeds maxLength {max_len} "
                    f"(got {len(value)})"
                )
    elif ptype == "enum":
        if not isinstance(value, str):
            raise PropValidationError(
                f"{kind}:{name}.{prop_key}: enum values must be strings"
            )
        if isinstance(bounds, list) and value not in bounds:
            raise PropValidationError(
                f"{kind}:{name}.{prop_key}: value {value!r} not in allowed enum "
                f"values {bounds}"
            )
    elif ptype == "tokenReference":
        if not isinstance(value, str):
            raise PropValidationError(
                f"{kind}:{name}.{prop_key}: tokenReference values must be strings"
            )
        # We don't validate that the token name exists in tokens.css —
        # that's a frontend concern + would require keeping a
        # token catalog mirror in the backend.
    elif ptype == "componentReference":
        if not isinstance(value, str):
            raise PropValidationError(
                f"{kind}:{name}.{prop_key}: componentReference values must be strings"
            )
    elif ptype == "array":
        if not isinstance(value, list):
            raise PropValidationError(
                f"{kind}:{name}.{prop_key}: expected array, got {type(value).__name__}"
            )
    elif ptype == "object":
        if not isinstance(value, dict):
            raise PropValidationError(
                f"{kind}:{name}.{prop_key}: expected object, got {type(value).__name__}"
            )
    else:
        # Unknown type in the snapshot — let it through but log.
        logger.warning(
            "[component_config] unknown prop type %r for %s:%s.%s",
            ptype, kind, name, prop_key,
        )


# ─── CRUD ────────────────────────────────────────────────────────


def list_configurations(
    db: Session,
    *,
    scope: str | None = None,
    vertical: str | None = None,
    tenant_id: str | None = None,
    component_kind: str | None = None,
    component_name: str | None = None,
    include_inactive: bool = False,
) -> list[ComponentConfiguration]:
    q = db.query(ComponentConfiguration)
    if scope is not None:
        if scope not in _VALID_SCOPES:
            raise InvalidConfigShape(f"scope filter invalid: {scope!r}")
        q = q.filter(ComponentConfiguration.scope == scope)
    if vertical is not None:
        q = q.filter(ComponentConfiguration.vertical == vertical)
    if tenant_id is not None:
        q = q.filter(ComponentConfiguration.tenant_id == tenant_id)
    if component_kind is not None:
        q = q.filter(ComponentConfiguration.component_kind == component_kind)
    if component_name is not None:
        q = q.filter(ComponentConfiguration.component_name == component_name)
    if not include_inactive:
        q = q.filter(ComponentConfiguration.is_active.is_(True))
    return q.order_by(ComponentConfiguration.created_at.desc()).all()


def get_configuration(
    db: Session, config_id: str
) -> ComponentConfiguration:
    row = (
        db.query(ComponentConfiguration)
        .filter(ComponentConfiguration.id == config_id)
        .first()
    )
    if not row:
        raise ComponentConfigNotFound(config_id)
    return row


def _find_active(
    db: Session,
    *,
    scope: str,
    vertical: str | None,
    tenant_id: str | None,
    component_kind: str,
    component_name: str,
) -> ComponentConfiguration | None:
    q = db.query(ComponentConfiguration).filter(
        ComponentConfiguration.scope == scope,
        ComponentConfiguration.component_kind == component_kind,
        ComponentConfiguration.component_name == component_name,
        ComponentConfiguration.is_active.is_(True),
    )
    if vertical is None:
        q = q.filter(ComponentConfiguration.vertical.is_(None))
    else:
        q = q.filter(ComponentConfiguration.vertical == vertical)
    if tenant_id is None:
        q = q.filter(ComponentConfiguration.tenant_id.is_(None))
    else:
        q = q.filter(ComponentConfiguration.tenant_id == tenant_id)
    return q.first()


def create_configuration(
    db: Session,
    *,
    scope: str,
    vertical: str | None = None,
    tenant_id: str | None = None,
    component_kind: str,
    component_name: str,
    prop_overrides: Mapping[str, Any] | None = None,
    actor_user_id: str | None = None,
) -> ComponentConfiguration:
    _validate_scope_keys(scope, vertical, tenant_id)
    _validate_kind(component_kind)
    cleaned = validate_overrides(
        component_kind, component_name, prop_overrides or {}, strict=True
    )

    existing = _find_active(
        db,
        scope=scope,
        vertical=vertical,
        tenant_id=tenant_id,
        component_kind=component_kind,
        component_name=component_name,
    )
    next_version = 1
    if existing is not None:
        existing.is_active = False
        next_version = existing.version + 1

    row = ComponentConfiguration(
        scope=scope,
        vertical=vertical,
        tenant_id=tenant_id,
        component_kind=component_kind,
        component_name=component_name,
        prop_overrides=dict(cleaned),
        version=next_version,
        is_active=True,
        created_by=actor_user_id,
        updated_by=actor_user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_configuration(
    db: Session,
    config_id: str,
    *,
    prop_overrides: Mapping[str, Any],
    actor_user_id: str | None = None,
) -> ComponentConfiguration:
    prior = get_configuration(db, config_id)
    if not prior.is_active:
        raise ComponentConfigError(
            f"cannot update inactive configuration {config_id!r}"
        )

    cleaned = validate_overrides(
        prior.component_kind,
        prior.component_name,
        prop_overrides,
        strict=True,
    )

    prior.is_active = False
    new_row = ComponentConfiguration(
        scope=prior.scope,
        vertical=prior.vertical,
        tenant_id=prior.tenant_id,
        component_kind=prior.component_kind,
        component_name=prior.component_name,
        prop_overrides=dict(cleaned),
        version=prior.version + 1,
        is_active=True,
        created_by=actor_user_id,
        updated_by=actor_user_id,
    )
    db.add(new_row)
    db.commit()
    db.refresh(new_row)
    return new_row


# ─── Resolution ──────────────────────────────────────────────────


def resolve_configuration(
    db: Session,
    *,
    component_kind: str,
    component_name: str,
    vertical: str | None = None,
    tenant_id: str | None = None,
) -> dict:
    """Return the fully-merged prop overrides for a component at
    the given scope context.

    Resolution order: platform_default → vertical_default(vertical)
    → tenant_override(tenant_id). Deeper scope wins.

    Returns:
        {
            "component_kind": ...,
            "component_name": ...,
            "vertical": ...,
            "tenant_id": ...,
            "props": { name: value, ... },
            "sources": [
                {scope, id, version, applied_keys},
                ...
            ],
            "orphaned_keys": [...],   # keys present in storage
                                       # but missing from registry
        }
    """
    _validate_kind(component_kind)

    sources: list[dict] = []
    merged: dict = {}
    orphaned: list[str] = []

    snapshot = lookup_component(component_kind, component_name)
    component_known_keys: set[str] = set(snapshot.keys()) if snapshot else set()

    # ── Class layer (May 2026) ──────────────────────────────────
    # Walk the component's class memberships and apply class
    # defaults BEFORE platform_default. v1: each component belongs
    # to exactly one class (its ComponentKind), so this loop fires
    # once per resolution. Multi-class extension drops in here
    # without changing per-component layer semantics.
    from app.services.component_class_config import (  # avoid circular imports
        lookup_class,
        resolve_class_config,
        UnknownClass,
    )
    from app.services.component_config.registry_snapshot import (
        lookup_component_classes,
    )

    classes = lookup_component_classes(component_kind, component_name)
    # Class-known-keys is the union of the component's own snapshot
    # keys + every class's registry-snapshot keys. Component props
    # CAN override class-level shared props (e.g., a widget overrides
    # `shadowToken` for its specific instance), so the class layer's
    # known-keys must be applied to its OWN orphan check, not the
    # component's.
    for class_name in classes:
        class_schema = lookup_class(class_name)
        if class_schema is None:
            continue
        try:
            class_resolved = resolve_class_config(
                db, component_class=class_name
            )
        except UnknownClass:
            continue
        class_props = class_resolved.get("props") or {}
        if not class_props:
            continue
        # Class props apply to the merged map. Class layer's own
        # orphan check already happened in resolve_class_config.
        merged.update(class_props)
        sources.append(
            {
                "scope": "class_default",
                "component_class": class_name,
                "id": class_resolved["source"]["id"] if class_resolved["source"] else None,
                "version": class_resolved["source"]["version"]
                if class_resolved["source"]
                else None,
                "applied_keys": list(class_props.keys()),
            }
        )

    # Per-component layers below override class defaults at
    # matching keys.
    known_keys: set[str] = component_known_keys

    # Walk the inheritance chain. At each layer, drop orphaned
    # keys silently but record them so the admin UI can flag for
    # cleanup.
    layers: list[tuple[str, dict]] = []

    platform_row = _find_active(
        db,
        scope=SCOPE_PLATFORM_DEFAULT,
        vertical=None,
        tenant_id=None,
        component_kind=component_kind,
        component_name=component_name,
    )
    if platform_row is not None:
        layers.append((SCOPE_PLATFORM_DEFAULT, platform_row.__dict__))
        ov = dict(platform_row.prop_overrides or {})
        for k in list(ov.keys()):
            if known_keys and k not in known_keys:
                orphaned.append(k)
                del ov[k]
        merged.update(ov)
        sources.append(
            {
                "scope": SCOPE_PLATFORM_DEFAULT,
                "id": platform_row.id,
                "version": platform_row.version,
                "applied_keys": list(ov.keys()),
            }
        )

    if vertical is not None:
        vertical_row = _find_active(
            db,
            scope=SCOPE_VERTICAL_DEFAULT,
            vertical=vertical,
            tenant_id=None,
            component_kind=component_kind,
            component_name=component_name,
        )
        if vertical_row is not None:
            ov = dict(vertical_row.prop_overrides or {})
            for k in list(ov.keys()):
                if known_keys and k not in known_keys:
                    orphaned.append(k)
                    del ov[k]
            merged.update(ov)
            sources.append(
                {
                    "scope": SCOPE_VERTICAL_DEFAULT,
                    "vertical": vertical,
                    "id": vertical_row.id,
                    "version": vertical_row.version,
                    "applied_keys": list(ov.keys()),
                }
            )

    if tenant_id is not None:
        tenant_row = _find_active(
            db,
            scope=SCOPE_TENANT_OVERRIDE,
            vertical=None,
            tenant_id=tenant_id,
            component_kind=component_kind,
            component_name=component_name,
        )
        if tenant_row is not None:
            ov = dict(tenant_row.prop_overrides or {})
            for k in list(ov.keys()):
                if known_keys and k not in known_keys:
                    orphaned.append(k)
                    del ov[k]
            merged.update(ov)
            sources.append(
                {
                    "scope": SCOPE_TENANT_OVERRIDE,
                    "tenant_id": tenant_id,
                    "id": tenant_row.id,
                    "version": tenant_row.version,
                    "applied_keys": list(ov.keys()),
                }
            )

    return {
        "component_kind": component_kind,
        "component_name": component_name,
        "vertical": vertical,
        "tenant_id": tenant_id,
        "props": merged,
        "sources": sources,
        "orphaned_keys": sorted(set(orphaned)),
    }
