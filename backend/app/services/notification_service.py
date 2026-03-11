"""
Notification service — in-app notification system for all business events.

Usage from any service:
    from app.services import notification_service

    notification_service.create_notification(
        db, company_id, user_id,
        title="Profile Updated",
        message="Your employee profile was updated by an admin.",
        type="info",
        category="employee",
        link="/profile",
        actor_id=current_user.id,
    )
"""

from sqlalchemy.orm import Session

from app.models.notification import Notification


def create_notification(
    db: Session,
    company_id: str,
    user_id: str,
    title: str,
    message: str,
    type: str = "info",
    category: str | None = None,
    link: str | None = None,
    actor_id: str | None = None,
) -> Notification:
    """
    Create an in-app notification for a user. Uses db.flush() (not commit)
    so the notification is committed atomically with the caller's operation.
    """
    notification = Notification(
        company_id=company_id,
        user_id=user_id,
        title=title,
        message=message,
        type=type,
        category=category,
        link=link,
        actor_id=actor_id,
    )
    db.add(notification)
    db.flush()
    return notification


def get_notifications(
    db: Session,
    user_id: str,
    company_id: str,
    page: int = 1,
    per_page: int = 20,
    unread_only: bool = False,
) -> dict:
    """Query notifications for a user with pagination."""
    query = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.company_id == company_id,
    )

    if unread_only:
        query = query.filter(Notification.is_read == False)  # noqa: E712

    total = query.count()
    items = (
        query.order_by(Notification.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    # Get unread count (always, regardless of filter)
    unread_count = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.company_id == company_id,
            Notification.is_read == False,  # noqa: E712
        )
        .count()
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "unread_count": unread_count,
    }


def get_unread_count(db: Session, user_id: str, company_id: str) -> int:
    """Return the number of unread notifications for a user."""
    return (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.company_id == company_id,
            Notification.is_read == False,  # noqa: E712
        )
        .count()
    )


def mark_as_read(
    db: Session,
    notification_id: str,
    user_id: str,
    company_id: str,
) -> Notification | None:
    """Mark a single notification as read. Returns None if not found."""
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == user_id,
            Notification.company_id == company_id,
        )
        .first()
    )
    if not notification:
        return None

    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification


def mark_all_as_read(db: Session, user_id: str, company_id: str) -> int:
    """Mark all unread notifications as read. Returns the number updated."""
    count = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.company_id == company_id,
            Notification.is_read == False,  # noqa: E712
        )
        .update({"is_read": True})
    )
    db.commit()
    return count
