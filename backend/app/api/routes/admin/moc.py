"""Maps of Content — admin platform router (MoC Phase 1).

Mounted at `/api/platform/admin/moc` (get_current_platform_user). A thin
realm layer over the realm-agnostic `maps_of_content` service — auth +
response shaping live here; the service takes operational primitives only,
so a future tenant router (`/api/v1/moc/*`, get_current_user) reuses it
unchanged.

    GET    /                 — list pages (scope / vertical / tenant filters)
    GET    /read             — resolved page for a context (3-tier walk),
                               references resolved for rendering
    POST   /                 — create a page
    GET    /{page_id}        — single raw page (authoring editor)
    GET    /{page_id}/read   — resolved page by id (references resolved)
    PATCH  /{page_id}        — update title/description/slug/sections
    DELETE /{page_id}        — soft-delete (frees the identity tuple)
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.database import get_db
from app.models.moc_page import MoCPage
from app.models.platform_user import PlatformUser
from app.services import maps_of_content as moc
from app.services.maps_of_content.task_catalog import resolve_task_catalog

logger = logging.getLogger(__name__)
router = APIRouter()

Scope = Literal["platform_default", "vertical_default", "tenant_override"]


# ─── Pydantic shapes ─────────────────────────────────────────────


class _PageResponse(BaseModel):
    id: str
    scope: str
    vertical: str | None
    tenant_id: str | None
    slug: str
    title: str
    description: str | None
    sections: list[Any]


class _CreatePage(BaseModel):
    scope: Scope = "vertical_default"
    vertical: str | None = None
    tenant_id: str | None = None
    slug: str
    title: str
    description: str | None = None
    sections: list[Any] = []


class _UpdatePage(BaseModel):
    title: str | None = None
    description: str | None = None
    slug: str | None = None
    sections: list[Any] | None = None


def _row_to_response(row: MoCPage) -> _PageResponse:
    return _PageResponse(
        id=row.id,
        scope=row.scope,
        vertical=row.vertical,
        tenant_id=row.tenant_id,
        slug=row.slug,
        title=row.title,
        description=row.description,
        sections=row.sections or [],
    )


# ─── Endpoints ───────────────────────────────────────────────────


@router.get("/", response_model=list[_PageResponse])
def admin_list_pages(
    scope: Scope | None = Query(None),
    vertical: str | None = Query(None),
    tenant_id: str | None = Query(None),
    include_inactive: bool = Query(False),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    rows = moc.list_pages(
        db,
        scope=scope,
        vertical=vertical,
        tenant_id=tenant_id,
        include_inactive=include_inactive,
    )
    return [_row_to_response(r) for r in rows]


@router.get("/read")
def admin_read_for_context(
    vertical: str | None = Query(None),
    tenant_id: str | None = Query(None),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """The resolved page for a (vertical, tenant) context — the 3-tier walk
    + reference resolution. The page surface's read path. 404 when no page
    resolves for the context."""
    view = moc.read_for_context(db, vertical=vertical, tenant_id=tenant_id)
    if view is None:
        raise HTTPException(status_code=404, detail="no MoC page for context")
    return view


@router.get("/tasks")
def admin_read_task_catalog(
    vertical: str = Query(...),
    tenant_id: str | None = Query(None),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """The vertical's task catalog (MoC-2b). Each task's ONE workflow + MANY
    focuses are resolved through the SAME `BUILDERS` path the cards use, so the
    frontend's `mocDeepLink` produces byte-identical hrefs. A reference that
    doesn't exist yet resolves orphan-tolerant (workflow null / focus
    available=False) — never errors. Empty list when no tasks are seeded."""
    return resolve_task_catalog(db, vertical=vertical, tenant_id=tenant_id)


@router.post("/", response_model=_PageResponse, status_code=201)
def admin_create_page(
    body: _CreatePage,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    try:
        row = moc.create_page(
            db,
            scope=body.scope,
            vertical=body.vertical,
            tenant_id=body.tenant_id,
            slug=body.slug,
            title=body.title,
            description=body.description,
            sections=body.sections,
            actor_id=admin.id,
        )
    except moc.InvalidReference as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _row_to_response(row)


@router.get("/{page_id}", response_model=_PageResponse)
def admin_get_page(
    page_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    row = moc.get_page(db, page_id)
    if row is None:
        raise HTTPException(status_code=404, detail="page not found")
    return _row_to_response(row)


@router.get("/{page_id}/read")
def admin_read_page(
    page_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    view = moc.read_page(db, page_id)
    if view is None:
        raise HTTPException(status_code=404, detail="page not found")
    return view


@router.patch("/{page_id}", response_model=_PageResponse)
def admin_update_page(
    page_id: str,
    body: _UpdatePage,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    try:
        row = moc.update_page(
            db,
            page_id,
            actor_id=admin.id,
            title=body.title,
            description=body.description,
            slug=body.slug,
            sections=body.sections,
        )
    except moc.InvalidReference as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if row is None:
        raise HTTPException(status_code=404, detail="page not found")
    return _row_to_response(row)


@router.delete("/{page_id}", status_code=204)
def admin_delete_page(
    page_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    ok = moc.delete_page(db, page_id, actor_id=admin.id)
    if not ok:
        raise HTTPException(status_code=404, detail="page not found")
