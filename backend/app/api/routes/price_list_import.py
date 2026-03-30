"""Price List Import routes — AI-powered price list extraction and matching."""

import logging
import re
import threading
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.company_resolver import get_current_company
from app.api.deps import get_current_user
from app.database import SessionLocal, get_db
from app.models.charge_library_item import ChargeLibraryItem
from app.models.company import Company
from app.models.price_list_import import PriceListImport, PriceListImportItem
from app.models.product import Product
from app.models.product_bundle import ProductBundle
from app.models.user import User
from app.schemas.price_list_import import (
    PriceListConfirmResponse,
    PriceListImportItemResponse,
    PriceListImportResponse,
    PriceListItemUpdate,
)
from app.services.price_list_extraction_service import extract_text_from_file

logger = logging.getLogger(__name__)
router = APIRouter()

FILE_TYPE_MAP = {
    ".xlsx": "excel",
    ".xls": "excel",
    ".csv": "csv",
    ".pdf": "pdf",
    ".docx": "word",
    ".doc": "word",
}


def _run_analysis_bg(import_id: str) -> None:
    """Run Claude analysis in a background thread with its own DB session."""
    from app.services.price_list_analysis_service import analyze_price_list

    db = SessionLocal()
    try:
        analyze_price_list(db, import_id)
    except Exception:
        logger.exception("Background analysis failed for import %s", import_id)
        # Ensure the import is marked as failed so the UI stops spinning
        try:
            db.rollback()
            imp = (
                db.query(PriceListImport)
                .filter(PriceListImport.id == import_id)
                .first()
            )
            if imp and imp.status not in ("review_ready", "confirmed", "failed"):
                imp.status = "failed"
                imp.error_message = "Analysis crashed unexpectedly. Please retry."
                db.commit()
        except Exception:
            logger.exception("Failed to mark import %s as failed", import_id)
    finally:
        db.close()


