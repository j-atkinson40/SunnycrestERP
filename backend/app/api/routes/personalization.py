"""Vault personalization API — config, tasks, photos."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.services.personalization_config import get_full_config, validate_personalization
from app.database import get_db
from app.models.order_personalization_photo import OrderPersonalizationPhoto
from app.models.order_personalization_task import OrderPersonalizationTask
from app.models.user import User

router = APIRouter()


class CompleteTaskRequest(BaseModel):
    notes: str | None = None


@router.get("/config")
def get_personalization_config():
    """Return the full personalization config (tiers, prints, symbols, images)."""
    return get_full_config()


@router.get("/orders/{order_id}/personalization")
def get_order_personalization(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get personalization tasks and photos for an order."""
    tasks = (
        db.query(OrderPersonalizationTask)
        .filter(
            OrderPersonalizationTask.order_id == order_id,
            OrderPersonalizationTask.company_id == current_user.company_id,
        )
        .order_by(OrderPersonalizationTask.created_at)
        .all()
    )

    photos = (
        db.query(OrderPersonalizationPhoto)
        .filter(
            OrderPersonalizationPhoto.order_id == order_id,
            OrderPersonalizationPhoto.company_id == current_user.company_id,
        )
        .all()
    )

    return {
        "tasks": [
            {
                "id": t.id,
                "task_type": t.task_type,
                "inscription_name": t.inscription_name,
                "inscription_dates": t.inscription_dates,
                "inscription_additional": t.inscription_additional,
                "print_name": t.print_name,
                "print_image_url": t.print_image_url,
                "symbol": t.symbol,
                "is_custom_legacy": t.is_custom_legacy,
                "status": t.status,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                "notes": t.notes,
            }
            for t in tasks
        ],
        "photos": [
            {
                "id": p.id,
                "filename": p.filename,
                "file_url": p.file_url,
                "uploaded_at": p.uploaded_at.isoformat() if p.uploaded_at else None,
                "notes": p.notes,
            }
            for p in photos
        ],
    }


@router.post("/orders/{order_id}/personalization/tasks/{task_id}/complete")
def complete_task(
    order_id: str,
    task_id: str,
    data: CompleteTaskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a personalization task as complete."""
    task = (
        db.query(OrderPersonalizationTask)
        .filter(
            OrderPersonalizationTask.id == task_id,
            OrderPersonalizationTask.order_id == order_id,
            OrderPersonalizationTask.company_id == current_user.company_id,
        )
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "complete"
    task.completed_by = current_user.id
    task.completed_at = datetime.now(timezone.utc)
    if data.notes:
        task.notes = data.notes

    db.commit()
    return {"completed": True}


@router.post("/orders/{order_id}/personalization/waive-photo")
def waive_legacy_photo(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Clear legacy_photo_pending flag."""
    from app.models.sales_order import SalesOrder

    order = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.id == order_id,
            SalesOrder.company_id == current_user.company_id,
        )
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.legacy_photo_pending = False
    db.commit()
    return {"waived": True}


@router.post("/orders/{order_id}/personalization/validate")
def validate_order_personalization(
    order_id: str,
    personalization_data: list[dict],
    tier: str,
    current_user: User = Depends(get_current_user),
):
    """Validate personalization selections against tier rules."""
    return validate_personalization(personalization_data, tier)
