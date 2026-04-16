"""Location service — multi-location management for company tenants."""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.delivery import Delivery
from app.models.location import Location
from app.models.sales_order import SalesOrder
from app.models.user_location_access import UserLocationAccess
from app.models.vault_item import VaultItem


def get_company_locations(
    db: Session,
    company_id: str,
    include_inactive: bool = False,
) -> list[Location]:
    """Get all locations for a company, ordered by display_order."""
    q = db.query(Location).filter(Location.company_id == company_id)
    if not include_inactive:
        q = q.filter(Location.is_active == True)
    return q.order_by(Location.display_order.asc(), Location.name.asc()).all()


def get_user_accessible_location_ids(
    db: Session,
    user_id: str,
    company_id: str,
) -> Optional[list[str]]:
    """Get the list of location IDs a user can access.

    Returns None if the user has all-location access (location_id IS NULL row).
    Returns a list of specific location IDs otherwise.
    """
    access_rows = (
        db.query(UserLocationAccess)
        .filter(
            UserLocationAccess.user_id == user_id,
            UserLocationAccess.company_id == company_id,
            UserLocationAccess.is_active == True,
        )
        .all()
    )

    if not access_rows:
        # No access rows at all — treat as all-access for backward compat
        return None

    # If any row has location_id=NULL, user has all-location access
    for row in access_rows:
        if row.location_id is None:
            return None

    return [row.location_id for row in access_rows]


def get_location_filter(
    db: Session,
    user_id: str,
    company_id: str,
    requested_location_id: Optional[str] = None,
) -> Optional[str | list[str]]:
    """Core method for filtering queries by location.

    Returns:
      None — user has all-access and no specific location requested
      str  — a single location ID to filter by
      list[str] — multiple location IDs to filter by

    Raises HTTPException 403 if the user requests a location they cannot access.
    """
    accessible = get_user_accessible_location_ids(db, user_id, company_id)

    if requested_location_id:
        # User is requesting a specific location
        if accessible is not None and requested_location_id not in accessible:
            raise HTTPException(
                status_code=403,
                detail="You do not have access to this location",
            )
        return requested_location_id

    # No specific location requested
    if accessible is None:
        return None  # All-access
    return accessible


def create_location(
    db: Session,
    company_id: str,
    name: str,
    location_type: str = "plant",
    **kwargs,
) -> Location:
    """Create a new location for a company."""
    location = Location(
        id=str(uuid.uuid4()),
        company_id=company_id,
        name=name,
        location_type=location_type,
        **kwargs,
    )
    db.add(location)
    db.flush()
    return location


def update_location(
    db: Session,
    location_id: str,
    company_id: str,
    **kwargs,
) -> Optional[Location]:
    """Update a location. Only provided kwargs are updated."""
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.company_id == company_id)
        .first()
    )
    if not location:
        return None
    for key, value in kwargs.items():
        if hasattr(location, key):
            setattr(location, key, value)
    location.updated_at = datetime.now(timezone.utc)
    db.flush()
    return location


def deactivate_location(
    db: Session,
    location_id: str,
    company_id: str,
) -> bool:
    """Soft-deactivate a location. Cannot deactivate the primary location."""
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.company_id == company_id)
        .first()
    )
    if not location:
        return False
    if location.is_primary:
        raise HTTPException(
            status_code=400,
            detail="Cannot deactivate the primary location",
        )
    location.is_active = False
    location.updated_at = datetime.now(timezone.utc)
    db.flush()
    return True


def is_multi_location(db: Session, company_id: str) -> bool:
    """Check if a company has more than one active location."""
    count = (
        db.query(func.count(Location.id))
        .filter(Location.company_id == company_id, Location.is_active == True)
        .scalar()
    )
    return (count or 0) > 1


def grant_user_access(
    db: Session,
    user_id: str,
    company_id: str,
    location_id: Optional[str],
    access_level: str = "operator",
) -> UserLocationAccess:
    """Grant a user access to a location (or all locations if location_id is None)."""
    # Check for existing active access with same parameters
    existing = (
        db.query(UserLocationAccess)
        .filter(
            UserLocationAccess.user_id == user_id,
            UserLocationAccess.company_id == company_id,
            UserLocationAccess.location_id == location_id if location_id else UserLocationAccess.location_id.is_(None),
            UserLocationAccess.is_active == True,
        )
        .first()
    )
    if existing:
        existing.access_level = access_level
        db.flush()
        return existing

    access = UserLocationAccess(
        id=str(uuid.uuid4()),
        user_id=user_id,
        company_id=company_id,
        location_id=location_id,
        access_level=access_level,
    )
    db.add(access)
    db.flush()
    return access


def revoke_user_access(
    db: Session,
    user_id: str,
    company_id: str,
    location_id: Optional[str],
) -> bool:
    """Revoke a user's access to a specific location."""
    q = db.query(UserLocationAccess).filter(
        UserLocationAccess.user_id == user_id,
        UserLocationAccess.company_id == company_id,
        UserLocationAccess.is_active == True,
    )
    if location_id:
        q = q.filter(UserLocationAccess.location_id == location_id)
    else:
        q = q.filter(UserLocationAccess.location_id.is_(None))

    access = q.first()
    if not access:
        return False
    access.is_active = False
    db.flush()
    return True


def get_user_location_assignments(
    db: Session,
    company_id: str,
) -> list[UserLocationAccess]:
    """Get all user-location access assignments for a company."""
    return (
        db.query(UserLocationAccess)
        .filter(
            UserLocationAccess.company_id == company_id,
            UserLocationAccess.is_active == True,
        )
        .all()
    )


