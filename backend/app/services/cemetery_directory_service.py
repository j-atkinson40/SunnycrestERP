"""Cemetery Directory Service — Google Places integration with 90-day caching.

Mirrors funeral_home_directory_service.py but targets cemeteries.
"""

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
    company_id: str,
    latitude: float,
    longitude: float,
    radius_miles: int = 50,
) -> list[dict]:
    """Get cemeteries in an area. Uses 90-day cache; fetches from Google Places if stale."""
    from app.models.cemetery_directory import CemeteryDirectory
    from app.models.cemetery_directory_fetch_log import CemeteryDirectoryFetchLog
    from app.models.cemetery_directory_selection import CemeteryDirectorySelection

    # Check cache — if no recent fetch for this company, hit Google Places
    cache_cutoff = datetime.now(timezone.utc) - timedelta(days=CACHE_DAYS)
    recent_fetch = (
        db.query(CemeteryDirectoryFetchLog)
        .filter(
            CemeteryDirectoryFetchLog.company_id == company_id,
            CemeteryDirectoryFetchLog.fetched_at > cache_cutoff,
        )
        .first()
    )

    if not recent_fetch:
        _fetch_from_google_places(db, company_id, latitude, longitude, radius_miles)

    # Collect already-actioned place_ids so we can flag them
    actioned_place_ids = {
        r[0]
        for r in db.query(CemeteryDirectorySelection.place_id)
        .filter(CemeteryDirectorySelection.company_id == company_id)
        .all()
    }

    # Bounding box filter
    lat_range = radius_miles / 69.0
    lng_range = radius_miles / 54.6
    entries = (
        db.query(CemeteryDirectory)
        .filter(
            CemeteryDirectory.company_id == company_id,
            CemeteryDirectory.is_active == True,  # noqa: E712
            CemeteryDirectory.latitude.between(
                Decimal(str(latitude - lat_range)),
                Decimal(str(latitude + lat_range)),
            ),
            CemeteryDirectory.longitude.between(
                Decimal(str(longitude - lng_range)),
                Decimal(str(longitude + lng_range)),
            ),
        )
        .order_by(CemeteryDirectory.city, CemeteryDirectory.name)
        .all()
    )

    return [_entry_to_dict(e, already_added=(e.place_id in actioned_place_ids)) for e in entries]


def get_directory_for_company(
    db: Session,
    company_id: str,
    radius_miles: int = 50,
) -> list[dict]:
    """Get directory entries using the company's geocoded facility address."""
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return []

    lat = float(company.facility_latitude) if company.facility_latitude else None
    lng = float(company.facility_longitude) if company.facility_longitude else None

    if not lat or not lng:
        if company.facility_address_line1 and company.facility_city:
            try:
                from app.services.geocoding_service import geocode_tenant_address
                if geocode_tenant_address(company_id):
                    db.refresh(company)
                    lat = float(company.facility_latitude) if company.facility_latitude else None
                    lng = float(company.facility_longitude) if company.facility_longitude else None
            except Exception:
                pass

    if not lat or not lng:
        logger.warning("No geocoded location for company %s — cannot search for cemeteries", company_id)
        return []

    return get_directory_for_area(db, company_id, lat, lng, radius_miles)


