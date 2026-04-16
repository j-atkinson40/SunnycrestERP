"""Wilbert Program Management API routes.

Manage Wilbert program enrollments, territories, product selections,
personalization config, fulfillment, permissions, and notifications.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.company_resolver import get_current_company
from app.api.deps import get_current_user
from app.database import get_db
from app.models.company import Company
from app.models.user import User

router = APIRouter()


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class EnrollProgramRequest(BaseModel):
    territory_ids: Optional[list[str]] = None
    uses_vault_territory: Optional[bool] = None
    enabled_product_ids: Optional[list[str]] = None


class UpdateTerritoryRequest(BaseModel):
    territory_ids: list[str]
    uses_vault_territory: bool


class UpdateProductsRequest(BaseModel):
    enabled_product_ids: list[str]


class UpdatePricingModeRequest(BaseModel):
    pricing_mode: str
    flat_fee_amount: Optional[float] = None


class UpdateOptionRequest(BaseModel):
    is_enabled: Optional[bool] = None
    applicable_product_ids: Optional[list[str] | str] = None
    price_addition: Optional[float] = None
    price_overrides_by_product: Optional[dict] = None


class CreateCustomOptionRequest(BaseModel):
    display_name: str
    description: Optional[str] = None
    applicable_product_ids: Optional[list[str] | str] = None
    price_addition: Optional[float] = None
    notes_for_director: Optional[str] = None


class UpdateApprovalRequest(BaseModel):
    workflow: str
    approver_user_id: Optional[str] = None
    family_proof_required: Optional[bool] = None
    family_proof_timeout_hours: Optional[int] = None
    family_proof_timeout_action: Optional[str] = None


class CalculatePriceRequest(BaseModel):
    product_id: str
    selected_option_keys: list[str]


class UpdatePermissionsRequest(BaseModel):
    permissions_config: dict


class UpdateNotificationsRequest(BaseModel):
    notifications_config: dict


class UpdateFulfillmentRequest(BaseModel):
    fulfillment_path: str
    fulfillment_config: Optional[dict] = None


class UpdatePayoutRequest(BaseModel):
    payout_config: dict


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/")
def list_programs(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """List company's enrolled programs."""
    try:
        from app.services.wilbert_program_service import WilbertProgramService

        programs = WilbertProgramService.get_company_programs(db, company.id)
        return {"programs": programs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalog")
def get_program_catalog(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Return the full program catalog with enrollment status for this company."""
    try:
        from app.services.wilbert_program_service import WilbertProgramService

        catalog = WilbertProgramService.get_catalog(db, company.id)
        return {"catalog": catalog}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{code}/enroll", status_code=201)
def enroll_in_program(
    code: str,
    data: EnrollProgramRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Enroll in a Wilbert program."""
    try:
        from app.services.wilbert_program_service import WilbertProgramService

        result = WilbertProgramService.enroll_in_program(
            db,
            company.id,
            code,
            territory_ids=data.territory_ids,
            uses_vault_territory=data.uses_vault_territory,
            enabled_product_ids=data.enabled_product_ids,
        )
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{code}/territory")
def update_program_territory(
    code: str,
    data: UpdateTerritoryRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Update territory for an enrolled program."""
    try:
        from app.services.wilbert_program_service import WilbertProgramService

        result = WilbertProgramService.configure_program_territory(
            db,
            company.id,
            code,
            territory_ids=data.territory_ids,
            uses_vault_territory=data.uses_vault_territory,
        )
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{code}/products")
def update_program_products(
    code: str,
    data: UpdateProductsRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Update enabled products for an enrolled program."""
    try:
        from app.services.wilbert_program_service import WilbertProgramService

        result = WilbertProgramService.configure_program_products(
            db, company.id, code, enabled_product_ids=data.enabled_product_ids
        )
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{code}")
def unenroll_from_program(
    code: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Unenroll from a Wilbert program."""
    try:
        from app.services.wilbert_program_service import WilbertProgramService

        WilbertProgramService.unenroll_from_program(db, company.id, code)
        db.commit()
        return {"status": "ok", "program_code": code}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Personalization config endpoints
# ---------------------------------------------------------------------------


@router.get("/{code}/personalization")
def get_personalization_config(
    code: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get personalization config for a program."""
    from app.services.personalization_config_service import PersonalizationConfigService

    return PersonalizationConfigService.get_config(db, company.id, code)


@router.patch("/{code}/personalization/pricing-mode")
def update_personalization_pricing_mode(
    code: str,
    data: UpdatePricingModeRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Update the pricing mode for personalization."""
    try:
        from app.services.personalization_config_service import PersonalizationConfigService

        result = PersonalizationConfigService.update_pricing_mode(
            db, company.id, code, data.pricing_mode, data.flat_fee_amount
        )
        db.commit()
        return result
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{code}/personalization/options/{option_key:path}")
def update_personalization_option(
    code: str,
    option_key: str,
    data: UpdateOptionRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Update a single personalization option's config."""
    try:
        from app.services.personalization_config_service import PersonalizationConfigService

        result = PersonalizationConfigService.update_option(
            db, company.id, code, option_key,
            is_enabled=data.is_enabled,
            applicable_product_ids=data.applicable_product_ids,
            price_addition=data.price_addition,
            price_overrides_by_product=data.price_overrides_by_product,
        )
        db.commit()
        return result
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{code}/personalization/options/custom", status_code=201)
def create_custom_personalization_option(
    code: str,
    data: CreateCustomOptionRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Create a custom personalization option (tier 4)."""
    try:
        from app.services.personalization_config_service import PersonalizationConfigService

        result = PersonalizationConfigService.create_custom_option(
            db, company.id, code, data.display_name,
            description=data.description,
            applicable_product_ids=data.applicable_product_ids,
            price_addition=data.price_addition,
            notes_for_director=data.notes_for_director,
        )
        db.commit()
        return result
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{code}/personalization/options/{option_key:path}")
def delete_custom_personalization_option(
    code: str,
    option_key: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Delete a custom personalization option. Only works on tier 4 items."""
    from app.services.personalization_config_service import PersonalizationConfigService

    deleted = PersonalizationConfigService.delete_custom_option(
        db, company.id, code, option_key
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Custom option not found or not deletable")
    db.commit()
    return {"deleted": True, "option_key": option_key}


@router.patch("/{code}/personalization/approval")
def update_personalization_approval(
    code: str,
    data: UpdateApprovalRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Update approval workflow settings."""
    try:
        from app.services.personalization_config_service import PersonalizationConfigService

        result = PersonalizationConfigService.update_approval_workflow(
            db, company.id, code, data.workflow,
            approver_user_id=data.approver_user_id,
            family_proof_required=data.family_proof_required,
            family_proof_timeout_hours=data.family_proof_timeout_hours,
            family_proof_timeout_action=data.family_proof_timeout_action,
        )
        db.commit()
        return result
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{code}/personalization/product/{product_id}")
def get_applicable_options_for_product(
    code: str,
    product_id: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get applicable personalization options for a product (Composer use)."""
    from app.services.personalization_config_service import PersonalizationConfigService

    options = PersonalizationConfigService.get_applicable_options_for_product(
        db, company.id, code, product_id
    )
    return {"options": options}


@router.post("/{code}/personalization/calculate-price")
def calculate_personalization_price(
    code: str,
    data: CalculatePriceRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Calculate total personalization price for selected options on a product."""
    from app.services.personalization_config_service import PersonalizationConfigService

    return PersonalizationConfigService.calculate_personalization_price(
        db, company.id, code, data.product_id, data.selected_option_keys
    )


# ---------------------------------------------------------------------------
# General program config endpoints
# ---------------------------------------------------------------------------


@router.patch("/{code}/permissions")
def update_program_permissions(
    code: str,
    data: UpdatePermissionsRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Update per-program role permissions."""
    from app.models import WilbertProgramEnrollment

    enrollment = (
        db.query(WilbertProgramEnrollment)
        .filter(
            WilbertProgramEnrollment.company_id == company.id,
            WilbertProgramEnrollment.program_code == code,
            WilbertProgramEnrollment.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=404, detail="No active enrollment found")

    enrollment.permissions_config = data.permissions_config
    from datetime import datetime, timezone

    enrollment.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"permissions_config": enrollment.permissions_config}


@router.patch("/{code}/notifications")
def update_program_notifications(
    code: str,
    data: UpdateNotificationsRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Update per-program notification preferences."""
    from app.models import WilbertProgramEnrollment

    enrollment = (
        db.query(WilbertProgramEnrollment)
        .filter(
            WilbertProgramEnrollment.company_id == company.id,
            WilbertProgramEnrollment.program_code == code,
            WilbertProgramEnrollment.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=404, detail="No active enrollment found")

    enrollment.notifications_config = data.notifications_config
    from datetime import datetime, timezone

    enrollment.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"notifications_config": enrollment.notifications_config}


@router.patch("/{code}/fulfillment")
def update_program_fulfillment(
    code: str,
    data: UpdateFulfillmentRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Update fulfillment path and optional config for a program."""
    from app.models import WilbertProgramEnrollment

    enrollment = (
        db.query(WilbertProgramEnrollment)
        .filter(
            WilbertProgramEnrollment.company_id == company.id,
            WilbertProgramEnrollment.program_code == code,
            WilbertProgramEnrollment.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=404, detail="No active enrollment found")

    enrollment.fulfillment_path = data.fulfillment_path
    if data.fulfillment_config is not None:
        enrollment.fulfillment_config = data.fulfillment_config
    from datetime import datetime, timezone

    enrollment.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "fulfillment_path": enrollment.fulfillment_path,
        "fulfillment_config": enrollment.fulfillment_config,
    }


@router.patch("/{code}/payout")
def update_program_payout(
    code: str,
    data: UpdatePayoutRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Update payout configuration for digital products."""
    from app.models import WilbertProgramEnrollment

    enrollment = (
        db.query(WilbertProgramEnrollment)
        .filter(
            WilbertProgramEnrollment.company_id == company.id,
            WilbertProgramEnrollment.program_code == code,
            WilbertProgramEnrollment.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=404, detail="No active enrollment found")

    enrollment.payout_config = data.payout_config
    from datetime import datetime, timezone

    enrollment.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"payout_config": enrollment.payout_config}


# ---------------------------------------------------------------------------
# Legacy Prints — per-tenant catalog of Wilbert standard + custom prints
# ---------------------------------------------------------------------------

from decimal import Decimal

from fastapi import File, UploadFile
from app.services import legacy_print_service


class UpdateLegacyPrintRequest(BaseModel):
    is_enabled: Optional[bool] = None
    price_addition: Optional[Decimal] = None


class CreateCustomPrintRequest(BaseModel):
    display_name: str
    description: Optional[str] = None
    file_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    price_addition: Optional[Decimal] = None


def _serialize_print(p) -> dict:
    return {
        "id": p.id,
        "program_code": p.program_code,
        "wilbert_catalog_key": p.wilbert_catalog_key,
        "display_name": p.display_name,
        "description": p.description,
        "file_url": p.file_url,
        "thumbnail_url": p.thumbnail_url,
        "is_enabled": p.is_enabled,
        "is_custom": p.is_custom,
        "price_addition": float(p.price_addition) if p.price_addition is not None else None,
        "sort_order": p.sort_order,
    }


@router.get("/{code}/legacy-prints")
def list_legacy_prints(
    code: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    prints = legacy_print_service.list_prints(db, company.id, code)
    return {
        "wilbert_catalog": [_serialize_print(p) for p in prints if not p.is_custom],
        "custom": [_serialize_print(p) for p in prints if p.is_custom],
    }


@router.patch("/{code}/legacy-prints/{print_id}")
def update_legacy_print(
    code: str,
    print_id: str,
    data: UpdateLegacyPrintRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    try:
        if data.is_enabled is not None:
            legacy_print_service.set_enabled(db, company.id, print_id, data.is_enabled)
        if data.price_addition is not None:
            legacy_print_service.set_price(db, company.id, print_id, data.price_addition)
        p = legacy_print_service.get_print(db, company.id, print_id)
        if not p:
            raise HTTPException(status_code=404, detail="Legacy print not found")
        return _serialize_print(p)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{code}/legacy-prints/custom")
def create_custom_legacy_print(
    code: str,
    data: CreateCustomPrintRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Create a custom Legacy print record.

    For file upload, call POST /{code}/legacy-prints/upload first to get file_url,
    then call this endpoint with the resulting URL.
    """
    p = legacy_print_service.create_custom(
        db=db,
        company_id=company.id,
        program_code=code,
        display_name=data.display_name,
        description=data.description,
        file_url=data.file_url,
        thumbnail_url=data.thumbnail_url,
        price_addition=data.price_addition,
    )
    return _serialize_print(p)


@router.delete("/{code}/legacy-prints/{print_id}")
def delete_legacy_print(
    code: str,
    print_id: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    try:
        ok = legacy_print_service.delete_custom(db, company.id, print_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Legacy print not found")
        return {"deleted": True}
    except ValueError as e:
        # e.g. tried to delete a Wilbert catalog print
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{code}/legacy-prints/enable-all")
def enable_all_wilbert_prints(
    code: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    count = legacy_print_service.enable_all_wilbert(db, company.id, code)
    return {"updated": count}


@router.post("/{code}/legacy-prints/disable-all")
def disable_all_wilbert_prints(
    code: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    count = legacy_print_service.disable_all_wilbert(db, company.id, code)
    return {"updated": count}


@router.post("/{code}/legacy-prints/upload")
async def upload_legacy_print_file(
    code: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Upload a custom Legacy print file. Returns {file_url, thumbnail_url}.

    Validates file type (PNG, PDF, TIFF only). Storage destination depends
    on deployed blob storage (R2 in production); for now the route returns
    a placeholder until a storage adapter is wired in.
    """
    ALLOWED_TYPES = {
        "image/png",
        "application/pdf",
        "image/tiff",
        "image/x-tiff",
    }
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. "
                   "Accepted: PNG, PDF, TIFF.",
        )
    # Read file to check size (max 25MB)
    contents = await file.read()
    if len(contents) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 25MB maximum size.")

    # Storage adapter not yet wired — return placeholder so the UI can be tested end-to-end.
    # Wiring R2 upload here would duplicate existing URN catalog image handling.
    # Follow-up task: integrate with R2 via the same service used for urn catalog images.
    return {
        "file_url": None,
        "thumbnail_url": None,
        "filename": file.filename,
        "size_bytes": len(contents),
        "content_type": file.content_type,
        "note": "Upload endpoint accepted the file, but blob storage wiring is pending. "
                "Use POST /{code}/legacy-prints/custom with a manually-hosted URL in the meantime.",
    }
