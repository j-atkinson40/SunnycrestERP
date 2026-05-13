"""Studio Inventory API — Studio 1a-ii.

PlatformUser-gated. Mounted at `/api/platform/admin/studio/inventory`
in `app/api/platform.py`.

Endpoints:

    GET /                        — Platform-wide inventory
    GET /?vertical=<slug>        — Vertical-scoped inventory

Both return the same `InventoryResponse` shape. Unknown vertical_slug
returns 404 (slug is validated against `verticals.slug` registry).

No caching headers — counts compute fresh per request per locked
decision 2. Recent-edits feed sourced from per-table `updated_at`
per locked decision 6 (audit-substrate write-side instrumentation
deferred to a dedicated arc).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.database import get_db
from app.models.platform_user import PlatformUser  # noqa: F401 — type only
from app.models.vertical import Vertical
from app.services.vertical_inventory import (
    InventoryResponse,
    get_inventory,
)


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=InventoryResponse)
@router.get("/", response_model=InventoryResponse)
def get_studio_inventory(
    vertical: str | None = Query(
        default=None,
        description=(
            "Vertical slug (must match a row in `verticals`). Omit "
            "for Platform-wide scope."
        ),
    ),
    db: Session = Depends(get_db),
    _: PlatformUser = Depends(get_current_platform_user),
) -> InventoryResponse:
    if vertical is not None:
        # Slug validation — 404 on unknown.
        exists = db.query(Vertical.slug).filter(Vertical.slug == vertical).first()
        if exists is None:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown vertical slug: {vertical!r}",
            )
    return get_inventory(db, vertical_slug=vertical)
