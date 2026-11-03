"""Service territory management — county-based delivery area setup."""

import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_company, get_current_user
from app.database import get_db
from app.models.company import Company
from app.models.service_territory import ManufacturerServiceTerritory
from app.models.user import User

router = APIRouter()


class CountyItem(BaseModel):
    state_code: str
    county_name: str
    county_fips: str | None = None


class SaveTerritoriesRequest(BaseModel):
    counties: list[CountyItem]


@router.get("/service-territories")
def get_service_territories(
    # ⚠️ `current_user` IS LOAD-BEARING AND IS NOT READ IN THE BODY. It is the
    # authentication. Until 2026-11-03 this endpoint depended only on
    # `get_current_company`, which resolves from the `X-Company-Slug` HEADER
    # (`app/api/company_resolver.py:8`) and authenticates nothing — so anyone
    # who knew a tenant slug could read that tenant's territories, its
    # `delivery_area_configured` flag and its `facility_state`. Measured as the
    # only such endpoint in the tenant realm.
    #
    # `get_current_user` supplies the same-company half too: it 401s when
    # `token_company_id != company.id` (`app/api/deps.py:63-67`) and loads the
    # user filtered on `User.company_id == company.id` (:72-76). So no further
    # check belongs here, and adding one would imply the dependency does less
    # than it does.
    #
    # Do not "clean up" this unused parameter. The ratchet in
    # `tests/test_service_territories_requires_login.py` fails if any tenant
    # route resolves a company without requiring a user.
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get current service territories for the company. Requires a signed-in
    user OF THAT COMPANY."""
    territories = (
        db.query(ManufacturerServiceTerritory)
        .filter(ManufacturerServiceTerritory.company_id == company.id)
        .order_by(ManufacturerServiceTerritory.state_code, ManufacturerServiceTerritory.county_name)
        .all()
    )
    return {
        "counties": [
            {
                "id": t.id,
                "state_code": t.state_code,
                "county_name": t.county_name,
                "county_fips": t.county_fips,
            }
            for t in territories
        ],
        "total": len(territories),
        "delivery_area_configured": company.get_setting("delivery_area_configured", False),
        "facility_state": company.facility_state,
    }


@router.post("/service-territories")
def save_service_territories(
    data: SaveTerritoriesRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Replace service territories with the provided list of counties."""
    # Remove existing territories
    db.query(ManufacturerServiceTerritory).filter(
        ManufacturerServiceTerritory.company_id == company.id
    ).delete()

    # Insert new ones
    for county in data.counties:
        territory = ManufacturerServiceTerritory(
            id=str(uuid.uuid4()),
            company_id=company.id,
            state_code=county.state_code.upper(),
            county_name=county.county_name,
            county_fips=county.county_fips,
        )
        db.add(territory)

    # Mark delivery area as configured
    if data.counties:
        company.set_setting("delivery_area_configured", True)
    else:
        company.set_setting("delivery_area_configured", False)

    db.commit()

    return {
        "status": "ok",
        "counties_saved": len(data.counties),
        "delivery_area_configured": len(data.counties) > 0,
    }
