"""Saved Views API — Phase 2.

Eight endpoints under `/api/v1/saved-views/*`. All tenant-scoped via
`get_current_user`. Authorization is delegated to `crud.py` (which
raises SavedViewPermissionDenied / SavedViewNotFound — translated to
HTTP here).

The `execute` endpoint is the hot path and has a blocking latency
gate at `tests/test_saved_view_execute_latency.py` (p50 < 150ms,
p99 < 500ms).

Response shapes are thin Pydantic mirrors of the typed dataclasses
in `app.services.saved_views.types`. Keep them in lock-step — bumping
the dataclass without bumping the response model is a bug.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.saved_views import (
    EntityType,
    ExecutorError,
    SavedView,
    SavedViewConfig,
    SavedViewError,
    SavedViewResult,
    create_saved_view,
    delete_saved_view,
    duplicate_saved_view,
    execute,
    get_saved_view,
    list_entities,
    list_saved_views_for_user,
    update_saved_view,
)

router = APIRouter()


# ── Response / request schemas ───────────────────────────────────────


class _SavedViewConfigBody(BaseModel):
    """Untyped dict for config pass-through — full shape validation
    happens in `SavedViewConfig.from_dict()` inside crud."""

    query: dict
    presentation: dict
    permissions: dict
    extras: dict = Field(default_factory=dict)


class _SavedViewResponse(BaseModel):
    id: str
    company_id: str
    title: str
    description: str | None
    created_by: str | None
    created_at: Any
    updated_at: Any
    config: dict  # SavedViewConfig.to_dict() output


class _CreateRequest(BaseModel):
    title: str
    description: str | None = None
    config: _SavedViewConfigBody


class _UpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    config: _SavedViewConfigBody | None = None


class _DuplicateRequest(BaseModel):
    new_title: str


class _ExecuteResponse(BaseModel):
    total_count: int
    rows: list[dict]
    groups: dict[str, list[dict]] | None = None
    aggregations: dict | None = None
    permission_mode: Literal["full", "cross_tenant_masked"]
    masked_fields: list[str] = Field(default_factory=list)


class _EntityTypeResponse(BaseModel):
    entity_type: str
    display_name: str
    icon: str
    navigate_url_template: str
    available_fields: list[dict]
    default_sort: list[dict]
    default_columns: list[str]


# ── Helpers ──────────────────────────────────────────────────────────


def _sv_to_response(sv: SavedView) -> _SavedViewResponse:
    return _SavedViewResponse(
        id=sv.id,
        company_id=sv.company_id,
        title=sv.title,
        description=sv.description,
        created_by=sv.created_by,
        created_at=sv.created_at,
        updated_at=sv.updated_at,
        config=sv.config.to_dict(),
    )


def _translate_saved_view_error(exc: SavedViewError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=str(exc))


# ── Routes ───────────────────────────────────────────────────────────


@router.get("", response_model=list[_SavedViewResponse])
def list_saved_views(
    entity_type: EntityType | None = Query(
        None, description="Optional filter — only views targeting this entity"
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[_SavedViewResponse]:
    """List saved views visible to the current user.

    Visibility is per the 4-level model (private / role_shared /
    user_shared / tenant_public). Shared views the user can see
    are included alongside owned views.
    """
    views = list_saved_views_for_user(
        db, user=current_user, entity_type=entity_type
    )
    return [_sv_to_response(v) for v in views]


@router.post("", response_model=_SavedViewResponse, status_code=201)
def create(
    body: _CreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _SavedViewResponse:
    """Create a new saved view. Owner is the calling user — any
    `owner_user_id` in the request config is IGNORED (server-side
    forces owner to the caller)."""
    try:
        config = SavedViewConfig.from_dict(
            {
                "query": body.config.query,
                "presentation": body.config.presentation,
                "permissions": body.config.permissions,
                "extras": body.config.extras or {},
            }
        )
        sv = create_saved_view(
            db,
            user=current_user,
            title=body.title,
            description=body.description,
            config=config,
        )
        return _sv_to_response(sv)
    except SavedViewError as exc:
        raise _translate_saved_view_error(exc) from exc
    except (KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=400, detail=f"Malformed config: {exc}"
        ) from exc


@router.get("/entity-types", response_model=list[_EntityTypeResponse])
def list_entity_types(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[_EntityTypeResponse]:
    """Registered entity types + their field metadata.

    The builder UI queries this once on load to populate field
    dropdowns per entity.
    """
    entities = list_entities()
    return [
        _EntityTypeResponse(
            entity_type=e.entity_type,
            display_name=e.display_name,
            icon=e.icon,
            navigate_url_template=e.navigate_url_template,
            available_fields=[f.to_dict() for f in e.available_fields],
            default_sort=list(e.default_sort),
            default_columns=list(e.default_columns),
        )
        for e in entities
    ]


@router.get("/{view_id}", response_model=_SavedViewResponse)
def get(
    view_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _SavedViewResponse:
    """Get one saved view by id. 404 if not found or not visible."""
    try:
        sv = get_saved_view(db, user=current_user, view_id=view_id)
        return _sv_to_response(sv)
    except SavedViewError as exc:
        raise _translate_saved_view_error(exc) from exc


@router.patch("/{view_id}", response_model=_SavedViewResponse)
def update(
    view_id: str,
    body: _UpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _SavedViewResponse:
    """Update title / description / config. Owner-only.

    Any field NOT provided in the body is preserved (partial update).
    """
    try:
        config: SavedViewConfig | None = None
        if body.config is not None:
            config = SavedViewConfig.from_dict(
                {
                    "query": body.config.query,
                    "presentation": body.config.presentation,
                    "permissions": body.config.permissions,
                    "extras": body.config.extras or {},
                }
            )
        sv = update_saved_view(
            db,
            user=current_user,
            view_id=view_id,
            title=body.title,
            description=body.description,
            config=config,
        )
        return _sv_to_response(sv)
    except SavedViewError as exc:
        raise _translate_saved_view_error(exc) from exc
    except (KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=400, detail=f"Malformed config: {exc}"
        ) from exc


@router.delete("/{view_id}")
def delete(
    view_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Soft-delete. Owner-only. Returns `{"status": "deleted"}`.

    (We return a 200 body rather than 204-no-content because some
    frontend HTTP clients choke on 204 + JSON decode; the body is
    trivially small and consistent with other delete endpoints in
    the codebase.)
    """
    try:
        delete_saved_view(db, user=current_user, view_id=view_id)
        return {"status": "deleted", "id": view_id}
    except SavedViewError as exc:
        raise _translate_saved_view_error(exc) from exc


