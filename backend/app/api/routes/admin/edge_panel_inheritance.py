"""Edge Panel Inheritance — admin API routes (sub-arc B-1.5).

Endpoints mounted at `/api/platform/admin/edge-panel-inheritance/`:

Tier 2 — Templates (platform admin only):
    GET    /templates
    GET    /templates/{template_id}
    POST   /templates
    PUT    /templates/{template_id}
    GET    /templates/{template_id}/usage

Tier 3 — Compositions (platform admin OR tenant matching tenant_id):
    GET    /compositions/by-tenant-template?tenant_id=&template_id=
    POST   /compositions
    POST   /compositions/{composition_id}/reset
    POST   /compositions/{composition_id}/reset-page/{page_id}
    POST   /compositions/{composition_id}/reset-placement/{page_id}/{placement_id}

Resolver (platform admin OR tenant matching tenant_id):
    GET    /resolve?panel_key=&vertical=&tenant_id=&user_id=

Auth for Tier 2 uses `get_current_platform_user` (realm='platform'
JWT). Tier 3 + resolve permit BOTH a platform admin AND a tenant
user whose company_id == tenant_id — implemented via a hybrid helper
that mirrors B-1's `_AuthedActor` / `_hybrid_actor` pattern verbatim.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.core.security import decode_token
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.services.edge_panel_inheritance import (
    EdgePanelCompositionError,
    EdgePanelCompositionNotFound,
    EdgePanelTemplateError,
    EdgePanelTemplateNotFound,
    EdgePanelTemplateResolveError,
    EdgePanelTemplateScopeMismatch,
    InvalidEdgePanelShape,
    count_compositions_referencing,
    create_template,
    get_composition_by_id,
    get_composition_by_tenant_template,
    get_template_by_id,
    list_templates,
    reset_composition,
    reset_page,
    reset_placement,
    resolve_edge_panel,
    update_template,
    upsert_composition,
)
from app.services.edge_panel_inheritance.schemas import (
    EdgePanelCompositionResponse,
    EdgePanelCompositionUpsertRequest,
    EdgePanelResolveResponse,
    EdgePanelTemplateCreateRequest,
    EdgePanelTemplateResponse,
    EdgePanelTemplateUpdateRequest,
    EdgePanelTemplateUsageResponse,
)


logger = logging.getLogger(__name__)
router = APIRouter()

_bearer = HTTPBearer(auto_error=False)


# ─── Hybrid auth (mirrors B-1) ──────────────────────────────────


class _AuthedActor(BaseModel):
    realm: str  # 'platform' | 'tenant'
    user_id: str
    company_id: str | None = None


def _resolve_actor(
    credentials: HTTPAuthorizationCredentials | None,
) -> _AuthedActor:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )
    realm = payload.get("realm")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    if realm == "platform":
        return _AuthedActor(realm="platform", user_id=user_id)
    if realm == "tenant":
        return _AuthedActor(
            realm="tenant",
            user_id=user_id,
            company_id=payload.get("company_id"),
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token realm not permitted on this endpoint",
    )


def _require_platform_or_tenant_match(
    actor: _AuthedActor, tenant_id: str
) -> None:
    if actor.realm == "platform":
        return
    if actor.realm == "tenant" and actor.company_id == tenant_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Caller does not have access to this tenant's edge-panel compositions",
    )


def _hybrid_actor(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> _AuthedActor:
    return _resolve_actor(credentials)


# ─── Error translation ──────────────────────────────────────────


def _translate(exc: Exception) -> HTTPException:
    if isinstance(
        exc,
        (
            EdgePanelTemplateNotFound,
            EdgePanelCompositionNotFound,
            EdgePanelTemplateResolveError,
        ),
    ):
        return HTTPException(status_code=404, detail=str(exc) or "Not found")
    if isinstance(
        exc,
        (InvalidEdgePanelShape, EdgePanelTemplateScopeMismatch),
    ):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, (EdgePanelTemplateError, EdgePanelCompositionError)):
        return HTTPException(status_code=409, detail=str(exc))
    logger.exception("unexpected error in edge panel inheritance api")
    return HTTPException(status_code=500, detail=str(exc))


# ─── Serialization helpers ──────────────────────────────────────


def _template_to_response(row) -> EdgePanelTemplateResponse:
    return EdgePanelTemplateResponse(
        id=row.id,
        scope=row.scope,
        vertical=row.vertical,
        panel_key=row.panel_key,
        display_name=row.display_name,
        description=row.description,
        pages=list(row.pages or []),
        canvas_config=dict(row.canvas_config or {}),
        version=row.version,
        is_active=row.is_active,
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


def _composition_to_response(row) -> EdgePanelCompositionResponse:
    return EdgePanelCompositionResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        inherits_from_template_id=row.inherits_from_template_id,
        inherits_from_template_version=row.inherits_from_template_version,
        deltas=dict(row.deltas or {}),
        canvas_config_overrides=dict(row.canvas_config_overrides or {}),
        version=row.version,
        is_active=row.is_active,
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


# ═══ Tier 2 — Templates ═════════════════════════════════════════


@router.get("/templates", response_model=list[EdgePanelTemplateResponse])
def admin_list_templates(
    scope: str | None = Query(default=None),
    vertical: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> list[EdgePanelTemplateResponse]:
    try:
        rows = list_templates(
            db,
            scope=scope,
            vertical=vertical,
            include_inactive=include_inactive,
        )
    except Exception as exc:
        raise _translate(exc)
    return [_template_to_response(r) for r in rows]


@router.get("/templates/{template_id}", response_model=EdgePanelTemplateResponse)
def admin_get_template(
    template_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> EdgePanelTemplateResponse:
    row = get_template_by_id(db, template_id)
    if row is None:
        raise _translate(EdgePanelTemplateNotFound(template_id))
    return _template_to_response(row)


@router.post(
    "/templates",
    response_model=EdgePanelTemplateResponse,
    status_code=201,
)
def admin_create_template(
    body: EdgePanelTemplateCreateRequest,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> EdgePanelTemplateResponse:
    try:
        row = create_template(
            db,
            scope=body.scope,
            vertical=body.vertical,
            panel_key=body.panel_key,
            display_name=body.display_name,
            description=body.description,
            pages=body.pages,
            canvas_config=body.canvas_config,
            # PlatformUser id can't satisfy users.id FK; audit
            # attribution deferred per CLAUDE.md §4 relocation note.
            created_by=None,
        )
    except Exception as exc:
        raise _translate(exc)
    return _template_to_response(row)


@router.put(
    "/templates/{template_id}", response_model=EdgePanelTemplateResponse
)
def admin_update_template(
    template_id: str,
    body: EdgePanelTemplateUpdateRequest,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> EdgePanelTemplateResponse:
    try:
        row = update_template(
            db,
            template_id,
            updated_by=None,
            display_name=body.display_name,
            description=body.description,
            pages=body.pages,
            canvas_config=body.canvas_config,
        )
    except Exception as exc:
        raise _translate(exc)
    return _template_to_response(row)


@router.get(
    "/templates/{template_id}/usage",
    response_model=EdgePanelTemplateUsageResponse,
)
def admin_template_usage(
    template_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> EdgePanelTemplateUsageResponse:
    if get_template_by_id(db, template_id) is None:
        raise _translate(EdgePanelTemplateNotFound(template_id))
    count = count_compositions_referencing(db, template_id)
    return EdgePanelTemplateUsageResponse(compositions_count=count)


# ═══ Tier 3 — Compositions ══════════════════════════════════════


@router.get(
    "/compositions/by-tenant-template",
    response_model=EdgePanelCompositionResponse,
)
def admin_get_composition_by_tenant_template(
    tenant_id: str = Query(..., min_length=1, max_length=36),
    template_id: str = Query(..., min_length=1, max_length=36),
    actor: _AuthedActor = Depends(_hybrid_actor),
    db: Session = Depends(get_db),
) -> EdgePanelCompositionResponse:
    _require_platform_or_tenant_match(actor, tenant_id)
    row = get_composition_by_tenant_template(db, tenant_id, template_id)
    if row is None:
        raise _translate(
            EdgePanelCompositionNotFound(
                f"no composition at tenant={tenant_id} template={template_id}"
            )
        )
    return _composition_to_response(row)


@router.post(
    "/compositions",
    response_model=EdgePanelCompositionResponse,
    status_code=201,
)
def admin_upsert_composition(
    body: EdgePanelCompositionUpsertRequest,
    actor: _AuthedActor = Depends(_hybrid_actor),
    db: Session = Depends(get_db),
) -> EdgePanelCompositionResponse:
    _require_platform_or_tenant_match(actor, body.tenant_id)
    try:
        row = upsert_composition(
            db,
            tenant_id=body.tenant_id,
            template_id=body.template_id,
            deltas=body.deltas,
            canvas_config_overrides=body.canvas_config_overrides,
            updated_by=actor.user_id if actor.realm == "tenant" else None,
        )
    except Exception as exc:
        raise _translate(exc)
    return _composition_to_response(row)


@router.post(
    "/compositions/{composition_id}/reset",
    response_model=EdgePanelCompositionResponse,
)
def admin_reset_composition(
    composition_id: str,
    actor: _AuthedActor = Depends(_hybrid_actor),
    db: Session = Depends(get_db),
) -> EdgePanelCompositionResponse:
    existing = get_composition_by_id(db, composition_id)
    if existing is None:
        raise _translate(EdgePanelCompositionNotFound(composition_id))
    _require_platform_or_tenant_match(actor, existing.tenant_id)
    try:
        row = reset_composition(
            db,
            existing.tenant_id,
            existing.inherits_from_template_id,
            updated_by=actor.user_id if actor.realm == "tenant" else None,
        )
    except Exception as exc:
        raise _translate(exc)
    return _composition_to_response(row)


@router.post(
    "/compositions/{composition_id}/reset-page/{page_id}",
    response_model=EdgePanelCompositionResponse,
)
def admin_reset_page(
    composition_id: str,
    page_id: str,
    actor: _AuthedActor = Depends(_hybrid_actor),
    db: Session = Depends(get_db),
) -> EdgePanelCompositionResponse:
    existing = get_composition_by_id(db, composition_id)
    if existing is None:
        raise _translate(EdgePanelCompositionNotFound(composition_id))
    _require_platform_or_tenant_match(actor, existing.tenant_id)
    try:
        row = reset_page(
            db,
            composition_id,
            page_id,
            updated_by=actor.user_id if actor.realm == "tenant" else None,
        )
    except Exception as exc:
        raise _translate(exc)
    return _composition_to_response(row)


@router.post(
    "/compositions/{composition_id}/reset-placement/{page_id}/{placement_id}",
    response_model=EdgePanelCompositionResponse,
)
def admin_reset_placement(
    composition_id: str,
    page_id: str,
    placement_id: str,
    actor: _AuthedActor = Depends(_hybrid_actor),
    db: Session = Depends(get_db),
) -> EdgePanelCompositionResponse:
    existing = get_composition_by_id(db, composition_id)
    if existing is None:
        raise _translate(EdgePanelCompositionNotFound(composition_id))
    _require_platform_or_tenant_match(actor, existing.tenant_id)
    try:
        row = reset_placement(
            db,
            composition_id,
            page_id,
            placement_id,
            updated_by=actor.user_id if actor.realm == "tenant" else None,
        )
    except Exception as exc:
        raise _translate(exc)
    return _composition_to_response(row)


# ═══ Resolver ═══════════════════════════════════════════════════


@router.get("/resolve", response_model=EdgePanelResolveResponse)
def admin_resolve(
    panel_key: str = Query(..., min_length=1, max_length=96),
    vertical: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    actor: _AuthedActor = Depends(_hybrid_actor),
    db: Session = Depends(get_db),
) -> EdgePanelResolveResponse:
    if tenant_id is not None:
        _require_platform_or_tenant_match(actor, tenant_id)
    elif actor.realm == "tenant":
        # Tenant calling without tenant_id — pin to their own.
        tenant_id = actor.company_id
    try:
        resolved = resolve_edge_panel(
            db,
            panel_key=panel_key,
            vertical=vertical,
            tenant_id=tenant_id,
            user_id=user_id,
        )
    except Exception as exc:
        raise _translate(exc)
    return EdgePanelResolveResponse(**resolved.model_dump())
