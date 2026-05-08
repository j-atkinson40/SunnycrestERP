"""Focus Compositions API — admin endpoints.

R-3.0 — composition data model gains rows with per-row column count.
The endpoint surface is unchanged structurally; payload shapes now
carry `rows` instead of `placements`. Pre-R-3.0 flat-placements
payloads are rejected at the boundary with a clear error pointing
at the rows-based contract.

Endpoints mounted at `/api/platform/admin/visual-editor/compositions`:

    GET    /              — list compositions matching filters
    POST   /              — create / version a composition
    PATCH  /{id}          — replace rows / canvas_config
    GET    /resolve       — resolved composition (inheritance walk)
    GET    /{id}          — single row

All admin-gated (PlatformUser).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.services.focus_compositions import (
    CompositionError,
    create_composition,
    get_composition,
    list_compositions,
    reject_legacy_placements_payload,
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
    rows: list
    canvas_config: dict
    kind: str = "focus"
    pages: list | None = None
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
    rows: list = Field(default_factory=list)
    canvas_config: dict = Field(default_factory=dict)
    kind: str = "focus"
    pages: list | None = None


class _UpdateRequest(BaseModel):
    rows: list | None = None
    canvas_config: dict | None = None
    pages: list | None = None


class _ResolveResponse(BaseModel):
    focus_type: str
    vertical: str | None
    tenant_id: str | None
    kind: str = "focus"
    source: str | None
    source_id: str | None
    source_version: int | None
    rows: list
    canvas_config: dict
    pages: list | None = None


def _serialize(row) -> _CompositionResponse:
    return _CompositionResponse(
        id=row.id,
        scope=row.scope,
        vertical=row.vertical,
        tenant_id=row.tenant_id,
        focus_type=row.focus_type,
        rows=list(row.rows or []),
        canvas_config=dict(row.canvas_config or {}),
        kind=row.kind,
        pages=list(row.pages) if row.pages is not None else None,
        version=row.version,
        is_active=row.is_active,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
        created_by=row.created_by,
        updated_by=row.updated_by,
    )


def _translate_error(err: CompositionError) -> HTTPException:
    return HTTPException(status_code=err.http_status, detail=str(err))


async def _read_raw_body_for_legacy_check(request: Request) -> dict | None:
    """Read the raw JSON body once + cache on request.state so we can
    inspect for the legacy `placements` shape WITHOUT consuming the
    body before Pydantic gets to it. Pydantic re-parses from the same
    cached body via FastAPI's internal mechanism.
    """
    try:
        body_bytes = await request.body()
        import json

        return json.loads(body_bytes) if body_bytes else None
    except (ValueError, TypeError):
        return None


@router.get("/", response_model=list[_CompositionResponse])
def list_endpoint(
    scope: str | None = Query(default=None),
    vertical: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    focus_type: str | None = Query(default=None),
    kind: str | None = Query(default=None),
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
        kind=kind,
        include_inactive=include_inactive,
    )
    return [_serialize(r) for r in rows]


@router.get("/resolve", response_model=_ResolveResponse)
def resolve_endpoint(
    focus_type: str = Query(...),
    vertical: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    kind: str = Query(default="focus"),
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> _ResolveResponse:
    result = resolve_composition(
        db,
        focus_type=focus_type,
        vertical=vertical,
        tenant_id=tenant_id,
        kind=kind,
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
async def create_endpoint(
    request: Request,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> _CompositionResponse:
    raw_body = await _read_raw_body_for_legacy_check(request)
    try:
        # Pre-flight check: pre-R-3.0 flat-placements payloads
        # surface a clear error pointing at the rows-based contract
        # before Pydantic complains about extra fields.
        reject_legacy_placements_payload(raw_body)
    except CompositionError as err:
        raise _translate_error(err)

    try:
        body = _CreateRequest.model_validate(raw_body or {})
    except Exception as err:
        raise HTTPException(status_code=422, detail=str(err))

    try:
        row = create_composition(
            db,
            scope=body.scope,
            focus_type=body.focus_type,
            vertical=body.vertical,
            tenant_id=body.tenant_id,
            rows=body.rows,
            canvas_config=body.canvas_config,
            kind=body.kind,
            pages=body.pages,
            # NOTE: PlatformUser id cannot satisfy users.id FK; same
            # carry-forward limitation flagged in CLAUDE.md §4.
            actor_user_id=None,
        )
    except CompositionError as err:
        raise _translate_error(err)
    return _serialize(row)


@router.patch("/{composition_id}", response_model=_CompositionResponse)
async def update_endpoint(
    composition_id: str,
    request: Request,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> _CompositionResponse:
    raw_body = await _read_raw_body_for_legacy_check(request)
    try:
        reject_legacy_placements_payload(raw_body)
    except CompositionError as err:
        raise _translate_error(err)

    try:
        body = _UpdateRequest.model_validate(raw_body or {})
    except Exception as err:
        raise HTTPException(status_code=422, detail=str(err))

    try:
        row = update_composition(
            db,
            composition_id=composition_id,
            rows=body.rows,
            canvas_config=body.canvas_config,
            pages=body.pages,
            actor_user_id=None,
        )
    except CompositionError as err:
        raise _translate_error(err)
    return _serialize(row)
