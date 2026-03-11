from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.notification import NotificationListResponse, NotificationResponse
from app.services import notification_service

router = APIRouter()


def _notification_to_response(notification, db: Session) -> dict:
    """Convert a Notification model to a response dict with actor name."""
    data = NotificationResponse.model_validate(notification).model_dump()
    if notification.actor_id:
        actor = db.query(User).filter(User.id == notification.actor_id).first()
        if actor:
            data["actor_name"] = f"{actor.first_name} {actor.last_name}"
    return data


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = notification_service.get_notifications(
        db,
        current_user.id,
        current_user.company_id,
        page=page,
        per_page=per_page,
        unread_only=unread_only,
    )
    return {
        "items": [_notification_to_response(n, db) for n in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "unread_count": result["unread_count"],
    }


@router.get("/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = notification_service.get_unread_count(
        db, current_user.id, current_user.company_id
    )
    return {"count": count}


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification = notification_service.mark_as_read(
        db, notification_id, current_user.id, current_user.company_id
    )
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    return _notification_to_response(notification, db)


@router.patch("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = notification_service.mark_all_as_read(
        db, current_user.id, current_user.company_id
    )
    return {"detail": f"Marked {count} notifications as read"}
