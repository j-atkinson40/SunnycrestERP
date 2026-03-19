"""Funeral Home Directory Service — Google Places integration with caching."""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import requests
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)

CACHE_DAYS = 90
MAX_RESULTS_PER_QUERY = 20


def get_directory_for_area(
    db: Session,
    tenant_id: str,
    latitude: float,
    longitude: float,
    radius_miles: int = 50,
) -> list[dict]:
    """Get funeral homes in an area. Uses cache if available, fetches from Google if not."""
    from app.models.funeral_home_directory import FuneralHomeDirectory
    from app.models.directory_fetch_log import DirectoryFetchLog
    from app.models.manufacturer_directory_selection import ManufacturerDirectorySelection

    # Check cache
    cache_cutoff = datetime.now(timezone.utc) - timedelta(days=CACHE_DAYS)
    recent_fetch = db.query(DirectoryFetchLog).filter(
        DirectoryFetchLog.fetch_type == "radius",
        DirectoryFetchLog.fetched_for_tenant_id == tenant_id,
        DirectoryFetchLog.fetched_at > cache_cutoff,
    ).first()

    if not recent_fetch:
        # Fetch from Google Places
        _fetch_from_google_places(db, tenant_id, latitude, longitude, radius_miles)

    # Load from directory, excluding already-actioned entries
    actioned_ids = [
        r[0] for r in db.query(ManufacturerDirectorySelection.directory_entry_id)
        .filter(ManufacturerDirectorySelection.tenant_id == tenant_id)
        .all()
    ]

    query = db.query(FuneralHomeDirectory).filter(
        FuneralHomeDirectory.is_active == True,  # noqa: E712
        FuneralHomeDirectory.linked_tenant_id == None,  # noqa: E711
    )
    if actioned_ids:
        query = query.filter(FuneralHomeDirectory.id.notin_(actioned_ids))

    # Simple distance filter using bounding box
    lat_range = radius_miles / 69.0  # ~69 miles per degree latitude
    lng_range = radius_miles / 54.6  # ~54.6 at 40deg latitude
    query = query.filter(
        FuneralHomeDirectory.latitude.between(
            Decimal(str(latitude - lat_range)),
            Decimal(str(latitude + lat_range)),
        ),
        FuneralHomeDirectory.longitude.between(
            Decimal(str(longitude - lng_range)),
            Decimal(str(longitude + lng_range)),
        ),
    )

    entries = query.order_by(FuneralHomeDirectory.city, FuneralHomeDirectory.name).all()

    return [_entry_to_dict(e) for e in entries]


def get_directory_for_tenant(
    db: Session,
    tenant_id: str,
    radius_miles: int = 50,
) -> list[dict]:
    """Get directory entries using the tenant's facility address for location."""
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == tenant_id).first()
    if not company:
        return []

    lat = float(company.facility_latitude) if company.facility_latitude else None
    lng = float(company.facility_longitude) if company.facility_longitude else None

    if not lat or not lng:
        # No geocoded location available
        return []

    return get_directory_for_area(db, tenant_id, lat, lng, radius_miles)


def get_platform_matches(db: Session, tenant_id: str) -> list[dict]:
    """Get funeral home tenants on the platform that might be this manufacturer's customers."""
    from app.models.company import Company

    # Find funeral home preset tenants
    fh_tenants = db.query(Company).filter(
        Company.vertical == "funeral_home",
        Company.is_active == True,  # noqa: E712
        Company.id != tenant_id,
    ).all()

    return [
        {"id": t.id, "name": t.name, "slug": t.slug}
        for t in fh_tenants
    ]


def record_selections(
    db: Session,
    tenant_id: str,
    selections: list[dict],
) -> dict:
    """Record manufacturer's selections from the directory."""
    from app.models.manufacturer_directory_selection import ManufacturerDirectorySelection
    from app.models.customer import Customer
    from app.models.funeral_home_directory import FuneralHomeDirectory

    created_customers = 0
    invitations_sent = 0
    skipped = 0

    for sel in selections:
        entry_id = sel["directory_entry_id"]
        action = sel.get("action", "skipped")
        invite = sel.get("invite", False)

        # Load directory entry for customer creation
        entry = db.query(FuneralHomeDirectory).filter(
            FuneralHomeDirectory.id == entry_id
        ).first()

        customer_id = None
        if action == "added_as_customer" and entry:
            # Create customer record
            customer = Customer(
                company_id=tenant_id,
                name=entry.name,
                phone=entry.phone,
                city=entry.city,
                state=entry.state_code,
                zip_code=entry.zip_code,
                address_line1=entry.address,
                website=entry.website,
                notes="Source: directory_discovery",
            )
            db.add(customer)
            db.flush()
            customer_id = customer.id
            created_customers += 1
        elif action == "skipped":
            skipped += 1

        # Record selection
        selection = ManufacturerDirectorySelection(
            tenant_id=tenant_id,
            directory_entry_id=entry_id,
            action=action,
            customer_id=customer_id,
            actioned_at=datetime.now(timezone.utc),
        )
        db.add(selection)

        if invite and action == "added_as_customer":
            invitations_sent += 1
            # TODO: create network_invitation record

    db.flush()
    return {
        "created_customers": created_customers,
        "invitations_sent": invitations_sent,
        "skipped": skipped,
    }


