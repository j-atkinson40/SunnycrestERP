"""Accounting AI analysis service — extracts, analyzes, and maps accounting data.

Uses Claude Haiku for cost-effective structured analysis of chart of accounts,
customers, vendors, and products. Returns confidence-scored mappings that the
review screen auto-approves (>= 0.85) or flags for tenant review.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.accounting_analysis import (
    TenantAccountingAnalysis,
    TenantAccountingImportStaging,
    TenantAlert,
    TenantGLMapping,
)
from app.models.accounting_connection import AccountingConnection

logger = logging.getLogger(__name__)

ANALYSIS_MODEL = "claude-haiku-4-5-20250514"
ANALYSIS_MAX_TOKENS = 4096

# Platform account categories for GL mapping
PLATFORM_CATEGORIES = {
    "revenue": [
        "vault_sales", "urn_sales", "equipment_sales", "delivery_revenue",
        "redi_rock_sales", "wastewater_sales", "rosetta_sales",
        "service_revenue", "other_revenue",
    ],
    "ar": ["ar_funeral_homes", "ar_contractors", "ar_government", "ar_other"],
    "cogs": ["vault_materials", "direct_labor", "delivery_costs", "other_cogs"],
    "ap": ["accounts_payable"],
    "expenses": [
        "rent", "utilities", "insurance", "payroll", "office_supplies",
        "vehicle_expense", "repairs_maintenance", "depreciation",
        "professional_fees", "advertising", "other_expense",
    ],
}

ANALYSIS_SYSTEM_PROMPT = """You are an accounting data analyst specializing in manufacturing \
and funeral service businesses. You will be given a chart of accounts and customer/vendor/product \
data from a new tenant onboarding to a business management platform.

Your job is to analyze this data and return structured JSON mapping their accounts to our platform schema.

Platform account categories that need mapping:

REVENUE: vault_sales, urn_sales, equipment_sales, delivery_revenue, redi_rock_sales, \
wastewater_sales, rosetta_sales, service_revenue, other_revenue
AR: ar_funeral_homes, ar_contractors, ar_government, ar_other
COGS: vault_materials, direct_labor, delivery_costs, other_cogs
AP: accounts_payable
EXPENSES: rent, utilities, insurance, payroll, office_supplies, vehicle_expense, \
repairs_maintenance, depreciation, professional_fees, advertising, other_expense

For each mapping return:
- account_number
- account_name
- platform_category (from lists above)
- confidence (0.0 to 1.0)
- reasoning (one sentence)
- alternative (second best guess if confidence below 0.85)

Also analyze:

STALE ACCOUNTS: Flag any accounts with zero transaction volume in the last 90 days \
(or no transaction data available) as potentially stale. Return a stale_accounts array.

CUSTOMER ANALYSIS: For each customer, infer:
- customer_type (funeral_home, cemetery, contractor, government, retail, unknown)
- confidence score
- reasoning

VENDOR ANALYSIS: For each vendor, infer:
- vendor_type (materials_supplier, equipment, utilities, professional_services, unknown)
- confidence score

PRODUCT MATCHING: For each product/item in their accounting system, suggest the closest \
match in our platform product catalog if one exists.

NETWORK COMPARISON: Note that this tenant is joining a network of similar businesses. \
Flag any accounts or configurations that appear unusual compared to standard \
manufacturing/funeral service COA patterns.

