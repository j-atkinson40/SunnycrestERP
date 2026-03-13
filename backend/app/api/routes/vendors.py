from fastapi import APIRouter, Depends, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import require_module, require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.vendor import (
    PaginatedVendors,
    VendorContactCreate,
    VendorContactResponse,
    VendorContactUpdate,
    VendorCreate,
    VendorImportResult,
    VendorListItem,
    VendorNoteCreate,
    VendorNoteResponse,
    VendorResponse,
    VendorStats,
    VendorUpdate,
)
from app.services import vendor_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _note_to_response(note) -> dict:
    data = VendorNoteResponse.model_validate(note).model_dump()
    if note.author:
        data["created_by_name"] = f"{note.author.first_name or ''} {note.author.last_name or ''}".strip() or note.author.email
    else:
        data["created_by_name"] = None
    return data


def _vendor_to_response(vendor) -> dict:
    data = VendorResponse.model_validate(vendor).model_dump()
    data["contacts"] = [
        VendorContactResponse.model_validate(c).model_dump()
        for c in (vendor.contacts or [])
    ]
    data["recent_notes"] = [
        _note_to_response(n) for n in (vendor.vendor_notes or [])[:10]
    ]
    return data


# ---------------------------------------------------------------------------
# Vendor endpoints
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=VendorStats)
def vendor_stats(
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("vendors.view")),
):
    return vendor_service.get_vendor_stats(db, current_user.company_id)


@router.get("", response_model=PaginatedVendors)
def list_vendors(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    vendor_status: str | None = Query(None),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("vendors.view")),
):
    result = vendor_service.get_vendors(
        db,
        current_user.company_id,
        page,
        per_page,
        search,
        vendor_status,
        include_inactive,
    )
    return {
        "items": [
            VendorListItem.model_validate(v).model_dump()
            for v in result["items"]
        ],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }


@router.post("", status_code=201)
def create_vendor(
    data: VendorCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("vendors.create")),
):
    vendor = vendor_service.create_vendor(
        db, data, current_user.company_id, actor_id=current_user.id
    )
    db.refresh(vendor)
    return _vendor_to_response(vendor)


@router.post("/import", response_model=VendorImportResult)
async def import_csv(
    file: UploadFile,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("vendors.create")),
):
    content = await file.read()
    result = vendor_service.import_vendors_from_csv(
        db, content, current_user.company_id, actor_id=current_user.id
    )
    return result


@router.get("/{vendor_id}")
def read_vendor(
    vendor_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("vendors.view")),
):
    vendor = vendor_service.get_vendor(
        db, vendor_id, current_user.company_id
    )
    return _vendor_to_response(vendor)


@router.patch("/{vendor_id}")
def update_vendor(
    vendor_id: str,
    data: VendorUpdate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("vendors.edit")),
):
    vendor = vendor_service.update_vendor(
        db, vendor_id, data, current_user.company_id, actor_id=current_user.id
    )
    db.refresh(vendor)
    return _vendor_to_response(vendor)


@router.delete("/{vendor_id}")
def delete_vendor(
    vendor_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("vendors.delete")),
):
    vendor_service.deactivate_vendor(
        db, vendor_id, current_user.company_id, actor_id=current_user.id
    )
    return {"detail": "Vendor deactivated"}


# ---------------------------------------------------------------------------
# Contact endpoints
# ---------------------------------------------------------------------------


@router.get("/{vendor_id}/contacts", response_model=list[VendorContactResponse])
def list_contacts(
    vendor_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("vendors.view")),
):
    contacts = vendor_service.get_vendor_contacts(
        db, vendor_id, current_user.company_id
    )
    return [VendorContactResponse.model_validate(c).model_dump() for c in contacts]


@router.post("/{vendor_id}/contacts", status_code=201)
def create_contact(
    vendor_id: str,
    data: VendorContactCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("vendors.edit")),
):
    contact = vendor_service.create_vendor_contact(
        db, vendor_id, data, current_user.company_id
    )
    return VendorContactResponse.model_validate(contact).model_dump()


@router.patch("/{vendor_id}/contacts/{contact_id}")
def update_contact(
    vendor_id: str,
    contact_id: str,
    data: VendorContactUpdate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("vendors.edit")),
):
    contact = vendor_service.update_vendor_contact(
        db, contact_id, data, current_user.company_id
    )
    return VendorContactResponse.model_validate(contact).model_dump()


@router.delete("/{vendor_id}/contacts/{contact_id}")
def delete_contact(
    vendor_id: str,
    contact_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("vendors.edit")),
):
    vendor_service.delete_vendor_contact(
        db, contact_id, current_user.company_id
    )
    return {"detail": "Contact deleted"}


# ---------------------------------------------------------------------------
# Note endpoints
# ---------------------------------------------------------------------------


@router.get("/{vendor_id}/notes")
def list_notes(
    vendor_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("vendors.view")),
):
    result = vendor_service.get_vendor_notes(
        db, vendor_id, current_user.company_id, page, per_page
    )
    return {
        "items": [_note_to_response(n) for n in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }


@router.post("/{vendor_id}/notes", status_code=201)
def create_note(
    vendor_id: str,
    data: VendorNoteCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("vendors.edit")),
):
    note = vendor_service.create_vendor_note(
        db, vendor_id, data, current_user.company_id, actor_id=current_user.id
    )
    return _note_to_response(note)
