"""Vault API routes — CRUD for vault items, calendar feed, cross-tenant."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services import vault_service

router = APIRouter()


# --- Pydantic schemas ---

class VaultItemCreate(BaseModel):
    item_type: str
    title: str
    description: Optional[str] = None
    r2_key: Optional[str] = None
    file_size_bytes: Optional[int] = None
    mime_type: Optional[str] = None
    document_type: Optional[str] = None
    event_start: Optional[datetime] = None
    event_end: Optional[datetime] = None
    event_location: Optional[str] = None
    event_type: Optional[str] = None
    event_type_sub: Optional[str] = None
    all_day: bool = False
    recurrence_rule: Optional[str] = None
    notify_recipients: Optional[list] = None
    notify_before_minutes: Optional[list] = None
    visibility: str = "internal"
    shared_with_company_ids: Optional[list] = None
    parent_item_id: Optional[str] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[str] = None
    status: str = "active"
    source: str = "user_upload"
    source_entity_id: Optional[str] = None
    metadata: Optional[dict] = Field(None, alias="metadata_json")


class VaultItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    event_start: Optional[datetime] = None
    event_end: Optional[datetime] = None
    event_location: Optional[str] = None
    event_type: Optional[str] = None
    event_type_sub: Optional[str] = None
    all_day: Optional[bool] = None
    visibility: Optional[str] = None
    shared_with_company_ids: Optional[list] = None
    status: Optional[str] = None
    metadata: Optional[dict] = Field(None, alias="metadata_json")


# --- Endpoints ---

@router.get("/items")
def list_vault_items(
    item_type: Optional[str] = None,
    event_type: Optional[str] = None,
    event_type_sub: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    status: Optional[str] = None,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[str] = None,
    source: Optional[str] = None,
    location_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Query vault items with flexible filtering."""
    items = vault_service.query_vault_items(
        db,
        current_user.company_id,
        item_type=item_type,
        event_type=event_type,
        event_type_sub=event_type_sub,
        date_from=date_from,
        date_to=date_to,
        status=status,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        source=source,
        location_id=location_id,
        limit=limit,
        offset=offset,
    )
    return [vault_service.serialize_vault_item(i) for i in items]