Return ONLY valid JSON with this structure:
{
  "gl_mappings": [...],
  "stale_accounts": [...],
  "customer_analysis": [...],
  "vendor_analysis": [...],
  "product_matches": [...],
  "network_flags": [...]
}
No preamble, no markdown."""


async def store_extracted_data(
    db: Session,
    tenant_id: str,
    data_type: str,
    raw_data: list[dict],
    source: str,
) -> TenantAccountingImportStaging:
    """Store extracted accounting data in staging table."""
    staging = TenantAccountingImportStaging(
        tenant_id=tenant_id,
        data_type=data_type,
        raw_data=raw_data,
        record_count=len(raw_data),
        source=source,
        status="extracted",
    )
    db.add(staging)
    db.commit()
    db.refresh(staging)
    return staging


async def run_ai_analysis(
    db: Session,
    tenant_id: str,
) -> str:
    """Run Claude AI analysis on all staged data for a tenant. Returns analysis_run_id."""

    run_id = str(uuid.uuid4())

    # Update connection with analysis status
    conn = (
        db.query(AccountingConnection)
        .filter(AccountingConnection.company_id == tenant_id)
        .first()
    )
    if conn:
        conn.ai_analysis_run_id = run_id
        conn.ai_analysis_status = "running"
        conn.ai_analysis_started_at = datetime.now(timezone.utc)
        db.commit()

    # Gather all staged data
    staged = (
        db.query(TenantAccountingImportStaging)
        .filter(
            TenantAccountingImportStaging.tenant_id == tenant_id,
            TenantAccountingImportStaging.status == "extracted",
        )
        .all()
    )

    if not staged:
        logger.warning(f"No staged data for tenant {tenant_id}")
        if conn:
            conn.ai_analysis_status = "no_data"
            db.commit()
        return run_id

    # Build the user message with all extracted data
    user_data = {}
    for s in staged:
        user_data[s.data_type] = s.raw_data
        s.status = "analyzing"
    db.commit()

    user_message = json.dumps(user_data, default=str)

    # Call via the Intelligence layer (Phase 2c-1 migration — the managed
    # `accounting.coa_classify` prompt carries the system prompt verbatim).
    try:
        from app.services.intelligence import intelligence_service

        result = intelligence_service.execute(
            db,
            prompt_key="accounting.coa_classify",
            variables={"user_data": user_message},
            company_id=tenant_id,
            caller_module="accounting_analysis_service.run_ai_analysis",
            caller_entity_type="company",
            caller_entity_id=tenant_id,
            caller_accounting_analysis_run_id=run_id,
        )

        if result.status != "success" or not isinstance(result.response_parsed, dict):
            raise RuntimeError(
                f"Intelligence execute status={result.status}: "
                f"{result.error_message or 'no parsed response'}"
            )
        analysis_result = result.response_parsed

    except Exception as e:
        logger.error(f"AI analysis failed for tenant {tenant_id}: {e}")
        if conn:
            conn.ai_analysis_status = "failed"
            db.commit()
        # Mark staging as extracted so manual mapping can proceed
        for s in staged:
            s.status = "extracted"
        db.commit()
        return run_id

    # Store analysis results
    auto_count = 0
    review_count = 0

    # GL account mappings
    for mapping in analysis_result.get("gl_mappings", []):
        conf = float(mapping.get("confidence", 0))
        is_auto = conf >= 0.85
        if is_auto:
            auto_count += 1
        else:
            review_count += 1

        db.add(TenantAccountingAnalysis(
            tenant_id=tenant_id,
            analysis_run_id=run_id,
            mapping_type="gl_account",
            source_id=mapping.get("account_number"),
            source_name=mapping.get("account_name", "Unknown"),
            source_data=mapping,
            platform_category=mapping.get("platform_category"),
            confidence=conf,
            reasoning=mapping.get("reasoning"),
            alternative=mapping.get("alternative"),
            status="confirmed" if is_auto else "pending",
            confirmed_at=datetime.now(timezone.utc) if is_auto else None,
        ))

    # Stale accounts
    for acct in analysis_result.get("stale_accounts", []):
        db.add(TenantAccountingAnalysis(
            tenant_id=tenant_id,
            analysis_run_id=run_id,
            mapping_type="gl_account",
            source_id=acct.get("account_number"),
            source_name=acct.get("account_name", "Unknown"),
            source_data=acct,
            is_stale=True,
            status="archived",
        ))

    # Customer analysis
    for cust in analysis_result.get("customer_analysis", []):
        conf = float(cust.get("confidence", 0))
        is_auto = conf >= 0.85
        if is_auto:
            auto_count += 1
        else:
            review_count += 1

        db.add(TenantAccountingAnalysis(
            tenant_id=tenant_id,
            analysis_run_id=run_id,
            mapping_type="customer",
            source_id=cust.get("customer_id"),
            source_name=cust.get("name", "Unknown"),
            source_data=cust,
            platform_category=cust.get("customer_type"),
            confidence=conf,
            reasoning=cust.get("reasoning"),
            status="confirmed" if is_auto else "pending",
            confirmed_at=datetime.now(timezone.utc) if is_auto else None,
        ))

    # Vendor analysis
    for vendor in analysis_result.get("vendor_analysis", []):
        conf = float(vendor.get("confidence", 0))
        is_auto = conf >= 0.85
        if is_auto:
            auto_count += 1
        else:
            review_count += 1

        db.add(TenantAccountingAnalysis(
            tenant_id=tenant_id,
            analysis_run_id=run_id,
            mapping_type="vendor",
            source_id=vendor.get("vendor_id"),
            source_name=vendor.get("name", "Unknown"),
            source_data=vendor,
            platform_category=vendor.get("vendor_type"),
            confidence=conf,
            reasoning=vendor.get("reasoning"),
            status="confirmed" if is_auto else "pending",
            confirmed_at=datetime.now(timezone.utc) if is_auto else None,
        ))

    # Product matches
    for prod in analysis_result.get("product_matches", []):
        conf = float(prod.get("confidence", 0))
        db.add(TenantAccountingAnalysis(
            tenant_id=tenant_id,
            analysis_run_id=run_id,
            mapping_type="product",
            source_id=prod.get("product_id"),
            source_name=prod.get("product_name", "Unknown"),
            source_data=prod,
            platform_category=prod.get("platform_match"),
            confidence=conf,
            reasoning=prod.get("reasoning"),
            status="confirmed" if conf >= 0.85 else "pending",
        ))

    # Update staging status
    for s in staged:
        s.status = "analyzed"

    # Update connection
    if conn:
        conn.ai_analysis_status = "complete"
        conn.ai_analysis_completed_at = datetime.now(timezone.utc)
        conn.ai_auto_approved_count = auto_count
        conn.ai_review_required_count = review_count

    db.commit()
    logger.info(
        f"AI analysis complete for tenant {tenant_id}: "
        f"{auto_count} auto-approved, {review_count} need review"
    )
    return run_id


def get_analysis_results(
    db: Session, tenant_id: str, run_id: str | None = None,
) -> dict:
    """Get analysis results grouped by type and status."""

    query = db.query(TenantAccountingAnalysis).filter(
        TenantAccountingAnalysis.tenant_id == tenant_id,
    )
    if run_id:
        query = query.filter(TenantAccountingAnalysis.analysis_run_id == run_id)

    results = query.order_by(TenantAccountingAnalysis.confidence.desc()).all()

    output = {
        "gl_accounts": {"auto_approved": [], "needs_review": [], "stale": []},
        "customers": {"auto_approved": [], "needs_review": []},
        "vendors": {"auto_approved": [], "needs_review": []},
        "products": {"auto_approved": [], "needs_review": []},
    }

    for r in results:
        item = {
            "id": r.id,
            "source_id": r.source_id,
            "source_name": r.source_name,
            "platform_category": r.platform_category,
            "confidence": float(r.confidence) if r.confidence else 0,
            "reasoning": r.reasoning,
            "alternative": r.alternative,
            "status": r.status,
            "is_stale": r.is_stale,
        }

        if r.mapping_type == "gl_account":
            if r.is_stale:
                output["gl_accounts"]["stale"].append(item)
            elif r.status == "confirmed":
                output["gl_accounts"]["auto_approved"].append(item)
            else:
                output["gl_accounts"]["needs_review"].append(item)
        elif r.mapping_type == "customer":
            if r.status == "confirmed":
                output["customers"]["auto_approved"].append(item)
            else:
                output["customers"]["needs_review"].append(item)
        elif r.mapping_type == "vendor":
            if r.status == "confirmed":
                output["vendors"]["auto_approved"].append(item)
            else:
                output["vendors"]["needs_review"].append(item)
        elif r.mapping_type == "product":
            if r.status == "confirmed":
                output["products"]["auto_approved"].append(item)
            else:
                output["products"]["needs_review"].append(item)

    return output


def confirm_analysis(
    db: Session, tenant_id: str, user_id: str, confirmations: list[dict],
) -> dict:
    """Process tenant confirmations — writes to live tables.

    Each confirmation: {id, action: 'confirm'|'ignore'|'change', new_category?: str}
    """
    now = datetime.now(timezone.utc)
    confirmed_count = 0
    ignored_count = 0

    for conf in confirmations:
        analysis = (
            db.query(TenantAccountingAnalysis)
            .filter(
                TenantAccountingAnalysis.id == conf["id"],
                TenantAccountingAnalysis.tenant_id == tenant_id,
            )
            .first()
        )
        if not analysis:
            continue

        action = conf.get("action", "confirm")

        if action == "ignore":
            analysis.status = "ignored"
            ignored_count += 1
        elif action in ("confirm", "change"):
            if action == "change" and conf.get("new_category"):
                analysis.platform_category = conf["new_category"]
            analysis.status = "confirmed"
            analysis.confirmed_at = now
            analysis.confirmed_by = user_id
            confirmed_count += 1

    db.commit()

    # Write confirmed GL mappings to live table
    confirmed_gl = (
        db.query(TenantAccountingAnalysis)
        .filter(
            TenantAccountingAnalysis.tenant_id == tenant_id,
            TenantAccountingAnalysis.mapping_type == "gl_account",
            TenantAccountingAnalysis.status == "confirmed",
            TenantAccountingAnalysis.is_stale == False,
        )
        .all()
    )

    for gl in confirmed_gl:
        existing = (
            db.query(TenantGLMapping)
            .filter(
                TenantGLMapping.tenant_id == tenant_id,
                TenantGLMapping.account_number == gl.source_id,
            )
            .first()
        )
        if not existing:
            db.add(TenantGLMapping(
                tenant_id=tenant_id,
                platform_category=gl.platform_category or "unknown",
                account_number=gl.source_id,
                account_name=gl.source_name,
            ))

    # Set first_sync_validation_pending
    conn = (
        db.query(AccountingConnection)
        .filter(AccountingConnection.company_id == tenant_id)
        .first()
    )
    if conn:
        conn.first_sync_validation_pending = True

    db.commit()

    return {"confirmed": confirmed_count, "ignored": ignored_count}


def create_tenant_alert(
    db: Session,
    tenant_id: str,
    alert_type: str,
    message: str,
    action_label: str | None = None,
    action_url: str | None = None,
    severity: str = "info",
) -> TenantAlert:
    """Create a tenant alert for background agent notifications."""
    alert = TenantAlert(
        tenant_id=tenant_id,
        alert_type=alert_type,
        message=message,
        action_label=action_label,
        action_url=action_url,
        severity=severity,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def get_unresolved_alerts(db: Session, tenant_id: str) -> list[dict]:
    """Get all unresolved alerts for a tenant."""
    alerts = (
        db.query(TenantAlert)
        .filter(
            TenantAlert.tenant_id == tenant_id,
            TenantAlert.resolved == False,
        )
        .order_by(TenantAlert.created_at.desc())
        .all()
    )
    return [
        {
            "id": a.id,
            "alert_type": a.alert_type,
            "message": a.message,
            "action_label": a.action_label,
            "action_url": a.action_url,
            "severity": a.severity,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in alerts
    ]


def resolve_alert(db: Session, alert_id: str, tenant_id: str, user_id: str) -> bool:
    """Mark an alert as resolved."""
    alert = (
        db.query(TenantAlert)
        .filter(TenantAlert.id == alert_id, TenantAlert.tenant_id == tenant_id)
        .first()
    )
    if not alert:
        return False
    alert.resolved = True
    alert.resolved_at = datetime.now(timezone.utc)
    alert.resolved_by = user_id
    db.commit()
    return True
