"""Focus Compositions API — admin endpoints (May 2026 composition layer).

Endpoints mounted at `/api/platform/admin/visual-editor/compositions`:

    GET    /              — list compositions matching filters
    POST   /              — create / version a composition
    PATCH  /{id}          — replace placements / canvas_config
    GET    /resolve       — resolved composition (inheritance walk)
    GET    /{id}          — single row

All admin-gated (PlatformUser).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.services.focus_compositions import (
    CompositionError,
    CompositionNotFound,
    InvalidCompositionShape,
    create_composition,
    get_composition,
    list_compositions,
    resolve_composition,
    update_composition,
)


logger = logging.getLogger(__name__)
router = APIRouter()


class _CompositionResponse(BaseModel):
    id: str
    scope: str
    vertical: str | None
    tenant_id: str | None
    focus_type: str
    placements: list
    canvas_config: dict
    version: int
    is_active: bool
    created_at: str
    updated_at: str
    created_by: str | None
    updated_by: str | None


class _CreateRequest(BaseModel):
    scope: str
    focus_type: str
    vertical: str | None = None
    tenant_id: str | None = None
    placements: list = Field(default_factory=list)
    canvas_config: dict = Field(default_factory=dict)


class _UpdateRequest(BaseModel):
    placements: list | None = None
    canvas_config: dict | None = None


class _ResolveResponse(BaseModel):
    focus_type: str
    vertical: str | None
    tenant_id: str | None
    source: str | None
    source_id: str | None
    source_version: int | None
    placements: list
    canvas_config: dict


def _serialize(row) -> _CompositionResponse:
    return _CompositionResponse(
        id=row.id,
        scope=row.scope,
        vertical=row.vertical,
        tenant_id=row.tenant_id,
        focus_type=row.focus_type,
        placements=list(row.placements or []),
        canvas_config=dict(row.canvas_config or {}),
        version=row.version,
        is_active=row.is_active,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
        created_by=row.created_by,
        updated_by=row.updated_by,
    )


def _translate_error(err: CompositionError) -> HTTPException:
    return HTTPException(status_code=err.http_status, detail=str(err))


@router.get("/", response_model=list[_CompositionResponse])
def list_endpoint(
    scope: str | None = Query(default=None),
    vertical: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    focus_type: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> list[_CompositionResponse]:
    rows = list_compositions(
        db,
        scope=scope,
        vertical=vertical,
        tenant_id=tenant_id,
        focus_type=focus_type,
        include_inactive=include_inactive,
    )
    return [_serialize(r) for r in rows]


@router.get("/resolve", response_model=_ResolveResponse)
def resolve_endpoint(
    focus_type: str = Query(...),
    vertical: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> _ResolveResponse:
    result = resolve_composition(
        db, focus_type=focus_type, vertical=vertical, tenant_id=tenant_id
    )
    return _ResolveResponse(**result)


@router.get("/{composition_id}", response_model=_CompositionResponse)
def get_endpoint(
    composition_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> _CompositionResponse:
    try:
        row = get_composition(db, composition_id=composition_id)
    except CompositionError as err:
        raise _translate_error(err)
    return _serialize(row)


@router.post("/", response_model=_CompositionResponse, status_code=201)
def create_endpoint(
    body: _CreateRequest,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> _CompositionResponse:
    try:
        row = create_composition(
            db,
            scope=body.scope,
            focus_type=body.focus_type,
            vertical=body.vertical,
            tenant_id=body.tenant_id,
            placements=body.placements,
            canvas_config=body.canvas_config,
            # NOTE: PlatformUser id cannot satisfy users.id FK; same
            # carry-forward limitation flagged in CLAUDE.md §4.
            actor_user_id=None,
        )
    except CompositionError as err:
        raise _translate_error(err)
    return _serialize(row)


@router.patch("/{composition_id}", response_model=_CompositionResponse)
def update_endpoint(
    composition_id: str,
    body: _UpdateRequest,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> _CompositionResponse:
    try:
        row = update_composition(
            db,
            composition_id=composition_id,
            placements=body.placements,
            canvas_config=body.canvas_config,
            actor_user_id=None,
        )
    except CompositionError as err:
        raise _translate_error(err)
    return _serialize(row)
