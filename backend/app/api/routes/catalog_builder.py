"""Catalog Builder routes — bulk product creation from structured selections."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.company_resolver import get_current_company
from app.api.deps import get_current_user
from app.database import get_db
from app.models.company import Company
from app.models.user import User
from app.services import catalog_builder_service

router = APIRouter()


class CatalogBuildRequest(BaseModel):
    burial_vaults: dict | None = None
    urn_vaults: dict | None = None
    urns: dict | None = None
    cemetery_equipment: dict | None = None
    markup_settings: dict | None = None


@router.post("/catalog-builder/build")
def build_catalog(
    data: CatalogBuildRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Build product catalog from structured category selections."""
    try:
        result = catalog_builder_service.build_catalog(
            db, company.id, current_user.id, data.model_dump(exclude_none=True)
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/catalog-builder/existing")
def get_existing(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get existing catalog-builder-created products for return visit detection."""
    return catalog_builder_service.get_existing_products(db, company.id)
