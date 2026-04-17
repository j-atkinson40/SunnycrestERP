"""Saved Orders API — list/match/create/update/delete compose templates."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services import saved_order_service

router = APIRouter()


# ──────────────────────────────────────────────────────── Schemas

class MatchRequest(BaseModel):
    input_text: str


class MatchResponse(BaseModel):
    match: dict | None = None


class CreateRequest(BaseModel):
    workflow_run_id: str
    name: str = Field(..., min_length=1, max_length=255)
    trigger_keywords: list[str] = Field(default_factory=list)
    scope: str = Field(default="user")


class UpdateRequest(BaseModel):
    name: str | None = None
    trigger_keywords: list[str] | None = None
    saved_fields: dict[str, Any] | None = None
    scope: str | None = None


# ──────────────────────────────────────────────────────── Routes

@router.post("/match", response_model=MatchResponse)
def match_saved_order(
    payload: MatchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the best saved-order match for the typed input, if any.

    Designed to be the first call on every overlay debounce — skipped
    on no-match, avoiding a downstream Claude extraction round-trip.
    """
    so = saved_order_service.find_match(
        db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        input_text=payload.input_text,
    )
    return MatchResponse(match=saved_order_service.serialize(so) if so else None)


@router.post("", status_code=201)
def create_saved_order(
    payload: CreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        so = saved_order_service.create_from_workflow_run(
            db,
            company_id=current_user.company_id,
            user_id=current_user.id,
            workflow_run_id=payload.workflow_run_id,
            name=payload.name,
            trigger_keywords=payload.trigger_keywords,
            scope=payload.scope,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return saved_order_service.serialize(so)


@router.get("")
def list_saved_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mine, shared = saved_order_service.list_for_user(
        db, company_id=current_user.company_id, user_id=current_user.id
    )
    return {
        "mine": [saved_order_service.serialize(r) for r in mine],
        "shared": [saved_order_service.serialize(r) for r in shared],
    }


@router.patch("/{saved_order_id}")
def update_saved_order(
    saved_order_id: str,
    payload: UpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    so = saved_order_service.get(
        db, company_id=current_user.company_id, saved_order_id=saved_order_id
    )
    if not so:
        raise HTTPException(status_code=404, detail="Saved order not found")
    # Only the creator can edit a user-scope template; any admin can edit company-scope.
    if so.scope == "user" and so.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot edit another user's saved order")
    so = saved_order_service.update(
        db,
        saved_order=so,
        name=payload.name,
        trigger_keywords=payload.trigger_keywords,
        saved_fields=payload.saved_fields,
        scope=payload.scope,
    )
    return saved_order_service.serialize(so)


@router.delete("/{saved_order_id}", status_code=204)
def delete_saved_order(
    saved_order_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    so = saved_order_service.get(
        db, company_id=current_user.company_id, saved_order_id=saved_order_id
    )
    if not so:
        raise HTTPException(status_code=404, detail="Saved order not found")
    if so.scope == "user" and so.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot delete another user's saved order")
    saved_order_service.soft_delete(db, saved_order=so)
    return None
