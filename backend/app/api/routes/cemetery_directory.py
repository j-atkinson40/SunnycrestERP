"""Cemetery Directory API routes for manufacturer cemetery onboarding."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.company_resolver import get_current_company
from app.api.deps import get_current_user
from app.database import get_db
from app.models.company import Company
from app.models.user import User
from app.schemas.cemetery_directory import (
    CemeteryDirectoryListResponse,
    CemeteryPlatformConnectRequest,
    CemeteryPlatformConnectResponse,
    CemeteryPlatformMatchListResponse,
    CemeteryPlatformMatchResponse,
    CemeteryRefreshRequest,
    CemeterySelectionRequest,
    CemeterySelectionResponse,
)
from app.services import cemetery_directory_service

router = APIRouter()


@router.get("/cemetery-directory/platform-matches", response_model=CemeteryPlatformMatchListResponse)
def get_platform_cemetery_matches(
    radius_miles: int = Query(100, ge=1, le=300, description="Search radius in miles"),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get cemetery tenants already on the platform within this manufacturer's area.

    Used for Step 0 of the cemetery setup wizard — lets manufacturers connect to
    existing platform cemetery tenants before searching Google Places.
    """
    matches = cemetery_directory_service.get_platform_cemetery_matches(
        db,
        company_id=company.id,
        radius_miles=radius_miles,
    )
    return CemeteryPlatformMatchListResponse(
        matches=[CemeteryPlatformMatchResponse(**m) for m in matches],
        total=len(matches),
    )


@router.post("/cemetery-directory/platform-connect", response_model=CemeteryPlatformConnectResponse)
def connect_platform_cemetery(
    data: CemeteryPlatformConnectRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Connect this manufacturer to a cemetery tenant that is already on the platform.

    Creates a PlatformTenantRelationship + Cemetery record. Idempotent.
    """
    result = cemetery_directory_service.connect_platform_cemetery(
        db,
        company_id=company.id,
        cemetery_tenant_id=data.cemetery_tenant_id,
        connected_by=current_user.id,
    )
    db.commit()
    return CemeteryPlatformConnectResponse(**result)


@router.get("/cemetery-directory", response_model=CemeteryDirectoryListResponse)
def get_cemetery_directory(
    radius_miles: int = Query(50, ge=1, le=200, description="Search radius in miles"),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get cemetery directory entries for the manufacturer's area.

    Uses the tenant's geocoded facility address as the center point.
    Results are cached for 90 days; call /refresh to force a fresh pull.
    Each entry includes an already_added flag if the cemetery has been
    previously selected or skipped.
    """
    entries = cemetery_directory_service.get_directory_for_company(
        db,
        company_id=company.id,
        radius_miles=radius_miles,
    )
    return CemeteryDirectoryListResponse(
        entries=entries,
        total=len(entries),
        cached=True,
    )


@router.post("/cemetery-directory/selections", response_model=CemeterySelectionResponse)
def record_selections(
    data: CemeterySelectionRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Create Cemetery records from the user's confirmed selections and manual entries.

    Equipment settings (provides_lowering_device, etc.) are applied at creation time.
    Nothing is auto-imported — this endpoint is only called after explicit user confirmation.
    """
    result = cemetery_directory_service.create_cemeteries_from_selections(
        db,
        company_id=company.id,
        selections=[s.model_dump() for s in data.selections],
        manual_entries=[m.model_dump() for m in data.manual_entries],
    )
    db.commit()

    # Mark the setup_cemeteries onboarding checklist item as complete
    try:
        from app.services import tenant_onboarding_service
        tenant_onboarding_service.check_completion(db, company.id, "setup_cemeteries")
        db.commit()
    except Exception:
        pass  # Don't fail the import if checklist update errors

    return CemeterySelectionResponse(**result)


@router.post("/cemetery-directory/refresh", response_model=CemeteryDirectoryListResponse)
def refresh_cemetery_directory(
    data: CemeteryRefreshRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Force a fresh Google Places pull by clearing the cache for this company."""
    cemetery_directory_service.clear_cache(db, company.id)

    entries = cemetery_directory_service.get_directory_for_company(
        db,
        company_id=company.id,
        radius_miles=data.radius_miles,
    )
    db.commit()
    return CemeteryDirectoryListResponse(
        entries=entries,
        total=len(entries),
        cached=False,
    )
