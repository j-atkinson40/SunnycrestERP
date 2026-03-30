"""Cemetery Directory Service — OpenStreetMap/Overpass API with Google Places fallback.

Primary source: OpenStreetMap via Overpass API (free, comprehensive).
Fallback: Google Places Text Search API.
90-day cache — respects Overpass API usage policy.
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
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_FALLBACK_URL = "https://overpass.kumi.systems/api/interpreter"
OVERPASS_USER_AGENT = "Bridgeable/1.0 (cemetery-discovery; contact: support@getbridgeable.com)"

# Keywords that indicate a non-cemetery business (case-insensitive)
_EXCLUSION_KEYWORDS = [
    "funeral home",
    "funeral service",
    "cremation",
    "mortuary",
    "mausoleum sales",
    "headstone",
    "gravestone",
    "monument",
]


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance in miles between two lat/lng points."""
    import math
    R = 3959
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _county_from_coords(lat: float, lng: float) -> tuple[str | None, str | None]:
    """Find county and state from coordinates using nearest ZIP centroid in static dataset.
    Returns (county, state) or (None, None) if no match within 50 miles.
    """
    try:
        from app.services.county_geographic_service import _load_zip_mapping
        zip_data = _load_zip_mapping()
        if not zip_data:
            return None, None

        best_dist = float("inf")
        best_county: str | None = None
        best_state: str | None = None

        for _zip, info in zip_data.items():
            z_lat = info.get("lat")
            z_lng = info.get("lng")
            if z_lat is None or z_lng is None:
                continue
            dist = _haversine(lat, lng, float(z_lat), float(z_lng))
            if dist < best_dist:
                best_dist = dist
                best_county = info.get("county")
                best_state = info.get("state")

        return (best_county, best_state) if best_dist <= 50 else (None, None)
    except Exception:
        return None, None


def _is_valid_cemetery_name(name: str) -> bool:
    """Return False if name indicates a non-cemetery business."""
    lower = name.lower()
    for kw in _EXCLUSION_KEYWORDS:
        if kw in lower:
            return False
    # Skip 'memorial garden' unless it also contains 'cemetery'
    if "memorial garden" in lower and "cemetery" not in lower:
        return False
    # Skip blank or very short names
    if len(name.strip()) < 3:
        return False
    return True


def get_directory_for_area(
    db: Session,
    company_id: str,
    latitude: float,
    longitude: float,
    radius_miles: int = 50,
) -> list[dict]:
    """Get cemeteries in an area. Uses 90-day cache; fetches from Overpass if stale."""
    from app.models.cemetery_directory import CemeteryDirectory
    from app.models.cemetery_directory_fetch_log import CemeteryDirectoryFetchLog
    from app.models.cemetery_directory_selection import CemeteryDirectorySelection

    # Check cache — if no recent fetch for this company, hit Overpass
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
        _fetch_from_overpass(db, company_id, latitude, longitude, radius_miles)

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

    return [
        _entry_to_dict(e, already_added=(e.place_id in actioned_place_ids), company_lat=latitude, company_lng=longitude)
        for e in entries
    ]


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
    """Delete fetch log records for this company to force a fresh Overpass pull."""
    from app.models.cemetery_directory_fetch_log import CemeteryDirectoryFetchLog

    db.query(CemeteryDirectoryFetchLog).filter(
        CemeteryDirectoryFetchLog.company_id == company_id
    ).delete()
    db.flush()


