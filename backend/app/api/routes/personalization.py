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


@router.get("/today-and-tomorrow")
def get_personalization_queue(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get personalization tasks for today's and tomorrow's service dates."""
    from datetime import date, timedelta
    from app.models.sales_order import SalesOrder, SalesOrderLine
    from app.models.customer import Customer

    today = date.today()
    tomorrow = today + timedelta(days=1)

    tasks = (
        db.query(OrderPersonalizationTask, SalesOrder)
        .join(SalesOrder, OrderPersonalizationTask.order_id == SalesOrder.id)
        .filter(
            OrderPersonalizationTask.company_id == current_user.company_id,
            SalesOrder.scheduled_date.in_([today, tomorrow]),
            SalesOrder.status.notin_(["cancelled", "void"]),
        )
        .order_by(SalesOrder.scheduled_date, SalesOrder.service_time)
        .all()
    )

    def serialize(task, order):
        customer = db.query(Customer).filter(Customer.id == order.customer_id).first() if order.customer_id else None
        return {
            "task_id": task.id,
            "task_type": task.task_type,
            "order_id": order.id,
            "funeral_home_name": customer.name if customer else "",
            "vault_name": task.notes or "",
            "deceased_name": order.deceased_name or "",
            "service_date": order.scheduled_date.isoformat() if order.scheduled_date else None,
            "service_time": order.service_time.strftime("%I:%M %p").lstrip("0") if order.service_time else None,
            "print_name": task.print_name,
            "print_image_url": task.print_image_url,
            "symbol": task.symbol,
            "inscription_name": task.inscription_name,
            "inscription_dates": task.inscription_dates,
            "inscription_additional": task.inscription_additional,
            "status": task.status,
            "has_photos": False,
            "legacy_photo_pending": order.legacy_photo_pending or False,
            "proof_url": task.proof_url,
            "is_custom_legacy": task.is_custom_legacy or False,
        }

    today_tasks = [serialize(t, o) for t, o in tasks if o.scheduled_date == today]
    tomorrow_tasks = [serialize(t, o) for t, o in tasks if o.scheduled_date == tomorrow]

    return {"today": today_tasks, "tomorrow": tomorrow_tasks}


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