def create_cemeteries_from_selections(
    db: Session,
    company_id: str,
    selections: list[dict],
    manual_entries: list[dict],
) -> dict:
    """Create Cemetery records from directory selections and manual entries.

    Equipment settings are set at creation time. Nothing is auto-imported —
    the user has already confirmed each selection before calling this.
    """
    from app.models.cemetery import Cemetery
    from app.models.cemetery_directory_selection import CemeteryDirectorySelection

    created = 0
    skipped = 0
    errors = 0

    for sel in selections:
        action = sel.get("action", "skip")
        place_id = sel.get("place_id", "")
        name = sel.get("name", "")

        if not place_id or not name:
            errors += 1
            continue

        # Guard against duplicates — skip if already processed
        existing_sel = (
            db.query(CemeteryDirectorySelection)
            .filter(
                CemeteryDirectorySelection.company_id == company_id,
                CemeteryDirectorySelection.place_id == place_id,
            )
            .first()
        )
        if existing_sel:
            skipped += 1
            continue

        cemetery_id = None
        if action == "add":
            # Pull location data from the cached directory entry
            from app.models.cemetery_directory import CemeteryDirectory
            entry = (
                db.query(CemeteryDirectory)
                .filter(
                    CemeteryDirectory.company_id == company_id,
                    CemeteryDirectory.place_id == place_id,
                )
                .first()
            )

            equip = sel.get("equipment") or {}
            try:
                cemetery = Cemetery(
                    company_id=company_id,
                    name=name,
                    address=entry.address if entry else None,
                    city=entry.city if entry else None,
                    state=entry.state_code if entry else None,
                    zip_code=entry.zip_code if entry else None,
                    county=sel.get("county") or (entry.county if entry else None),
                    cemetery_provides_lowering_device=bool(equip.get("provides_lowering_device", False)),
                    cemetery_provides_grass=bool(equip.get("provides_grass", False)),
                    cemetery_provides_tent=bool(equip.get("provides_tent", False)),
                    cemetery_provides_chairs=bool(equip.get("provides_chairs", False)),
                    equipment_note=sel.get("equipment_note"),
                )
                db.add(cemetery)
                db.flush()
                cemetery_id = cemetery.id
                created += 1
            except Exception as exc:
                logger.exception("Failed to create cemetery for place_id %s: %s", place_id, exc)
                errors += 1
                continue

        # Record the selection regardless of action
        db.add(
            CemeteryDirectorySelection(
                company_id=company_id,
                place_id=place_id,
                name=name,
                action=action,
                cemetery_id=cemetery_id,
            )
        )
        if action == "skip":
            skipped += 1

    # Manual entries — no place_id, no duplicate guard
    for entry in manual_entries:
        name = entry.get("name", "").strip()
        if not name:
            continue
        equip = entry.get("equipment") or {}
        try:
            cemetery = Cemetery(
                company_id=company_id,
                name=name,
                city=entry.get("city"),
                state=entry.get("state"),
                county=entry.get("county"),
                cemetery_provides_lowering_device=bool(equip.get("provides_lowering_device", False)),
                cemetery_provides_grass=bool(equip.get("provides_grass", False)),
                cemetery_provides_tent=bool(equip.get("provides_tent", False)),
                cemetery_provides_chairs=bool(equip.get("provides_chairs", False)),
                equipment_note=entry.get("equipment_note"),
            )
            db.add(cemetery)
            created += 1
        except Exception as exc:
            logger.exception("Failed to create manual cemetery %s: %s", name, exc)
            errors += 1

    db.flush()
    return {"created": created, "skipped": skipped, "errors": errors}


def get_platform_cemetery_matches(
    db: Session,
    company_id: str,
    radius_miles: int = 100,
) -> list[dict]:
    """Get cemetery tenants on the platform that are geographically near this manufacturer.

    Excludes cemeteries the manufacturer has already connected to.
    Returns a list of dicts: {id, name, city, state, connected}.
    """
    from app.models.company import Company
    from app.models.platform_tenant_relationship import PlatformTenantRelationship

    # Get manufacturer's lat/lng
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return []

    lat = float(company.facility_latitude) if company.facility_latitude else None
    lng = float(company.facility_longitude) if company.facility_longitude else None
    if not lat or not lng:
        return []

    lat_range = radius_miles / 69.0
    lng_range = radius_miles / 54.6

    # IDs already connected as cemetery_network
    connected_ids = {
        r[0]
        for r in db.query(PlatformTenantRelationship.supplier_tenant_id)
        .filter(
            PlatformTenantRelationship.tenant_id == company_id,
            PlatformTenantRelationship.relationship_type == "cemetery_network",
            PlatformTenantRelationship.status == "active",
        )
        .all()
    }

    # Cemetery tenants within bounding box
    from decimal import Decimal

    cemetery_tenants = (
        db.query(Company)
        .filter(
            Company.vertical == "cemetery",
            Company.is_active.is_(True),
            Company.id != company_id,
            Company.facility_latitude.between(
                Decimal(str(lat - lat_range)),
                Decimal(str(lat + lat_range)),
            ),
            Company.facility_longitude.between(
                Decimal(str(lng - lng_range)),
                Decimal(str(lng + lng_range)),
            ),
        )
        .order_by(Company.name)
        .all()
    )

    return [
        {
            "id": t.id,
            "name": t.name,
            "city": getattr(t, "facility_city", None) or getattr(t, "address_city", None),
            "state": getattr(t, "facility_state", None) or getattr(t, "address_state", None),
            "connected": t.id in connected_ids,
        }
        for t in cemetery_tenants
    ]


