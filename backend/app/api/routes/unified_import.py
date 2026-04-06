"""Unified onboarding import wizard API routes.

Prefix: /api/v1/onboarding/import
"""

import csv
import io
import logging
from threading import Thread

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Request/Response schemas ───────────────────────────────────────


class ColumnMappingConfirm(BaseModel):
    column_mapping: dict[str, str]


class MergeClusterRequest(BaseModel):
    primary_staging_id: str


class BulkClassifyRequest(BaseModel):
    staging_ids: list[str]
    customer_type: str
    contractor_type: str | None = None


class SkipSourceRequest(BaseModel):
    source: str  # accounting | order_history | cemetery_csv | funeral_home_csv


# ── Session endpoints ──────────────────────────────────────────────


@router.post("/session/start")
def start_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or return existing unified import session."""
    from app.services.onboarding.unified_import_service import (
        get_or_create_session,
        serialize_session,
    )

    session = get_or_create_session(db, current_user.company_id)
    return serialize_session(session)


@router.get("/session")
def get_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current session state."""
    from app.services.onboarding.unified_import_service import (
        get_session as _get_session,
        serialize_session,
    )

    session = _get_session(db, current_user.company_id)
    if not session:
        raise HTTPException(404, "No import session found. Call POST /session/start first.")
    return serialize_session(session)


@router.post("/session/reset")
def reset_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reset session and all staging data."""
    from app.services.onboarding.unified_import_service import (
        reset_session as _reset_session,
        serialize_session,
    )

    session = _reset_session(db, current_user.company_id)
    return serialize_session(session)


# ── Accounting source endpoints ────────────────────────────────────


@router.post("/accounting/upload-sage")
def upload_sage_files(
    customer_file: UploadFile | None = File(None),
    ar_aging_file: UploadFile | None = File(None),
    vendor_file: UploadFile | None = File(None),
    ap_aging_file: UploadFile | None = File(None),
    coa_file: UploadFile | None = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload Sage 100 export files and ingest into staging."""
    from app.services.data_migration_service import DataMigrationService
    from app.services.onboarding.unified_import_service import (
        get_or_create_session,
        ingest_accounting_customers,
        serialize_session,
    )

    session = get_or_create_session(db, current_user.company_id)

    parsed_customers = []
    result = {"customers": 0, "vendors": 0, "coa": 0, "ar_invoices": 0, "ap_bills": 0}

    svc = DataMigrationService

    if customer_file:
        content = customer_file.file.read()
        parsed = svc.parse_customers(content)
        parsed_customers.extend(parsed)
        result["customers"] = len(parsed)

    if ar_aging_file:
        content = ar_aging_file.file.read()
        invoices, ar_customers = svc.parse_ar_aging(content)
        result["ar_invoices"] = len(invoices)
        # Merge AR customer data (credit limits etc) into parsed customers
        for arc in ar_customers:
            found = False
            for pc in parsed_customers:
                if pc.get("sage_customer_no") == arc.get("sage_customer_no"):
                    pc.update({k: v for k, v in arc.items() if v and not pc.get(k)})
                    found = True
                    break
            if not found:
                parsed_customers.append(arc)

    if parsed_customers:
        count = ingest_accounting_customers(db, session, parsed_customers)
        result["staging_count"] = count

    session.accounting_source = "sage"
    session.accounting_status = "uploaded"
    db.commit()

    return {"result": result, "session": serialize_session(session)}


