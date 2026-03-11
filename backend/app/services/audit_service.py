"""
Audit logging service — append-only event log for all business operations.

Usage from any service:
    from app.services import audit_service

    audit_service.log_action(
        db, company_id, "created", "user", user.id,
        user_id=current_user.id,
        changes={"email": "new@example.com"},
    )
"""

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_action(
    db: Session,
    company_id: str,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    user_id: str | None = None,
    changes: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    """
    Record an audit event. Uses db.flush() (not commit) so the audit entry
    is committed atomically with the caller's business operation.
    """
    entry = AuditLog(
        company_id=company_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=json.dumps(changes) if changes else None,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(entry)
    db.flush()
    return entry


def compute_changes(old: dict, new: dict) -> dict | None:
    """
    Compare old and new values, return a dict of changed fields.
    Format: {"field_name": {"old": old_value, "new": new_value}}
    Returns None if no changes.
    """
    changes = {}
    for key in new:
        if key in old and old[key] != new[key]:
            changes[key] = {"old": old[key], "new": new[key]}
    return changes if changes else None


def get_audit_logs(
    db: Session,
    company_id: str,
    page: int = 1,
    per_page: int = 50,
    user_id: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict:
    """Query audit logs with pagination and filtering."""
    query = db.query(AuditLog).filter(AuditLog.company_id == company_id)

    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)
    if date_from:
        query = query.filter(AuditLog.created_at >= date_from)
    if date_to:
        query = query.filter(AuditLog.created_at <= date_to)

    total = query.count()
    items = (
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


def get_audit_log(db: Session, log_id: str, company_id: str) -> AuditLog | None:
    """Fetch a single audit log entry."""
    return (
        db.query(AuditLog)
        .filter(AuditLog.id == log_id, AuditLog.company_id == company_id)
        .first()
    )
