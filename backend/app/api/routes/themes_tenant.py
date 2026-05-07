"""Tenant-realm theme resolve endpoint — R-2.5.

R-1.6.14 wired theme resolve+apply into the runtime editor shell.
R-2.5 extends the same pattern to production tenant boot
(`PresetThemeProvider` on every authenticated tenant route) so
committed overrides reach end users, not just the editor preview.

The existing admin endpoint at
`/api/platform/admin/visual-editor/themes/resolve` is gated by
`get_current_platform_user` (PlatformUser realm). Tenant operators
cannot call it. This module exposes a tenant-realm equivalent at
`/api/v1/themes/resolve` that:

  - Requires `get_current_user` (tenant JWT realm)
  - Infers `vertical` + `tenant_id` from `current_user.company` —
    tenants CANNOT request resolution for a different tenant; the
    server picks the caller's company every time.
  - Accepts only `mode` (light/dark) as a query param.
  - Returns the same shape as the admin endpoint
    (`mode / vertical / tenant_id / tokens / sources`) so the frontend
    resolver helpers (`stackFromResolved`, `composeEffective`) work
    unchanged.

Scope discipline: this endpoint is READ-ONLY. Tenants never write
theme rows. Authoring lands in `PlatformAdminUser` write paths via
the runtime editor / visual editor — both already exist.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.platform_themes import (
    InvalidThemeShape,
    ThemeServiceError,
    resolve_theme,
)


logger = logging.getLogger(__name__)
router = APIRouter()


Mode = Literal["light", "dark"]


class _ResolveResponse(BaseModel):
    mode: Mode
    vertical: str | None
    tenant_id: str | None
    tokens: dict[str, Any] = Field(default_factory=dict)
    sources: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/resolve", response_model=_ResolveResponse)
def tenant_resolve_theme(
    mode: Mode = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _ResolveResponse:
    """Resolve the active theme for the caller's own tenant context.

    Returns the fully-merged token override map for
    (caller's vertical, caller's tenant_id, mode). Inheritance order
    matches the admin endpoint: platform_default → vertical_default
    → tenant_override; deeper scope wins. The `sources` array reports
    which scopes contributed.

    Tenants without an authored override at any scope receive
    `tokens: {}` + `sources: []` — the frontend then falls through to
    `tokens.css` static defaults via `composeEffective`'s fallback
    layer, which is the canonical "no overrides yet" behavior.
    """
    company = current_user.company
    vertical = company.vertical if company is not None else None
    tenant_id = company.id if company is not None else None

    try:
        result = resolve_theme(
            db,
            mode=mode,
            vertical=vertical,
            tenant_id=tenant_id,
        )
    except InvalidThemeShape as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ThemeServiceError as exc:
        logger.exception("[themes-tenant] resolve failed")
        raise HTTPException(status_code=500, detail=str(exc))

    return _ResolveResponse(**result)
