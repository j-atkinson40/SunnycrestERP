"""Job Coordination Focus routes (JCF-1, tenant realm).

The thin router over the realm-agnostic service. The read-guard is the
service's `can_access`/`read_instance` (owner tenant OR active FocusShare);
denied reads return 404 — existence is not disclosed across tenants.

  POST /api/v1/coordination-focus/for-order/{sales_order_id}  — idempotent spawn (owner only)
  GET  /api/v1/coordination-focus/{instance_id}               — guarded read (instance + composition)
  POST /api/v1/coordination-focus/{instance_id}/shares        — grant (owner only)
  POST /api/v1/coordination-focus/shares/{share_id}/revoke    — revoke (owner only)
  GET  /api/v1/coordination-focus/{instance_id}/messages      — thread (guarded)
  POST /api/v1/coordination-focus/{instance_id}/messages      — post (guarded)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.coordination_focus import FocusShare
from app.services import coordination_focus as jcf

router = APIRouter()


class GrantRequest(BaseModel):
    target_company_id: str
    target_user_id: str | None = None


class PostMessageRequest(BaseModel):
    body: str = Field(..., min_length=1)


def _message_out(m) -> dict:
    return {
        "id": m.id,
        "instance_id": m.instance_id,
        "author_company_id": m.author_company_id,
        "author_user_id": m.author_user_id,
        "body": m.body,
        "created_at": m.created_at.isoformat(),
    }


@router.post("/for-order/{sales_order_id}")
def spawn_for_order(
    sales_order_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Order-launched spawn (idempotent). Owner-tenant only: the order must
    belong to the caller's tenant."""
    try:
        instance = jcf.ensure_instance_for_order(db, sales_order_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Order not found")
    if instance.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Order not found")
    return jcf.read_instance(
        db,
        instance.id,
        company_id=current_user.company_id,
        user_id=current_user.id,
    )


@router.get("/{instance_id}")
def read_instance(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return jcf.read_instance(
            db,
            instance_id,
            company_id=current_user.company_id,
            user_id=current_user.id,
        )
    except jcf.AccessDenied:
        raise HTTPException(status_code=404, detail="Not found")


@router.post("/{instance_id}/shares")
def grant_share(
    instance_id: str,
    body: GrantRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    instance = jcf.get_instance(db, instance_id)
    if instance is None or instance.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        share = jcf.grant_share(
            db,
            instance,
            target_company_id=body.target_company_id,
            target_user_id=body.target_user_id,
            granted_by_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "id": share.id,
        "instance_id": share.instance_id,
        "target_company_id": share.target_company_id,
        "target_user_id": share.target_user_id,
        "permission": share.permission,
        "granted_at": share.granted_at.isoformat(),
    }


@router.post("/shares/{share_id}/revoke")
def revoke_share(
    share_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    share = db.query(FocusShare).filter(FocusShare.id == share_id).first()
    if share is None or share.owner_company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Not found")
    jcf.revoke_share(db, share, revoked_by_user_id=current_user.id)
    return {"id": share.id, "revoked_at": share.revoked_at.isoformat()}


@router.get("/{instance_id}/messages")
def list_messages(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        msgs = jcf.list_messages(
            db,
            instance_id,
            company_id=current_user.company_id,
            user_id=current_user.id,
        )
    except jcf.AccessDenied:
        raise HTTPException(status_code=404, detail="Not found")
    return {"messages": [_message_out(m) for m in msgs]}


@router.post("/{instance_id}/messages")
def post_message(
    instance_id: str,
    body: PostMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        msg = jcf.post_message(
            db,
            instance_id,
            company_id=current_user.company_id,
            user_id=current_user.id,
            body=body.body,
        )
    except jcf.AccessDenied:
        raise HTTPException(status_code=404, detail="Not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _message_out(msg)
