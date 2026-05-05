"""Component Configurations API — admin endpoints (Phase 3 of the
Admin Visual Editor).

Endpoints (all admin-gated, mounted at `/api/v1/admin/component-configurations`):

    GET    /              — list rows matching filters
    POST   /              — create a new active configuration
                             (versions a prior row at the same tuple)
    PATCH  /{id}          — replace prop_overrides on the active row
    GET    /resolve       — fully-merged inheritance walk
    GET    /registry      — registry snapshot (kind+name+prop schema)
    GET    /{id}          — single row (for History UI; Phase 4 surface)
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models.user import User
from app.services.component_config import (
    ComponentConfigError,
    ComponentConfigNotFound,
    ConfigScopeMismatch,
    InvalidConfigShape,
    PropValidationError,
    REGISTRY_SNAPSHOT,
    UnknownComponent,
    create_configuration,
    get_configuration,
    list_configurations,
    resolve_configuration,
    update_configuration,
)


logger = logging.getLogger(__name__)
router = APIRouter()


Scope = Literal["platform_default", "vertical_default", "tenant_override"]
ComponentKind = Literal[
    "widget",
    "focus",
    "focus-template",
    "document-block",
    "pulse-widget",
    "workflow-node",
    "layout",
    "composite",
]


# ─── Pydantic shapes ─────────────────────────────────────────────


class _ConfigResponse(BaseModel):
    id: str
    scope: Scope
    vertical: str | None
    tenant_id: str | None
    component_kind: str
    component_name: str
    prop_overrides: dict[str, Any]
    version: int
    is_active: bool
    created_at: str
    updated_at: str
    created_by: str | None = None
    updated_by: str | None = None


class _CreateConfigRequest(BaseModel):
    scope: Scope
    vertical: str | None = None
    tenant_id: str | None = None
    component_kind: ComponentKind
    component_name: str = Field(min_length=1, max_length=96)
    prop_overrides: dict[str, Any] = Field(default_factory=dict)


class _PatchConfigRequest(BaseModel):
    prop_overrides: dict[str, Any] = Field(default_factory=dict)


class _ResolveResponse(BaseModel):
    component_kind: str
    component_name: str
    vertical: str | None
    tenant_id: str | None
    props: dict[str, Any]
    sources: list[dict[str, Any]]
    orphaned_keys: list[str]


class _RegistryComponentEntry(BaseModel):
    component_kind: str
    component_name: str
    props: dict[str, dict[str, Any]]


class _RegistryResponse(BaseModel):
    components: list[_RegistryComponentEntry]


# ─── Helpers ─────────────────────────────────────────────────────


def _row_to_response(row) -> _ConfigResponse:
    return _ConfigResponse(
        id=row.id,
        scope=row.scope,
        vertical=row.vertical,
        tenant_id=row.tenant_id,
        component_kind=row.component_kind,
        component_name=row.component_name,
        prop_overrides=dict(row.prop_overrides or {}),
        version=row.version,
        is_active=row.is_active,
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
        created_by=row.created_by,
        updated_by=row.updated_by,
    )


def _translate_service_error(exc: ComponentConfigError) -> HTTPException:
    if isinstance(exc, ComponentConfigNotFound):
        return HTTPException(
            status_code=404, detail=str(exc) or "Configuration not found"
        )
    if isinstance(
        exc,
        (InvalidConfigShape, ConfigScopeMismatch, PropValidationError, UnknownComponent),
    ):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=409, detail=str(exc))


# ─── Endpoints ───────────────────────────────────────────────────


@router.get("/registry", response_model=_RegistryResponse)
def admin_get_registry_snapshot(
    admin: User = Depends(require_admin),
) -> _RegistryResponse:
    """Return the backend registry snapshot. Used by the editor's
    component browser + the validation-bounds preview."""
    components = [
        _RegistryComponentEntry(
            component_kind=kind,
            component_name=name,
            props=props,
        )
        for (kind, name), props in REGISTRY_SNAPSHOT.items()
    ]
    return _RegistryResponse(components=components)


@router.get("/", response_model=list[_ConfigResponse])
def admin_list_configurations(
    scope: Scope | None = Query(default=None),
    vertical: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    component_kind: ComponentKind | None = Query(default=None),
    component_name: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[_ConfigResponse]:
    rows = list_configurations(
        db,
        scope=scope,
        vertical=vertical,
        tenant_id=tenant_id,
        component_kind=component_kind,
        component_name=component_name,
        include_inactive=include_inactive,
    )
    return [_row_to_response(r) for r in rows]


@router.get("/resolve", response_model=_ResolveResponse)
def admin_resolve_configuration(
    component_kind: ComponentKind = Query(...),
    component_name: str = Query(..., min_length=1, max_length=96),
    vertical: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> _ResolveResponse:
    try:
        result = resolve_configuration(
            db,
            component_kind=component_kind,
            component_name=component_name,
            vertical=vertical,
            tenant_id=tenant_id,
        )
    except ComponentConfigError as exc:
        raise _translate_service_error(exc)
    return _ResolveResponse(**result)


@router.get("/{config_id}", response_model=_ConfigResponse)
def admin_get_configuration(
    config_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> _ConfigResponse:
    try:
        row = get_configuration(db, config_id)
    except ComponentConfigError as exc:
        raise _translate_service_error(exc)
    return _row_to_response(row)


@router.post("/", response_model=_ConfigResponse, status_code=201)
def admin_create_configuration(
    body: _CreateConfigRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> _ConfigResponse:
    try:
        row = create_configuration(
            db,
            scope=body.scope,
            vertical=body.vertical,
            tenant_id=body.tenant_id,
            component_kind=body.component_kind,
            component_name=body.component_name,
            prop_overrides=body.prop_overrides,
            actor_user_id=admin.id,
        )
    except ComponentConfigError as exc:
        raise _translate_service_error(exc)
    return _row_to_response(row)


@router.patch("/{config_id}", response_model=_ConfigResponse)
def admin_patch_configuration(
    config_id: str,
    body: _PatchConfigRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> _ConfigResponse:
    try:
        row = update_configuration(
            db,
            config_id,
            prop_overrides=body.prop_overrides,
            actor_user_id=admin.id,
        )
    except ComponentConfigError as exc:
        raise _translate_service_error(exc)
    return _row_to_response(row)
