"""Network Discovery Service — automated network discovery for funeral homes and cemeteries.

NEW: no existing equivalent. Uses Google Places API (already integrated) as primary
source, with stub methods for Wilbert locator, NFDA, and state licensing board
scraping that can be filled in later.
"""

import logging
from difflib import SequenceMatcher

import requests
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Company, CompanyEntity

logger = logging.getLogger(__name__)


class NetworkDiscoveryService:
    """Discovers funeral homes and cemeteries in a licensee's territory."""

    @staticmethod
    def discover_network(
        db: Session,
        company_id: str,
        territory_code: str,
        counties: list[str],
        state: str,
    ) -> dict:
        """Main entry: run discovery across all sources, deduplicate, return grouped results.

        Returns dict with funeral_homes, cemeteries, neighboring_licensees,
        and source metadata.
        """
        funeral_homes_google = NetworkDiscoveryService.discover_funeral_homes_google(
            counties, state
        )
        cemeteries_google = NetworkDiscoveryService.discover_cemeteries_google(
            counties, state
        )

        # Stub sources (return empty for now)
        fh_wilbert = NetworkDiscoveryService.scrape_wilbert_locator(counties, state)
        fh_nfda = NetworkDiscoveryService.scrape_nfda_directory(state, counties)
        fh_state = NetworkDiscoveryService.scrape_state_licensing(state, counties)

        # Merge funeral home sources
        all_fh_sources = [funeral_homes_google, fh_wilbert, fh_nfda, fh_state]
        merged_funeral_homes = NetworkDiscoveryService.deduplicate_and_merge(all_fh_sources)

        # Check which are already in the CRM
        existing_entities = (
            db.query(CompanyEntity)
            .filter(
                CompanyEntity.company_id == company_id,
                CompanyEntity.is_funeral_home == True,  # noqa: E712
            )
            .all()
        )
        existing_names = {e.name.lower().strip() for e in existing_entities}

        for fh in merged_funeral_homes:
            fh["already_in_crm"] = fh.get("name", "").lower().strip() in existing_names

        # Check for neighboring licensees
        neighboring = NetworkDiscoveryService.find_neighboring_licensees(
            db, territory_code
        )

        return {
            "territory_code": territory_code,
            "state": state,
            "counties": counties,
            "funeral_homes": merged_funeral_homes,
            "funeral_homes_count": len(merged_funeral_homes),
            "cemeteries": cemeteries_google,
            "cemeteries_count": len(cemeteries_google),
            "neighboring_licensees": neighboring,
            "sources": {
                "google_places": len(funeral_homes_google) + len(cemeteries_google),
                "wilbert_locator": len(fh_wilbert),
                "nfda": len(fh_nfda),
                "state_licensing": len(fh_state),
            },
        }

    @staticmethod
    def discover_funeral_homes_google(
        counties: list[str], state: str
    ) -> list[dict]:
        """Search Google Places API for funeral homes in territory counties."""
        api_key = getattr(settings, "GOOGLE_PLACES_API_KEY", None)
        if not api_key:
            logger.warning("GOOGLE_PLACES_API_KEY not configured — skipping Google discovery")
            return []

        results = []
        seen_place_ids = set()

        for county in counties[:10]:  # Limit to prevent excessive API calls
            query = f"funeral home in {county} County, {state}"
            try:
                places = _google_text_search(api_key, query)
                for place in places:
                    place_id = place.get("place_id")
                    if place_id and place_id not in seen_place_ids:
                        seen_place_ids.add(place_id)
                        results.append(_parse_google_place(place, "funeral_home"))
            except Exception:
                logger.exception("Google Places search failed for county=%s", county)

        return results

    @staticmethod
    def discover_cemeteries_google(
        counties: list[str], state: str
    ) -> list[dict]:
        """Search Google Places API for cemeteries in territory counties."""
        api_key = getattr(settings, "GOOGLE_PLACES_API_KEY", None)
        if not api_key:
            logger.warning("GOOGLE_PLACES_API_KEY not configured — skipping cemetery discovery")
            return []

        results = []
        seen_place_ids = set()

        for county in counties[:10]:
            query = f"cemetery in {county} County, {state}"
            try:
                places = _google_text_search(api_key, query)
                for place in places:
                    place_id = place.get("place_id")
                    if place_id and place_id not in seen_place_ids:
                        seen_place_ids.add(place_id)
                        results.append(_parse_google_place(place, "cemetery"))
            except Exception:
                logger.exception("Google Places search failed for county=%s", county)

        return results

    @staticmethod
    def scrape_wilbert_locator(
        counties: list[str], state: str
    ) -> list[dict]:
        """STUB: Scrape Wilbert.com locator for funeral homes in territory.

        Not yet implemented — requires Playwright or headless browser.
        Returns empty list.
        """
        logger.info(
            "Wilbert locator scraping not yet implemented (counties=%s, state=%s)",
            counties,
            state,
        )
        return []

    @staticmethod
    def scrape_nfda_directory(
        state: str, counties: list[str]
    ) -> list[dict]:
        """STUB: Scrape NFDA directory for funeral homes.

        Not yet implemented — requires authenticated access.
        Returns empty list.
        """
        logger.info(
            "NFDA directory scraping not yet implemented (state=%s)",
            state,
        )
        return []

    @staticmethod
    def scrape_state_licensing(
        state: str, counties: list[str]
    ) -> list[dict]:
        """STUB: Scrape state licensing board for funeral homes.

        Not yet implemented — varies by state.
        Returns empty list.
        """
        logger.info(
            "State licensing board scraping not yet implemented (state=%s)",
            state,
        )
        return []

    @staticmethod
    def deduplicate_and_merge(sources: list[list[dict]]) -> list[dict]:
        """Normalize names, zip-code match, merge results from multiple sources.

        Uses name similarity and zip code matching to identify duplicates.
        Merged entries track which sources contributed.
        """
        all_entries = []
        for source_list in sources:
            for entry in source_list:
                all_entries.append(entry)

        if not all_entries:
            return []

        merged = []
        used = set()

        for i, entry in enumerate(all_entries):
            if i in used:
                continue

            best_entry = dict(entry)
            best_entry.setdefault("sources", [])
            if entry.get("source") and entry["source"] not in best_entry["sources"]:
                best_entry["sources"].append(entry["source"])

            name_a = entry.get("name", "").lower().strip()
            zip_a = entry.get("zip", "")

            for j in range(i + 1, len(all_entries)):
                if j in used:
                    continue

                other = all_entries[j]
                name_b = other.get("name", "").lower().strip()
                zip_b = other.get("zip", "")

                # Check for duplicate: high name similarity + same zip
                name_sim = SequenceMatcher(None, name_a, name_b).ratio()
                is_duplicate = False

                if name_sim >= 0.85:
                    is_duplicate = True
                elif name_sim >= 0.7 and zip_a and zip_b and zip_a == zip_b:
                    is_duplicate = True

                if is_duplicate:
                    used.add(j)
                    # Merge: prefer non-empty fields
                    for key in ("phone", "email", "website", "address"):
                        if not best_entry.get(key) and other.get(key):
                            best_entry[key] = other[key]
                    if other.get("source") and other["source"] not in best_entry["sources"]:
                        best_entry["sources"].append(other["source"])

            merged.append(best_entry)

        return merged

    @staticmethod
    def find_neighboring_licensees(
        db: Session, territory_code: str
    ) -> list[dict]:
        """Check for other Wilbert licensees (companies) near this territory.

        Looks for companies with wilbert_vault_territory set in their settings.
        """
        from app.models import WilbertProgramEnrollment

        # Find all companies with vault program enrollments
        enrollments = (
            db.query(WilbertProgramEnrollment)
            .filter(
                WilbertProgramEnrollment.program_code == "vault",
                WilbertProgramEnrollment.is_active == True,  # noqa: E712
            )
            .all()
        )

        neighbors = []
        for enrollment in enrollments:
            company = (
                db.query(Company)
                .filter(Company.id == enrollment.company_id)
                .first()
            )
            if not company:
                continue

            neighbors.append({
                "company_id": company.id,
                "name": company.name,
                "slug": company.slug if hasattr(company, "slug") else None,
                "state": company.facility_state if hasattr(company, "facility_state") else None,
                "territory_ids": enrollment.territory_ids,
            })

        return neighbors


def _google_text_search(api_key: str, query: str, max_results: int = 20) -> list[dict]:
    """Execute a Google Places Text Search query."""
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": query,
        "key": api_key,
    }

    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    return data.get("results", [])[:max_results]


def _parse_google_place(place: dict, entity_type: str) -> dict:
    """Parse a Google Places result into a normalized dict."""
    addr = place.get("formatted_address", "")
    addr_parts = [p.strip() for p in addr.split(",")]

    city = addr_parts[0] if len(addr_parts) >= 3 else ""
    state_zip = addr_parts[1].strip() if len(addr_parts) >= 3 else ""
    state = state_zip.split(" ")[0] if state_zip else ""
    zip_code = state_zip.split(" ")[1] if len(state_zip.split(" ")) > 1 else ""

    location = place.get("geometry", {}).get("location", {})

    return {
        "name": place.get("name", ""),
        "address": addr,
        "city": city,
        "state": state,
        "zip": zip_code,
        "phone": None,  # Requires Place Details API call
        "latitude": location.get("lat"),
        "longitude": location.get("lng"),
        "google_place_id": place.get("place_id"),
        "rating": place.get("rating"),
        "entity_type": entity_type,
        "source": "google_places",
    }
