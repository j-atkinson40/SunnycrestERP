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


@lru_cache(maxsize=1)
def _load_ny_zip_counties() -> dict:
    """ZIP → [county, …] for New York, from the state's own cross-reference.

    ⚠️ THIS IS AN AMBIGUITY FILTER, NOT A COUNTY SOURCE, AND THE DIFFERENCE IS
    THE WHOLE DESIGN. Every row in the state's dataset is dated 2007-07-25 and
    it has never been revised, so it UNDER-DETECTS: a ZIP it lists as spanning
    two counties almost certainly still does, but one it lists as clean may have
    become ambiguous since and would be missed. Under-detection is the unsafe
    direction — which is why an explicit `customer.tax_county` overrides it, and
    why an ambiguous ZIP refuses rather than picking.

    Distinct from `_load_zip_mapping()`, which is 107 county CENTROIDS for the
    radius suggestion and was never a coverage table — using it as one is what
    made 14580 (Webster, Monroe) resolve to nothing while 14604 resolved fine.
    """
    path = os.path.join(DATA_DIR, "ny-zip-counties.json")
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("ny-zip-counties.json not found — ZIP resolution disabled")
        return {"zips": {}, "metadata": {}}


def counties_for_zip(zip_code: str, state: str = "NY") -> list[str]:
    """Every county a ZIP touches. Empty when unknown — NOT a resolution."""
    if (state or "").upper() != "NY":
        return []
    z = (zip_code or "").strip()[:5]
    return list(_load_ny_zip_counties()["zips"].get(z, []))


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance in miles between two lat/lng points."""
    R = 3959  # Earth radius in miles
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _platform_rate_for_county(db, state: str, county: str, on) -> dict | None:
    """The in-force `platform_tax_rates` row for a county, if one is loaded.

    ⚠️ TABLE FIRST, FILE SECOND, AND THE ORDER IS THE POINT. `us-county-tax-rates.json`
    is an unversioned snapshot with one commit in its history; it was wrong for
    nine New York counties for nineteen months because nothing could correct it
    centrally and nothing recorded that nobody had checked. The table carries
    effective dates, the reporting code, and `verified_on`. Where it has an
    answer, the file's is stale by construction.

    Returns None when the state has not been loaded, so every state except New
    York still resolves through the file — deliberately, because only New York
    has been verified against a primary source.
    """
    from app.models.tax import PlatformTaxRate

    rows = (
        db.query(PlatformTaxRate)
        .filter(
            PlatformTaxRate.state == state.upper(),
            PlatformTaxRate.county.ilike(county.strip()),
            PlatformTaxRate.effective_to.is_(None),
        )
        .all()
    )
    if not rows:
        return None
    # A county can hold several jurisdictions. The county-wide rate is the
    # "– except" row; a city row applies only inside that city and cannot be
    # chosen from a county name alone. Preferring the county-wide row is
    # CORRECT for eleven of New York's twelve split counties and WRONG for
    # Yonkers — recorded in the seed's docstring, and not fixable without
    # resolving on address rather than county.
    rows = [r for r in rows if r.is_in_force_on(on)]
    if not rows:
        return None
    countywide = next((r for r in rows if "(city)" not in r.jurisdiction_name), rows[0])
    combined = float(countywide.rate_percentage)
    state_only = (
        db.query(PlatformTaxRate)
        .filter(
            PlatformTaxRate.state == state.upper(),
            PlatformTaxRate.county.is_(None),
            PlatformTaxRate.effective_to.is_(None),
        )
        .first()
    )
    state_rate = float(state_only.rate_percentage) if state_only else None
    return {
        "state_rate": state_rate,
        "county_rate": round(combined - state_rate, 4) if state_rate is not None else None,
        "combined_rate": combined,
        "is_state_rate_only": state_rate is not None and combined == state_rate,
        "jurisdiction_code": countywide.jurisdiction_code,
        "source": "platform_tax_rates",
        "verified_on": countywide.verified_on.isoformat(),
    }


def _county_has_dated_coverage(db, state: str, county: str) -> bool:
    """Does `platform_tax_rates` carry ANY row for this state+county, at any date?

    ⚠️ KEYED ON THE COUNTY, NOT THE STATE, AND THAT DISTINCTION IS THE WHOLE
    GUARD. The first version asked whether the STATE had any rows, which made a
    THIRD absence collapse into the refusal: a New York county missing from the
    table — a caller's misspelling, or one the seed never loaded — would be
    refused instead of falling back to the file. That is the Ohio argument at
    county granularity: we have no dated data for that county, so the undated
    file is not a worse answer than nothing, it is the only answer.

    Caught by `test_platform_tax_rates.py` when the gate ran, not by noticing.

    Deliberately ignores `effective_to`: a county whose only row has been CLOSED
    still has dated coverage, and a date outside it is a refusal rather than a
    fallback. The question here is "did we ever record dates for this county",
    not "is something in force now" — that second question is
    `_platform_rate_for_county`, and its None is what brings us here.
    """
    from app.models.tax import PlatformTaxRate

    return (
        db.query(PlatformTaxRate.id)
        .filter(
            PlatformTaxRate.state == state.upper(),
            PlatformTaxRate.county.ilike(county.strip()),
        )
        .first()
        is not None
    )


def get_tax_rate_for_county(state: str, county: str, db=None, on=None) -> dict | None:
    """Look up combined tax rate for a state+county, as of `on`.

    Reads `platform_tax_rates` when a session is supplied and the state has been
    loaded; otherwise falls back to the static dataset. `db` is optional so the
    function stays callable from contexts that have no session.

    ⚠️ A DATE THE TABLE CANNOT ANSWER IS REFUSED, NOT ANSWERED FROM THE UNDATED
    FILE. Before this, asking about 2019 returned **today's** rate: the platform
    lookup found no row in force, fell through to
    `us-county-tax-rates.json` — which has no date concept at all — and handed
    back the current figure as though it were the 2019 one. The caller supplied a
    date, got an answer, and the answer silently ignored it. That is worse than
    not asking, because it looks like history.

    The distinction that decides it is not "did we find a rate" but "does this
    COUNTY have dated coverage" — county, not state, because three absences
    reach this line and only one of them is a refusal:

      - county NOT in `platform_tax_rates` because its whole state is absent
        (Ohio today) → fall back to the file. We have no dated data and never
        claimed to; the file is undated for every date equally.
      - county not in the table though its state is loaded (a misspelling, or
        one the seed missed) → **also fall back**, for exactly the same reason.
        Refusing here would break a county the file can still answer.
      - county IS in the table, date outside its range → **refuse**, carrying
        `unknown_because`. `platform_tax_rates` holds one edition
        (`effective_from` 2025-03-01 on every row), so every pre-epoch question
        about a loaded county lands here.

    "I do not have rates for that date" is a first-class answer in this codebase
    — `require_resolution` raises rather than defaulting to zero, an unbacked
    exemption flag resolves TAXABLE with the gap listed, an ambiguous ZIP
    refuses and names the counties.

    ⚠️ LATENT TODAY, AND SAYING SO: no caller passes a historical date.
    `build_suggestions` omits `on`, so it always asks about now. This is the
    trap waiting for whoever builds historical recompute — the parameter exists,
    accepts a past date, and until now answered it with a present number.
    """
    from datetime import date as _date

    asked = on or _date.today()
    if db is not None:
        hit = _platform_rate_for_county(db, state, county, asked)
        if hit:
            return hit
        if _county_has_dated_coverage(db, state, county):
            return {
                "state_rate": None, "county_rate": None, "combined_rate": None,
                "is_state_rate_only": False,
                "unknown_because": (
                    f"no {county.strip()} County, {state.upper()} rate is recorded "
                    f"as in force on {asked.isoformat()} — that county has dated "
                    "coverage and this date falls outside it, so the undated "
                    "fallback would answer with a figure from another period"
                ),
            }

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
    db=None,
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

        rate_info = get_tax_rate_for_county(state, county, db=db)
        # ⚠️ TWO FACTS SHARED THE WORD `source` AND THE VALUABLE ONE WAS THROWN
        # AWAY. This dict's `source` means HOW THE COUNTY WAS SUGGESTED
        # (radius_lookup / customer_addresses / service_territory).
        # `get_tax_rate_for_county` returns a `source` meaning WHERE THE RATE
        # CAME FROM (`platform_tax_rates` when the state has been verified
        # against a primary publication, absent when it fell back to the static
        # file). Building this dict with an explicit key list silently dropped
        # the second, so a New York suggestion — verified against Publication
        # 718 last week — and an Ohio one from a 2025 compilation nobody has
        # ever checked arrived byte-identical.
        #
        # Renamed to `suggested_by`, and the provenance passed through under
        # its own names. `rate_verified_on` being null IS the honest signal.
        suggestions.append({
            "county": county,
            "state": state.upper(),
            "combined_rate": rate_info["combined_rate"] if rate_info else None,
            "state_rate": rate_info["state_rate"] if rate_info else None,
            "county_rate": rate_info["county_rate"] if rate_info else None,
            "is_state_rate_only": rate_info["is_state_rate_only"] if rate_info else True,
            "suggested_by": source,
            # Retained for one release so an unmigrated caller does not break.
            # `suggested_by` is the name; this is the old one.
            "source": source,
            "rate_source": (rate_info or {}).get("source"),
            "rate_verified_on": (rate_info or {}).get("verified_on"),
            "jurisdiction_code": (rate_info or {}).get("jurisdiction_code"),
            # Why there is no rate, when there is a reason worth giving. Null in
            # the ordinary "county not in the file" case — that has no story.
            "rate_unknown_because": (rate_info or {}).get("unknown_because"),
            "distance_miles": distance,
            "already_configured": key in existing_keys,
            # ⚠️ KEYED ON AN ACTUAL RATE, NOT ON A NON-NULL DICT. The
            # date-refusal above returns a dict WITHOUT a rate, so
            # `rate_info is not None` would have reported `rate_found: True`
            # alongside `combined_rate: None` — a found rate that is not a rate.
            "rate_found": bool(rate_info) and rate_info.get("combined_rate") is not None,
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
