"""Dashboard Layouts API — admin endpoints (Phase R-0 of the
Runtime-Aware Editor).

Endpoints (all PlatformUser-gated, mounted at
`/api/platform/admin/visual-editor/dashboard-layouts`):

    GET    /              — list layout rows matching filters
    POST   /              — create a new active layout (versions a
                            prior row at the same tuple if present)
    PATCH  /{id}          — replace layout_config + bump version
    GET    /resolve       — full inheritance walk for the editor's
                            inheritance indicator
    GET    /{id}          — single row (for History UI)

Audit attribution: Phase 8a relocation note (CLAUDE.md §4) — created_by
/ updated_by are FK-constrained to users.id which PlatformUser ids
cannot satisfy. Pass actor_user_id=None for platform-user writes for
now; column-level attribution lands in a future migration.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.services.dashboard_layouts import (
    DashboardLayoutNotFound,
    DashboardLayoutScopeMismatch,
    DashboardLayoutServiceError,
    InvalidDashboardLayoutShape,
    create_layout,
    get_layout_by_id,
    list_layouts,
    resolve_layout,
    update_layout,
)


logger = logging.getLogger(__name__)
router = APIRouter()


Scope = Literal["platform_default", "vertical_default", "tenant_default"]


# ─── Schemas ────────────────────────────────────────────────────


class _LayoutResponse(BaseModel):
    id: str
    scope: Scope
    vertical: str | None = None
    tenant_id: str | None = None
    page_context: str
    layout_config: list[dict[str, Any]]
    version: int
    is_active: bool
    created_at: Any
    updated_at: Any


class _CreateLayoutRequest(BaseModel):
    scope: Scope
    vertical: str | None = Field(default=None)
    tenant_id: str | None = Field(default=None)
    page_context: str
    layout_config: list[dict[str, Any]] = Field(default_factory=list)


class _UpdateLayoutRequest(BaseModel):
    layout_config: list[dict[str, Any]]


class _ResolveResponse(BaseModel):
    layout_config: list[dict[str, Any]]
    source: Scope | None
    source_id: str | None
    source_version: int | None
    sources: list[dict[str, Any]]
    page_context: str
    vertical: str | None = None
    tenant_id: str | None = None


# ─── Translation helpers ────────────────────────────────────────


def _row_to_response(row) -> _LayoutResponse:
    return _LayoutResponse(
        id=row.id,
        scope=row.scope,
        vertical=row.vertical,
        tenant_id=row.tenant_id,
        page_context=row.page_context,
        layout_config=list(row.layout_config or []),
        version=row.version,
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _translate_layout_error(err: DashboardLayoutServiceError) -> HTTPException:
    if isinstance(err, DashboardLayoutNotFound):
        return HTTPException(status_code=404, detail=str(err) or "Layout not found")
    if isinstance(err, (DashboardLayoutScopeMismatch, InvalidDashboardLayoutShape)):
        return HTTPException(status_code=400, detail=str(err))
    return HTTPException(status_code=400, detail=str(err))


# ─── Endpoints ──────────────────────────────────────────────────


@router.get("/", response_model=list[_LayoutResponse])
def list_dashboard_layouts(
    scope: Scope | None = Query(default=None),
    vertical: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    page_context: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    _platform_user: PlatformUser = Depends(get_current_platform_user),
) -> list[_LayoutResponse]:
    try:
        rows = list_layouts(
            db,
            scope=scope,
            vertical=vertical,
            tenant_id=tenant_id,
            page_context=page_context,
            include_inactive=include_inactive,
        )
    except DashboardLayoutServiceError as err:
        raise _translate_layout_error(err)
    return [_row_to_response(r) for r in rows]


@router.get("/resolve", response_model=_ResolveResponse)
def resolve_dashboard_layout(
    page_context: str = Query(...),
    vertical: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _platform_user: PlatformUser = Depends(get_current_platform_user),
) -> _ResolveResponse:
    try:
        result = resolve_layout(
            db,
            page_context=page_context,
            vertical=vertical,
            tenant_id=tenant_id,
        )
    except DashboardLayoutServiceError as err:
        raise _translate_layout_error(err)
    return _ResolveResponse(**result)


@router.get("/{layout_id}", response_model=_LayoutResponse)
def get_dashboard_layout(
    layout_id: str,
    db: Session = Depends(get_db),
    _platform_user: PlatformUser = Depends(get_current_platform_user),
) -> _LayoutResponse:
    try:
        row = get_layout_by_id(db, layout_id)
    except DashboardLayoutServiceError as err:
        raise _translate_layout_error(err)
    return _row_to_response(row)


@router.post("/", response_model=_LayoutResponse, status_code=201)
def create_dashboard_layout(
    payload: _CreateLayoutRequest,
    db: Session = Depends(get_db),
    _platform_user: PlatformUser = Depends(get_current_platform_user),
) -> _LayoutResponse:
    try:
        # actor_user_id=None per CLAUDE.md §4 audit-attribution note.
        # PlatformUser ids cannot satisfy users.id FK constraint.
        row = create_layout(
            db,
            scope=payload.scope,
            vertical=payload.vertical,
            tenant_id=payload.tenant_id,
            page_context=payload.page_context,
            layout_config=payload.layout_config,
            actor_user_id=None,
        )
    except DashboardLayoutServiceError as err:
        raise _translate_layout_error(err)
    return _row_to_response(row)


@router.patch("/{layout_id}", response_model=_LayoutResponse)
def update_dashboard_layout(
    layout_id: str,
    payload: _UpdateLayoutRequest,
    db: Session = Depends(get_db),
    _platform_user: PlatformUser = Depends(get_current_platform_user),
) -> _LayoutResponse:
    try:
        row = update_layout(
            db,
            layout_id,
            layout_config=payload.layout_config,
            actor_user_id=None,
        )
    except DashboardLayoutServiceError as err:
        raise _translate_layout_error(err)
    return _row_to_response(row)
