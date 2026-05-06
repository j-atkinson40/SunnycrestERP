"""Component Class Configurations API — admin endpoints (May 2026
class layer).

Endpoints mounted at `/api/platform/admin/visual-editor/classes`:

    GET    /              — list class config rows (filter by
                             component_class, include_inactive)
    POST   /              — create / version a class config
    PATCH  /{id}          — replace prop_overrides on the row
    GET    /resolve       — resolved class default for a class
    GET    /registry      — class registry snapshot (class names +
                             configurable prop schema)
    GET    /{id}          — single row

All admin-gated via PlatformUser auth.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.services.component_class_config import (
    CLASS_REGISTRY_SNAPSHOT,
    ClassConfigError,
    ClassConfigNotFound,
    InvalidClassConfigShape,
    UnknownClass,
    all_classes,
    create_class_config,
    get_class_config,
    list_class_configs,
    resolve_class_config,
    update_class_config,
)


logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Pydantic shapes ─────────────────────────────────────────────


class _ClassConfigResponse(BaseModel):
    id: str
    component_class: str
    prop_overrides: dict
    version: int
    is_active: bool
    created_at: str
    updated_at: str
    created_by: str | None
    updated_by: str | None


class _CreateClassConfigRequest(BaseModel):
    component_class: str
    prop_overrides: dict = Field(default_factory=dict)


class _UpdateClassConfigRequest(BaseModel):
    prop_overrides: dict


class _ResolvedClassResponse(BaseModel):
    component_class: str
    props: dict
    source: dict | None
    orphaned_keys: list[str]


class _RegistryResponse(BaseModel):
    classes: dict[str, dict[str, dict]]


def _serialize(row) -> _ClassConfigResponse:
    return _ClassConfigResponse(
        id=row.id,
        component_class=row.component_class,
        prop_overrides=dict(row.prop_overrides or {}),
        version=row.version,
        is_active=row.is_active,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
        created_by=row.created_by,
        updated_by=row.updated_by,
    )


def _translate_error(err: ClassConfigError) -> HTTPException:
    return HTTPException(status_code=err.http_status, detail=str(err))


# ─── Endpoints ───────────────────────────────────────────────────


@router.get("/", response_model=list[_ClassConfigResponse])
def list_endpoint(
    component_class: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> list[_ClassConfigResponse]:
    rows = list_class_configs(
        db,
        component_class=component_class,
        include_inactive=include_inactive,
    )
    return [_serialize(r) for r in rows]


@router.get("/registry", response_model=_RegistryResponse)
def registry_endpoint(
    admin: PlatformUser = Depends(get_current_platform_user),
) -> _RegistryResponse:
    """Return the class registry snapshot the editor uses to render
    its config controls. Class names + class-level configurable
    props with type + bounds + tokenCategory."""
    return _RegistryResponse(classes=dict(CLASS_REGISTRY_SNAPSHOT))


@router.get("/resolve", response_model=_ResolvedClassResponse)
def resolve_endpoint(
    component_class: str = Query(...),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> _ResolvedClassResponse:
    try:
        result = resolve_class_config(db, component_class=component_class)
    except ClassConfigError as err:
        raise _translate_error(err)
    return _ResolvedClassResponse(**result)


@router.get("/{config_id}", response_model=_ClassConfigResponse)
def get_endpoint(
    config_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> _ClassConfigResponse:
    try:
        row = get_class_config(db, config_id=config_id)
    except ClassConfigError as err:
        raise _translate_error(err)
    return _serialize(row)


@router.post(
    "/",
    response_model=_ClassConfigResponse,
    status_code=201,
)
def create_endpoint(
    body: _CreateClassConfigRequest,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> _ClassConfigResponse:
    try:
        row = create_class_config(
            db,
            component_class=body.component_class,
            prop_overrides=body.prop_overrides,
            # NOTE: PlatformUser id cannot satisfy users.id FK on
            # created_by/updated_by columns. Documented in CLAUDE.md
            # §4 admin platform architecture.
            actor_user_id=None,
        )
    except ClassConfigError as err:
        raise _translate_error(err)
    return _serialize(row)


@router.patch("/{config_id}", response_model=_ClassConfigResponse)
def update_endpoint(
    config_id: str,
    body: _UpdateClassConfigRequest,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> _ClassConfigResponse:
    try:
        row = update_class_config(
            db,
            config_id=config_id,
            prop_overrides=body.prop_overrides,
            actor_user_id=None,
        )
    except ClassConfigError as err:
        raise _translate_error(err)
    return _serialize(row)
