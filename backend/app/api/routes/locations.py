"""Location API routes — multi-location management."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.services import location_service
from app.services.location_service import _serialize_location

router = APIRouter()


# --- Pydantic schemas ---


class LocationCreate(BaseModel):
    name: str
    location_type: str = "plant"
    wilbert_territory_id: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_primary: bool = False
    display_order: int = 0
    metadata: Optional[dict] = Field(None, alias="metadata_json")


class LocationUpdate(BaseModel):
    name: Optional[str] = None
    location_type: Optional[str] = None
    wilbert_territory_id: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_primary: Optional[bool] = None
    display_order: Optional[int] = None
    metadata: Optional[dict] = Field(None, alias="metadata_json")


class UserLocationAccessCreate(BaseModel):
    user_id: str
    location_id: Optional[str] = None
    access_level: str = "operator"


class LocationResponse(BaseModel):
    id: str
    company_id: str
    name: str
    location_type: str
    wilbert_territory_id: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_primary: bool
    is_active: bool
    display_order: int
    metadata: Optional[dict] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class UserLocationAccessResponse(BaseModel):
    id: str
    user_id: str
    company_id: str
    location_id: Optional[str] = None
    access_level: str
    is_active: bool
    created_at: Optional[str] = None


# --- Location CRUD endpoints ---


@router.get("")
def list_locations(
    include_inactive: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all locations for the current company."""
    locations = location_service.get_company_locations(
        db, current_user.company_id, include_inactive=include_inactive
    )
    return [_serialize_location(loc) for loc in locations]


@router.post("", status_code=201)
def create_location(
    data: LocationCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new location. Admin only."""
    kwargs = data.model_dump(exclude_unset=True)
    # Rename metadata alias
    if "metadata" in kwargs:
        kwargs["metadata_json"] = kwargs.pop("metadata")

    name = kwargs.pop("name")
    location_type = kwargs.pop("location_type", "plant")

    location = location_service.create_location(
        db,
        company_id=current_user.company_id,
        name=name,
        location_type=location_type,
        **kwargs,
    )
    db.commit()
    return _serialize_location(location)


@router.get("/overview")
def get_locations_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get overview stats for all accessible locations."""
    return location_service.get_locations_overview(
        db, current_user.company_id, current_user.id
    )


@router.get("/users")
def list_user_location_assignments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all user-location access assignments for the company."""
    assignments = location_service.get_user_location_assignments(
        db, current_user.company_id
    )
    return [
        {
            "id": a.id,
            "user_id": a.user_id,
            "company_id": a.company_id,
            "location_id": a.location_id,
            "access_level": a.access_level,
            "is_active": a.is_active,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in assignments
    ]


@router.post("/users", status_code=201)
def grant_user_location_access(
    data: UserLocationAccessCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Grant a user access to a location. Admin only."""
    access = location_service.grant_user_access(
        db,
        user_id=data.user_id,
        company_id=current_user.company_id,
        location_id=data.location_id,
        access_level=data.access_level,
    )
    db.commit()
    return {
        "id": access.id,
        "user_id": access.user_id,
        "company_id": access.company_id,
        "location_id": access.location_id,
        "access_level": access.access_level,
        "is_active": access.is_active,
        "created_at": access.created_at.isoformat() if access.created_at else None,
    }


@router.delete("/users/{access_id}")
def revoke_user_location_access(
    access_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Revoke a user's location access by access record ID. Admin only."""
    from app.models.user_location_access import UserLocationAccess

    access = (
        db.query(UserLocationAccess)
        .filter(
            UserLocationAccess.id == access_id,
            UserLocationAccess.company_id == current_user.company_id,
            UserLocationAccess.is_active == True,
        )
        .first()
    )
    if not access:
        raise HTTPException(status_code=404, detail="Access record not found")

    access.is_active = False
    db.commit()
    return {"status": "revoked"}


@router.get("/{location_id}")
def get_location(
    location_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single location by ID."""
    from app.models.location import Location

    location = (
        db.query(Location)
        .filter(
            Location.id == location_id,
            Location.company_id == current_user.company_id,
        )
        .first()
    )
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return _serialize_location(location)


@router.patch("/{location_id}")
def update_location(
    location_id: str,
    data: LocationUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a location. Admin only."""
    update_data = data.model_dump(exclude_unset=True)
    if "metadata" in update_data:
        update_data["metadata_json"] = update_data.pop("metadata")

    location = location_service.update_location(
        db, location_id, current_user.company_id, **update_data
    )
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    db.commit()
    return _serialize_location(location)


@router.delete("/{location_id}")
def deactivate_location(
    location_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Deactivate a location. Admin only. Cannot deactivate primary."""
    result = location_service.deactivate_location(
        db, location_id, current_user.company_id
    )
    if not result:
        raise HTTPException(status_code=404, detail="Location not found")
    db.commit()
    return {"status": "deactivated"}


@router.get("/{location_id}/summary")
def get_location_summary(
    location_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get operational summary stats for a single location."""
    # Verify location exists and belongs to company
    from app.models.location import Location

    location = (
        db.query(Location)
        .filter(
            Location.id == location_id,
            Location.company_id == current_user.company_id,
        )
        .first()
    )
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    return location_service.get_location_summary(
        db, current_user.company_id, location_id
    )