def _fetch_from_overpass(
    db: Session,
    company_id: str,
    latitude: float,
    longitude: float,
    radius_miles: int,
) -> list:
    """Fetch cemeteries from OpenStreetMap via Overpass API. Falls back to Google Places on error."""
    from app.models.cemetery_directory import CemeteryDirectory
    from app.models.cemetery_directory_fetch_log import CemeteryDirectoryFetchLog

    radius_meters = int(radius_miles * 1609.34)

    query = f"""[out:json][timeout:30];
(
  node["amenity"="grave_yard"](around:{radius_meters},{latitude},{longitude});
  way["amenity"="grave_yard"](around:{radius_meters},{latitude},{longitude});
  node["landuse"="cemetery"](around:{radius_meters},{latitude},{longitude});
  way["landuse"="cemetery"](around:{radius_meters},{latitude},{longitude});
  relation["landuse"="cemetery"](around:{radius_meters},{latitude},{longitude});
);
out center tags;"""

    now = datetime.now(timezone.utc)
    results = []

    try:
        resp = requests.post(
            OVERPASS_URL,
            data=query,
            headers={
                "Content-Type": "text/plain",
                "User-Agent": OVERPASS_USER_AGENT,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

    except requests.exceptions.Timeout:
        logger.warning("Overpass API timeout — falling back to Google Places")
        return _fetch_from_google_places(db, company_id, latitude, longitude, radius_miles)
    except Exception as exc:
        logger.warning("Overpass API error (%s) — falling back to Google Places", exc)
        return _fetch_from_google_places(db, company_id, latitude, longitude, radius_miles)

    for element in data.get("elements", []):
        tags = element.get("tags", {})
        name = tags.get("name") or tags.get("name:en") or ""
        if not name:
            continue
        if not _is_valid_cemetery_name(name):
            continue

        # Coordinates
        el_type = element.get("type", "node")
        if el_type == "node":
            el_lat = element.get("lat")
            el_lng = element.get("lon")
        else:
            center = element.get("center", {})
            el_lat = center.get("lat")
            el_lng = center.get("lon")

        if el_lat is None or el_lng is None:
            continue

        osm_element_id = f"{el_type}/{element['id']}"
        place_id = f"osm:{osm_element_id}"

        # Address from tags
        city = tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village")
        state_code = tags.get("addr:state")
        zip_code = tags.get("addr:postcode")
        county = tags.get("addr:county")
        street = tags.get("addr:street")
        address = None
        if street and city and state_code:
            address = f"{street}, {city}, {state_code} {zip_code or ''}".strip().rstrip(",")

        # Fill in county from static ZIP data if missing
        if not county:
            county, inferred_state = _county_from_coords(el_lat, el_lng)
            if not state_code and inferred_state:
                state_code = inferred_state

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
            existing.name = name
            existing.city = city or existing.city
            existing.state_code = state_code or existing.state_code
            existing.zip_code = zip_code or existing.zip_code
            existing.county = county or existing.county
            existing.latitude = Decimal(str(el_lat))
            existing.longitude = Decimal(str(el_lng))
            existing.source = "openstreetmap"
            existing.osm_id = osm_element_id
            existing.last_verified_at = now
            existing.is_active = True
            results.append(existing)
        else:
            entry = CemeteryDirectory(
                company_id=company_id,
                place_id=place_id,
                osm_id=osm_element_id,
                name=name,
                address=address,
                city=city,
                state_code=state_code,
                zip_code=zip_code,
                county=county,
                latitude=Decimal(str(el_lat)),
                longitude=Decimal(str(el_lng)),
                source="openstreetmap",
                is_active=True,
                first_fetched_at=now,
                last_verified_at=now,
            )
            db.add(entry)
            results.append(entry)

    db.flush()

    # Log the fetch
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

    logger.info(
        "Overpass API returned %d cemeteries within %d miles of (%.4f, %.4f)",
        len(results),
        radius_miles,
        latitude,
        longitude,
    )
    return results


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


def _entry_to_dict(
    entry,
    already_added: bool = False,
    company_lat: float | None = None,
    company_lng: float | None = None,
) -> dict:
    distance_miles = None
    if company_lat is not None and company_lng is not None:
        if entry.latitude and entry.longitude:
            distance_miles = round(
                _haversine(company_lat, company_lng, float(entry.latitude), float(entry.longitude)),
                1,
            )

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
        "distance_miles": distance_miles,
        "source": getattr(entry, "source", "google_places"),
    }
