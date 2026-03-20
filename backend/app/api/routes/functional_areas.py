"""Functional area routes — extension-gated access areas for team management."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.company_resolver import get_current_company
from app.api.deps import get_current_user
from app.database import get_db
from app.models.company import Company
from app.models.user import User
from app.services import functional_area_service

router = APIRouter()


@router.get("/functional-areas")
def list_functional_areas(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Return functional areas available for this tenant, filtered by extensions."""
    areas = functional_area_service.get_areas_for_tenant(db, company.id)
    return {"areas": areas}