@router.post("/{view_id}/duplicate", response_model=_SavedViewResponse, status_code=201)
def duplicate(
    view_id: str,
    body: _DuplicateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _SavedViewResponse:
    """Duplicate into a new PRIVATE view owned by the caller.

    Use case: take a shared/seeded view and fork it into your own
    editable copy.
    """
    try:
        sv = duplicate_saved_view(
            db,
            user=current_user,
            view_id=view_id,
            new_title=body.new_title,
        )
        return _sv_to_response(sv)
    except SavedViewError as exc:
        raise _translate_saved_view_error(exc) from exc


@router.post("/{view_id}/execute", response_model=_ExecuteResponse)
def execute_view(
    view_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _ExecuteResponse:
    """Execute the view and return results. HOT PATH.

    p50 budget: 150 ms. p99 budget: 500 ms. Enforced by the blocking
    CI gate at `tests/test_saved_view_execute_latency.py`.
    """
    import time as _t_time
    from app.services import arc_telemetry as _arc_t
    _t0 = _t_time.perf_counter()
    _errored = False

    try:
        sv = get_saved_view(db, user=current_user, view_id=view_id)
    except SavedViewError as exc:
        _errored = True
        _arc_t.record(
            "saved_view_execute",
            (_t_time.perf_counter() - _t0) * 1000.0,
            errored=True,
        )
        raise _translate_saved_view_error(exc) from exc

    try:
        result: SavedViewResult = execute(
            db,
            config=sv.config,
            caller_company_id=current_user.company_id,
            owner_company_id=sv.company_id,
        )
    except ExecutorError as exc:
        _errored = True
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        _arc_t.record(
            "saved_view_execute",
            (_t_time.perf_counter() - _t0) * 1000.0,
            errored=_errored,
        )

    return _ExecuteResponse(
        total_count=result.total_count,
        rows=result.rows,
        groups=result.groups,
        aggregations=result.aggregations,
        permission_mode=result.permission_mode,
        masked_fields=result.masked_fields,
    )
