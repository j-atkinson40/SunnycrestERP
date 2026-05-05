"""Platform Themes API — admin endpoints (Phase 2 of the Admin
Visual Editor).

Endpoints (all admin-gated, mounted at `/api/v1/admin/themes`):

    GET    /              — list theme rows matching filters
    POST   /              — create a new active theme row (versions
                             a prior row at the same tuple if one exists)
    PATCH  /{id}          — replace token_overrides on the active
                             row at the same tuple (versioning)
    GET    /resolve       — fully-merged inheritance walk for the
                             editor's live preview
    GET    /{id}          — single row (for History UI; Phase 3 surface)

Tenant-facing Workshop UI ships in a later phase. Phase 2 is
admin-only support tooling.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.services.platform_themes import (
    InvalidThemeShape,
    ThemeNotFound,
    ThemeScopeMismatch,
    ThemeServiceError,
    create_theme,
    get_theme,
    list_themes,
    resolve_theme,
    update_theme,
)


logger = logging.getLogger(__name__)
router = APIRouter()


Scope = Literal["platform_default", "vertical_default", "tenant_override"]
Mode = Literal["light", "dark"]


# ─── Pydantic shapes ─────────────────────────────────────────────


class _ThemeResponse(BaseModel):
    id: str
    scope: Scope
    vertical: str | None
    tenant_id: str | None
    mode: Mode
    token_overrides: dict[str, Any]
    version: int
    is_active: bool
    created_at: str
    updated_at: str
    created_by: str | None = None
    updated_by: str | None = None


class _CreateThemeRequest(BaseModel):
    scope: Scope
    vertical: str | None = None
    tenant_id: str | None = None
    mode: Mode
    token_overrides: dict[str, Any] = Field(default_factory=dict)


class _PatchThemeRequest(BaseModel):
    token_overrides: dict[str, Any] = Field(default_factory=dict)


class _ResolveResponse(BaseModel):
    mode: Mode
    vertical: str | None
    tenant_id: str | None
    tokens: dict[str, Any]
    sources: list[dict[str, Any]]


# ─── Helpers ─────────────────────────────────────────────────────


def _row_to_response(row) -> _ThemeResponse:
    return _ThemeResponse(
        id=row.id,
        scope=row.scope,
        vertical=row.vertical,
        tenant_id=row.tenant_id,
        mode=row.mode,
        token_overrides=dict(row.token_overrides or {}),
        version=row.version,
        is_active=row.is_active,
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
        created_by=row.created_by,
        updated_by=row.updated_by,
    )


def _translate_service_error(exc: ThemeServiceError) -> HTTPException:
    if isinstance(exc, ThemeNotFound):
        return HTTPException(status_code=404, detail=str(exc) or "Theme not found")
    if isinstance(exc, (InvalidThemeShape, ThemeScopeMismatch)):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=409, detail=str(exc))


# ─── Endpoints ───────────────────────────────────────────────────


@router.get("/", response_model=list[_ThemeResponse])
def admin_list_themes(
    scope: Scope | None = Query(default=None),
    vertical: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    mode: Mode | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[_ThemeResponse]:
    rows = list_themes(
        db,
        scope=scope,
        vertical=vertical,
        tenant_id=tenant_id,
        mode=mode,
        include_inactive=include_inactive,
    )
    return [_row_to_response(r) for r in rows]


@router.get("/resolve", response_model=_ResolveResponse)
def admin_resolve_theme(
    mode: Mode = Query(...),
    vertical: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> _ResolveResponse:
    """Return the fully-merged token override map at the requested
    scope context. Deeper scope wins. Sources array reports which
    rows contributed (for the UI's "overridden at X" indicator).
    """
    try:
        result = resolve_theme(
            db,
            mode=mode,
            vertical=vertical,
            tenant_id=tenant_id,
        )
    except ThemeServiceError as exc:
        raise _translate_service_error(exc)
    return _ResolveResponse(**result)


@router.get("/{theme_id}", response_model=_ThemeResponse)
def admin_get_theme(
    theme_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> _ThemeResponse:
    try:
        row = get_theme(db, theme_id)
    except ThemeServiceError as exc:
        raise _translate_service_error(exc)
    return _row_to_response(row)


@router.post("/", response_model=_ThemeResponse, status_code=201)
def admin_create_theme(
    body: _CreateThemeRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> _ThemeResponse:
    try:
        row = create_theme(
            db,
            scope=body.scope,
            vertical=body.vertical,
            tenant_id=body.tenant_id,
            mode=body.mode,
            token_overrides=body.token_overrides,
            actor_user_id=admin.id,
        )
    except ThemeServiceError as exc:
        raise _translate_service_error(exc)
    return _row_to_response(row)


@router.patch("/{theme_id}", response_model=_ThemeResponse)
def admin_patch_theme(
    theme_id: str,
    body: _PatchThemeRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> _ThemeResponse:
    try:
        row = update_theme(
            db,
            theme_id,
            token_overrides=body.token_overrides,
            actor_user_id=admin.id,
        )
    except ThemeServiceError as exc:
        raise _translate_service_error(exc)
    return _row_to_response(row)
