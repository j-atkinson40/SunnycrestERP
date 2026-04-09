"""Urn Sales extension — API routes."""

import base64
import csv
import io
import tempfile
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_admin, require_extension
from app.models.user import User
from app.schemas.urns import (
    AncillaryItemResponse,
    CatalogIngestionRequest,
    CatalogIngestionResponse,
    CatalogSyncLogResponse,
    CorrectionSummaryResponse,
    DropShipFeedItemResponse,
    FHApprovalRequest,
    FHChangeRequest,
    UrnBulkMarkupRequest,
    UrnBulkMarkupResponse,
    UrnEngravingJobResponse,
    UrnEngravingSpecsUpdate,
    UrnOrderCreate,
    UrnOrderFromExtraction,
    UrnOrderResponse,
    UrnPriceImportRequest,
    UrnPriceImportResponse,
    UrnPricingUpdate,
    UrnProductCreate,
    UrnProductResponse,
    UrnProductSearchResult,
    UrnProductUpdate,
    UrnTenantSettingsResponse,
    UrnTenantSettingsUpdate,
)

router = APIRouter()

urn_ext = require_extension("urn_sales")


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


@router.get("/products", response_model=list[UrnProductResponse])
def list_products(
    source_type: str | None = None,
    material: str | None = None,
    active: bool | None = True,
    discontinued: bool | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_product_service import UrnProductService

    return UrnProductService.list_products(
        db, current_user.company_id,
        source_type=source_type, material=material,
        active=active, discontinued=discontinued,
        limit=limit, offset=offset,
    )


@router.get("/products/search", response_model=list[UrnProductSearchResult])
def search_products(
    q: str = Query(..., min_length=1),
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_product_service import UrnProductService

    results = UrnProductService.search_products(db, current_user.company_id, q)
    return [
        UrnProductSearchResult(
            id=r["product"].id,
            name=r["product"].name,
            sku=r["product"].sku,
            source_type=r["product"].source_type,
            material=r["product"].material,
            style=r["product"].style,
            retail_price=r["product"].retail_price,
            image_url=r["product"].image_url,
            match_score=r["match_score"],
            availability_note=r["availability_note"],
        )
        for r in results
    ]


@router.get("/products/{product_id}", response_model=UrnProductResponse)
def get_product(
    product_id: str,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_product_service import UrnProductService

    return UrnProductService.get_product(db, current_user.company_id, product_id)


@router.post("/products", response_model=UrnProductResponse, status_code=201)
def create_product(
    data: UrnProductCreate,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_product_service import UrnProductService

    return UrnProductService.create_product(db, current_user.company_id, data)


@router.patch("/products/{product_id}", response_model=UrnProductResponse)
def update_product(
    product_id: str,
    data: UrnProductUpdate,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_product_service import UrnProductService

    return UrnProductService.update_product(
        db, current_user.company_id, product_id, data,
    )


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------


@router.get("/orders", response_model=list[UrnOrderResponse])
def list_orders(
    status: str | None = None,
    funeral_home_id: str | None = None,
    fulfillment_type: str | None = None,
    need_by_start: date | None = None,
    need_by_end: date | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_order_service import UrnOrderService

    orders = UrnOrderService.list_orders(
        db, current_user.company_id,
        status_filter=status, funeral_home_id=funeral_home_id,
        fulfillment_type=fulfillment_type,
        need_by_start=need_by_start, need_by_end=need_by_end,
        limit=limit, offset=offset,
    )
    return [_serialize_order(o) for o in orders]


@router.get("/orders/search")
def search_orders(
    fh_id: str | None = None,
    decedent_name: str | None = None,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_order_service import UrnOrderService

    orders = UrnOrderService.search_orders(
        db, current_user.company_id,
        fh_id=fh_id, decedent_name=decedent_name,
    )
    return [_serialize_order(o) for o in orders]


@router.get("/orders/{order_id}", response_model=UrnOrderResponse)
def get_order(
    order_id: str,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_order_service import UrnOrderService

    order = UrnOrderService.get_order(db, current_user.company_id, order_id)
    return _serialize_order(order)


@router.post("/orders", response_model=UrnOrderResponse, status_code=201)
def create_order(
    data: UrnOrderCreate,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_order_service import UrnOrderService

    order = UrnOrderService.create_order(
        db, current_user.company_id, data.model_dump(),
        intake_channel="manual", created_by=current_user.id,
    )
    return _serialize_order(order)


@router.post("/orders/from-extraction", status_code=201)
def create_order_from_extraction(
    data: UrnOrderFromExtraction,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_order_service import UrnOrderService

    return UrnOrderService.create_draft_from_extraction(
        db, current_user.company_id, data.model_dump(),
        intake_channel="call_intelligence",
    )


@router.post("/orders/{order_id}/confirm", response_model=UrnOrderResponse)
def confirm_order(
    order_id: str,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_order_service import UrnOrderService

    order = UrnOrderService.confirm_order(db, current_user.company_id, order_id)
    return _serialize_order(order)


@router.post("/orders/{order_id}/cancel", response_model=UrnOrderResponse)
def cancel_order(
    order_id: str,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_order_service import UrnOrderService

    order = UrnOrderService.cancel_order(db, current_user.company_id, order_id)
    return _serialize_order(order)


@router.post("/orders/{order_id}/delivered", response_model=UrnOrderResponse)
def mark_delivered(
    order_id: str,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_order_service import UrnOrderService

    order = UrnOrderService.mark_delivered(db, current_user.company_id, order_id)
    return _serialize_order(order)


# ---------------------------------------------------------------------------
# Engraving
# ---------------------------------------------------------------------------


@router.get("/orders/{order_id}/engraving", response_model=list[UrnEngravingJobResponse])
def get_engraving_jobs(
    order_id: str,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_engraving_service import UrnEngravingService

    return UrnEngravingService.get_jobs_for_order(
        db, current_user.company_id, order_id,
    )


@router.patch(
    "/engraving/{job_id}/specs",
    response_model=UrnEngravingJobResponse,
)
def update_engraving_specs(
    job_id: str,
    data: UrnEngravingSpecsUpdate,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_engraving_service import UrnEngravingService

    return UrnEngravingService.update_specs(
        db, current_user.company_id, job_id, data.model_dump(exclude_unset=True),
    )


@router.post("/orders/{order_id}/wilbert-form")
def generate_wilbert_form(
    order_id: str,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_engraving_service import UrnEngravingService

    result = UrnEngravingService.generate_wilbert_form(
        db, current_user.company_id, order_id,
    )
    pdf_bytes = result.pop("pdf_bytes", None)
    pdf_b64 = base64.b64encode(pdf_bytes).decode() if pdf_bytes else None
    return {
        "order_id": result["order_id"],
        "entries": result["entries"],
        "pdf_base64": pdf_b64,
    }


@router.post("/orders/{order_id}/wilbert-form/pdf")
def download_wilbert_form_pdf(
    order_id: str,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_engraving_service import UrnEngravingService

    result = UrnEngravingService.generate_wilbert_form(
        db, current_user.company_id, order_id,
    )
    pdf_bytes = result.get("pdf_bytes", b"")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="engraving-{order_id[:8]}.pdf"'},
    )


@router.post("/orders/{order_id}/submit-to-wilbert", response_model=UrnOrderResponse)
def submit_to_wilbert(
    order_id: str,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_engraving_service import UrnEngravingService

    order = UrnEngravingService.submit_to_wilbert(
        db, current_user.company_id, order_id,
    )
    return _serialize_order(order)


@router.post(
    "/engraving/{job_id}/upload-proof",
    response_model=UrnEngravingJobResponse,
)
def upload_proof(
    job_id: str,
    file_id: str = Query(...),
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_engraving_service import UrnEngravingService

    return UrnEngravingService.upload_proof(
        db, current_user.company_id, job_id, file_id,
    )


@router.post(
    "/engraving/{job_id}/send-fh-approval",
    response_model=UrnEngravingJobResponse,
)
def send_fh_approval_email(
    job_id: str,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_engraving_service import UrnEngravingService

    return UrnEngravingService.send_fh_approval_email(
        db, current_user.company_id, job_id,
    )


@router.post(
    "/engraving/{job_id}/staff-approve",
    response_model=UrnEngravingJobResponse,
)
def staff_approve_proof(
    job_id: str,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_engraving_service import UrnEngravingService

    return UrnEngravingService.staff_approve_proof(
        db, current_user.company_id, job_id, current_user.id,
    )


@router.post(
    "/engraving/{job_id}/staff-reject",
    response_model=UrnEngravingJobResponse,
)
def staff_reject_proof(
    job_id: str,
    notes: str = Query(...),
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_engraving_service import UrnEngravingService

    return UrnEngravingService.staff_reject_proof(
        db, current_user.company_id, job_id, notes,
    )


@router.get("/engraving/{job_id}/correction-summary", response_model=CorrectionSummaryResponse)
def get_correction_summary(
    job_id: str,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_engraving_service import UrnEngravingService

    return UrnEngravingService.get_correction_summary(
        db, current_user.company_id, job_id,
    )


@router.post(
    "/engraving/{job_id}/verbal-approval",
    response_model=UrnEngravingJobResponse,
)
def attach_verbal_approval(
    job_id: str,
    transcript_excerpt: str = Query(...),
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_engraving_service import UrnEngravingService

    return UrnEngravingService.attach_verbal_approval(
        db, current_user.company_id, job_id, transcript_excerpt,
    )


@router.post(
    "/engraving/{job_id}/verbal-change-request",
    response_model=UrnEngravingJobResponse,
)
def attach_verbal_change_request(
    job_id: str,
    notes: str = Query(...),
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_engraving_service import UrnEngravingService

    return UrnEngravingService.attach_verbal_change_request(
        db, current_user.company_id, job_id, notes,
    )


# ---------------------------------------------------------------------------
# FH proof approval (public, token-validated — no auth required)
# ---------------------------------------------------------------------------


@router.get("/proof-approval/{token}")
def get_proof_for_approval(
    token: str,
    db: Session = Depends(get_db),
):
    from app.services.urn_engraving_service import UrnEngravingService

    job = UrnEngravingService._get_job_by_token(db, token)
    return {
        "job_id": job.id,
        "piece_label": job.piece_label,
        "engraving_line_1": job.engraving_line_1,
        "engraving_line_2": job.engraving_line_2,
        "engraving_line_3": job.engraving_line_3,
        "engraving_line_4": job.engraving_line_4,
        "font_selection": job.font_selection,
        "color_selection": job.color_selection,
        "proof_file_id": job.proof_file_id,
    }


@router.post("/proof-approval/{token}/approve")
def fh_approve_proof(
    token: str,
    data: FHApprovalRequest,
    db: Session = Depends(get_db),
):
    from app.services.urn_engraving_service import UrnEngravingService

    job = UrnEngravingService.process_fh_approval(
        db, token, data.approved_by_name, data.approved_by_email,
    )
    return {"status": "approved", "job_id": job.id}


@router.post("/proof-approval/{token}/request-changes")
def fh_request_changes(
    token: str,
    data: FHChangeRequest,
    db: Session = Depends(get_db),
):
    from app.services.urn_engraving_service import UrnEngravingService

    job = UrnEngravingService.process_fh_change_request(db, token, data.notes)
    return {"status": "changes_requested", "job_id": job.id}


# ---------------------------------------------------------------------------
# Scheduling board integration
# ---------------------------------------------------------------------------


@router.get("/scheduling/ancillary-items", response_model=list[AncillaryItemResponse])
def get_ancillary_items(
    reference_date: date = Query(...),
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_order_service import UrnOrderService

    orders = UrnOrderService.get_ancillary_items_for_scheduling(
        db, current_user.company_id, reference_date,
    )
    return [
        AncillaryItemResponse(
            order_id=o.id,
            urn_name=o.urn_product.name if o.urn_product else "Unknown",
            quantity=o.quantity,
            funeral_home_name=o.funeral_home.name if o.funeral_home else None,
            need_by_date=o.need_by_date,
            status=o.status,
        )
        for o in orders
    ]


@router.get("/scheduling/drop-ship-feed", response_model=list[DropShipFeedItemResponse])
def get_drop_ship_feed(
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_order_service import UrnOrderService

    orders = UrnOrderService.get_drop_ship_visibility_feed(
        db, current_user.company_id,
    )
    return [
        DropShipFeedItemResponse(
            order_id=o.id,
            urn_name=o.urn_product.name if o.urn_product else "Unknown",
            funeral_home_name=o.funeral_home.name if o.funeral_home else None,
            status=o.status,
            expected_arrival_date=o.expected_arrival_date,
            tracking_number=o.tracking_number,
            wilbert_order_ref=o.wilbert_order_ref,
        )
        for o in orders
    ]


# ---------------------------------------------------------------------------
# Catalog ingestion (PDF + web)
# ---------------------------------------------------------------------------


@router.post("/catalog/ingest-pdf", response_model=CatalogIngestionResponse)
def ingest_from_pdf(
    file: UploadFile = File(...),
    enrich_from_website: bool = Query(False),
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    """Upload a Wilbert catalog PDF and ingest all products."""
    from app.services.wilbert_ingestion_service import WilbertIngestionService

    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        content = file.file.read()
        tmp.write(content)
        tmp_path = tmp.name

    log = WilbertIngestionService.ingest_from_pdf(
        db, current_user.company_id, tmp_path,
        enrich_from_website=enrich_from_website,
    )

    # Clean up temp file
    import os
    try:
        os.unlink(tmp_path)
    except OSError:
        pass

    return CatalogIngestionResponse(
        sync_log_id=log.id,
        products_added=log.products_added,
        products_updated=log.products_updated,
        products_skipped=log.products_skipped,
        status=log.status,
    )


@router.post("/catalog/enrich-from-web", response_model=CatalogSyncLogResponse)
def enrich_from_website(
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    """Enrich existing products with descriptions and images from wilbert.com."""
    from app.models.urn_catalog_sync_log import UrnCatalogSyncLog as SyncLog
    from app.services.urn_catalog_scraper import UrnCatalogScraper
    from app.models.urn_product import UrnProduct
    from datetime import datetime, timezone

    log = SyncLog(
        tenant_id=current_user.company_id,
        status="running",
        sync_type="website",
    )
    db.add(log)
    db.commit()

    try:
        products = (
            db.query(UrnProduct)
            .filter(
                UrnProduct.tenant_id == current_user.company_id,
                UrnProduct.source_type == "drop_ship",
                UrnProduct.is_active == True,
            )
            .all()
        )

        enriched, not_found = UrnCatalogScraper.enrich_products_from_web(
            db, current_user.company_id, products
        )

        log.products_updated = enriched
        log.products_skipped = not_found
        log.status = "completed"
        log.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        db.rollback()
        log = db.query(SyncLog).filter(SyncLog.id == log.id).first()
        if log:
            log.status = "failed"
            log.error_message = str(e)[:2000]
            log.completed_at = datetime.now(timezone.utc)
            db.commit()

    return log


# ---------------------------------------------------------------------------
# Pricing management
# ---------------------------------------------------------------------------


@router.patch("/products/{product_id}/pricing", response_model=UrnProductResponse)
def update_product_pricing(
    product_id: str,
    data: UrnPricingUpdate,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    """Update cost and/or retail price for a single product."""
    from app.services.urn_product_service import UrnProductService

    product = UrnProductService.get_product(db, current_user.company_id, product_id)

    if data.base_cost is not None:
        product.base_cost = data.base_cost
    if data.retail_price is not None:
        product.retail_price = data.retail_price

    db.commit()
    db.refresh(product)
    return product


@router.post("/pricing/bulk-markup", response_model=UrnBulkMarkupResponse)
def apply_bulk_markup(
    data: UrnBulkMarkupRequest,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    """Apply markup percentage to products' base_cost → retail_price."""
    from app.services.wilbert_ingestion_service import WilbertIngestionService

    updated, skipped = WilbertIngestionService.apply_bulk_markup(
        db, current_user.company_id,
        markup_percent=data.markup_percent,
        rounding=data.rounding,
        material=data.material,
        product_type=data.product_type,
        only_unpriced=data.only_unpriced,
    )
    db.commit()
    return UrnBulkMarkupResponse(updated_count=updated, skipped_count=skipped)


@router.post("/pricing/import-csv", response_model=UrnPriceImportResponse)
def import_prices_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    """Import prices from CSV (columns: sku, base_cost, retail_price)."""
    from app.services.wilbert_ingestion_service import WilbertIngestionService
    from decimal import Decimal, InvalidOperation

    content = file.file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))

    rows = []
    for row in reader:
        sku = (row.get("sku") or row.get("SKU") or "").strip()
        if not sku:
            continue

        entry = {"sku": sku}
        cost_raw = (row.get("base_cost") or row.get("cost") or row.get("wholesale_cost") or "").strip()
        price_raw = (row.get("retail_price") or row.get("price") or row.get("selling_price") or "").strip()

        try:
            if cost_raw:
                entry["base_cost"] = float(cost_raw.replace("$", "").replace(",", ""))
            if price_raw:
                entry["retail_price"] = float(price_raw.replace("$", "").replace(",", ""))
        except (ValueError, InvalidOperation):
            continue

        rows.append(entry)

    result = WilbertIngestionService.import_prices_from_csv(
        db, current_user.company_id, rows,
    )
    db.commit()

    return UrnPriceImportResponse(
        matched=result["matched"],
        updated=result["updated"],
        not_found=result["not_found"],
    )


@router.post("/pricing/import-json", response_model=UrnPriceImportResponse)
def import_prices_json(
    data: UrnPriceImportRequest,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    """Import prices from JSON payload."""
    from app.services.wilbert_ingestion_service import WilbertIngestionService

    rows = [r.model_dump() for r in data.rows]
    result = WilbertIngestionService.import_prices_from_csv(
        db, current_user.company_id, rows,
    )
    db.commit()

    return UrnPriceImportResponse(
        matched=result["matched"],
        updated=result["updated"],
        not_found=result["not_found"],
    )


# ---------------------------------------------------------------------------
# Catalog sync log
# ---------------------------------------------------------------------------


@router.get("/catalog/sync-log", response_model=list[CatalogSyncLogResponse])
def get_sync_logs(
    limit: int = Query(20, le=100),
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.models.urn_catalog_sync_log import UrnCatalogSyncLog

    return (
        db.query(UrnCatalogSyncLog)
        .filter(UrnCatalogSyncLog.tenant_id == current_user.company_id)
        .order_by(UrnCatalogSyncLog.started_at.desc())
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# Intake agent
# ---------------------------------------------------------------------------


@router.post("/intake/email")
def process_intake_email(
    email_data: dict,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_intake_agent import UrnIntakeAgent

    return UrnIntakeAgent.process_intake_email(
        db, current_user.company_id, email_data,
    )


@router.post("/intake/match-proof")
def match_proof_email(
    email_data: dict,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.services.urn_intake_agent import UrnIntakeAgent

    return UrnIntakeAgent.match_proof_email(
        db, current_user.company_id, email_data,
    )


# ---------------------------------------------------------------------------
# Tenant settings
# ---------------------------------------------------------------------------


@router.get("/settings", response_model=UrnTenantSettingsResponse)
def get_urn_settings(
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.models.urn_tenant_settings import UrnTenantSettings

    settings = (
        db.query(UrnTenantSettings)
        .filter(UrnTenantSettings.tenant_id == current_user.company_id)
        .first()
    )
    if not settings:
        settings = UrnTenantSettings(tenant_id=current_user.company_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.patch("/settings", response_model=UrnTenantSettingsResponse)
def update_urn_settings(
    data: UrnTenantSettingsUpdate,
    current_user: User = Depends(urn_ext),
    db: Session = Depends(get_db),
):
    from app.models.urn_tenant_settings import UrnTenantSettings

    settings = (
        db.query(UrnTenantSettings)
        .filter(UrnTenantSettings.tenant_id == current_user.company_id)
        .first()
    )
    if not settings:
        settings = UrnTenantSettings(tenant_id=current_user.company_id)
        db.add(settings)
        db.flush()

    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(settings, key, val)

    db.commit()
    db.refresh(settings)
    return settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_order(order) -> dict:
    """Build UrnOrderResponse-compatible dict from ORM order."""
    return {
        "id": order.id,
        "tenant_id": order.tenant_id,
        "case_id": order.case_id,
        "funeral_home_id": order.funeral_home_id,
        "funeral_home_name": order.funeral_home.name if order.funeral_home else None,
        "fh_contact_email": order.fh_contact_email,
        "urn_product_id": order.urn_product_id,
        "urn_product_name": order.urn_product.name if order.urn_product else None,
        "fulfillment_type": order.fulfillment_type,
        "quantity": order.quantity,
        "need_by_date": order.need_by_date,
        "delivery_method": order.delivery_method,
        "status": order.status,
        "wilbert_order_ref": order.wilbert_order_ref,
        "tracking_number": order.tracking_number,
        "expected_arrival_date": order.expected_arrival_date,
        "unit_cost": order.unit_cost,
        "unit_retail": order.unit_retail,
        "intake_channel": order.intake_channel,
        "notes": order.notes,
        "is_active": order.is_active,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "engraving_jobs": [
            {
                "id": j.id,
                "urn_order_id": j.urn_order_id,
                "piece_label": j.piece_label,
                "engraving_line_1": j.engraving_line_1,
                "engraving_line_2": j.engraving_line_2,
                "engraving_line_3": j.engraving_line_3,
                "engraving_line_4": j.engraving_line_4,
                "font_selection": j.font_selection,
                "color_selection": j.color_selection,
                "photo_file_id": j.photo_file_id,
                "proof_status": j.proof_status,
                "proof_file_id": j.proof_file_id,
                "proof_received_at": j.proof_received_at,
                "fh_approved_by_name": j.fh_approved_by_name,
                "fh_approved_at": j.fh_approved_at,
                "fh_change_request_notes": j.fh_change_request_notes,
                "approved_by": j.approved_by,
                "approved_at": j.approved_at,
                "rejection_notes": j.rejection_notes,
                "resubmission_count": j.resubmission_count,
                "verbal_approval_flagged": j.verbal_approval_flagged,
                "submitted_at": j.submitted_at,
                "created_at": j.created_at,
            }
            for j in (order.engraving_jobs or [])
        ],
    }
