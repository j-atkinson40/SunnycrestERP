"""Workflow Templates API — admin endpoints (Phase 4 of the
Admin Visual Editor).

Endpoints (all admin-gated, mounted at
`/api/v1/admin/workflow-templates`):

    GET  /                              — list templates
    POST /                              — create template
    GET  /resolve                       — full inheritance walk
    GET  /{id}                          — single template
    GET  /{id}/dependent-forks          — forks based on this template chain
    PATCH /{id}                         — update template (versions + notify forks)
    POST /{id}/fork                     — create a tenant fork from this template
    POST /forks/{fork_id}/accept-merge  — tenant accepts upstream merge
    POST /forks/{fork_id}/reject-merge  — tenant rejects upstream merge
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.services.workflow_templates import (
    CanvasValidationError,
    ForkNotFound,
    InvalidTemplateShape,
    TemplateNotFound,
    TemplateScopeMismatch,
    WorkflowTemplateError,
    accept_merge,
    create_template,
    fork_for_tenant,
    get_dependent_forks,
    get_fork,
    get_template,
    list_forks,
    list_templates,
    reject_merge,
    resolve_workflow,
    update_template,
)


logger = logging.getLogger(__name__)
router = APIRouter()


Scope = Literal["platform_default", "vertical_default"]


# ─── Pydantic shapes ─────────────────────────────────────────────


class _TemplateMetadataResponse(BaseModel):
    id: str
    scope: Scope
    vertical: str | None
    workflow_type: str
    display_name: str
    description: str | None
    version: int
    is_active: bool
    created_at: str
    updated_at: str
    created_by: str | None = None
    updated_by: str | None = None


class _TemplateFullResponse(_TemplateMetadataResponse):
    canvas_state: dict[str, Any]


class _CreateTemplateRequest(BaseModel):
    scope: Scope
    vertical: str | None = None
    workflow_type: str = Field(min_length=1, max_length=96)
    display_name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    canvas_state: dict[str, Any] = Field(default_factory=dict)
    notify_forks: bool = True


class _PatchTemplateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=160)
    description: str | None = None
    canvas_state: dict[str, Any] | None = None
    notify_forks: bool = True


class _ForkResponse(BaseModel):
    id: str
    tenant_id: str
    workflow_type: str
    forked_from_template_id: str | None
    forked_from_version: int
    canvas_state: dict[str, Any]
    pending_merge_available: bool
    pending_merge_template_id: str | None
    version: int
    is_active: bool
    created_at: str
    updated_at: str


class _ForkRequest(BaseModel):
    tenant_id: str = Field(min_length=1)


class _ResolveResponse(BaseModel):
    workflow_type: str
    vertical: str | None
    tenant_id: str | None
    source: str | None
    source_id: str | None
    source_version: int | None
    canvas_state: dict[str, Any]
    pending_merge_available: bool


# ─── Helpers ─────────────────────────────────────────────────────


def _row_to_metadata(row) -> _TemplateMetadataResponse:
    return _TemplateMetadataResponse(
        id=row.id,
        scope=row.scope,
        vertical=row.vertical,
        workflow_type=row.workflow_type,
        display_name=row.display_name,
        description=row.description,
        version=row.version,
        is_active=row.is_active,
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
        created_by=row.created_by,
        updated_by=row.updated_by,
    )


def _row_to_full(row) -> _TemplateFullResponse:
    return _TemplateFullResponse(
        id=row.id,
        scope=row.scope,
        vertical=row.vertical,
        workflow_type=row.workflow_type,
        display_name=row.display_name,
        description=row.description,
        canvas_state=dict(row.canvas_state or {}),
        version=row.version,
        is_active=row.is_active,
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
        created_by=row.created_by,
        updated_by=row.updated_by,
    )


def _fork_to_response(fork) -> _ForkResponse:
    return _ForkResponse(
        id=fork.id,
        tenant_id=fork.tenant_id,
        workflow_type=fork.workflow_type,
        forked_from_template_id=fork.forked_from_template_id,
        forked_from_version=fork.forked_from_version,
        canvas_state=dict(fork.canvas_state or {}),
        pending_merge_available=fork.pending_merge_available,
        pending_merge_template_id=fork.pending_merge_template_id,
        version=fork.version,
        is_active=fork.is_active,
        created_at=fork.created_at.isoformat() if fork.created_at else "",
        updated_at=fork.updated_at.isoformat() if fork.updated_at else "",
    )


def _translate_service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (TemplateNotFound, ForkNotFound)):
        return HTTPException(status_code=404, detail=str(exc) or "Not found")
    if isinstance(
        exc,
        (
            InvalidTemplateShape,
            TemplateScopeMismatch,
            CanvasValidationError,
        ),
    ):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, WorkflowTemplateError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


# ─── Endpoints ───────────────────────────────────────────────────


@router.get("/", response_model=list[_TemplateMetadataResponse])
def admin_list_templates(
    scope: Scope | None = Query(default=None),
    vertical: str | None = Query(default=None),
    workflow_type: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> list[_TemplateMetadataResponse]:
    """List endpoint returns metadata only — no canvas_state in
    the payload to keep list responses lightweight even for
    workflows with 30-50 nodes."""
    rows = list_templates(
        db,
        scope=scope,
        vertical=vertical,
        workflow_type=workflow_type,
        include_inactive=include_inactive,
    )
    return [_row_to_metadata(r) for r in rows]


@router.get("/resolve", response_model=_ResolveResponse)
def admin_resolve_workflow(
    workflow_type: str = Query(..., min_length=1, max_length=96),
    vertical: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> _ResolveResponse:
    try:
        result = resolve_workflow(
            db,
            workflow_type=workflow_type,
            vertical=vertical,
            tenant_id=tenant_id,
        )
    except Exception as exc:
        raise _translate_service_error(exc)
    return _ResolveResponse(**result)


@router.get("/{template_id}", response_model=_TemplateFullResponse)
def admin_get_template(
    template_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> _TemplateFullResponse:
    try:
        row = get_template(db, template_id)
    except Exception as exc:
        raise _translate_service_error(exc)
    return _row_to_full(row)


@router.get("/{template_id}/dependent-forks", response_model=list[_ForkResponse])
def admin_list_dependent_forks(
    template_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> list[_ForkResponse]:
    try:
        forks = get_dependent_forks(db, template_id)
    except Exception as exc:
        raise _translate_service_error(exc)
    return [_fork_to_response(f) for f in forks]


@router.post("/", response_model=_TemplateFullResponse, status_code=201)
def admin_create_template(
    body: _CreateTemplateRequest,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> _TemplateFullResponse:
    try:
        row = create_template(
            db,
            scope=body.scope,
            vertical=body.vertical,
            workflow_type=body.workflow_type,
            display_name=body.display_name,
            description=body.description,
            canvas_state=body.canvas_state,
            actor_user_id=None,  # NOTE: PlatformUser id cannot satisfy users.id FK; platform-user attribution requires migration to drop FK or add platform_user_id columns. Tracked as relocation-phase follow-up.
            notify_forks=body.notify_forks,
        )
    except Exception as exc:
        raise _translate_service_error(exc)
    return _row_to_full(row)


@router.patch("/{template_id}", response_model=_TemplateFullResponse)
def admin_patch_template(
    template_id: str,
    body: _PatchTemplateRequest,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> _TemplateFullResponse:
    try:
        row = update_template(
            db,
            template_id,
            display_name=body.display_name,
            description=body.description,
            canvas_state=body.canvas_state,
            actor_user_id=None,  # NOTE: PlatformUser id cannot satisfy users.id FK; platform-user attribution requires migration to drop FK or add platform_user_id columns. Tracked as relocation-phase follow-up.
            notify_forks=body.notify_forks,
        )
    except Exception as exc:
        raise _translate_service_error(exc)
    return _row_to_full(row)


@router.post("/{template_id}/fork", response_model=_ForkResponse, status_code=201)
def admin_fork_for_tenant(
    template_id: str,
    body: _ForkRequest,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> _ForkResponse:
    """Admin-side fork — used for support / troubleshooting + the
    Phase 4 backfill flow. Tenant-side fork lifecycle (lazy
    creation when tenant first customizes their workflow) lands in
    Phase 5+."""
    try:
        # Read workflow_type from the template
        template = get_template(db, template_id)
        fork = fork_for_tenant(
            db,
            tenant_id=body.tenant_id,
            workflow_type=template.workflow_type,
            source_template_id=template_id,
            actor_user_id=None,  # NOTE: PlatformUser id cannot satisfy users.id FK; platform-user attribution requires migration to drop FK or add platform_user_id columns. Tracked as relocation-phase follow-up.
        )
    except Exception as exc:
        raise _translate_service_error(exc)
    return _fork_to_response(fork)


@router.post(
    "/forks/{fork_id}/accept-merge", response_model=_ForkResponse
)
def admin_accept_merge(
    fork_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> _ForkResponse:
    try:
        # Fetch fork to read its identity tuple, then call the
        # tuple-keyed service method (the service uses
        # tenant_id + workflow_type as the identity, not fork_id,
        # because forks are unique per tuple at the active level).
        fork = get_fork(db, fork_id)
        updated = accept_merge(
            db,
            tenant_id=fork.tenant_id,
            workflow_type=fork.workflow_type,
            actor_user_id=None,  # NOTE: PlatformUser id cannot satisfy users.id FK; platform-user attribution requires migration to drop FK or add platform_user_id columns. Tracked as relocation-phase follow-up.
        )
    except Exception as exc:
        raise _translate_service_error(exc)
    return _fork_to_response(updated)


@router.post(
    "/forks/{fork_id}/reject-merge", response_model=_ForkResponse
)
def admin_reject_merge(
    fork_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> _ForkResponse:
    try:
        fork = get_fork(db, fork_id)
        updated = reject_merge(
            db,
            tenant_id=fork.tenant_id,
            workflow_type=fork.workflow_type,
            actor_user_id=None,  # NOTE: PlatformUser id cannot satisfy users.id FK; platform-user attribution requires migration to drop FK or add platform_user_id columns. Tracked as relocation-phase follow-up.
        )
    except Exception as exc:
        raise _translate_service_error(exc)
    return _fork_to_response(updated)


@router.get("/forks/", response_model=list[_ForkResponse])
def admin_list_forks(
    tenant_id: str | None = Query(default=None),
    workflow_type: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> list[_ForkResponse]:
    forks = list_forks(
        db,
        tenant_id=tenant_id,
        workflow_type=workflow_type,
        include_inactive=include_inactive,
    )
    return [_fork_to_response(f) for f in forks]