@router.post("/price-list-import", response_model=PriceListImportResponse)
def upload_price_list(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Upload a price list file, extract text, and start AI analysis."""
    # Determine file type from extension
    fname = file.filename or "unknown"
    ext = ""
    if "." in fname:
        ext = "." + fname.rsplit(".", 1)[1].lower()
    file_type = FILE_TYPE_MAP.get(ext, "other")

    if file_type == "other":
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext or 'unknown'}. Supported: xlsx, xls, csv, pdf, docx",
        )

    # Read file content
    content = file.file.read()

    # Extract text synchronously (fast)
    try:
        raw_text = extract_text_from_file(content, file_type)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract text: {e}")

    if not raw_text.strip():
        raise HTTPException(
            status_code=400, detail="No text could be extracted from the file."
        )

    # Create import record
    now = datetime.now(timezone.utc)
    imp = PriceListImport(
        id=str(uuid.uuid4()),
        tenant_id=company.id,
        file_name=fname,
        file_type=file_type,
        file_size_bytes=len(content),
        status="extracting",
        raw_extracted_text=raw_text,
        created_at=now,
        updated_at=now,
    )
    db.add(imp)
    imp.status = "extracted"
    db.commit()
    db.refresh(imp)

    # Start Claude analysis in background thread
    thread = threading.Thread(target=_run_analysis_bg, args=(imp.id,), daemon=True)
    thread.start()

    return imp


@router.get(
    "/price-list-import/{import_id}/status",
    response_model=PriceListImportResponse,
)
def get_import_status(
    import_id: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Poll import status and progress counts."""
    imp = (
        db.query(PriceListImport)
        .filter(
            PriceListImport.id == import_id,
            PriceListImport.tenant_id == company.id,
        )
        .first()
    )
    if not imp:
        raise HTTPException(status_code=404, detail="Import not found")
    return imp


@router.get("/price-list-import/{import_id}/review")
def get_import_review(
    import_id: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get all items grouped by match status for review."""
    imp = (
        db.query(PriceListImport)
        .filter(
            PriceListImport.id == import_id,
            PriceListImport.tenant_id == company.id,
        )
        .first()
    )
    if not imp:
        raise HTTPException(status_code=404, detail="Import not found")

    items = (
        db.query(PriceListImportItem)
        .filter(PriceListImportItem.import_id == import_id)
        .order_by(PriceListImportItem.match_status, PriceListImportItem.extracted_name)
        .all()
    )

    grouped = {
        "high_confidence": [],
        "low_confidence": [],
        "unmatched": [],
        "ignored": [],
        "custom": [],
        "charges": [],
    }
    for item in items:
        # Charge items go into charges tab
        if item.charge_category:
            bucket = grouped["charges"]
        elif item.match_status == "bundle":
            bucket = grouped["low_confidence"]
        else:
            bucket = grouped.get(item.match_status, grouped["unmatched"])
        bucket.append(PriceListImportItemResponse.model_validate(item))

    return {
        "import": PriceListImportResponse.model_validate(imp),
        "items": grouped,
    }


@router.patch(
    "/price-list-import/{import_id}/items/{item_id}",
    response_model=PriceListImportItemResponse,
)
def update_import_item(
    import_id: str,
    item_id: str,
    data: PriceListItemUpdate,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Update a single import item (action, names, prices, template match)."""
    item = (
        db.query(PriceListImportItem)
        .filter(
            PriceListImportItem.id == item_id,
            PriceListImportItem.import_id == import_id,
            PriceListImportItem.tenant_id == company.id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Import item not found")

    if data.action is not None:
        item.action = data.action
    if data.final_product_name is not None:
        item.final_product_name = data.final_product_name
    if data.final_price is not None:
        item.final_price = data.final_price
    if data.final_sku is not None:
        item.final_sku = data.final_sku
    if data.matched_template_id is not None:
        item.matched_template_id = data.matched_template_id
    if data.has_conditional_pricing is not None:
        item.has_conditional_pricing = data.has_conditional_pricing
    if data.extracted_price_with_vault is not None:
        item.extracted_price_with_vault = data.extracted_price_with_vault
    if data.extracted_price_standalone is not None:
        item.extracted_price_standalone = data.extracted_price_standalone
    if data.charge_match_type is not None:
        item.charge_match_type = data.charge_match_type
    if data.matched_charge_id is not None:
        item.matched_charge_id = data.matched_charge_id
    if data.charge_key_to_use is not None:
        item.charge_key_to_use = data.charge_key_to_use
    if data.pricing_type_suggestion is not None:
        item.pricing_type_suggestion = data.pricing_type_suggestion
    if data.enable_on_import is not None:
        item.enable_on_import = data.enable_on_import

    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


@router.post("/price-list-import/{import_id}/accept-all")
def accept_all_items(
    import_id: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Bulk set all items action to create_product."""
    imp = (
        db.query(PriceListImport)
        .filter(
            PriceListImport.id == import_id,
            PriceListImport.tenant_id == company.id,
        )
        .first()
    )
    if not imp:
        raise HTTPException(status_code=404, detail="Import not found")

    # Non-charge items → create_product (or create_bundle for bundles)
    db.query(PriceListImportItem).filter(
        PriceListImportItem.import_id == import_id,
        PriceListImportItem.charge_category.is_(None),
        PriceListImportItem.match_status != "bundle",
    ).update({"action": "create_product"})

    # Bundle items → create_bundle
    db.query(PriceListImportItem).filter(
        PriceListImportItem.import_id == import_id,
        PriceListImportItem.match_status == "bundle",
    ).update({"action": "create_bundle"})

    # Charge items → create_custom (add to charge library)
    db.query(PriceListImportItem).filter(
        PriceListImportItem.import_id == import_id,
        PriceListImportItem.charge_category.isnot(None),
    ).update({"action": "create_custom"})

    db.commit()

    return {"message": "All items accepted"}


@router.post(
    "/price-list-import/{import_id}/confirm",
    response_model=PriceListConfirmResponse,
)
def confirm_import(
    import_id: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Create products from confirmed import items."""
    imp = (
        db.query(PriceListImport)
        .filter(
            PriceListImport.id == import_id,
            PriceListImport.tenant_id == company.id,
        )
        .first()
    )
    if not imp:
        raise HTTPException(status_code=404, detail="Import not found")
    if imp.status == "confirmed":
        raise HTTPException(status_code=400, detail="Import already confirmed")

    items = (
        db.query(PriceListImportItem)
        .filter(PriceListImportItem.import_id == import_id)
        .all()
    )

    created = 0
    bundles_created = 0
    skipped = 0
    now = datetime.now(timezone.utc)

    for item in items:
        if item.action == "skip":
            skipped += 1
            continue

        if item.action == "create_bundle":
            # Create as a ProductBundle instead of a Product
            # Determine pricing: conditional or single
            if item.has_conditional_pricing and item.extracted_price_with_vault and item.extracted_price_standalone:
                bundle = ProductBundle(
                    id=str(uuid.uuid4()),
                    company_id=company.id,
                    name=item.final_product_name,
                    sku=item.final_sku,
                    price=item.extracted_price_standalone,  # backward compat
                    has_conditional_pricing=True,
                    standalone_price=item.extracted_price_standalone,
                    with_vault_price=item.extracted_price_with_vault,
                    is_active=True,
                    source="price_list_import",
                    created_by=current_user.id,
                    created_at=now,
                    updated_at=now,
                )
            else:
                bundle = ProductBundle(
                    id=str(uuid.uuid4()),
                    company_id=company.id,
                    name=item.final_product_name,
                    sku=item.final_sku,
                    price=item.final_price,
                    is_active=True,
                    source="price_list_import",
                    created_by=current_user.id,
                    created_at=now,
                    updated_at=now,
                )
            db.add(bundle)
            bundles_created += 1
            continue

        product = Product(
            id=str(uuid.uuid4()),
            company_id=company.id,
            name=item.final_product_name,
            sku=item.final_sku,
            source="price_list_import",
            is_active=True,
            created_by=current_user.id,
            created_at=now,
            updated_at=now,
        )
        # Apply conditional pricing logic
        if item.extracted_price_with_vault is not None and item.extracted_price_standalone is not None:
            product.price = item.extracted_price_with_vault
            product.price_without_our_product = item.extracted_price_standalone
            product.has_conditional_pricing = True
        elif item.is_call_office:
            product.price = None
            product.is_call_office = True
        else:
            product.price = item.final_price
            product.has_conditional_pricing = False
        db.add(product)
        item.product_id = product.id
        created += 1

    # Process charge-type items
    charges_created = 0
    charges_updated = 0
    # Track keys processed in this batch to prevent within-batch duplicates colliding at commit
    _batch_charge_keys: dict[str, ChargeLibraryItem] = {}

    def _apply_charge_fields(target: ChargeLibraryItem, item: "PriceListImportItem") -> None:
        """Update a charge record's fields from an import item."""
        if item.has_conditional_pricing:
            target.has_conditional_pricing = True
            target.with_vault_price = item.extracted_price_with_vault
            target.standalone_price = item.extracted_price_standalone
            target.fixed_amount = item.extracted_price_standalone
        elif item.extracted_price is not None:
            target.fixed_amount = item.extracted_price
        if item.pricing_type_suggestion:
            target.pricing_type = item.pricing_type_suggestion
        target.is_enabled = item.enable_on_import
        target.updated_at = now

    for item in items:
        if item.action not in ("create_custom",) or not item.charge_category:
            continue  # Only process charge-type items with create_custom action

        if item.matched_charge_id:
            # Update existing charge by explicit match ID
            existing_charge = db.query(ChargeLibraryItem).filter(
                ChargeLibraryItem.id == item.matched_charge_id,
            ).first()
            if existing_charge:
                _apply_charge_fields(existing_charge, item)
                charges_updated += 1
                _batch_charge_keys[existing_charge.charge_key] = existing_charge
                continue

        # Resolve charge key
        charge_key = item.charge_key_to_use or item.charge_key_suggestion
        if not charge_key:
            base_key = re.sub(r"[^a-z0-9]+", "_", (item.final_product_name or item.extracted_name).lower()).strip("_")
            charge_key = f"{base_key}_custom"

        # Check within-batch duplicates first (handles case where two import items share the same key)
        if charge_key in _batch_charge_keys:
            _apply_charge_fields(_batch_charge_keys[charge_key], item)
            charges_updated += 1
            continue

        # Check DB for existing record with this key (handles re-imports)
        existing = db.query(ChargeLibraryItem).filter(
            ChargeLibraryItem.tenant_id == company.id,
            ChargeLibraryItem.charge_key == charge_key,
        ).first()
        if existing:
            _apply_charge_fields(existing, item)
            charges_updated += 1
            _batch_charge_keys[charge_key] = existing
            continue

        # Get next sort_order
        max_sort = db.query(func.max(ChargeLibraryItem.sort_order)).filter(
            ChargeLibraryItem.tenant_id == company.id,
        ).scalar() or 0

        new_charge = ChargeLibraryItem(
            id=str(uuid.uuid4()),
            tenant_id=company.id,
            charge_key=charge_key,
            charge_name=item.final_product_name or item.extracted_name,
            category=item.charge_category or "other",
            is_enabled=item.enable_on_import,
            is_system=False,
            pricing_type=item.pricing_type_suggestion or "variable",
            fixed_amount=(
                item.extracted_price_standalone if item.has_conditional_pricing
                else item.extracted_price
            ),
            has_conditional_pricing=item.has_conditional_pricing or False,
            with_vault_price=item.extracted_price_with_vault if item.has_conditional_pricing else None,
            standalone_price=item.extracted_price_standalone if item.has_conditional_pricing else None,
            variable_placeholder=f"Enter {(item.final_product_name or item.extracted_name).lower()} amount",
            invoice_label=item.final_product_name or item.extracted_name,
            sort_order=max_sort + 1,
            created_at=now,
            updated_at=now,
        )
        db.add(new_charge)
        _batch_charge_keys[charge_key] = new_charge
        charges_created += 1

    imp.status = "confirmed"
    imp.confirmed_at = now
    imp.confirmed_by = current_user.id
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("confirm_import db.commit() failed for import %s", import_id)
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    return PriceListConfirmResponse(
        import_id=import_id,
        products_created=created,
        products_skipped=skipped,
        charges_created=charges_created,
        charges_updated=charges_updated,
    )


@router.get("/price-list-imports", response_model=list[PriceListImportResponse])
def list_imports(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """List all price list imports for the current tenant."""
    imports = (
        db.query(PriceListImport)
        .filter(PriceListImport.tenant_id == company.id)
        .order_by(PriceListImport.created_at.desc())
        .all()
    )
    return imports
