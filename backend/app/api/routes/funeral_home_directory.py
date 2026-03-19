"""Funeral Home Directory API routes for manufacturer customer onboarding."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.company_resolver import get_current_company
from app.api.deps import get_current_user
from app.database import get_db
from app.models.company import Company
from app.models.user import User
from app.schemas.funeral_home_directory import (
    DirectoryListResponse,
    ManualCustomerRequest,
    ManualCustomerResponse,
    PlatformMatchListResponse,
    RefreshRequest,
    SelectionRequest,
    SelectionResponse,
)
from app.services import funeral_home_directory_service

router = APIRouter()


@router.get("/funeral-home-directory", response_model=DirectoryListResponse)
def get_directory(
    latitude: float = Query(..., description="Center latitude"),
    longitude: float = Query(..., description="Center longitude"),
    radius_miles: int = Query(50, ge=1, le=200, description="Search radius in miles"),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get funeral home directory entries for the manufacturer's area."""
    entries = funeral_home_directory_service.get_directory_for_area(
        db,
        tenant_id=company.id,
        latitude=latitude,
        longitude=longitude,
        radius_miles=radius_miles,
    )
    return DirectoryListResponse(
        entries=entries,
        total=len(entries),
        cached=True,  # simplified; real impl would track this
    )


@router.get(
    "/funeral-home-directory/platform-matches",
    response_model=PlatformMatchListResponse,
)
def get_platform_matches(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get funeral home tenants already on the platform."""
    matches = funeral_home_directory_service.get_platform_matches(db, company.id)
    return PlatformMatchListResponse(matches=matches, total=len(matches))


@router.post(
    "/funeral-home-directory/selections",
    response_model=SelectionResponse,
)
def record_selections(
    data: SelectionRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Record manufacturer's selections from the directory (add, skip, invite)."""
    result = funeral_home_directory_service.record_selections(
        db,
        tenant_id=company.id,
        selections=[s.model_dump() for s in data.selections],
    )
    db.commit()
    return SelectionResponse(**result)


@router.post(
    "/funeral-home-directory/manual",
    response_model=ManualCustomerResponse,
)
def add_manual_customers(
    data: ManualCustomerRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Add manually entered funeral home customers."""
    result = funeral_home_directory_service.add_manual_customers(
        db,
        tenant_id=company.id,
        customers=[c.model_dump() for c in data.customers],
    )
    db.commit()
    return ManualCustomerResponse(**result)


@router.post(
    "/funeral-home-directory/refresh",
    response_model=DirectoryListResponse,
)
def refresh_directory(
    data: RefreshRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Force refresh directory data from Google Places."""
    # Delete recent fetch logs to force re-fetch
    from app.models.directory_fetch_log import DirectoryFetchLog

    db.query(DirectoryFetchLog).filter(
        DirectoryFetchLog.fetched_for_tenant_id == company.id,
        DirectoryFetchLog.fetch_type == "radius",
    ).delete()
    db.flush()

    entries = funeral_home_directory_service.get_directory_for_area(
        db,
        tenant_id=company.id,
        latitude=data.latitude,
        longitude=data.longitude,
        radius_miles=data.radius_miles,
    )
    db.commit()
    return DirectoryListResponse(
        entries=entries,
        total=len(entries),
        cached=False,
    )
