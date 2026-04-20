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

V-1d extended create_notification with the alert-flavor fields
(severity, due_date, source_reference_type/_id) so safety alerts +
new sources (compliance_expiry, delivery_failed, etc.) can route
through the same call. See notify_tenant_admins for the admin
fan-out used by tenant-wide events that don't target a single user.
"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.role import Role
from app.models.user import User

logger = logging.getLogger(__name__)


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
    *,
    severity: str | None = None,
    due_date: datetime | None = None,
    source_reference_type: str | None = None,
    source_reference_id: str | None = None,
) -> Notification:
    """
    Create an in-app notification for a user. Uses db.flush() (not commit)
    so the notification is committed atomically with the caller's operation.

    Alert-flavor kwargs (severity, due_date, source_reference_*) are
    optional and used by the V-1d notification sources (safety_alert,
    compliance_expiry, delivery_failed, etc.).
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
        severity=severity,
        due_date=due_date,
        source_reference_type=source_reference_type,
        source_reference_id=source_reference_id,
    )
    db.add(notification)
    db.flush()
    return notification


def notify_tenant_admins(
    db: Session,
    company_id: str,
    title: str,
    message: str,
    *,
    type: str = "info",
    category: str | None = None,
    link: str | None = None,
    actor_id: str | None = None,
    severity: str | None = None,
    due_date: datetime | None = None,
    source_reference_type: str | None = None,
    source_reference_id: str | None = None,
) -> list[Notification]:
    """Fan-out: create one Notification per active admin user in a tenant.

    Mirrors the r29 migration's SQL fan-out (INNER JOIN users→roles,
    role.slug='admin', user.is_active). If a tenant has no admins the
    return list is empty and no rows are created — the caller should
    log or ignore. Wrap this in try/except if the event is not
    mission-critical (every V-1d wire-up does).
    """
    admins = (
        db.query(User)
        .join(Role, Role.id == User.role_id)
        .filter(
            User.company_id == company_id,
            User.is_active.is_(True),
            Role.slug == "admin",
        )
        .all()
    )
    out: list[Notification] = []
    for admin in admins:
        out.append(
            create_notification(
                db,
                company_id=company_id,
                user_id=admin.id,
                title=title,
                message=message,
                type=type,
                category=category,
                link=link,
                actor_id=actor_id,
                severity=severity,
                due_date=due_date,
                source_reference_type=source_reference_type,
                source_reference_id=source_reference_id,
            )
        )
    if not out:
        logger.info(
            "notify_tenant_admins: no active admins for company_id=%s "
            "category=%s — notification not created",
            company_id,
            category,
        )
    return out


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
