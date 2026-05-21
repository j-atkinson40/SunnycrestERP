"""Widget Builder draft + publish API (WB-4a).

Endpoints backing the Widget Builder shell. Mounted at
`/api/v1/widget-definitions/*` (deliberately distinct from `/widgets`
which serves the legacy 4-axis catalog + layout endpoints).

Three endpoints:

  • POST /                         — create a new composed widget with
                                     a default empty flex-stack root.
                                     Returns 201 + the new row.
  • PUT  /{slug}/draft             — auto-save the draft (permissive
                                     validation; preserves
                                     `published_composition_blob`).
  • POST /{slug}/publish           — promote draft → live (full
                                     validator pass; returns 422 with
                                     errors on invalid).
  • GET  /{slug}                   — fetch a single widget (matches the
                                     WB-4a editor's load path).

Per investigation Area 2 lock: composition_blob is the DRAFT;
published_composition_blob is the LIVE render. Tenant render paths
read published first; legacy fallback to draft handled by the
frontend dispatch (see `runtime/dispatch.ts`).
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
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
    """Draft save payload.

    composition_blob is `Any` on the wire — permissive auto-save per
    Area 5 lock. Publish enforces validity. Title can ride along for
    inline-rename support without a separate endpoint.
    """

    composition_blob: Any
    edit_session_id: Optional[str] = None
    title: Optional[str] = None


# ── endpoints ─────────────────────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED)
def create_widget(
    body: CreateWidgetDefinitionBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new composed widget with an empty flex-stack root.

    Tier scope defaults to 'vertical' (per investigation: most
    operator-authored widgets are vertical-scoped; platform-scope is
    reserved for cross-vertical primitives shipped by the platform
    team). composition_version=1; published_composition_blob=NULL.
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List composed widget definitions for the WB-4b list view.

    Returns every row that has a non-NULL `composition_blob` (i.e.
    rows authored via the Widget Builder) — legacy hand-coded widgets
    are excluded. Optional `tier_scope` query filter narrows to
    'platform' or 'vertical'.
    """
    from app.models.widget_definition import WidgetDefinition

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


@router.get("/{slug}")
def get_widget(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch a single widget by slug for the Widget Builder editor."""
    try:
        row = _resolve_widget(db, slug)
    except WidgetDefinitionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=slug)
    return serialize_widget(row)


@router.put("/{slug}/draft")
def put_draft(
    slug: str,
    body: SaveDraftBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Auto-save the draft. Permissive — full validation deferred to Publish."""
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Promote the draft to live. Full validation; 422 on invalid."""
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
