"""Price List Import routes — AI-powered price list extraction and matching."""

import logging
import threading
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.company_resolver import get_current_company
from app.api.deps import get_current_user
from app.database import SessionLocal, get_db
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
    }
    for item in items:
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

    db.query(PriceListImportItem).filter(
        PriceListImportItem.import_id == import_id
    ).update({"action": "create_product"})
    db.commit()

    return {"message": "All items set to create_product"}


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
            price=item.final_price,
            source="price_list_import",
            is_active=True,
            created_by=current_user.id,
            created_at=now,
            updated_at=now,
        )
        db.add(product)
        item.product_id = product.id
        created += 1

    imp.status = "confirmed"
    imp.confirmed_at = now
    imp.confirmed_by = current_user.id
    db.commit()

    return PriceListConfirmResponse(
        import_id=import_id,
        products_created=created,
        products_skipped=skipped,
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
