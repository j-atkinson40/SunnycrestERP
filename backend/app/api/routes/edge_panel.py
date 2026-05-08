"""Edge panel tenant-realm endpoints — R-5.0.

Three endpoints:

  - `GET /api/v1/edge-panel/resolve?panel_key=...` — resolves the
    composition for the caller's own tenant context, layering in the
    user's `User.preferences.edge_panel_overrides[panel_key]` blob.
    Returns the same shape as the admin endpoint (kind="edge_panel"
    flavor — `pages` is populated, `rows` empty).

  - `GET /api/v1/edge-panel/preferences` — returns the caller's
    `User.preferences.edge_panel_overrides` map (read-only access to
    one's own per-panel overrides). Surface for the deferred
    `/settings/edge-panel` page (R-5.1+).

  - `PATCH /api/v1/edge-panel/preferences` — replaces the caller's
    `User.preferences.edge_panel_overrides` map. Tenant operators write
    their own overrides; cross-user access is structurally impossible
    (the user identity comes from the JWT).

  - `GET /api/v1/edge-panel/tenant-config` — returns the caller's
    tenant-level edge panel config (width + enabled flag) read from
    `Company.settings_json`. Defaults: width=320, enabled=true.

Tenants never write platform/vertical/tenant_override composition
rows via these endpoints — those live in the admin realm at
`/api/platform/admin/visual-editor/compositions/`. This module is
READ + per-user-override write only.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.focus_compositions import (
    CompositionError,
    resolve_edge_panel,
)


logger = logging.getLogger(__name__)
router = APIRouter()


_DEFAULT_WIDTH = 320


class _ResolveResponse(BaseModel):
    panel_key: str
    vertical: str | None
    tenant_id: str | None
    source: str | None
    source_id: str | None
    source_version: int | None
    pages: list[dict[str, Any]] = Field(default_factory=list)
    canvas_config: dict[str, Any] = Field(default_factory=dict)


class _PreferencesResponse(BaseModel):
    edge_panel_overrides: dict[str, Any] = Field(default_factory=dict)


class _PreferencesPatchRequest(BaseModel):
    edge_panel_overrides: dict[str, Any]


class _TenantConfigResponse(BaseModel):
    enabled: bool = True
    width: int = _DEFAULT_WIDTH


def _user_overrides_for(user: User, panel_key: str) -> dict | None:
    prefs = user.preferences or {}
    overrides_root = prefs.get("edge_panel_overrides")
    if not isinstance(overrides_root, dict):
        return None
    blob = overrides_root.get(panel_key)
    if not isinstance(blob, dict):
        return None
    return blob


@router.get("/resolve", response_model=_ResolveResponse)
def resolve_endpoint(
    panel_key: str = Query(...),
    ignore_user_overrides: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _ResolveResponse:
    """Resolve an edge panel composition for the caller's context.

    `ignore_user_overrides=true` (R-5.1) returns the unmodified tenant
    default — used by the `/settings/edge-panel` page to compute the
    diff for ownership-badge rendering. The user's own overrides are
    bypassed; tenant + vertical + platform inheritance still applies.
    """
    company = current_user.company
    vertical = company.vertical if company is not None else None
    tenant_id = company.id if company is not None else None
    user_overrides = (
        None
        if ignore_user_overrides
        else _user_overrides_for(current_user, panel_key)
    )

    try:
        result = resolve_edge_panel(
            db,
            panel_key=panel_key,
            vertical=vertical,
            tenant_id=tenant_id,
            user_overrides=user_overrides,
        )
    except CompositionError as err:
        raise HTTPException(status_code=err.http_status, detail=str(err))

    return _ResolveResponse(
        panel_key=panel_key,
        vertical=result.get("vertical"),
        tenant_id=result.get("tenant_id"),
        source=result.get("source"),
        source_id=result.get("source_id"),
        source_version=result.get("source_version"),
        pages=list(result.get("pages") or []),
        canvas_config=dict(result.get("canvas_config") or {}),
    )


@router.get("/preferences", response_model=_PreferencesResponse)
def get_preferences(
    current_user: User = Depends(get_current_user),
) -> _PreferencesResponse:
    prefs = current_user.preferences or {}
    overrides = prefs.get("edge_panel_overrides") or {}
    if not isinstance(overrides, dict):
        overrides = {}
    return _PreferencesResponse(edge_panel_overrides=overrides)


@router.patch("/preferences", response_model=_PreferencesResponse)
def patch_preferences(
    body: _PreferencesPatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> _PreferencesResponse:
    if not isinstance(body.edge_panel_overrides, dict):
        raise HTTPException(
            status_code=422,
            detail="edge_panel_overrides must be an object",
        )
    prefs = dict(current_user.preferences or {})
    prefs["edge_panel_overrides"] = body.edge_panel_overrides
    current_user.preferences = prefs
    flag_modified(current_user, "preferences")
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return _PreferencesResponse(
        edge_panel_overrides=current_user.preferences.get(
            "edge_panel_overrides", {}
        )
    )


@router.get("/tenant-config", response_model=_TenantConfigResponse)
def tenant_config(
    current_user: User = Depends(get_current_user),
) -> _TenantConfigResponse:
    company = current_user.company
    if company is None:
        return _TenantConfigResponse()
    settings = company.settings or {}
    enabled = settings.get("edge_panel_enabled")
    width = settings.get("edge_panel_width")
    return _TenantConfigResponse(
        enabled=bool(enabled) if enabled is not None else True,
        width=int(width) if isinstance(width, (int, float)) and width else _DEFAULT_WIDTH,
    )
