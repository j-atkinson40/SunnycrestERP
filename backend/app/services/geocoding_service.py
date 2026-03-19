"""Geocode tenant facility addresses using Google Maps Geocoding API."""

import logging

import requests
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal

logger = logging.getLogger(__name__)


def geocode_tenant_address(tenant_id: str) -> bool:
    """Geocode a tenant's facility address. Updates lat/lng on the company record."""
    db = SessionLocal()
    try:
        company = db.execute(
            text(
                "SELECT facility_address_line1, facility_city, facility_state, facility_zip "
                "FROM companies WHERE id = :id"
            ),
            {"id": tenant_id},
        ).fetchone()

        if not company or not company[0]:
            return False

        address = f"{company[0]}, {company[1]}, {company[2]} {company[3]}"

        api_key = getattr(settings, "GOOGLE_PLACES_API_KEY", None)
        if not api_key:
            logger.warning("No GOOGLE_PLACES_API_KEY — skipping geocode")
            return False

        resp = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": address, "key": api_key},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") == "OK" and data.get("results"):
            location = data["results"][0]["geometry"]["location"]
            db.execute(
                text(
                    "UPDATE companies SET facility_latitude = :lat, facility_longitude = :lng "
                    "WHERE id = :id"
                ),
                {"lat": location["lat"], "lng": location["lng"], "id": tenant_id},
            )
            db.commit()
            logger.info(
                "Geocoded tenant %s: %s, %s",
                tenant_id,
                location["lat"],
                location["lng"],
            )
            return True
        else:
            logger.warning(
                "Geocode failed for tenant %s: %s", tenant_id, data.get("status")
            )
            return False
    except Exception as e:
        logger.exception("Geocode error for tenant %s: %s", tenant_id, e)
        return False
    finally:
        db.close()
