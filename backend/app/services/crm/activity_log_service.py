"""Activity log service — system event logging and manual activity tracking."""

import logging
import uuid as _uuid
from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog

logger = logging.getLogger(__name__)


def log_system_event(
    db: Session,
    tenant_id: str,
    master_company_id: str | None,
    activity_type: str,
    title: str,
    body: str | None = None,
    related_order_id: str | None = None,
    related_invoice_id: str | None = None,
    related_legacy_proof_id: str | None = None,
    customer_id: str | None = None,
) -> None:
    """Log a system-generated activity event.

    If master_company_id is None but customer_id is provided, looks up
    the company_entity via customers.master_company_id.
    """
    if not master_company_id and customer_id:
        from app.models.customer import Customer
        row = db.query(Customer.master_company_id).filter(Customer.id == customer_id).first()
        master_company_id = row[0] if row and row[0] else None

    if not master_company_id:
        logger.debug("Activity not logged — customer %s has no master_company_id", customer_id)
        return

    try:
        entry = ActivityLog(
            id=str(_uuid.uuid4()),
            tenant_id=tenant_id,
            master_company_id=master_company_id,
            activity_type=activity_type,
            is_system_generated=True,
            title=title,
            body=body,
            related_order_id=related_order_id,
            related_invoice_id=related_invoice_id,
            related_legacy_proof_id=related_legacy_proof_id,
        )
        db.add(entry)
    except Exception:
        logger.exception("Failed to log system event for %s", master_company_id)


def log_manual_activity(
    db: Session,
    tenant_id: str,
    master_company_id: str,
    activity_type: str,
    title: str,
    logged_by: str,
    body: str | None = None,
    outcome: str | None = None,
    contact_id: str | None = None,
    follow_up_date: str | None = None,
    follow_up_assigned_to: str | None = None,
) -> ActivityLog:
    """Create a manual activity log entry."""
    entry = ActivityLog(
        id=str(_uuid.uuid4()),
        tenant_id=tenant_id,
        master_company_id=master_company_id,
        activity_type=activity_type,
        is_system_generated=False,
        title=title,
        body=body,
        outcome=outcome,
        contact_id=contact_id,
        logged_by=logged_by,
        follow_up_date=follow_up_date,
        follow_up_assigned_to=follow_up_assigned_to,
    )
    db.add(entry)
    db.flush()
    return entry


def get_feed(
    db: Session,
    master_company_id: str,
    activity_type: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Return paginated activity feed for a company entity."""
    query = db.query(ActivityLog).filter(ActivityLog.master_company_id == master_company_id)
    if activity_type:
        query = query.filter(ActivityLog.activity_type == activity_type)

    total = query.count()
    items = (
        query.order_by(desc(ActivityLog.created_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {
        "items": [_serialize(e) for e in items],
        "total": total,
        "page": page,
        "pages": (total + per_page - 1) // per_page,
    }


def get_tenant_feed(
    db: Session,
    tenant_id: str,
    *,
    limit: int = 50,
    since: datetime | None = None,
) -> list[dict]:
    """Tenant-wide ActivityLog tail — aggregates across ALL companies
    the tenant tracks in CRM.

    Distinct from `get_feed` which is scoped to one CompanyEntity.
    Used by V-1c's Vault Overview CrmRecentActivityWidget.

    Joins on `CompanyEntity` so each activity carries the owning
    company's name/id for display. Tenant isolation: every
    ActivityLog row has a `tenant_id`; we filter by it AND ensure the
    join to CompanyEntity keeps us within the same tenant (defense in
    depth — ActivityLog.tenant_id is the canonical gate).

    Returns a list of dicts with: id, activity_type, title, body,
    is_system_generated, company_id, company_name, created_at,
    logged_by. Body is truncated to 200 chars to keep the payload
    tight for widget use; full bodies remain available via the
    per-company feed.
    """
    from app.models.company_entity import CompanyEntity  # avoid cycle

    query = (
        db.query(ActivityLog, CompanyEntity)
        .join(
            CompanyEntity,
            ActivityLog.master_company_id == CompanyEntity.id,
        )
        .filter(ActivityLog.tenant_id == tenant_id)
    )

    if since is not None:
        query = query.filter(ActivityLog.created_at >= since)

    rows = (
        query.order_by(desc(ActivityLog.created_at))
        .limit(max(1, min(limit, 200)))
        .all()
    )

    result: list[dict] = []
    for activity, company in rows:
        body = activity.body
        if body and len(body) > 200:
            body = body[:200] + "…"
        result.append(
            {
                "id": activity.id,
                "activity_type": activity.activity_type,
                "title": activity.title,
                "body": body,
                "is_system_generated": activity.is_system_generated,
                "company_id": company.id,
                "company_name": company.name,
                "created_at": activity.created_at,
                "logged_by": activity.logged_by,
            }
        )
    return result


def complete_followup(db: Session, activity_id: str, user_id: str) -> ActivityLog:
    """Mark a follow-up as completed."""
    entry = db.query(ActivityLog).filter(ActivityLog.id == activity_id).first()
    if not entry:
        raise ValueError("Activity not found")
    entry.follow_up_completed = True
    entry.follow_up_completed_at = datetime.now(timezone.utc)
    db.flush()
    return entry


def _serialize(e: ActivityLog) -> dict:
    return {
        "id": e.id,
        "activity_type": e.activity_type,
        "is_system_generated": e.is_system_generated,
        "title": e.title,
        "body": e.body,
        "outcome": e.outcome,
        "contact_id": e.contact_id,
        "logged_by": e.logged_by,
        "follow_up_date": e.follow_up_date.isoformat() if e.follow_up_date else None,
        "follow_up_assigned_to": e.follow_up_assigned_to,
        "follow_up_completed": e.follow_up_completed,
        "related_order_id": e.related_order_id,
        "related_invoice_id": e.related_invoice_id,
        "related_legacy_proof_id": e.related_legacy_proof_id,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }
