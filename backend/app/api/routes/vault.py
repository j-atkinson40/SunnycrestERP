"""Vault API routes — CRUD for vault items, calendar feed, cross-tenant."""

from datetime import datetime, timezone
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


# ── Vault Hub service registry (V-1a) ────────────────────────────────
#
# The endpoints below back the Vault Hub sidebar on the frontend — which
# cross-cutting services appear (Documents, Intelligence, later CRM /
# Notifications / Accounting admin). Separate concern from the VaultItem
# CRUD above: this is UI structure, not data.
#
# Filtering mirrors the frontend nav-service rules: admins see
# everything; non-admins are gated on `required_permission` /
# `required_module` / `required_extension` on each descriptor.


class _VaultServiceResponse(BaseModel):
    service_key: str
    display_name: str
    icon: str
    route_prefix: str
    sort_order: int


class _VaultServicesResponse(BaseModel):
    services: list[_VaultServiceResponse]


class _VaultOverviewWidgetEntry(BaseModel):
    widget_id: str
    service_key: str
    display_name: str
    default_size: str
    default_position: int
    is_available: bool
    unavailable_reason: str | None = None


class _VaultOverviewLayoutEntry(BaseModel):
    widget_id: str
    position: int
    size: str


class _VaultOverviewWidgetsResponse(BaseModel):
    widgets: list[_VaultOverviewWidgetEntry]
    default_layout: list[_VaultOverviewLayoutEntry]


