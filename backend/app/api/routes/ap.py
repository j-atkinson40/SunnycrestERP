"""API routes for AP Aging report and Sage export."""

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import require_module, require_permission
from app.database import get_db
from app.models.user import User
from app.services import ap_aging_service, ap_sage_export_service

router = APIRouter()


@router.get("/aging")
def ap_aging(
    as_of_date: str | None = Query(None),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.view")),
):
    """AP aging report with vendor buckets."""
    parsed_date = None
    if as_of_date:
        try:
            parsed_date = datetime.fromisoformat(as_of_date)
            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    rows = ap_aging_service.get_ap_aging(
        db, current_user.company_id, parsed_date
    )

    # Calculate totals
    totals = {
        "current": sum(r["current"] for r in rows),
        "d1_30": sum(r["d1_30"] for r in rows),
        "d31_60": sum(r["d31_60"] for r in rows),
        "d61_90": sum(r["d61_90"] for r in rows),
        "d90_plus": sum(r["d90_plus"] for r in rows),
        "total": sum(r["total"] for r in rows),
    }

    # Serialize Decimals to float for JSON
    for r in rows:
        for k in ("current", "d1_30", "d31_60", "d61_90", "d90_plus", "total"):
            r[k] = float(r[k])
    for k in totals:
        totals[k] = float(totals[k])

    return {"vendors": rows, "totals": totals}


@router.get("/aging/csv")
def ap_aging_csv(
    as_of_date: str | None = Query(None),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.export")),
):
    """Export AP aging to CSV."""
    parsed_date = None
    if as_of_date:
        try:
            parsed_date = datetime.fromisoformat(as_of_date)
            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    rows = ap_aging_service.get_ap_aging(
        db, current_user.company_id, parsed_date
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Vendor", "Current", "1-30", "31-60", "61-90", "90+", "Total"])
    for r in rows:
        writer.writerow([
            r["vendor_name"],
            float(r["current"]),
            float(r["d1_30"]),
            float(r["d31_60"]),
            float(r["d61_90"]),
            float(r["d90_plus"]),
            float(r["total"]),
        ])
    # Totals row
    writer.writerow([
        "TOTAL",
        float(sum(r["current"] for r in rows)),
        float(sum(r["d1_30"] for r in rows)),
        float(sum(r["d31_60"] for r in rows)),
        float(sum(r["d61_90"] for r in rows)),
        float(sum(r["d90_plus"] for r in rows)),
        float(sum(r["total"] for r in rows)),
    ])

    output.seek(0)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=ap_aging_{today}.csv"},
    )


# ---------------------------------------------------------------------------
# Sage export endpoints
# ---------------------------------------------------------------------------


def _parse_date(date_str: str) -> datetime:
    """Parse an ISO date string into a timezone-aware datetime."""
    dt = datetime.fromisoformat(date_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@router.post("/sage-export/bills")
def sage_export_bills(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.export")),
):
    """Generate Sage CSV for vendor bills in date range."""
    csv_str, count, log_id = ap_sage_export_service.generate_bills_csv(
        db,
        current_user.company_id,
        _parse_date(date_from),
        _parse_date(date_to),
        actor_id=current_user.id,
    )
    return {"csv": csv_str, "record_count": count, "sync_log_id": log_id}


@router.get("/sage-export/bills/download")
def sage_export_bills_download(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.export")),
):
    """Download Sage CSV for vendor bills."""
    csv_str, _count, _log_id = ap_sage_export_service.generate_bills_csv(
        db,
        current_user.company_id,
        _parse_date(date_from),
        _parse_date(date_to),
        actor_id=current_user.id,
    )
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return StreamingResponse(
        iter([csv_str]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=ap_bills_sage_{today}.csv"
        },
    )


@router.post("/sage-export/payments")
def sage_export_payments(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.export")),
):
    """Generate Sage CSV for vendor payments in date range."""
    csv_str, count, log_id = ap_sage_export_service.generate_payments_csv(
        db,
        current_user.company_id,
        _parse_date(date_from),
        _parse_date(date_to),
        actor_id=current_user.id,
    )
    return {"csv": csv_str, "record_count": count, "sync_log_id": log_id}


@router.get("/sage-export/payments/download")
def sage_export_payments_download(
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.export")),
):
    """Download Sage CSV for vendor payments."""
    csv_str, _count, _log_id = ap_sage_export_service.generate_payments_csv(
        db,
        current_user.company_id,
        _parse_date(date_from),
        _parse_date(date_to),
        actor_id=current_user.id,
    )
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return StreamingResponse(
        iter([csv_str]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=ap_payments_sage_{today}.csv"
        },
    )


@router.get("/sage-export/history")
def sage_export_history(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.view")),
):
    """Get AP sage export history."""
    return ap_sage_export_service.get_ap_export_history(
        db, current_user.company_id, page, per_page,
    )