def get_location_summary(
    db: Session,
    company_id: str,
    location_id: str,
) -> dict:
    """Get operational summary stats for a single location."""
    now = datetime.now(timezone.utc)
    today = now.date()
    today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
    today_end = today_start + timedelta(days=1)
    week_end = today_start + timedelta(days=7)

    # Active orders at this location
    active_orders = (
        db.query(func.count(SalesOrder.id))
        .filter(
            SalesOrder.company_id == company_id,
            SalesOrder.location_id == location_id,
            SalesOrder.status.in_(["confirmed", "processing"]),
        )
        .scalar()
        or 0
    )

    # Pending deliveries from this location
    pending_deliveries = (
        db.query(func.count(Delivery.id))
        .filter(
            Delivery.company_id == company_id,
            Delivery.origin_location_id == location_id,
            Delivery.status.in_(["pending", "scheduled"]),
        )
        .scalar()
        or 0
    )

    # Deliveries today
    deliveries_today = (
        db.query(func.count(Delivery.id))
        .filter(
            Delivery.company_id == company_id,
            Delivery.origin_location_id == location_id,
            Delivery.requested_date == today,
        )
        .scalar()
        or 0
    )

    # Overdue compliance items (vault_items with event_type compliance_expiry, past due)
    overdue_compliance = (
        db.query(func.count(VaultItem.id))
        .filter(
            VaultItem.company_id == company_id,
            VaultItem.location_id == location_id,
            VaultItem.event_type == "compliance_expiry",
            VaultItem.status == "active",
            VaultItem.is_active == True,
            VaultItem.event_start < today_start,
        )
        .scalar()
        or 0
    )

    # Compliance due this week
    compliance_due_this_week = (
        db.query(func.count(VaultItem.id))
        .filter(
            VaultItem.company_id == company_id,
            VaultItem.location_id == location_id,
            VaultItem.event_type == "compliance_expiry",
            VaultItem.status == "active",
            VaultItem.is_active == True,
            VaultItem.event_start >= today_start,
            VaultItem.event_start < week_end,
        )
        .scalar()
        or 0
    )

    # Production scheduled today (vault items with production events today)
    production_scheduled_today = (
        db.query(func.count(VaultItem.id))
        .filter(
            VaultItem.company_id == company_id,
            VaultItem.location_id == location_id,
            VaultItem.item_type == "event",
            VaultItem.event_type.in_(["production_pour", "production_strip", "work_order"]),
            VaultItem.status == "active",
            VaultItem.is_active == True,
            VaultItem.event_start >= today_start,
            VaultItem.event_start < today_end,
        )
        .scalar()
        or 0
    )

    return {
        "location_id": location_id,
        "active_orders": active_orders,
        "pending_deliveries": pending_deliveries,
        "deliveries_today": deliveries_today,
        "overdue_compliance": overdue_compliance,
        "compliance_due_this_week": compliance_due_this_week,
        "production_scheduled_today": production_scheduled_today,
    }


def get_locations_overview(
    db: Session,
    company_id: str,
    user_id: str,
) -> dict:
    """Get overview of all locations with summaries, filtered by user access."""
    accessible = get_user_accessible_location_ids(db, user_id, company_id)

    locations = get_company_locations(db, company_id)
    if accessible is not None:
        locations = [loc for loc in locations if loc.id in accessible]

    summaries = []
    totals = {
        "active_orders": 0,
        "pending_deliveries": 0,
        "deliveries_today": 0,
        "overdue_compliance": 0,
        "compliance_due_this_week": 0,
        "production_scheduled_today": 0,
    }

    for loc in locations:
        summary = get_location_summary(db, company_id, loc.id)
        # Determine location status
        if summary["overdue_compliance"] > 0:
            loc_status = "attention_needed"
        elif summary["active_orders"] > 0 or summary["deliveries_today"] > 0:
            loc_status = "on_track"
        else:
            loc_status = "no_activity"

        summaries.append({
            "location": _serialize_location(loc),
            "summary": summary,
            "status": loc_status,
        })

        for key in totals:
            totals[key] += summary[key]

    return {
        "total_locations": len(locations),
        "locations": summaries,
        "totals": totals,
    }


def ensure_primary_location(db: Session, company_id: str) -> Location:
    """Ensure a primary location exists for a company. Creates one if missing."""
    primary = (
        db.query(Location)
        .filter(
            Location.company_id == company_id,
            Location.is_primary == True,
            Location.is_active == True,
        )
        .first()
    )
    if primary:
        return primary

    # Get company name for the location
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == company_id).first()
    name = company.name if company else "Main Location"

    location = Location(
        id=str(uuid.uuid4()),
        company_id=company_id,
        name=name,
        location_type="primary",
        is_primary=True,
        is_active=True,
        display_order=0,
    )
    db.add(location)
    db.flush()
    return location


def _serialize_location(loc: Location) -> dict:
    """Serialize a Location to a dict for API responses."""
    return {
        "id": loc.id,
        "company_id": loc.company_id,
        "name": loc.name,
        "location_type": loc.location_type,
        "wilbert_territory_id": loc.wilbert_territory_id,
        "address_line1": loc.address_line1,
        "address_line2": loc.address_line2,
        "city": loc.city,
        "state": loc.state,
        "zip_code": loc.zip_code,
        "phone": loc.phone,
        "email": loc.email,
        "is_primary": loc.is_primary,
        "is_active": loc.is_active,
        "display_order": loc.display_order,
        "metadata": loc.metadata_json,
        "created_at": loc.created_at.isoformat() if loc.created_at else None,
        "updated_at": loc.updated_at.isoformat() if loc.updated_at else None,
    }
