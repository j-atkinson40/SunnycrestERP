"""County geographic service — finds nearby counties and pre-fills tax rates."""

import json
import logging
import math
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")


@lru_cache(maxsize=1)
def _load_tax_rates() -> dict:
    path = os.path.join(DATA_DIR, "us-county-tax-rates.json")
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("us-county-tax-rates.json not found")
        return {"rates": []}


@lru_cache(maxsize=1)
def _load_zip_mapping() -> dict:
    path = os.path.join(DATA_DIR, "us-zip-county-mapping.json")
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("us-zip-county-mapping.json not found")
        return {}


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance in miles between two lat/lng points."""
    R = 3959  # Earth radius in miles
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def get_tax_rate_for_county(state: str, county: str) -> dict | None:
    """Look up combined tax rate for a state+county from static dataset."""
    data = _load_tax_rates()
    state_upper = state.upper()
    county_lower = county.lower().strip()

    for r in data["rates"]:
        if r["state"] == state_upper and r.get("county") and r["county"].lower() == county_lower:
            return {
                "state_rate": r["state_rate"],
                "county_rate": r["county_rate"],
                "combined_rate": r["combined_rate"],
                "is_state_rate_only": r["county_rate"] is None or r["county_rate"] == 0,
            }

    # Fall back to state-only rate
    for r in data["rates"]:
        if r["state"] == state_upper and r.get("county") is None:
            return {
                "state_rate": r["state_rate"],
                "county_rate": None,
                "combined_rate": r["combined_rate"],
                "is_state_rate_only": True,
            }

    return None


def get_counties_in_radius(zip_code: str, radius_miles: float = 100, max_counties: int = 25) -> list[dict]:
    """Find counties within radius_miles of the given zip code using static data."""
    mapping = _load_zip_mapping()
    center = mapping.get(zip_code)
    if not center:
        return []

    center_lat = center["lat"]
    center_lng = center["lng"]

    # Calculate distances to all zips and collect unique counties
    county_distances: dict[str, dict] = {}  # key: "state|county"

    for zc, info in mapping.items():
        dist = _haversine(center_lat, center_lng, info["lat"], info["lng"])
        if dist > radius_miles:
            continue

        key = f"{info['state']}|{info['county']}"
        if key not in county_distances or dist < county_distances[key]["distance_miles"]:
            county_distances[key] = {
                "county": info["county"],
                "state": info["state"],
                "distance_miles": round(dist, 1),
                "source": "radius_lookup",
            }

    # Sort by distance, cap at max
    results = sorted(county_distances.values(), key=lambda x: x["distance_miles"])
    return results[:max_counties]


def build_suggestions(
    tenant_zip: str | None,
    tenant_state: str | None,
    service_territory_counties: list[dict] | None = None,
    customer_counties: list[dict] | None = None,
    existing_jurisdictions: list[dict] | None = None,
    radius_miles: float = 100,
) -> list[dict]:
    """
    Build county suggestions with pre-filled tax rates.

    Args:
        tenant_zip: Tenant's zip code for radius lookup
        tenant_state: Tenant's state code
        service_territory_counties: [{county, state}] from service territory
        customer_counties: [{county, state}] from imported customers
        existing_jurisdictions: [{county, state}] already configured
        radius_miles: Search radius in miles
    """
    seen: set[str] = set()
    suggestions: list[dict] = []

    # Track existing jurisdictions
    existing_keys = set()
    if existing_jurisdictions:
        for ej in existing_jurisdictions:
            existing_keys.add(f"{ej.get('state', '').upper()}|{ej.get('county', '').lower()}")

    def _add(county: str, state: str, source: str, distance: float | None = None):
        key = f"{state.upper()}|{county.lower()}"
        if key in seen:
            return
        seen.add(key)

        rate_info = get_tax_rate_for_county(state, county)
        suggestions.append({
            "county": county,
            "state": state.upper(),
            "combined_rate": rate_info["combined_rate"] if rate_info else None,
            "state_rate": rate_info["state_rate"] if rate_info else None,
            "county_rate": rate_info["county_rate"] if rate_info else None,
            "is_state_rate_only": rate_info["is_state_rate_only"] if rate_info else True,
            "source": source,
            "distance_miles": distance,
            "already_configured": key in existing_keys,
            "rate_found": rate_info is not None,
        })

    # Group 1: Service territory counties
    if service_territory_counties:
        for sc in service_territory_counties:
            _add(sc["county"], sc["state"], "service_territory")

    # Group 2: Radius-based counties
    if tenant_zip:
        radius_counties = get_counties_in_radius(tenant_zip, radius_miles)
        for rc in radius_counties:
            _add(rc["county"], rc["state"], "radius_lookup", rc["distance_miles"])

    # Group 3: Customer address counties
    if customer_counties:
        for cc in customer_counties:
            _add(cc["county"], cc["state"], "customer_addresses")

    return suggestions
