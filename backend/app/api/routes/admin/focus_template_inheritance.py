"""Focus Template Inheritance — admin API routes (sub-arc B-1).

Endpoints mounted at `/api/platform/admin/focus-template-inheritance/`:

Tier 1 — Cores (platform admin only):
    GET    /cores
    GET    /cores/{core_id}
    POST   /cores
    PUT    /cores/{core_id}
    GET    /cores/{core_id}/usage

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
    POST   /compositions/{composition_id}/reset-placement/{placement_id}

Resolver (platform admin OR tenant matching tenant_id):
    GET    /resolve?template_slug=&vertical=&tenant_id=

Auth for Tier 1/2 uses `get_current_platform_user` (relocation-phase
convention: realm='platform' JWT). Tier 3 + resolve permit BOTH a
platform admin AND a tenant user whose company_id == tenant_id —
implemented via a hybrid helper that decodes the token, checks
realm, and validates tenant ownership at the route level. No new
auth machinery introduced.

Permission gating on Tier 3 (`focus.author`) is sub-arc D's job;
this surface gates only via realm + tenant_id match.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.core.security import decode_token
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.services.focus_template_inheritance import (
    CompositionNotFound,
    CoreNotFound,
    CoreSlugImmutable,
    FocusCompositionError,
    FocusCoreError,
    FocusTemplateError,
    FocusTemplateNotFound,
    InvalidCompositionShape,
    InvalidCoreShape,
    InvalidTemplateShape,
    TemplateNotFound,
    TemplateScopeMismatch,
    count_compositions_referencing,
    count_templates_referencing,
    create_core,
    create_or_update_composition,
    create_template,
    get_composition_by_tenant_template,
    get_core_by_id,
    get_template_by_id,
    list_cores,
    list_templates,
    reset_composition_to_default,
    reset_placement_to_default,
    resolve_focus,
    update_core,
    update_template,
)
from app.services.focus_template_inheritance.focus_compositions_service import (
    get_composition_by_id,
)
from app.services.focus_template_inheritance.schemas import (
    CompositionResponse,
    CompositionUpsertRequest,
    CoreCreateRequest,
    CoreResponse,
    CoreUpdateRequest,
    CoreUsageResponse,
    ResolveResponse,
    TemplateCreateRequest,
    TemplateResponse,
    TemplateUpdateRequest,
    TemplateUsageResponse,
)


logger = logging.getLogger(__name__)
router = APIRouter()

_bearer = HTTPBearer(auto_error=False)


# ─── Hybrid auth: platform OR tenant matching tenant_id ──────────


class _AuthedActor(BaseModel):
    """Result of hybrid auth check. Discriminates by `realm`."""

    realm: str  # 'platform' | 'tenant'
    user_id: str
    company_id: str | None = None  # set when realm='tenant'


def _resolve_actor(
    credentials: HTTPAuthorizationCredentials | None,
) -> _AuthedActor:
    """Decode + validate the bearer token. Returns the actor's realm +
    identity. Raises 401 on missing or invalid token. Does NOT enforce
    tenant_id ownership — that's the caller's responsibility."""
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
    """Tier 3 + resolve gate: platform admin always allowed; tenant
    actor allowed when their token's company_id matches tenant_id."""
    if actor.realm == "platform":
        return
    if actor.realm == "tenant" and actor.company_id == tenant_id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Caller does not have access to this tenant's compositions",
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
            CoreNotFound,
            TemplateNotFound,
            CompositionNotFound,
            FocusTemplateNotFound,
        ),
    ):
        return HTTPException(status_code=404, detail=str(exc) or "Not found")
    if isinstance(
        exc,
        (
            InvalidCoreShape,
            InvalidTemplateShape,
            InvalidCompositionShape,
            TemplateScopeMismatch,
            CoreSlugImmutable,
        ),
    ):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(
        exc, (FocusCoreError, FocusTemplateError, FocusCompositionError)
    ):
        return HTTPException(status_code=409, detail=str(exc))
    logger.exception("unexpected error in focus template inheritance api")
    return HTTPException(status_code=500, detail=str(exc))


# ─── Serialization helpers ──────────────────────────────────────


