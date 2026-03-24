"""Financial reports and audit package API routes."""

import json
import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.report import AuditHealthCheck, AuditPackage
from app.models.user import User
from app.services.financial_report_service import (
    get_ap_aging_report,
    get_ar_aging_report,
    get_income_statement,
    get_invoice_register,
    get_sales_by_customer,
    get_tax_summary,
    run_health_check,
)

logger = logging.getLogger(__name__)
router = APIRouter()

REPORT_MODEL = "claude-haiku-4-5-20250514"


# ── Report endpoints ──

@router.get("/income-statement")
def income_statement(
    period_start: str = Query(...), period_end: str = Query(...),
    comparison_start: str | None = Query(None), comparison_end: str | None = Query(None),
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    return get_income_statement(
        db, current_user.company_id, date.fromisoformat(period_start), date.fromisoformat(period_end),
        date.fromisoformat(comparison_start) if comparison_start else None,
        date.fromisoformat(comparison_end) if comparison_end else None,
        current_user.id,
    )


@router.get("/ar-aging")
def ar_aging(
    as_of: str | None = Query(None),
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    return get_ar_aging_report(db, current_user.company_id, date.fromisoformat(as_of) if as_of else None, current_user.id)


@router.get("/ap-aging")
def ap_aging(
    as_of: str | None = Query(None),
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    return get_ap_aging_report(db, current_user.company_id, date.fromisoformat(as_of) if as_of else None, current_user.id)


@router.get("/sales-by-customer")
def sales_by_customer(
    period_start: str = Query(...), period_end: str = Query(...),
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    return get_sales_by_customer(db, current_user.company_id, date.fromisoformat(period_start), date.fromisoformat(period_end), current_user.id)


@router.get("/invoice-register")
def invoice_register(
    period_start: str = Query(...), period_end: str = Query(...),
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    return get_invoice_register(db, current_user.company_id, date.fromisoformat(period_start), date.fromisoformat(period_end), current_user.id)


@router.get("/tax-summary")
def tax_summary(
    period_start: str = Query(...), period_end: str = Query(...),
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    return get_tax_summary(db, current_user.company_id, date.fromisoformat(period_start), date.fromisoformat(period_end), current_user.id)


# ── Audit Health ──

@router.get("/audit-health")
def get_audit_health(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    latest = db.query(AuditHealthCheck).filter(
        AuditHealthCheck.tenant_id == current_user.company_id,
    ).order_by(AuditHealthCheck.check_date.desc()).first()
    if not latest:
        return run_health_check(db, current_user.company_id)
    return {
        "overall_score": latest.overall_score, "green": latest.green_count,
        "amber": latest.amber_count, "red": latest.red_count,
        "findings": latest.findings, "check_date": str(latest.check_date),
    }


@router.get("/audit-health/run")
def refresh_audit_health(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    return run_health_check(db, current_user.company_id)


@router.get("/audit-health/history")
def audit_health_history(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    checks = db.query(AuditHealthCheck).filter(
        AuditHealthCheck.tenant_id == current_user.company_id,
    ).order_by(AuditHealthCheck.check_date.desc()).limit(180).all()
    return [{"check_date": str(c.check_date), "overall_score": c.overall_score,
             "green": c.green_count, "amber": c.amber_count, "red": c.red_count} for c in checks]


# ── Audit Packages ──

class PackageRequest(BaseModel):
    package_name: str
    period_start: str
    period_end: str
    report_types: list[str]


class ParsePackageRequest(BaseModel):
    input: str


@router.post("/audit-packages/parse-request")
def parse_package_request(
    body: ParsePackageRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        import anthropic
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=REPORT_MODEL, max_tokens=400,
            system=(
                "Parse an audit package request. Available reports: income_statement, balance_sheet, "
                "trial_balance, gl_detail, ar_aging, ap_aging, sales_by_customer, sales_by_product, "
                "invoice_register, payment_history, vendor_payment_history, cash_flow, tax_summary. "
                "Full audit package: income_statement, balance_sheet, trial_balance, ar_aging, ap_aging, gl_detail, tax_summary. "
                'Return JSON: {"package_name": str, "period_start": str, "period_end": str, "reports": [str], "confidence": float}'
            ),
            messages=[{"role": "user", "content": body.input}],
        )
        return json.loads(response.content[0].text)
    except Exception as e:
        return {"error": str(e), "confidence": 0}


@router.post("/audit-packages/generate")
def generate_package(
    body: PackageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pkg = AuditPackage(
        tenant_id=current_user.company_id, package_name=body.package_name,
        period_start=date.fromisoformat(body.period_start),
        period_end=date.fromisoformat(body.period_end),
        reports_included=body.report_types,
        generated_by=current_user.id,
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)

    # Run reports (synchronous for now — in production would be async)
    ps = date.fromisoformat(body.period_start)
    pe = date.fromisoformat(body.period_end)
    report_data = {}
    for rt in body.report_types:
        try:
            if rt == "income_statement":
                report_data[rt] = get_income_statement(db, current_user.company_id, ps, pe, user_id=current_user.id)
            elif rt == "ar_aging":
                report_data[rt] = get_ar_aging_report(db, current_user.company_id, pe, current_user.id)
            elif rt == "ap_aging":
                report_data[rt] = get_ap_aging_report(db, current_user.company_id, pe, current_user.id)
            elif rt == "sales_by_customer":
                report_data[rt] = get_sales_by_customer(db, current_user.company_id, ps, pe, current_user.id)
            elif rt == "invoice_register":
                report_data[rt] = get_invoice_register(db, current_user.company_id, ps, pe, current_user.id)
            elif rt == "tax_summary":
                report_data[rt] = get_tax_summary(db, current_user.company_id, ps, pe, current_user.id)
        except Exception as e:
            logger.error(f"Report {rt} failed: {e}")

    pkg.status = "complete"
    pkg.completed_at = datetime.now(timezone.utc)
    db.commit()

    return {"id": pkg.id, "status": "complete", "reports_generated": len(report_data)}


@router.get("/audit-packages/history")
def package_history(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    pkgs = db.query(AuditPackage).filter(
        AuditPackage.tenant_id == current_user.company_id,
    ).order_by(AuditPackage.generated_at.desc()).limit(20).all()
    return [
        {"id": p.id, "package_name": p.package_name, "period_start": str(p.period_start),
         "period_end": str(p.period_end), "status": p.status,
         "reports_included": p.reports_included, "pdf_page_count": p.pdf_page_count,
         "generated_at": p.generated_at.isoformat() if p.generated_at else None}
        for p in pkgs
    ]