def connect_platform_cemetery(
    db: Session,
    company_id: str,
    cemetery_tenant_id: str,
    connected_by: str | None = None,
) -> dict:
    """Create a PlatformTenantRelationship + Cemetery record for a platform cemetery tenant.

    Idempotent — safe to call again if already connected.
    Returns {connected: bool, cemetery_id: str | None}.
    """
    from datetime import datetime, timezone

    from app.models.cemetery import Cemetery
    from app.models.cemetery_directory_selection import CemeteryDirectorySelection
    from app.models.company import Company
    from app.models.platform_tenant_relationship import PlatformTenantRelationship

    # Look up cemetery tenant
    cemetery_company = db.query(Company).filter(Company.id == cemetery_tenant_id).first()
    if not cemetery_company:
        return {"connected": False, "cemetery_id": None}

    place_id = f"platform:{cemetery_tenant_id}"

    # Idempotent — skip if already connected
    existing_rel = (
        db.query(PlatformTenantRelationship)
        .filter(
            PlatformTenantRelationship.tenant_id == company_id,
            PlatformTenantRelationship.supplier_tenant_id == cemetery_tenant_id,
            PlatformTenantRelationship.relationship_type == "cemetery_network",
        )
        .first()
    )
    if existing_rel:
        # Find existing cemetery record if any
        existing_sel = (
            db.query(CemeteryDirectorySelection)
            .filter(
                CemeteryDirectorySelection.company_id == company_id,
                CemeteryDirectorySelection.place_id == place_id,
            )
            .first()
        )
        return {"connected": True, "cemetery_id": existing_sel.cemetery_id if existing_sel else None}

    # Create the relationship
    rel = PlatformTenantRelationship(
        tenant_id=company_id,
        supplier_tenant_id=cemetery_tenant_id,
        relationship_type="cemetery_network",
        status="active",
        connected_by=connected_by,
        connected_at=datetime.now(timezone.utc),
    )
    db.add(rel)

    # Create Cemetery record from platform tenant data
    city = getattr(cemetery_company, "facility_city", None) or getattr(cemetery_company, "address_city", None)
    state = getattr(cemetery_company, "facility_state", None) or getattr(cemetery_company, "address_state", None)

    cemetery = Cemetery(
        company_id=company_id,
        name=cemetery_company.name,
        city=city,
        state=state,
    )
    db.add(cemetery)
    db.flush()

    # Audit record
    db.add(
        CemeteryDirectorySelection(
            company_id=company_id,
            place_id=place_id,
            name=cemetery_company.name,
            action="connected",
            cemetery_id=cemetery.id,
        )
    )
    db.flush()

    return {"connected": True, "cemetery_id": cemetery.id}


def clear_cache(db: Session, company_id: str) -> None:
    """Delete fetch log records for this company to force a fresh Google Places pull."""
    from app.models.cemetery_directory_fetch_log import CemeteryDirectoryFetchLog

    db.query(CemeteryDirectoryFetchLog).filter(
        CemeteryDirectoryFetchLog.company_id == company_id
    ).delete()
    db.flush()


def _fetch_from_google_places(
    db: Session,
    company_id: str,
    latitude: float,
    longitude: float,
    radius_miles: int,
) -> list:
    """Fetch cemeteries from Google Places Text Search API and upsert into cemetery_directory."""
    from app.models.cemetery_directory import CemeteryDirectory
    from app.models.cemetery_directory_fetch_log import CemeteryDirectoryFetchLog

    api_key = getattr(settings, "GOOGLE_PLACES_API_KEY", None)
    if not api_key:
        logger.warning("GOOGLE_PLACES_API_KEY not configured — returning empty cemetery results")
        db.add(
            CemeteryDirectoryFetchLog(
                company_id=company_id,
                center_lat=Decimal(str(latitude)),
                center_lng=Decimal(str(longitude)),
                search_radius_miles=radius_miles,
                result_count=0,
            )
        )
        db.flush()
        return []

    radius_meters = min(radius_miles * 1609, 50000)  # Google Text Search max: 50 km
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": "cemetery",
        "location": f"{latitude},{longitude}",
        "radius": radius_meters,
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

            # Parse address components
            addr = place.get("formatted_address", "")
            parts = addr.split(",")
            city = parts[-3].strip() if len(parts) >= 3 else ""
            state_zip = parts[-2].strip() if len(parts) >= 2 else ""
            state_code = state_zip.split()[0] if state_zip else ""
            zip_code = state_zip.split()[1] if len(state_zip.split()) > 1 else ""

            geo = place.get("geometry", {}).get("location", {})
            now = datetime.now(timezone.utc)

            # Upsert by (company_id, place_id)
            existing = (
                db.query(CemeteryDirectory)
                .filter(
                    CemeteryDirectory.company_id == company_id,
                    CemeteryDirectory.place_id == place_id,
                )
                .first()
            )

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
                entry = CemeteryDirectory(
                    company_id=company_id,
                    place_id=place_id,
                    name=place.get("name", "Unknown Cemetery"),
                    address=addr,
                    city=city,
                    state_code=state_code,
                    zip_code=zip_code,
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

    except Exception as exc:
        logger.exception("Google Places API error fetching cemeteries: %s", exc)

    # Log the fetch for cache tracking
    db.add(
        CemeteryDirectoryFetchLog(
            company_id=company_id,
            center_lat=Decimal(str(latitude)),
            center_lng=Decimal(str(longitude)),
            search_radius_miles=radius_miles,
            result_count=len(results),
        )
    )
    db.flush()

    return results


def _entry_to_dict(entry, already_added: bool = False) -> dict:
    return {
        "id": entry.id,
        "place_id": entry.place_id,
        "name": entry.name,
        "address": entry.address,
        "city": entry.city,
        "state_code": entry.state_code,
        "zip_code": entry.zip_code,
        "county": entry.county,
        "google_rating": float(entry.google_rating) if entry.google_rating else None,
        "google_review_count": entry.google_review_count,
        "latitude": float(entry.latitude) if entry.latitude else None,
        "longitude": float(entry.longitude) if entry.longitude else None,
        "already_added": already_added,
    }