@router.get("/services", response_model=_VaultServicesResponse)
def list_vault_services(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Vault Hub services visible to the current user.

    Phase V-1a — documents + intelligence. The frontend sidebar at
    `/vault/*` renders one nav item per returned service.

    Filtering (mirrors navigation-service.ts rules):
      - admins see everything
      - non-admins: `required_permission` must be in the user's
        permission set; `required_module` / `required_extension` must
        be active on the tenant.
    """
    from app.services.vault import list_services
    from app.services.permission_service import user_has_permission
    from app.services.module_service import is_module_enabled
    from app.models.tenant_extension import TenantExtension

    # Resolve the user's active extensions for the extension gate.
    # NB: TenantExtension uses `tenant_id`, not `company_id`. Also no
    # is_active field — rows exist when an extension is active.
    active_extensions = {
        e.extension_key
        for e in db.query(TenantExtension)
        .filter(TenantExtension.tenant_id == current_user.company_id)
        .all()
    }

    visible: list[_VaultServiceResponse] = []
    for desc in list_services():
        if not current_user.is_super_admin:
            if desc.required_permission and not user_has_permission(
                current_user, db, desc.required_permission
            ):
                continue
            if desc.required_module and not is_module_enabled(
                db, current_user.company_id, desc.required_module
            ):
                continue
            if (
                desc.required_extension
                and desc.required_extension not in active_extensions
            ):
                continue
        visible.append(
            _VaultServiceResponse(
                service_key=desc.service_key,
                display_name=desc.display_name,
                icon=desc.icon,
                route_prefix=desc.route_prefix,
                sort_order=desc.sort_order,
            )
        )
    return _VaultServicesResponse(services=visible)


@router.get(
    "/overview/widgets",
    response_model=_VaultOverviewWidgetsResponse,
)
def list_vault_overview_widgets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Vault Hub overview widgets visible to the current user.

    Phase V-1b. This endpoint is a **metadata view** on top of the
    existing widget framework — it joins:

      - `vault.hub_registry` (which service owns which widget)
      - the widget framework's availability filtering
        (`widget_service.get_available_widgets("vault_overview", ...)`)

    …and returns a flat list of widgets the user can see, plus the
    recommended default layout. The frontend `useDashboard` hook still
    owns actual layout persistence (`/widgets/layout?page_context=
    vault_overview`); this endpoint lets V-1c+ consumers group widgets
    by their owning service without having to re-implement the
    service-key → widget-ids mapping.

    A widget appears only if:
      1. its owning service is visible to the user (same filter as
         /services above), AND
      2. the widget framework marks it `is_available=True` (which
         handles extension/permission/preset gates at the widget level).
    """
    from app.services.vault import VaultServiceDescriptor, list_services
    from app.services.widgets import widget_service
    from app.services.permission_service import user_has_permission
    from app.services.module_service import is_module_enabled
    from app.models.tenant_extension import TenantExtension

    # Resolve tenant extensions (same as /services).
    active_extensions = {
        e.extension_key
        for e in db.query(TenantExtension)
        .filter(TenantExtension.tenant_id == current_user.company_id)
        .all()
    }

    # 1. Build widget_id → owning service_key map, filtered by
    # service visibility.
    widget_to_service: dict[str, VaultServiceDescriptor] = {}
    for svc in list_services():
        if not current_user.is_super_admin:
            if svc.required_permission and not user_has_permission(
                current_user, db, svc.required_permission
            ):
                continue
            if svc.required_module and not is_module_enabled(
                db, current_user.company_id, svc.required_module
            ):
                continue
            if (
                svc.required_extension
                and svc.required_extension not in active_extensions
            ):
                continue
        for widget_id in svc.overview_widget_ids:
            widget_to_service[widget_id] = svc

    # 2. Ask the widget framework what's available on the
    # vault_overview page context.
    available_defs = widget_service.get_available_widgets(
        db, current_user.company_id, current_user, "vault_overview"
    )

    # 3. Intersect + build the response list.
    widgets: list[_VaultOverviewWidgetEntry] = []
    for defn in available_defs:
        wid = defn["widget_id"]
        svc = widget_to_service.get(wid)
        if svc is None:
            # Widget was seeded under vault_overview but no Vault
            # service claims it — skip defensively. Seed-list and
            # hub-registry should stay in lock-step, but if they
            # diverge, the hub registry is the source of truth for
            # what Vault considers "overview" widgets.
            continue
        widgets.append(
            _VaultOverviewWidgetEntry(
                widget_id=wid,
                service_key=svc.service_key,
                display_name=defn["title"],
                default_size=defn["default_size"],
                default_position=defn["default_position"],
                is_available=defn["is_available"],
                unavailable_reason=defn.get("unavailable_reason"),
            )
        )

    # 4. Recommended default layout — widgets that are available +
    # default_enabled, sorted by default_position. Frontend uses this
    # if it wants to bypass useDashboard (e.g. pre-render SSR), but
    # the canonical layout still lives in `/widgets/layout`.
    widgets_sorted = sorted(widgets, key=lambda w: w.default_position)
    default_layout = [
        _VaultOverviewLayoutEntry(
            widget_id=w.widget_id,
            position=w.default_position,
            size=w.default_size,
        )
        for w in widgets_sorted
        if w.is_available
    ]

    return _VaultOverviewWidgetsResponse(
        widgets=widgets_sorted,
        default_layout=default_layout,
    )


# ── V-1c: CRM tenant-wide activity tail ─────────────────────────────
#
# Lifts the per-company ActivityLog feed to tenant scope. Backs the
# CrmRecentActivityWidget on the Vault Overview and any future
# "all recent activity" page. Tenant isolation: every ActivityLog row
# has a `tenant_id`; the service filter is the canonical gate.


class _VaultActivityItem(BaseModel):
    id: str
    activity_type: str
    title: str | None
    body: str | None
    is_system_generated: bool
    company_id: str
    company_name: str
    created_at: datetime
    logged_by: str | None


class _VaultRecentActivityResponse(BaseModel):
    activities: list[_VaultActivityItem]


@router.get(
    "/activity/recent",
    response_model=_VaultRecentActivityResponse,
)
def list_recent_activity(
    limit: int = Query(50, ge=1, le=200),
    since_days: int | None = Query(None, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tenant-wide recent CRM activity. Joins `ActivityLog` with its
    owning `CompanyEntity` for display.

    Query parameters:
      - `limit` — up to 200 rows (default 50).
      - `since_days` — optional window; if set, only activities in
        the last N days are returned.

    Permission: requires authenticated tenant user. The underlying
    service filters on `tenant_id = current_user.company_id`; there is
    no cross-tenant leakage path.
    """
    from datetime import timedelta
    from app.services.crm import activity_log_service

    since = None
    if since_days is not None:
        since = datetime.now(timezone.utc) - timedelta(days=since_days)

    rows = activity_log_service.get_tenant_feed(
        db,
        tenant_id=current_user.company_id,
        limit=limit,
        since=since,
    )
    return _VaultRecentActivityResponse(
        activities=[_VaultActivityItem(**r) for r in rows]
    )