@router.post("/accounting/connect-qbo")
def connect_qbo(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Initiate QBO OAuth — returns auth URL for frontend redirect."""
    from app.services.accounting.qbo_oauth_service import generate_auth_url
    from app.services.onboarding.unified_import_service import get_or_create_session

    session = get_or_create_session(db, current_user.company_id)
    session.accounting_source = "qbo"
    db.commit()

    auth_url = generate_auth_url(current_user.company_id)
    return {"auth_url": auth_url}


@router.post("/accounting/skip")
def skip_accounting(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Skip accounting import."""
    from app.services.onboarding.unified_import_service import (
        get_or_create_session,
        serialize_session,
    )

    session = get_or_create_session(db, current_user.company_id)
    session.accounting_source = "skip"
    session.accounting_status = "skipped"
    db.commit()
    return serialize_session(session)


# ── Order history endpoint ─────────────────────────────────────────


@router.post("/order-history/upload")
def upload_order_history(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload order history CSV — reuses existing historical order import parse."""
    from app.services.historical_order_import_service import (
        detect_format,
        parse_csv_content,
    )
    from app.services.onboarding.unified_import_service import (
        get_or_create_session,
        serialize_session,
    )

    session = get_or_create_session(db, current_user.company_id)

    content = file.file.read().decode("utf-8-sig", errors="replace")
    headers, rows = parse_csv_content(content)

    if not rows:
        raise HTTPException(400, "No data rows found in file")

    format_info = detect_format(headers, rows[:5], current_user.company_id)

    # Store the raw content for later processing
    from app.models.historical_order_import import HistoricalOrderImport

    import_record = HistoricalOrderImport(
        company_id=current_user.company_id,
        status="preview",
        source_filename=file.filename,
        source_system=format_info.get("source_system", "generic_csv"),
        total_rows=len(rows),
        column_mapping=format_info.get("column_mapping", {}),
        mapping_confidence=format_info.get("mapping_confidence", {}),
        raw_csv_content=content,
    )
    db.add(import_record)

    session.order_history_status = "uploaded"
    session.staging_orders_count = len(rows)
    db.commit()

    return {
        "import_id": import_record.id,
        "format_detected": format_info.get("source_system"),
        "column_mapping": format_info.get("column_mapping", {}),
        "mapping_confidence": format_info.get("mapping_confidence", {}),
        "total_rows": len(rows),
        "preview": rows[:10],
        "session": serialize_session(session),
    }


@router.post("/order-history/skip")
def skip_order_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Skip order history import."""
    from app.services.onboarding.unified_import_service import (
        get_or_create_session,
        serialize_session,
    )

    session = get_or_create_session(db, current_user.company_id)
    session.order_history_status = "skipped"
    db.commit()
    return serialize_session(session)


# ── Cemetery CSV endpoints ─────────────────────────────────────────


@router.post("/cemetery-csv/upload")
def upload_cemetery_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Parse cemetery CSV and return column mapping for confirmation."""
    from app.services.onboarding.csv_column_detector import detect_columns
    from app.services.onboarding.unified_import_service import get_or_create_session

    session = get_or_create_session(db, current_user.company_id)

    content = file.file.read().decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(content))
    headers = reader.fieldnames or []
    rows = [dict(r) for r in reader]

    if not rows:
        raise HTTPException(400, "No data rows found in file")

    mapping = detect_columns(headers, rows[:5], "cemetery")

    # Store raw content for confirm step
    session.cemetery_csv_content = content
    session.cemetery_csv_mapping = mapping
    db.commit()

    needs_confirmation = any(v < 0.80 for v in mapping["confidence"].values()) or bool(
        mapping["unmapped_fields"]
    )

    return {
        "column_mapping": mapping["field_map"],
        "confidence": mapping["confidence"],
        "unmapped_fields": mapping["unmapped_fields"],
        "extra_columns": mapping["extra_columns"],
        "total_rows": len(rows),
        "sample_rows": rows[:5],
        "needs_confirmation": needs_confirmation,
        "available_headers": headers,
    }


@router.post("/cemetery-csv/confirm")
def confirm_cemetery_csv(
    body: ColumnMappingConfirm,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Confirm column mapping and ingest cemetery CSV into staging."""
    from app.services.onboarding.unified_import_service import (
        get_or_create_session,
        ingest_csv_source,
        serialize_session,
    )

    session = get_or_create_session(db, current_user.company_id)
    if not session.cemetery_csv_content:
        raise HTTPException(400, "No cemetery CSV uploaded. Upload first.")

    reader = csv.DictReader(io.StringIO(session.cemetery_csv_content))
    rows = [dict(r) for r in reader]

    count = ingest_csv_source(db, session, "cemetery_csv", rows, body.column_mapping)
    return {"ingested_count": count, "session": serialize_session(session)}


@router.post("/cemetery-csv/skip")
def skip_cemetery_csv(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Skip cemetery CSV import."""
    from app.services.onboarding.unified_import_service import (
        get_or_create_session,
        serialize_session,
    )

    session = get_or_create_session(db, current_user.company_id)
    session.cemetery_csv_status = "skipped"
    db.commit()
    return serialize_session(session)


# ── Funeral home CSV endpoints ─────────────────────────────────────


@router.post("/funeral-home-csv/upload")
def upload_fh_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Parse funeral home CSV and return column mapping for confirmation."""
    from app.services.onboarding.csv_column_detector import detect_columns
    from app.services.onboarding.unified_import_service import get_or_create_session

    session = get_or_create_session(db, current_user.company_id)

    content = file.file.read().decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(content))
    headers = reader.fieldnames or []
    rows = [dict(r) for r in reader]

    if not rows:
        raise HTTPException(400, "No data rows found in file")

    mapping = detect_columns(headers, rows[:5], "funeral_home")

    session.funeral_home_csv_content = content
    session.funeral_home_csv_mapping = mapping
    db.commit()

    needs_confirmation = any(v < 0.80 for v in mapping["confidence"].values()) or bool(
        mapping["unmapped_fields"]
    )

    return {
        "column_mapping": mapping["field_map"],
        "confidence": mapping["confidence"],
        "unmapped_fields": mapping["unmapped_fields"],
        "extra_columns": mapping["extra_columns"],
        "total_rows": len(rows),
        "sample_rows": rows[:5],
        "needs_confirmation": needs_confirmation,
        "available_headers": headers,
    }


@router.post("/funeral-home-csv/confirm")
def confirm_fh_csv(
    body: ColumnMappingConfirm,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Confirm column mapping and ingest funeral home CSV into staging."""
    from app.services.onboarding.unified_import_service import (
        get_or_create_session,
        ingest_csv_source,
        serialize_session,
    )

    session = get_or_create_session(db, current_user.company_id)
    if not session.funeral_home_csv_content:
        raise HTTPException(400, "No funeral home CSV uploaded. Upload first.")

    reader = csv.DictReader(io.StringIO(session.funeral_home_csv_content))
    rows = [dict(r) for r in reader]

    count = ingest_csv_source(db, session, "fh_csv", rows, body.column_mapping)
    return {"ingested_count": count, "session": serialize_session(session)}


@router.post("/funeral-home-csv/skip")
def skip_fh_csv(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Skip funeral home CSV import."""
    from app.services.onboarding.unified_import_service import (
        get_or_create_session,
        serialize_session,
    )

    session = get_or_create_session(db, current_user.company_id)
    session.funeral_home_csv_status = "skipped"
    db.commit()
    return serialize_session(session)


# ── Processing endpoints ───────────────────────────────────────────


@router.post("/process")
def process_sources(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Trigger cross-referencing, classification, and clustering.

    Runs synchronously for now (typically <30s). Returns summary.
    """
    from app.services.onboarding.unified_import_service import (
        get_session as _get_session,
        ingest_order_history_signals,
        process_all_sources,
        serialize_session,
    )

    session = _get_session(db, current_user.company_id)
    if not session:
        raise HTTPException(404, "No import session found")

    # Check at least one source is uploaded
    has_source = any([
        session.accounting_status in ("uploaded", "processed"),
        session.order_history_status in ("uploaded", "processed"),
        session.cemetery_csv_status in ("uploaded", "processed"),
        session.funeral_home_csv_status in ("uploaded", "processed"),
    ])
    if not has_source:
        raise HTTPException(400, "At least one data source must be uploaded before processing")

    # Ingest order history signals if order history was uploaded
    if session.order_history_status == "uploaded":
        try:
            from app.services.historical_order_import_service import get_latest_import, run_import
            from app.models.historical_order_import import HistoricalOrderImport
            from app.services.historical_order_import_service import parse_csv_content

            latest = (
                db.query(HistoricalOrderImport)
                .filter(
                    HistoricalOrderImport.company_id == current_user.company_id,
                    HistoricalOrderImport.status == "preview",
                )
                .order_by(HistoricalOrderImport.created_at.desc())
                .first()
            )
            if latest and latest.raw_csv_content:
                headers, rows = parse_csv_content(latest.raw_csv_content)
                run_import(db, latest, rows, latest.column_mapping or {})
                ingest_order_history_signals(db, session, current_user.company_id)
        except Exception:
            logger.exception("Order history ingest failed, continuing without it")

    summary = process_all_sources(db, session.id)
    db.refresh(session)
    return {"summary": summary, "session": serialize_session(session)}


# ── Review endpoints ───────────────────────────────────────────────


@router.get("/review")
def get_review(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get review queue: clusters and classification groups."""
    from app.services.onboarding.unified_import_service import (
        get_review_data,
        get_session as _get_session,
    )

    session = _get_session(db, current_user.company_id)
    if not session:
        raise HTTPException(404, "No import session found")
    return get_review_data(db, session.id)


@router.post("/review/cluster/{cluster_id}/merge")
def merge_cluster_endpoint(
    cluster_id: str,
    body: MergeClusterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Merge a duplicate cluster into a single record."""
    from app.services.onboarding.unified_import_service import (
        get_session as _get_session,
        merge_cluster,
    )

    session = _get_session(db, current_user.company_id)
    if not session:
        raise HTTPException(404, "No import session found")
    return merge_cluster(db, session.id, cluster_id, body.primary_staging_id)


@router.post("/review/cluster/{cluster_id}/split")
def split_cluster_endpoint(
    cluster_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark cluster members as intentionally separate."""
    from app.services.onboarding.unified_import_service import (
        get_session as _get_session,
        split_cluster,
    )

    session = _get_session(db, current_user.company_id)
    if not session:
        raise HTTPException(404, "No import session found")
    return split_cluster(db, session.id, cluster_id)


@router.post("/review/bulk-classify")
def bulk_classify_endpoint(
    body: BulkClassifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bulk-approve a classification for multiple records."""
    from app.services.onboarding.unified_import_service import (
        bulk_classify,
        get_session as _get_session,
    )

    session = _get_session(db, current_user.company_id)
    if not session:
        raise HTTPException(404, "No import session found")
    return bulk_classify(db, session.id, body.staging_ids, body.customer_type, body.contractor_type)


@router.post("/review/accept-all-high-confidence")
def accept_all_high_confidence(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Accept all suggested merges and classifications with confidence >= 0.90."""
    from app.models.import_staging_company import ImportStagingCompany
    from app.services.onboarding.unified_import_service import (
        get_session as _get_session,
        merge_cluster,
    )

    session = _get_session(db, current_user.company_id)
    if not session:
        raise HTTPException(404, "No import session found")

    # Auto-merge all high-confidence clusters
    clusters = (
        db.query(ImportStagingCompany.cluster_id)
        .filter(
            ImportStagingCompany.session_id == session.id,
            ImportStagingCompany.cluster_id.isnot(None),
            ImportStagingCompany.review_status == "pending",
        )
        .distinct()
        .all()
    )

    merged = 0
    for (cid,) in clusters:
        members = (
            db.query(ImportStagingCompany)
            .filter(
                ImportStagingCompany.session_id == session.id,
                ImportStagingCompany.cluster_id == cid,
            )
            .all()
        )
        # Check if all members have high confidence
        all_high = all(float(m.cross_ref_confidence or m.classification_confidence or 0) >= 0.90 for m in members)
        if all_high:
            primary = next((m for m in members if m.is_cluster_primary), members[0])
            merge_cluster(db, session.id, cid, primary.id)
            merged += 1

    # Auto-approve remaining pending high confidence
    pending = (
        db.query(ImportStagingCompany)
        .filter(
            ImportStagingCompany.session_id == session.id,
            ImportStagingCompany.review_status == "pending",
            ImportStagingCompany.cluster_id.is_(None),
        )
        .all()
    )
    approved = 0
    for row in pending:
        conf = float(row.cross_ref_confidence or row.classification_confidence or 0)
        if conf >= 0.85:
            row.review_status = "approved"
            approved += 1
    db.commit()

    return {"clusters_merged": merged, "records_approved": approved}


# ── Apply endpoint ─────────────────────────────────────────────────


@router.post("/apply")
def apply_import(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Apply all approved staging records to real tables."""
    from app.services.onboarding.unified_import_service import (
        apply_all,
        get_session as _get_session,
        serialize_session,
    )

    session = _get_session(db, current_user.company_id)
    if not session:
        raise HTTPException(404, "No import session found")

    if session.phase not in ("review", "error"):
        raise HTTPException(400, f"Cannot apply in phase '{session.phase}'. Must be in 'review' phase.")

    result = apply_all(db, session.id, current_user.id)
    db.refresh(session)
    return {"result": result, "session": serialize_session(session)}
