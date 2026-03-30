"""Data Migration API routes — Sage 100 → Bridgeable import pipeline."""

import json
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_admin
from app.models.user import User
from app.services.data_migration_service import DataMigrationService

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /parse — parse uploaded files and return a preview
# ---------------------------------------------------------------------------


@router.post("/parse")
async def parse_migration_files(
    coa_file: Optional[UploadFile] = File(None),
    customers_file: Optional[UploadFile] = File(None),
    ar_aging_file: Optional[UploadFile] = File(None),
    vendors_file: Optional[UploadFile] = File(None),
    ap_aging_file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Parse one or more Sage 100 export files and return a preview with counts and samples.

    All files are optional — only parse what is provided.
    """
    result: dict = {}

    # COA
    if coa_file and coa_file.filename:
        content = await coa_file.read()
        parsed = DataMigrationService.parse_coa(content)
        active = [a for a in parsed if a["status"] == "active"]
        inactive = [a for a in parsed if a["status"] != "active"]
        result["coa"] = {
            "count": len(parsed),
            "active_count": len(active),
            "inactive_count": len(inactive),
            "sample": parsed[:10],
        }

    # Customers
    _parsed_customers: list[dict] = []
    if customers_file and customers_file.filename:
        content = await customers_file.read()
        _parsed_customers = DataMigrationService.parse_customers(content)
        active = [c for c in _parsed_customers if c["status"] != "Inactive"]
        by_division: dict[str, int] = {}
        for c in _parsed_customers:
            div = c.get("division", "?")
            by_division[div] = by_division.get(div, 0) + 1
        result["customers"] = {
            "count": len(_parsed_customers),
            "active_count": len(active),
            "by_division": by_division,
            "sample": _parsed_customers[:10],
        }

    # AR Aging
    if ar_aging_file and ar_aging_file.filename:
        content = await ar_aging_file.read()
        ar_invoices, ar_customers = DataMigrationService.parse_ar_aging(content)

        total_balance = float(
            sum(abs(inv["balance"]) for inv in ar_invoices if inv["balance"] != 0)
        )
        customers_with_holds = sum(
            1 for c in ar_customers if c.get("on_credit_hold")
        )
        unique_customers = len({inv["sage_customer_no"] for inv in ar_invoices})

        # Build aging bucket totals
        current_total = float(sum(inv.get("current_amount", 0) for inv in ar_invoices))
        one_month_total = float(sum(inv.get("one_month", 0) for inv in ar_invoices))
        two_months_total = float(sum(inv.get("two_months", 0) for inv in ar_invoices))
        three_months_total = float(sum(inv.get("three_months", 0) for inv in ar_invoices))
        four_months_total = float(sum(inv.get("four_months", 0) for inv in ar_invoices))

        # Serialize sample (convert Decimal / datetime for JSON)
        sample = []
        for inv in ar_invoices[:10]:
            sample.append(
                {
                    "sage_customer_no": inv["sage_customer_no"],
                    "customer_name": inv["customer_name"],
                    "invoice_number": inv["invoice_number"],
                    "invoice_date": inv["invoice_date"].isoformat() if inv.get("invoice_date") else None,
                    "due_date": inv["due_date"].isoformat() if inv.get("due_date") else None,
                    "balance": float(inv["balance"]),
                    "days_delinquent": inv.get("days_delinquent", 0),
                    "on_credit_hold": inv.get("on_credit_hold", False),
                }
            )

        result["ar_invoices"] = {
            "count": len(ar_invoices),
            "total_balance": total_balance,
            "customer_count": unique_customers,
            "customers_with_holds": customers_with_holds,
            "by_aging_bucket": {
                "current": current_total,
                "one_month": one_month_total,
                "two_months": two_months_total,
                "three_months": three_months_total,
                "four_months": four_months_total,
            },
            "sample": sample,
        }

    # Vendors
    if vendors_file and vendors_file.filename:
        content = await vendors_file.read()
        parsed = DataMigrationService.parse_vendors(content)
        active = [v for v in parsed if v["status"] == "Active"]
        result["vendors"] = {
            "count": len(parsed),
            "active_count": len(active),
            "sample": parsed[:10],
        }

    # AP Aging
    if ap_aging_file and ap_aging_file.filename:
        content = await ap_aging_file.read()
        ap_bills = DataMigrationService.parse_ap_aging(content)

        total_balance = float(
            sum(abs(b["invoice_balance"]) for b in ap_bills if b["invoice_balance"] != 0)
        )
        current_total = float(sum(b.get("current_amount", 0) for b in ap_bills))
        one_month_total = float(sum(b.get("one_month", 0) for b in ap_bills))
        two_months_total = float(sum(b.get("two_months", 0) for b in ap_bills))
        three_months_total = float(sum(b.get("three_months", 0) for b in ap_bills))
        four_months_total = float(sum(b.get("four_months", 0) for b in ap_bills))

        sample = []
        for b in ap_bills[:10]:
            sample.append(
                {
                    "sage_vendor_no": b["sage_vendor_no"],
                    "vendor_name": b["vendor_name"],
                    "invoice_number": b["invoice_number"],
                    "invoice_date": b["invoice_date"].isoformat() if b.get("invoice_date") else None,
                    "due_date": b["due_date"].isoformat() if b.get("due_date") else None,
                    "invoice_balance": float(b["invoice_balance"]),
                    "on_hold": b.get("on_hold", False),
                }
            )

        result["ap_bills"] = {
            "count": len(ap_bills),
            "total_balance": total_balance,
            "by_aging_bucket": {
                "current": current_total,
                "one_month": one_month_total,
                "two_months": two_months_total,
                "three_months": three_months_total,
                "four_months": four_months_total,
            },
            "sample": sample,
        }

    if not result:
        raise HTTPException(
            status_code=400,
            detail="No files were provided. Upload at least one file to parse.",
        )

    # Extension content detection — runs if we have customers or products parsed
    # Products are not parsed at this stage (they come from a separate catalog import),
    # so we detect from customers only for now.
    result["extension_content"] = DataMigrationService.detect_extension_content(
        _parsed_customers,
        [],  # products not available at parse time
    )

    return result


# ---------------------------------------------------------------------------
# POST /run — run the full migration (streaming ndjson)
# ---------------------------------------------------------------------------


@router.post("/run")
async def run_migration(
    options: str = Form(...),  # JSON string
    coa_file: Optional[UploadFile] = File(None),
    customers_file: Optional[UploadFile] = File(None),
    ar_aging_file: Optional[UploadFile] = File(None),
    vendors_file: Optional[UploadFile] = File(None),
    ap_aging_file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run the full Sage 100 → Bridgeable migration pipeline.

    Accepts multipart form data with:
    - options (JSON string): {
        include_inactive_accounts: bool,
        include_inactive_customers: bool,
        include_inactive_vendors: bool,
        cutover_date: "YYYY-MM-DD"
      }
    - coa_file, customers_file, ar_aging_file, vendors_file, ap_aging_file (all optional)

    Returns a streaming ndjson response where each line is a JSON progress event.
    """
    try:
        opts = json.loads(options)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid options JSON")

    cutover_date_str = opts.get("cutover_date")
    if not cutover_date_str:
        raise HTTPException(status_code=400, detail="cutover_date is required in options")
    try:
        cutover_date = date.fromisoformat(cutover_date_str)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cutover_date format: {cutover_date_str!r} — use YYYY-MM-DD",
        )

    # Read all file contents up front (async reads must happen before the sync generator)
    files: dict = {}
    if coa_file and coa_file.filename:
        files["coa"] = await coa_file.read()
    if customers_file and customers_file.filename:
        files["customers"] = await customers_file.read()
    if ar_aging_file and ar_aging_file.filename:
        files["ar_aging"] = await ar_aging_file.read()
    if vendors_file and vendors_file.filename:
        files["vendors"] = await vendors_file.read()
    if ap_aging_file and ap_aging_file.filename:
        files["ap_aging"] = await ap_aging_file.read()

    if not files:
        raise HTTPException(status_code=400, detail="No files were provided for migration.")

    tenant_id = current_user.company_id
    initiated_by = opts.get("initiated_by", "owner")
    extension_decisions = opts.get("extension_decisions") or {}

    def event_generator():
        try:
            gen = DataMigrationService.run_full_migration(
                db=db,
                tenant_id=tenant_id,
                files=files,
                options=opts,
                cutover_date=cutover_date,
                initiated_by=initiated_by,
                extension_decisions=extension_decisions,
            )
            for event in gen:
                yield json.dumps(event) + "\n"
        except Exception as e:
            yield json.dumps({"status": "error", "message": str(e)}) + "\n"

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson",
    )


