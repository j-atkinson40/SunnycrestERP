"""Admin Visual Editor — Widget Builder API (WB-cycle-followup-2).

Platform-realm mirror of the tenant Widget Builder endpoints at
`backend/app/api/routes/widget_definitions.py` + the composed-definitions
endpoint at `backend/app/api/routes/widgets.py`.

Closes the 403 gap from WB-cycle-followup-1: rail entry on
`admin.getbridgeable.com` surfaced the Widget Builder shell but the
underlying endpoints lived only on the tenant API tree (gated by
`Depends(get_current_user)`), which rejects platform-realm tokens.

Per investigation 2026-05-26 Area 5 lock: the service layer at
`app.services.widget_definitions` is realm-agnostic (no tenant filter;
data model has no `company_id`), so this module consumes the existing
service functions verbatim. Only the auth surface + URL prefix differ.

Endpoints (all `Depends(get_current_platform_user)`, mounted at
`/api/platform/admin/visual-editor/widgets`):

    GET    /                       — list composed widget definitions
                                      (composition_blob NOT NULL),
                                      optional ?tier_scope filter
    POST   /                       — create a new composed widget
    GET    /{slug}                 — single widget by slug
    PUT    /{slug}/draft           — auto-save draft (permissive)
    POST   /{slug}/publish         — promote draft → live (strict)
    GET    /composed-definitions   — minimal palette payload for the
                                      visual-editor metadata registry
                                      bridge (parallel to tenant
                                      /widgets/composed-definitions;
                                      Q-B1 lock keeps the tenant boot
                                      bridge UNCHANGED — this endpoint
                                      is structural parity for future
                                      admin-side palette consumers)

Per Q-B1 lock: this module does NOT modify the tenant
`registerComposedWidgets` runtime bridge. Tenant render paths read
the tenant endpoints; admin Widget Builder consumers read this module.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user, get_db
from app.models.platform_user import PlatformUser
from app.models.widget_definition import WidgetDefinition
from app.services.widget_definitions import (
    CannotPublishWithoutDraftError,
    CompositionBlobValidationError,
    WidgetDefinitionNotFoundError,
    create_widget_definition,
    publish_draft,
    save_draft,
    serialize_widget,
)
from app.services.widget_definitions.publish import _resolve_widget


router = APIRouter()


# ── request shapes ────────────────────────────────────────────────────


class CreateWidgetDefinitionBody(BaseModel):
    """Create payload — all fields optional; defaults applied server-side."""

    title: Optional[str] = None
    slug: Optional[str] = None
    tier_scope: Optional[str] = Field(default="vertical")
    category: Optional[str] = None


class SaveDraftBody(BaseModel):
    """Draft save payload (permissive — publish enforces validity)."""

    composition_blob: Any
    edit_session_id: Optional[str] = None
    title: Optional[str] = None


# ── endpoints ─────────────────────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED)
def create_widget(
    body: CreateWidgetDefinitionBody,
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Create a new composed widget with an empty flex-stack root.

    Mirrors `routes/widget_definitions.py::create_widget`.
    """
    tier_scope = body.tier_scope or "vertical"
    if tier_scope not in ("platform", "vertical"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"tier_scope must be 'platform' or 'vertical'; got {tier_scope!r}",
        )
    row = create_widget_definition(
        db,
        title=body.title,
        slug=body.slug,
        tier_scope=tier_scope,
        category=body.category,
    )
    db.commit()
    return serialize_widget(row)


@router.get("")
def list_widgets(
    tier_scope: Optional[str] = None,
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """List composed widget definitions for the Widget Builder list view.

    Mirrors `routes/widget_definitions.py::list_widgets`.
    """
    q = db.query(WidgetDefinition).filter(
        WidgetDefinition.composition_blob.isnot(None)
    )
    if tier_scope is not None:
        if tier_scope not in ("platform", "vertical"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"tier_scope must be 'platform' or 'vertical'; "
                    f"got {tier_scope!r}"
                ),
            )
        q = q.filter(WidgetDefinition.tier_scope == tier_scope)
    rows = q.order_by(WidgetDefinition.title.asc()).all()
    return {"widgets": [serialize_widget(r) for r in rows]}


@router.get("/composed-definitions")
def list_composed_widget_definitions(
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Minimal palette payload for the visual-editor metadata registry.

    Mirrors `routes/widgets.py::list_composed_widget_definitions`. Per
    Q-B1 lock: the tenant boot bridge (`registerComposedWidgets.ts`)
    remains the canonical consumer of `/api/v1/widgets/composed-definitions`
    on the tenant tree. This endpoint exists for future admin-side
    palette consumers + structural parity; it is NOT wired into the
    tenant `App.tsx` boot path in this build.
    """
    rows = (
        db.query(WidgetDefinition)
        .filter(WidgetDefinition.composition_blob.isnot(None))
        .all()
    )
    return [
        {
            "widget_id": r.widget_id,
            "title": r.title,
            "description": r.description,
            "icon": r.icon,
            "category": r.category,
            "composition_blob": r.composition_blob,
            "composition_version": r.composition_version,
            "tier_scope": r.tier_scope,
            "supported_surfaces": r.supported_surfaces or ["dashboard_grid"],
            "default_size": r.default_size,
            "supported_sizes": r.supported_sizes or ["1x1"],
        }
        for r in rows
    ]


@router.get("/{slug}")
def get_widget(
    slug: str,
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Fetch a single widget by slug.

    Mirrors `routes/widget_definitions.py::get_widget`.
    """
    try:
        row = _resolve_widget(db, slug)
    except WidgetDefinitionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=slug)
    return serialize_widget(row)


@router.put("/{slug}/draft")
def put_draft(
    slug: str,
    body: SaveDraftBody,
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Auto-save the draft (permissive).

    Mirrors `routes/widget_definitions.py::put_draft`. `actor_user_id`
    is the platform user's id — the audit-attribution limitation
    documented in CLAUDE.md §4 (Bridgeable Admin tree) applies: the
    `users.id` FK on audit columns cannot resolve a PlatformUser id,
    so the service layer's actor stamping degrades gracefully when the
    actor is a platform user.
    """
    if not isinstance(body.composition_blob, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="composition_blob must be a JSON object",
        )
    try:
        row = save_draft(
            db,
            slug=slug,
            composition_blob=body.composition_blob,
            edit_session_id=body.edit_session_id,
            actor_user_id=str(current_user.id),
            title=body.title,
        )
    except WidgetDefinitionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=slug)
    db.commit()
    return serialize_widget(row)


@router.post("/{slug}/publish")
def post_publish(
    slug: str,
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Promote the draft to live; full validation; 422 on invalid.

    Mirrors `routes/widget_definitions.py::post_publish`.
    """
    try:
        row = publish_draft(db, slug=slug)
    except WidgetDefinitionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=slug)
    except CannotPublishWithoutDraftError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "no_draft",
                "message": "composition_blob is NULL — nothing to publish",
            },
        )
    except CompositionBlobValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "composition_invalid",
                "errors": exc.errors,
            },
        )
    db.commit()
    return serialize_widget(row)
