"""Cemetery location mapping service — links cemeteries to fulfilling locations.

A fulfilling_location_id on company_entities (where is_cemetery=True) indicates
which tenant location handles jobs at that cemetery.
"""

import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.company_entity import CompanyEntity

logger = logging.getLogger(__name__)


def get_fulfilling_location(
    db: Session, cemetery_id: str, company_id: str
) -> Company | None:
    """Return the tenant location assigned to this cemetery, or None."""
    cemetery = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.id == cemetery_id,
            CompanyEntity.company_id == company_id,
            CompanyEntity.is_cemetery.is_(True),
        )
        .first()
    )
    if not cemetery:
        return None
    if not cemetery.fulfilling_location_id:
        return None
    return (
        db.query(Company).filter(Company.id == cemetery.fulfilling_location_id).first()
    )


def set_fulfilling_location(
    db: Session, cemetery_id: str, location_id: str, company_id: str
) -> CompanyEntity:
    """Set which tenant location fulfills jobs at this cemetery.

    Validates that:
    - The cemetery exists and belongs to the tenant
    - The location exists and belongs to the tenant (hierarchy_level='location' or is the tenant itself)
    """
    cemetery = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.id == cemetery_id,
            CompanyEntity.company_id == company_id,
            CompanyEntity.is_cemetery.is_(True),
        )
        .first()
    )
    if not cemetery:
        raise HTTPException(status_code=404, detail="Cemetery not found")

    # Validate location belongs to tenant
    location = (
        db.query(Company)
        .filter(
            Company.id == location_id,
        )
        .first()
    )
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    # Location must be the tenant itself or a child location of the tenant
    if location.id != company_id and location.parent_company_id != company_id:
        raise HTTPException(
            status_code=400,
            detail="Location does not belong to this tenant",
        )

    cemetery.fulfilling_location_id = location_id
    db.commit()
    db.refresh(cemetery)

    logger.info(
        "Cemetery %s (%s) mapped to location %s (%s)",
        cemetery.id,
        cemetery.name,
        location.id,
        location.name,
    )
    return cemetery