# ---------------------------------------------------------------------------
# GET /status — latest migration run status
# ---------------------------------------------------------------------------


@router.get("/status")
def get_migration_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the latest migration run status for the current tenant."""
    status = DataMigrationService.get_migration_status(db, current_user.company_id)
    if status is None:
        raise HTTPException(
            status_code=404,
            detail="No migration runs found for this tenant.",
        )

    # If migration completed, ensure the onboarding checklist item is marked done
    # (handles runs that completed before this auto-complete logic was added)
    if status.get("status") in ("complete", "partial"):
        try:
            from app.services.onboarding_service import check_completion
            check_completion(db, current_user.company_id, "data_migration")
            db.commit()
        except Exception:
            pass

    return status


# ---------------------------------------------------------------------------
# POST /rollback/{run_id} — roll back a migration run (admin only)
# ---------------------------------------------------------------------------


@router.post("/rollback/{run_id}")
def rollback_migration(
    run_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Roll back a migration run, deleting all sage-migrated records.

    Requires admin permission. This is irreversible — the migration will need
    to be re-run to restore the data.
    """
    try:
        result = DataMigrationService.rollback_migration(
            db=db,
            tenant_id=current_user.company_id,
            run_id=run_id,
            rolled_back_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rollback failed: {str(e)}")

    return {
        "success": True,
        "run_id": run_id,
        "rolled_back_records": result["rolled_back_records"],
        "message": f"Successfully rolled back {result['rolled_back_records']} records.",
    }
