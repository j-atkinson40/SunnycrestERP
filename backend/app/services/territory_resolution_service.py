"""Territory Resolution Service — resolves and manages Wilbert territory definitions.

NEW: no existing equivalent. Handles territory lookup, suggestion, and confirmation.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import WilbertTerritory

logger = logging.getLogger(__name__)


KNOWN_TERRITORY_PATTERNS = {
    "CNY": {
        "state": "NY",
        "region": "Central New York",
        "suggested_counties": [
            "Onondaga", "Cayuga", "Cortland", "Madison",
            "Oswego", "Tompkins", "Seneca", "Wayne",
        ],
    },
    "WNY": {
        "state": "NY",
        "region": "Western New York",
        "suggested_counties": [
            "Erie", "Niagara", "Monroe", "Genesee",
            "Orleans", "Wyoming", "Livingston", "Ontario",
        ],
    },
    "ENY": {
        "state": "NY",
        "region": "Eastern New York",
        "suggested_counties": [
            "Albany", "Rensselaer", "Schenectady", "Saratoga",
            "Columbia", "Greene", "Warren", "Washington",
        ],
    },
    "SNY": {
        "state": "NY",
        "region": "Southern New York",
        "suggested_counties": [
            "Broome", "Tioga", "Chemung", "Steuben",
            "Schuyler", "Allegany", "Cattaraugus", "Chautauqua",
        ],
    },
}


class TerritoryResolutionService:
    """Resolves and manages Wilbert territory definitions."""

    @staticmethod
    def resolve_territory(db: Session, territory_code: str, state: str) -> dict:
        """Check DB first for a confirmed territory, else return suggestions.

        Returns a dict with 'source' ('confirmed' or 'suggested'), territory data,
        and suggested counties if not yet confirmed.
        """
        # Check database for confirmed territory
        territory = (
            db.query(WilbertTerritory)
            .filter(WilbertTerritory.territory_code == territory_code)
            .first()
        )

        if territory and territory.confirmed_at:
            return {
                "source": "confirmed",
                "territory_code": territory.territory_code,
                "state": territory.state,
                "counties": territory.counties or [],
                "zip_codes": territory.zip_codes or [],
                "confirmed_by_company_id": territory.confirmed_by_company_id,
                "confirmed_at": territory.confirmed_at.isoformat() if territory.confirmed_at else None,
            }

        # Check known patterns for suggestions
        pattern = KNOWN_TERRITORY_PATTERNS.get(territory_code.upper())
        if pattern and pattern["state"] == state.upper():
            return {
                "source": "suggested",
                "territory_code": territory_code,
                "state": state.upper(),
                "suggested_counties": pattern["suggested_counties"],
                "region": pattern["region"],
                "note": "These counties are suggested based on known Wilbert territory patterns. Please confirm or adjust.",
            }

        # No match at all
        return {
            "source": "unknown",
            "territory_code": territory_code,
            "state": state.upper(),
            "suggested_counties": [],
            "note": f"No known territory pattern for {territory_code} in {state}. Please define counties manually.",
        }

    @staticmethod
    def confirm_territory(
        db: Session,
        territory_code: str,
        state: str,
        counties: list[str],
        confirmed_by_company_id: str,
    ) -> WilbertTerritory:
        """Store a confirmed territory definition.

        Creates or updates the WilbertTerritory record. Once confirmed,
        this territory is available to all licensees on the platform.
        """
        existing = (
            db.query(WilbertTerritory)
            .filter(WilbertTerritory.territory_code == territory_code)
            .first()
        )

        now = datetime.now(timezone.utc)

        if existing:
            existing.state = state.upper()
            existing.counties = counties
            existing.confirmed_by_company_id = confirmed_by_company_id
            existing.confirmed_at = now
            db.flush()
            logger.info(
                "Updated confirmed territory %s (%d counties) by company=%s",
                territory_code,
                len(counties),
                confirmed_by_company_id,
            )
            return existing

        territory = WilbertTerritory(
            id=str(uuid.uuid4()),
            territory_code=territory_code,
            state=state.upper(),
            counties=counties,
            confirmed_by_company_id=confirmed_by_company_id,
            confirmed_at=now,
        )
        db.add(territory)
        db.flush()
        logger.info(
            "Created confirmed territory %s (%d counties) by company=%s",
            territory_code,
            len(counties),
            confirmed_by_company_id,
        )
        return territory

    @staticmethod
    def get_territory(db: Session, territory_code: str) -> WilbertTerritory | None:
        """Look up a territory by code."""
        return (
            db.query(WilbertTerritory)
            .filter(WilbertTerritory.territory_code == territory_code)
            .first()
        )

    @staticmethod
    def get_suggested_counties(territory_code: str, state: str) -> list[str]:
        """Return suggested counties from KNOWN_TERRITORY_PATTERNS.

        Returns empty list if no pattern is known.
        """
        pattern = KNOWN_TERRITORY_PATTERNS.get(territory_code.upper())
        if pattern and pattern["state"] == state.upper():
            return pattern["suggested_counties"]
        return []
