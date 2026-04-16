"""Vault service — core CRUD for vaults and vault items."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.vault import Vault
from app.models.vault_item import VaultItem


def get_or_create_company_vault(db: Session, company_id: str) -> Vault:
    """Get or create the primary company vault for a tenant."""
    vault = (
        db.query(Vault)
        .filter(
            Vault.company_id == company_id,
            Vault.vault_type == "company",
            Vault.is_active == True,
        )
        .first()
    )
    if not vault:
        vault = Vault(
            id=str(uuid.uuid4()),
            company_id=company_id,
            vault_type="company",
            name="Company Vault",
        )
        db.add(vault)
        db.flush()
    return vault


def create_vault_item(
    db: Session,
    *,
    company_id: str,
    item_type: str,
    title: str,
    vault_id: Optional[str] = None,
    description: Optional[str] = None,
    r2_key: Optional[str] = None,
    file_size_bytes: Optional[int] = None,
    mime_type: Optional[str] = None,
    document_type: Optional[str] = None,
    event_start: Optional[datetime] = None,
    event_end: Optional[datetime] = None,
    event_location: Optional[str] = None,
    event_type: Optional[str] = None,
    event_type_sub: Optional[str] = None,
    all_day: bool = False,
    recurrence_rule: Optional[str] = None,
    notify_recipients: Optional[list] = None,
    notify_before_minutes: Optional[list] = None,
    visibility: str = "internal",
    shared_with_company_ids: Optional[list] = None,
    parent_item_id: Optional[str] = None,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[str] = None,
    status: str = "active",
    source: str = "system_generated",
    source_entity_id: Optional[str] = None,
    created_by: Optional[str] = None,
    metadata_json: Optional[dict] = None,
) -> VaultItem:
    """Create a new vault item. Auto-creates company vault if vault_id not provided."""
    if not vault_id:
        vault = get_or_create_company_vault(db, company_id)
        vault_id = vault.id

    item = VaultItem(
        id=str(uuid.uuid4()),
        vault_id=vault_id,
        company_id=company_id,
        item_type=item_type,
        title=title,
        description=description,
        r2_key=r2_key,
        file_size_bytes=file_size_bytes,
        mime_type=mime_type,
        document_type=document_type,
        event_start=event_start,
        event_end=event_end,
        event_location=event_location,
        event_type=event_type,
        event_type_sub=event_type_sub,
        all_day=all_day,
        recurrence_rule=recurrence_rule,
        notify_recipients=notify_recipients,
        notify_before_minutes=notify_before_minutes,
        visibility=visibility,
        shared_with_company_ids=shared_with_company_ids,
        parent_item_id=parent_item_id,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        status=status,
        source=source,
        source_entity_id=source_entity_id,
        created_by=created_by,
        metadata_json=metadata_json,
    )
    db.add(item)
    db.flush()
    return item


def get_vault_item(db: Session, item_id: str, company_id: str) -> Optional[VaultItem]:
    """Get a single vault item by ID, scoped to company."""
    return (
        db.query(VaultItem)
        .filter(
            VaultItem.id == item_id,
            VaultItem.company_id == company_id,
            VaultItem.is_active == True,
        )
        .first()
    )


def query_vault_items(
    db: Session,
    company_id: str,
    *,
    item_type: Optional[str] = None,
    event_type: Optional[str] = None,
    event_type_sub: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    status: Optional[str] = None,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[str] = None,
    source: Optional[str] = None,
    visibility: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[VaultItem]:
    """Query vault items with flexible filtering."""
    q = db.query(VaultItem).filter(
        VaultItem.company_id == company_id,
        VaultItem.is_active == True,
    )
    if item_type:
        q = q.filter(VaultItem.item_type == item_type)
    if event_type:
        q = q.filter(VaultItem.event_type == event_type)
    if event_type_sub:
        q = q.filter(VaultItem.event_type_sub == event_type_sub)
    if date_from:
        q = q.filter(VaultItem.event_start >= date_from)
    if date_to:
        q = q.filter(VaultItem.event_start <= date_to)
    if status:
        q = q.filter(VaultItem.status == status)
    if related_entity_type:
        q = q.filter(VaultItem.related_entity_type == related_entity_type)
    if related_entity_id:
        q = q.filter(VaultItem.related_entity_id == related_entity_id)
    if source:
        q = q.filter(VaultItem.source == source)
    if visibility:
        q = q.filter(VaultItem.visibility == visibility)

    q = q.order_by(VaultItem.event_start.asc().nullslast(), VaultItem.created_at.desc())
    return q.offset(offset).limit(limit).all()


def get_cross_tenant_items(
    db: Session,
    requesting_company_id: str,
    from_company_id: str,
    *,
    item_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[VaultItem]:
    """Get vault items shared with the requesting company from a specific company."""
    q = db.query(VaultItem).filter(
        VaultItem.company_id == from_company_id,
        VaultItem.is_active == True,
        VaultItem.shared_with_company_ids.op("@>")(f'["{requesting_company_id}"]'),
    )
    if item_type:
        q = q.filter(VaultItem.item_type == item_type)
    q = q.order_by(VaultItem.created_at.desc())
    return q.offset(offset).limit(limit).all()


def update_vault_item(
    db: Session,
    item_id: str,
    company_id: str,
    **kwargs,
) -> Optional[VaultItem]:
    """Update a vault item. Only provided kwargs are updated."""
    item = get_vault_item(db, item_id, company_id)
    if not item:
        return None
    for key, value in kwargs.items():
        if hasattr(item, key):
            setattr(item, key, value)
    db.flush()
    return item


def get_vault_summary(db: Session, company_id: str) -> dict:
    """Get vault summary counts for dashboard widgets."""
    from sqlalchemy import func, case
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    week_end = today_start + timedelta(days=7)

    base = db.query(VaultItem).filter(
        VaultItem.company_id == company_id,
        VaultItem.is_active == True,
        VaultItem.status == "active",
    )

    total = base.count()
    events_today = base.filter(
        VaultItem.item_type == "event",
        VaultItem.event_start >= today_start,
        VaultItem.event_start < today_end,
    ).count()
    events_this_week = base.filter(
        VaultItem.item_type == "event",
        VaultItem.event_start >= today_start,
        VaultItem.event_start < week_end,
    ).count()
    upcoming_expiries = base.filter(
        VaultItem.event_type == "compliance_expiry",
        VaultItem.event_start >= today_start,
        VaultItem.event_start < today_start + timedelta(days=30),
    ).count()
    documents = base.filter(VaultItem.item_type == "document").count()

    return {
        "total_items": total,
        "events_today": events_today,
        "events_this_week": events_this_week,
        "upcoming_expiries": upcoming_expiries,
        "documents": documents,
    }


def get_upcoming_events(
    db: Session,
    company_id: str,
    *,
    days: int = 7,
    role: Optional[str] = None,
) -> list[VaultItem]:
    """Get upcoming events for morning briefing and dashboards.

    Role-based filtering:
      driver → delivery events only
      production → production + compliance events
      safety → compliance + training events
      admin/owner → all event types
    """
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = today_start + timedelta(days=days)

    q = db.query(VaultItem).filter(
        VaultItem.company_id == company_id,
        VaultItem.is_active == True,
        VaultItem.item_type == "event",
        VaultItem.status == "active",
        VaultItem.event_start >= today_start,
        VaultItem.event_start <= end,
    )

    # Role-based filtering
    ROLE_EVENT_TYPES = {
        "driver": ["delivery", "route", "driver_assignment"],
        "production": ["production_pour", "production_strip", "work_order", "compliance_expiry"],
        "safety": ["compliance_expiry", "safety_training", "maintenance"],
    }
    if role and role in ROLE_EVENT_TYPES:
        allowed = ROLE_EVENT_TYPES[role]
        q = q.filter(VaultItem.event_type.in_(allowed))

    return q.order_by(VaultItem.event_start.asc()).all()


def serialize_vault_item(item: VaultItem) -> dict:
    """Serialize a VaultItem to a dict for API response."""
    return {
        "id": item.id,
        "vault_id": item.vault_id,
        "company_id": item.company_id,
        "item_type": item.item_type,
        "title": item.title,
        "description": item.description,
        "r2_key": item.r2_key,
        "file_size_bytes": item.file_size_bytes,
        "mime_type": item.mime_type,
        "document_type": item.document_type,
        "event_start": item.event_start.isoformat() if item.event_start else None,
        "event_end": item.event_end.isoformat() if item.event_end else None,
        "event_location": item.event_location,
        "event_type": item.event_type,
        "event_type_sub": item.event_type_sub,
        "all_day": item.all_day,
        "recurrence_rule": item.recurrence_rule,
        "notify_recipients": item.notify_recipients,
        "notify_before_minutes": item.notify_before_minutes,
        "visibility": item.visibility,
        "shared_with_company_ids": item.shared_with_company_ids,
        "parent_item_id": item.parent_item_id,
        "related_entity_type": item.related_entity_type,
        "related_entity_id": item.related_entity_id,
        "status": item.status,
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        "source": item.source,
        "source_entity_id": item.source_entity_id,
        "created_by": item.created_by,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "is_active": item.is_active,
        "metadata": item.metadata_json,
    }