def _core_to_response(row) -> CoreResponse:
    return CoreResponse(
        id=row.id,
        core_slug=row.core_slug,
        display_name=row.display_name,
        description=row.description,
        registered_component_kind=row.registered_component_kind,
        registered_component_name=row.registered_component_name,
        default_starting_column=row.default_starting_column,
        default_column_span=row.default_column_span,
        default_row_index=row.default_row_index,
        min_column_span=row.min_column_span,
        max_column_span=row.max_column_span,
        canvas_config=dict(row.canvas_config or {}),
        chrome=dict(row.chrome or {}),
        version=row.version,
        is_active=row.is_active,
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


def _template_to_response(row) -> TemplateResponse:
    return TemplateResponse(
        id=row.id,
        scope=row.scope,
        vertical=row.vertical,
        template_slug=row.template_slug,
        display_name=row.display_name,
        description=row.description,
        inherits_from_core_id=row.inherits_from_core_id,
        inherits_from_core_version=row.inherits_from_core_version,
        rows=list(row.rows or []),
        canvas_config=dict(row.canvas_config or {}),
        chrome_overrides=dict(row.chrome_overrides or {}),
        substrate=dict(getattr(row, "substrate", None) or {}),
        typography=dict(getattr(row, "typography", None) or {}),
        version=row.version,
        is_active=row.is_active,
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


def _composition_to_response(row) -> CompositionResponse:
    return CompositionResponse(
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


# ═══ Tier 1 — Cores ═════════════════════════════════════════════


@router.get("/cores", response_model=list[CoreResponse])
def admin_list_cores(
    include_inactive: bool = Query(default=False),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> list[CoreResponse]:
    rows = list_cores(db, include_inactive=include_inactive)
    return [_core_to_response(r) for r in rows]


@router.get("/cores/{core_id}", response_model=CoreResponse)
def admin_get_core(
    core_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> CoreResponse:
    row = get_core_by_id(db, core_id)
    if row is None:
        raise _translate(CoreNotFound(core_id))
    return _core_to_response(row)


@router.post("/cores", response_model=CoreResponse, status_code=201)
def admin_create_core(
    body: CoreCreateRequest,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> CoreResponse:
    try:
        row = create_core(
            db,
            core_slug=body.core_slug,
            display_name=body.display_name,
            description=body.description,
            registered_component_kind=body.registered_component_kind,
            registered_component_name=body.registered_component_name,
            default_starting_column=body.default_starting_column,
            default_column_span=body.default_column_span,
            default_row_index=body.default_row_index,
            min_column_span=body.min_column_span,
            max_column_span=body.max_column_span,
            canvas_config=body.canvas_config,
            chrome=body.chrome,
            # PlatformUser id cannot satisfy users.id FK; attribution
            # deferred per relocation-phase note in CLAUDE.md.
            created_by=None,
        )
    except Exception as exc:
        raise _translate(exc)
    return _core_to_response(row)


@router.put("/cores/{core_id}", response_model=CoreResponse)
def admin_update_core(
    core_id: str,
    body: CoreUpdateRequest,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> CoreResponse:
    try:
        row = update_core(
            db,
            core_id,
            updated_by=None,
            display_name=body.display_name,
            description=body.description,
            registered_component_kind=body.registered_component_kind,
            registered_component_name=body.registered_component_name,
            default_starting_column=body.default_starting_column,
            default_column_span=body.default_column_span,
            default_row_index=body.default_row_index,
            min_column_span=body.min_column_span,
            max_column_span=body.max_column_span,
            canvas_config=body.canvas_config,
            chrome=body.chrome,
        )
    except Exception as exc:
        raise _translate(exc)
    return _core_to_response(row)


@router.get("/cores/{core_id}/usage", response_model=CoreUsageResponse)
def admin_core_usage(
    core_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> CoreUsageResponse:
    if get_core_by_id(db, core_id) is None:
        raise _translate(CoreNotFound(core_id))
    count = count_templates_referencing(db, core_id)
    # Build the listing alongside the count — small lists, single query.
    from app.models.focus_template import FocusTemplate as _FT

    rows = (
        db.query(_FT)
        .filter(
            _FT.inherits_from_core_id == core_id,
            _FT.is_active.is_(True),
        )
        .all()
    )
    return CoreUsageResponse(
        templates_count=count,
        templates=[
            {
                "id": r.id,
                "template_slug": r.template_slug,
                "scope": r.scope,
                "vertical": r.vertical,
            }
            for r in rows
        ],
    )


# ═══ Tier 2 — Templates ═════════════════════════════════════════


@router.get("/templates", response_model=list[TemplateResponse])
def admin_list_templates(
    scope: str | None = Query(default=None),
    vertical: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> list[TemplateResponse]:
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


@router.get("/templates/{template_id}", response_model=TemplateResponse)
def admin_get_template(
    template_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> TemplateResponse:
    row = get_template_by_id(db, template_id)
    if row is None:
        raise _translate(TemplateNotFound(template_id))
    return _template_to_response(row)


@router.post("/templates", response_model=TemplateResponse, status_code=201)
def admin_create_template(
    body: TemplateCreateRequest,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> TemplateResponse:
    try:
        row = create_template(
            db,
            scope=body.scope,
            vertical=body.vertical,
            template_slug=body.template_slug,
            display_name=body.display_name,
            description=body.description,
            inherits_from_core_id=body.inherits_from_core_id,
            rows=body.rows,
            canvas_config=body.canvas_config,
            chrome_overrides=body.chrome_overrides,
            substrate=body.substrate,
            typography=body.typography,
            created_by=None,
        )
    except Exception as exc:
        raise _translate(exc)
    return _template_to_response(row)


@router.put("/templates/{template_id}", response_model=TemplateResponse)
def admin_update_template(
    template_id: str,
    body: TemplateUpdateRequest,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> TemplateResponse:
    try:
        row = update_template(
            db,
            template_id,
            updated_by=None,
            display_name=body.display_name,
            description=body.description,
            rows=body.rows,
            canvas_config=body.canvas_config,
            chrome_overrides=body.chrome_overrides,
            substrate=body.substrate,
            typography=body.typography,
        )
    except Exception as exc:
        raise _translate(exc)
    return _template_to_response(row)


@router.get("/templates/{template_id}/usage", response_model=TemplateUsageResponse)
def admin_template_usage(
    template_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> TemplateUsageResponse:
    if get_template_by_id(db, template_id) is None:
        raise _translate(TemplateNotFound(template_id))
    count = count_compositions_referencing(db, template_id)
    return TemplateUsageResponse(compositions_count=count)


# ═══ Tier 3 — Compositions ══════════════════════════════════════


@router.get(
    "/compositions/by-tenant-template", response_model=CompositionResponse
)
def admin_get_composition_by_tenant_template(
    tenant_id: str = Query(..., min_length=1, max_length=36),
    template_id: str = Query(..., min_length=1, max_length=36),
    actor: _AuthedActor = Depends(_hybrid_actor),
    db: Session = Depends(get_db),
) -> CompositionResponse:
    _require_platform_or_tenant_match(actor, tenant_id)
    row = get_composition_by_tenant_template(db, tenant_id, template_id)
    if row is None:
        raise _translate(
            CompositionNotFound(
                f"no composition at tenant={tenant_id} template={template_id}"
            )
        )
    return _composition_to_response(row)


@router.post(
    "/compositions", response_model=CompositionResponse, status_code=201
)
def admin_upsert_composition(
    body: CompositionUpsertRequest,
    actor: _AuthedActor = Depends(_hybrid_actor),
    db: Session = Depends(get_db),
) -> CompositionResponse:
    _require_platform_or_tenant_match(actor, body.tenant_id)
    try:
        row = create_or_update_composition(
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
    "/compositions/{composition_id}/reset", response_model=CompositionResponse
)
def admin_reset_composition(
    composition_id: str,
    actor: _AuthedActor = Depends(_hybrid_actor),
    db: Session = Depends(get_db),
) -> CompositionResponse:
    existing = get_composition_by_id(db, composition_id)
    if existing is None:
        raise _translate(CompositionNotFound(composition_id))
    _require_platform_or_tenant_match(actor, existing.tenant_id)
    try:
        row = reset_composition_to_default(
            db,
            existing.tenant_id,
            existing.inherits_from_template_id,
            updated_by=actor.user_id if actor.realm == "tenant" else None,
        )
    except Exception as exc:
        raise _translate(exc)
    return _composition_to_response(row)


@router.post(
    "/compositions/{composition_id}/reset-placement/{placement_id}",
    response_model=CompositionResponse,
)
def admin_reset_placement(
    composition_id: str,
    placement_id: str,
    actor: _AuthedActor = Depends(_hybrid_actor),
    db: Session = Depends(get_db),
) -> CompositionResponse:
    existing = get_composition_by_id(db, composition_id)
    if existing is None:
        raise _translate(CompositionNotFound(composition_id))
    _require_platform_or_tenant_match(actor, existing.tenant_id)
    try:
        row = reset_placement_to_default(
            db,
            existing.tenant_id,
            existing.inherits_from_template_id,
            placement_id,
            updated_by=actor.user_id if actor.realm == "tenant" else None,
        )
    except Exception as exc:
        raise _translate(exc)
    return _composition_to_response(row)


# ═══ Resolver ═══════════════════════════════════════════════════


@router.get("/resolve", response_model=ResolveResponse)
def admin_resolve_focus(
    template_slug: str = Query(..., min_length=1, max_length=96),
    vertical: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    actor: _AuthedActor = Depends(_hybrid_actor),
    db: Session = Depends(get_db),
) -> ResolveResponse:
    if tenant_id is not None:
        _require_platform_or_tenant_match(actor, tenant_id)
    elif actor.realm == "tenant":
        # Tenant calling without tenant_id — pin to their own.
        tenant_id = actor.company_id
    try:
        resolved = resolve_focus(
            db,
            template_slug=template_slug,
            vertical=vertical,
            tenant_id=tenant_id,
        )
    except Exception as exc:
        raise _translate(exc)
    return ResolveResponse(**resolved.model_dump())