def add_manual_customers(
    db: Session,
    tenant_id: str,
    customers: list[dict],
) -> dict:
    """Add manually entered funeral home customers."""
    from app.models.customer import Customer

    created = 0
    for c in customers:
        if not c.get("name"):
            continue
        customer = Customer(
            company_id=tenant_id,
            name=c["name"],
            phone=c.get("phone"),
            city=c.get("city"),
            notes="Source: manual_onboarding",
        )
        db.add(customer)
        created += 1

    db.flush()
    return {"created_customers": created}


def _fetch_from_google_places(
    db: Session,
    tenant_id: str,
    latitude: float,
    longitude: float,
    radius_miles: int,
) -> list:
    """Fetch funeral homes from Google Places API."""
    from app.models.funeral_home_directory import FuneralHomeDirectory
    from app.models.directory_fetch_log import DirectoryFetchLog

    api_key = getattr(settings, "GOOGLE_PLACES_API_KEY", None)
    if not api_key:
        logger.warning("GOOGLE_PLACES_API_KEY not configured — returning empty results")
        # Log the fetch attempt anyway
        log = DirectoryFetchLog(
            fetch_type="radius",
            center_lat=Decimal(str(latitude)),
            center_lng=Decimal(str(longitude)),
            radius_miles=radius_miles,
            results_count=0,
            fetched_at=datetime.now(timezone.utc),
            fetched_for_tenant_id=tenant_id,
        )
        db.add(log)
        db.flush()
        return []

    # Google Places Text Search
    radius_meters = radius_miles * 1609
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": "funeral home",
        "location": f"{latitude},{longitude}",
        "radius": min(radius_meters, 50000),  # Max 50km for text search
        "key": api_key,
    }

    results = []
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for place in data.get("results", [])[:MAX_RESULTS_PER_QUERY]:
            place_id = place.get("place_id")
            if not place_id:
                continue

            # Parse address
            addr = place.get("formatted_address", "")
            parts = addr.split(",")
            city = parts[-3].strip() if len(parts) >= 3 else ""
            state_zip = parts[-2].strip() if len(parts) >= 2 else ""
            state_code = state_zip.split()[0] if state_zip else ""
            zip_code = state_zip.split()[1] if len(state_zip.split()) > 1 else ""

            geo = place.get("geometry", {}).get("location", {})

            # Upsert
            existing = db.query(FuneralHomeDirectory).filter(
                FuneralHomeDirectory.place_id == place_id
            ).first()

            now = datetime.now(timezone.utc)
            if existing:
                existing.name = place.get("name", existing.name)
                existing.address = addr
                existing.city = city
                existing.state_code = state_code
                existing.zip_code = zip_code
                existing.google_rating = place.get("rating")
                existing.google_review_count = place.get("user_ratings_total")
                existing.last_verified_at = now
                existing.is_active = True
                results.append(existing)
            else:
                entry = FuneralHomeDirectory(
                    place_id=place_id,
                    name=place.get("name", "Unknown"),
                    address=addr,
                    city=city,
                    state_code=state_code,
                    zip_code=zip_code,
                    phone=None,  # Need Places Details for phone
                    google_rating=place.get("rating"),
                    google_review_count=place.get("user_ratings_total"),
                    latitude=Decimal(str(geo.get("lat", 0))),
                    longitude=Decimal(str(geo.get("lng", 0))),
                    is_active=True,
                    first_fetched_at=now,
                    last_verified_at=now,
                )
                db.add(entry)
                results.append(entry)

        db.flush()

    except Exception as e:
        logger.exception("Google Places API error: %s", e)

    # Log fetch
    log = DirectoryFetchLog(
        fetch_type="radius",
        center_lat=Decimal(str(latitude)),
        center_lng=Decimal(str(longitude)),
        radius_miles=radius_miles,
        results_count=len(results),
        fetched_at=datetime.now(timezone.utc),
        fetched_for_tenant_id=tenant_id,
    )
    db.add(log)
    db.flush()

    return results


def _entry_to_dict(entry) -> dict:
    return {
        "id": entry.id,
        "place_id": entry.place_id,
        "name": entry.name,
        "address": entry.address,
        "city": entry.city,
        "state_code": entry.state_code,
        "zip_code": entry.zip_code,
        "phone": entry.phone,
        "website": entry.website,
        "google_rating": float(entry.google_rating) if entry.google_rating else None,
        "google_review_count": entry.google_review_count,
        "latitude": float(entry.latitude) if entry.latitude else None,
        "longitude": float(entry.longitude) if entry.longitude else None,
    }
