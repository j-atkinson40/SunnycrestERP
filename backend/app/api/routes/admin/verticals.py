"""Verticals admin API — list / get / patch endpoints.

Verticals-lite precursor arc. PlatformUser-gated; mounted at
`/api/platform/admin/verticals` in `app/api/platform.py`.

Endpoints:

    GET   /                — list verticals (sort_order ASC; archived
                              excluded unless ?include_archived=true)
    GET   /{slug}          — single vertical by slug
    PATCH /{slug}          — partial update of mutable fields
                              (display_name, description, status,
                              icon, sort_order). Slug is immutable.

See migration `r92_verticals_table` for schema + canonical seeds
(manufacturing, funeral_home, cemetery, crematory).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.models.vertical import Vertical
from app.services.verticals_service import (
    VerticalNotFound,
    get_vertical,
    list_verticals,
    update_vertical,
)


logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Pydantic shapes ─────────────────────────────────────────────


class VerticalResponse(BaseModel):
    slug: str
    display_name: str
    description: str | None
    status: str
    icon: str | None
    sort_order: int
    created_at: str
    updated_at: str


class VerticalUpdate(BaseModel):
    """All-optional partial-update body. Slug is deliberately NOT
    present — the column is immutable (primary key). Extra fields
    on the request body are forbidden so a caller passing
    `{"slug": ...}` is rejected at the Pydantic boundary with a
    422 rather than silently ignored."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    description: str | None = None
    status: str | None = None
    icon: str | None = None
    sort_order: int | None = None


def _row_to_response(row: Vertical) -> VerticalResponse:
    return VerticalResponse(
        slug=row.slug,
        display_name=row.display_name,
        description=row.description,
        status=row.status,
        icon=row.icon,
        sort_order=row.sort_order,
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


# ─── Endpoints ───────────────────────────────────────────────────


@router.get("/", response_model=list[VerticalResponse])
def list_endpoint(
    include_archived: bool = Query(False),
    _: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> list[VerticalResponse]:
    rows = list_verticals(db, include_archived=include_archived)
    return [_row_to_response(r) for r in rows]


@router.get("/{slug}", response_model=VerticalResponse)
def get_endpoint(
    slug: str,
    _: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> VerticalResponse:
    try:
        row = get_vertical(db, slug)
    except VerticalNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _row_to_response(row)


@router.patch("/{slug}", response_model=VerticalResponse)
def patch_endpoint(
    slug: str,
    body: VerticalUpdate,
    _: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
) -> VerticalResponse:
    try:
        row = update_vertical(
            db,
            slug,
            display_name=body.display_name,
            description=body.description,
            status=body.status,
            icon=body.icon,
            sort_order=body.sort_order,
        )
    except VerticalNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _row_to_response(row)
