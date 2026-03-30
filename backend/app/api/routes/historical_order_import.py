"""Historical order import API endpoints.

POST  /historical-orders/parse      — upload file, get preview + import_id
POST  /historical-orders/run        — run import using stored file
GET   /historical-orders/status     — latest completed import for tenant
GET   /historical-orders/top-cemeteries  — top cemeteries from history
DELETE /historical-orders/{import_id}   — rollback a specific import
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.historical_order_import import HistoricalOrder, HistoricalOrderImport
from app.models.user import User
from app.services import historical_order_import_service as svc

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_import(rec: HistoricalOrderImport) -> dict:
    return {
        "import_id": rec.id,
        "status": rec.status,
        "source_filename": rec.source_filename,
        "source_system": rec.source_system,
        "total_rows": rec.total_rows,
        "imported_rows": rec.imported_rows,
        "skipped_rows": rec.skipped_rows,
        "error_rows": rec.error_rows,
        "customers_created": rec.customers_created,
        "customers_matched": rec.customers_matched,
        "cemeteries_created": rec.cemeteries_created,
        "cemeteries_matched": rec.cemeteries_matched,
        "fh_cemetery_pairs_created": rec.fh_cemetery_pairs_created,
        "column_mapping": rec.column_mapping,
        "mapping_confidence": rec.mapping_confidence,
        "warnings": rec.warnings,
        "errors": rec.errors,
        "recommended_templates": rec.recommended_templates,
        "cutover_date": str(rec.cutover_date) if rec.cutover_date else None,
        "started_at": rec.started_at.isoformat() if rec.started_at else None,
        "completed_at": rec.completed_at.isoformat() if rec.completed_at else None,
    }


# ---------------------------------------------------------------------------
# POST /parse  — upload and preview (does NOT run the import)
# ---------------------------------------------------------------------------


@router.post("/parse")
async def parse_order_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a CSV and get a rich preview + detected column mapping.

    Creates an import record in 'mapping' status so the file can be
    referenced by the subsequent /run call without re-uploading.

    Privacy: the 'Family Name' column (decedent names) is flagged as
    skip_privacy and never included in any preview data.
    """
    company_id = current_user.company_id

    # ── Read and validate file ────────────────────────────────────────────────
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = (file.filename or "").lower().rsplit(".", 1)[-1]
    if ext not in ("csv", "txt"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported. Please export your spreadsheet as CSV.",
        )

    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 10 MB limit.")

    # Decode — try UTF-8 first, then latin-1
    try:
        content = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw_bytes.decode("latin-1")

    # ── Parse ────────────────────────────────────────────────────────────────
    try:
        headers, rows = svc.parse_csv_content(content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {exc}") from exc

    if not rows:
        raise HTTPException(status_code=400, detail="File contains no data rows.")

    # ── Detect format ─────────────────────────────────────────────────────────
    sample = rows[:5]
    detection = svc.detect_format(headers, sample, company_id)
    column_mapping = detection["column_mapping"]
    mapping_confidence = detection["mapping_confidence"]
    source_system = detection["source_system"]

    # ── Generate preview ──────────────────────────────────────────────────────
    preview = svc.generate_preview(db, company_id, rows, column_mapping)

    # ── Create import record to store file for /run ───────────────────────────
    import_record = HistoricalOrderImport(
        id=str(uuid.uuid4()),
        company_id=company_id,
        status="mapping",
        source_filename=file.filename,
        source_system=source_system,
        total_rows=len(rows),
        column_mapping=column_mapping,
        mapping_confidence=mapping_confidence,
        warnings=preview["warnings"],
        raw_csv_content=content,
        initiated_by=current_user.id,
    )
    db.add(import_record)
    db.commit()

    return {
        "import_id": import_record.id,
        "format_detected": source_system,
        "total_rows": len(rows),
        "column_mapping": column_mapping,
        "mapping_confidence": mapping_confidence,
        "preview": preview,
        "warnings": preview["warnings"],
    }


# ---------------------------------------------------------------------------
# POST /run  — execute the import
# ---------------------------------------------------------------------------


class RunRequest:
    """Not a Pydantic model — using Form fields to allow future file re-upload."""


@router.post("/run")
def run_order_import(
    import_id: str = Form(...),
    column_mapping: str = Form(...),       # JSON string (user-confirmed)
    cutover_date: str = Form(None),
    create_missing_customers: bool = Form(True),
    create_missing_cemeteries: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run the historical order import using the file stored during /parse.

    Returns a detailed summary when complete.
    """
    company_id = current_user.company_id

    # ── Load import record ────────────────────────────────────────────────────
    import_record = (
        db.query(HistoricalOrderImport)
        .filter(
            HistoricalOrderImport.id == import_id,
            HistoricalOrderImport.company_id == company_id,
        )
        .first()
    )
    if not import_record:
        raise HTTPException(status_code=404, detail="Import record not found.")
    if import_record.status not in ("mapping", "preview"):
        raise HTTPException(
            status_code=409,
            detail=f"Import is in '{import_record.status}' status — cannot re-run.",
        )
    if not import_record.raw_csv_content:
        raise HTTPException(status_code=400, detail="No file content stored. Please re-upload.")

    # ── Parse user-confirmed column mapping ───────────────────────────────────
    try:
        user_mapping: dict = json.loads(column_mapping)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid column_mapping JSON: {exc}") from exc

    # Merge with detected mapping (user's overrides win)
    merged_mapping = {**import_record.column_mapping, **user_mapping}

    # ── Parse cutover date ────────────────────────────────────────────────────
    cutover: date | None = None
    if cutover_date:
        try:
            cutover = date.fromisoformat(cutover_date)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid cutover_date: {cutover_date}")

    # ── Re-parse CSV ──────────────────────────────────────────────────────────
    try:
        _headers, rows = svc.parse_csv_content(import_record.raw_csv_content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to re-parse stored CSV: {exc}") from exc

    # ── Update record status and settings ────────────────────────────────────
    import_record.status = "importing"
    import_record.column_mapping = merged_mapping
    import_record.cutover_date = cutover
    db.flush()

    # ── Run import ────────────────────────────────────────────────────────────
    try:
        summary = svc.run_import(
            db=db,
            import_record=import_record,
            rows=rows,
            column_mapping=merged_mapping,
            create_missing_customers=create_missing_customers,
            create_missing_cemeteries=create_missing_cemeteries,
            cutover_date=cutover,
        )
    except Exception as exc:
        import_record.status = "failed"
        import_record.errors = [str(exc)]
        db.commit()
        logger.error("Historical import failed for company %s: %s", company_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Import failed: {exc}") from exc

    return {
        "status": "complete",
        "import_id": import_id,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# GET /status  — latest completed import
# ---------------------------------------------------------------------------


@router.get("/status")
def get_import_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the latest completed import for this tenant, or null if none."""
    rec = svc.get_latest_import(db, current_user.company_id)
    if not rec:
        return {"import": None}
    return {"import": _serialize_import(rec)}


# ---------------------------------------------------------------------------
# GET /top-cemeteries  — for cemetery setup wizard pre-population
# ---------------------------------------------------------------------------


@router.get("/top-cemeteries")
def top_cemeteries_from_history(
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the most-ordered cemeteries from historical data.

    Used by the cemetery setup wizard to pre-populate entry forms.
    """
    results = svc.get_top_cemeteries_from_history(db, current_user.company_id, limit)
    return {"cemeteries": results}


# ---------------------------------------------------------------------------
# DELETE /{import_id}  — rollback
# ---------------------------------------------------------------------------


@router.delete("/{import_id}", status_code=200)
def rollback_import(
    import_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove all historical_orders rows for this import.

    Does NOT remove customers or cemeteries that were created during import
    since they may already be in active use.
    """
    import_record = (
        db.query(HistoricalOrderImport)
        .filter(
            HistoricalOrderImport.id == import_id,
            HistoricalOrderImport.company_id == current_user.company_id,
        )
        .first()
    )
    if not import_record:
        raise HTTPException(status_code=404, detail="Import not found.")

    deleted = (
        db.query(HistoricalOrder)
        .filter(HistoricalOrder.import_id == import_id)
        .delete(synchronize_session=False)
    )

    import_record.status = "rolled_back"
    db.commit()

    return {
        "detail": f"Rolled back import {import_id}. {deleted} historical order records removed.",
        "rows_removed": deleted,
    }