@router.get("/items/{item_id}")
def get_vault_item(
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single vault item by ID."""
    item = vault_service.get_vault_item(db, item_id, current_user.company_id)
    if not item:
        raise HTTPException(status_code=404, detail="Vault item not found")
    return vault_service.serialize_vault_item(item)


@router.post("/items", status_code=201)
def create_vault_item(
    data: VaultItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new vault item."""
    item = vault_service.create_vault_item(
        db,
        company_id=current_user.company_id,
        item_type=data.item_type,
        title=data.title,
        description=data.description,
        r2_key=data.r2_key,
        file_size_bytes=data.file_size_bytes,
        mime_type=data.mime_type,
        document_type=data.document_type,
        event_start=data.event_start,
        event_end=data.event_end,
        event_location=data.event_location,
        event_type=data.event_type,
        event_type_sub=data.event_type_sub,
        all_day=data.all_day,
        recurrence_rule=data.recurrence_rule,
        notify_recipients=data.notify_recipients,
        notify_before_minutes=data.notify_before_minutes,
        visibility=data.visibility,
        shared_with_company_ids=data.shared_with_company_ids,
        parent_item_id=data.parent_item_id,
        related_entity_type=data.related_entity_type,
        related_entity_id=data.related_entity_id,
        status=data.status,
        source=data.source,
        source_entity_id=data.source_entity_id,
        created_by=current_user.id,
        metadata_json=data.metadata,
    )
    db.commit()
    return vault_service.serialize_vault_item(item)


@router.patch("/items/{item_id}")
def update_vault_item(
    item_id: str,
    data: VaultItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a vault item."""
    update_data = data.model_dump(exclude_unset=True)
    # Rename metadata alias
    if "metadata" in update_data:
        update_data["metadata_json"] = update_data.pop("metadata")
    item = vault_service.update_vault_item(
        db, item_id, current_user.company_id, **update_data
    )
    if not item:
        raise HTTPException(status_code=404, detail="Vault item not found")
    db.commit()
    return vault_service.serialize_vault_item(item)


@router.get("/summary")
def get_vault_summary(
    location_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get vault summary counts for dashboard widgets."""
    return vault_service.get_vault_summary(
        db, current_user.company_id, location_id=location_id
    )


@router.get("/upcoming-events")
def get_upcoming_events(
    days: int = Query(7, ge=1, le=90),
    role: Optional[str] = None,
    location_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get upcoming events for morning briefing and dashboards."""
    items = vault_service.get_upcoming_events(
        db, current_user.company_id, days=days, role=role, location_id=location_id
    )
    return [vault_service.serialize_vault_item(i) for i in items]


@router.get("/items/cross-tenant/{company_id}")
def get_cross_tenant_items(
    company_id: str,
    item_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get vault items shared with the requesting company from a specific company."""
    items = vault_service.get_cross_tenant_items(
        db,
        current_user.company_id,
        company_id,
        item_type=item_type,
        limit=limit,
        offset=offset,
    )
    return [vault_service.serialize_vault_item(i) for i in items]


@router.get("/calendar.ics")
def get_calendar_feed(
    token: str = Query(...),
    role: Optional[str] = None,
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """iCal feed for calendar sync. Token-based auth (no JWT required)."""
    from app.models.user import User as UserModel

    # Validate calendar token
    user = (
        db.query(UserModel)
        .filter(UserModel.calendar_token == token, UserModel.is_active == True)
        .first()
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid calendar token")

    items = vault_service.get_upcoming_events(
        db, user.company_id, days=days, role=role
    )

    # Generate iCal
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Bridgeable//Vault Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:Bridgeable - {role or 'All'} Events",
    ]

    for item in items:
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{item.id}@bridgeable")
        lines.append(f"SUMMARY:{_ical_escape(item.title)}")
        if item.description:
            lines.append(f"DESCRIPTION:{_ical_escape(item.description)}")
        if item.event_location:
            lines.append(f"LOCATION:{_ical_escape(item.event_location)}")
        if item.event_start:
            if item.all_day:
                lines.append(f"DTSTART;VALUE=DATE:{item.event_start.strftime('%Y%m%d')}")
                if item.event_end:
                    lines.append(f"DTEND;VALUE=DATE:{item.event_end.strftime('%Y%m%d')}")
            else:
                lines.append(f"DTSTART:{item.event_start.strftime('%Y%m%dT%H%M%SZ')}")
                if item.event_end:
                    lines.append(f"DTEND:{item.event_end.strftime('%Y%m%dT%H%M%SZ')}")
        if item.event_type:
            lines.append(f"CATEGORIES:{item.event_type}")
        lines.append(f"STATUS:{'CONFIRMED' if item.status == 'active' else 'CANCELLED'}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")

    return PlainTextResponse(
        content="\r\n".join(lines),
        media_type="text/calendar",
        headers={"Content-Disposition": "attachment; filename=bridgeable-calendar.ics"},
    )


@router.post("/sync-compliance")
def sync_compliance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sync compliance expiry data into vault items. Admin only."""
    from app.services.vault_compliance_sync import sync_compliance_expiries

    stats = sync_compliance_expiries(db, current_user.company_id)
    return {"status": "ok", **stats}


@router.post("/generate-calendar-token")
def generate_calendar_token(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate or regenerate a calendar sync token for the current user."""
    import secrets

    token = secrets.token_urlsafe(32)
    current_user.calendar_token = token
    db.commit()
    return {"calendar_token": token}


def _ical_escape(text: str) -> str:
    """Escape text for iCal format."""
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")
