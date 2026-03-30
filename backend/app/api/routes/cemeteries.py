"""Cemetery management endpoints."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_module, require_permission
from app.database import get_db
from app.models.user import User
from app.services import cemetery_service
from app.services.cemetery_service import get_cemetery

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CemeteryCreate(BaseModel):
    name: str
    state: str | None = None
    county: str | None = None
    city: str | None = None
    address: str | None = None
    zip_code: str | None = None
    phone: str | None = None
    contact_name: str | None = None
    cemetery_provides_lowering_device: bool = False
    cemetery_provides_grass: bool = False
    cemetery_provides_tent: bool = False
    cemetery_provides_chairs: bool = False
    access_notes: str | None = None


class CemeteryUpdate(BaseModel):
    name: str | None = None
    state: str | None = None
    county: str | None = None
    city: str | None = None
    address: str | None = None
    zip_code: str | None = None
    phone: str | None = None
    contact_name: str | None = None
    cemetery_provides_lowering_device: bool | None = None
    cemetery_provides_grass: bool | None = None
    cemetery_provides_tent: bool | None = None
    cemetery_provides_chairs: bool | None = None
    access_notes: str | None = None


def _serialize(cemetery) -> dict:
    return {
        "id": cemetery.id,
        "company_id": cemetery.company_id,
        "name": cemetery.name,
        "address": cemetery.address,
        "city": cemetery.city,
        "state": cemetery.state,
        "county": cemetery.county,
        "zip_code": cemetery.zip_code,
        "phone": cemetery.phone,
        "contact_name": cemetery.contact_name,
        "cemetery_provides_lowering_device": cemetery.cemetery_provides_lowering_device,
        "cemetery_provides_grass": cemetery.cemetery_provides_grass,
        "cemetery_provides_tent": cemetery.cemetery_provides_tent,
        "cemetery_provides_chairs": cemetery.cemetery_provides_chairs,
        "equipment_note": cemetery.equipment_note,
        "access_notes": cemetery.access_notes,
        "is_active": cemetery.is_active,
        "created_at": cemetery.created_at.isoformat() if cemetery.created_at else None,
        "updated_at": cemetery.updated_at.isoformat() if cemetery.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
def list_cemeteries(
    search: str | None = Query(None),
    state: str | None = Query(None),
    county: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("customers.view")),
):
    result = cemetery_service.list_cemeteries(
        db,
        current_user.company_id,
        search=search,
        state=state,
        county=county,
        page=page,
        per_page=per_page,
    )
    return {
        "items": [_serialize(c) for c in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }


@router.get("/{cemetery_id}")
def get_cemetery_detail(
    cemetery_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("customers.view")),
):
    cemetery = get_cemetery(db, cemetery_id, current_user.company_id)
    return _serialize(cemetery)


@router.post("", status_code=201)
def create_cemetery(
    data: CemeteryCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("customers.create")),
):
    cemetery = cemetery_service.create_cemetery(
        db,
        company_id=current_user.company_id,
        **data.model_dump(),
    )
    return _serialize(cemetery)


@router.patch("/{cemetery_id}")
def update_cemetery(
    cemetery_id: str,
    data: CemeteryUpdate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("customers.edit")),
):
    fields = {k: v for k, v in data.model_dump().items() if v is not None}
    # Allow explicit False for boolean fields
    for k, v in data.model_dump().items():
        if isinstance(v, bool):
            fields[k] = v
    cemetery = cemetery_service.update_cemetery(
        db, cemetery_id, current_user.company_id, **fields
    )
    return _serialize(cemetery)


@router.delete("/{cemetery_id}")
def delete_cemetery(
    cemetery_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("customers.delete")),
):
    cemetery_service.delete_cemetery(db, cemetery_id, current_user.company_id)
    return {"detail": "Cemetery deactivated"}


@router.get("/{cemetery_id}/equipment-prefill")
def equipment_prefill(
    cemetery_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("sales")),
    current_user: User = Depends(require_permission("customers.view")),
):
    """Return equipment suggestion for a cemetery selection on an order form."""
    cemetery = get_cemetery(db, cemetery_id, current_user.company_id)
    return cemetery_service.get_equipment_prefill(cemetery)
