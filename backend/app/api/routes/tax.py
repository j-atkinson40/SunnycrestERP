"""Tax rate, jurisdiction, and resolution API routes."""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.customer import Customer
from app.models.tax import TaxJurisdiction, TaxRate
from app.models.user import User

import uuid

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ──

class TaxRateCreate(BaseModel):
    rate_name: str
    rate_percentage: float
    description: str | None = None
    is_default: bool = False
    gl_account_id: str | None = None


class JurisdictionCreate(BaseModel):
    state: str
    county: str
    tax_rate_id: str
    zip_codes: list[str] | None = None


class ResolveLineRequest(BaseModel):
    customer_id: str
    product_id: str | None = None
    line_amount: float
    delivery_state: str | None = None
    delivery_county: str | None = None
    delivery_zip: str | None = None


class ResolveInvoiceRequest(BaseModel):
    customer_id: str
    delivery_state: str | None = None
    delivery_county: str | None = None
    delivery_zip: str | None = None
    lines: list[dict]  # [{product_id, amount}]


# ── Tax Rates ──

@router.get("/rates")
def list_rates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rates = db.query(TaxRate).filter(
        TaxRate.tenant_id == current_user.company_id,
    ).order_by(TaxRate.rate_name).all()

    # Get jurisdiction counts per rate
    rate_ids = [r.id for r in rates]
    jurisdiction_counts = {}
    if rate_ids:
        counts = db.query(
            TaxJurisdiction.tax_rate_id, func.count(TaxJurisdiction.id),
        ).filter(
            TaxJurisdiction.tax_rate_id.in_(rate_ids), TaxJurisdiction.is_active == True,
        ).group_by(TaxJurisdiction.tax_rate_id).all()
        jurisdiction_counts = dict(counts)

    return [
        {
            "id": r.id, "rate_name": r.rate_name,
            "rate_percentage": float(r.rate_percentage),
            "description": r.description, "is_default": r.is_default,
            "is_active": r.is_active, "gl_account_id": r.gl_account_id,
            "jurisdiction_count": jurisdiction_counts.get(r.id, 0),
        }
        for r in rates
    ]


@router.post("/rates")
def create_rate(
    body: TaxRateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.is_default:
        db.query(TaxRate).filter(
            TaxRate.tenant_id == current_user.company_id, TaxRate.is_default == True,
        ).update({"is_default": False})

    rate = TaxRate(
        tenant_id=current_user.company_id,
        rate_name=body.rate_name,
        rate_percentage=Decimal(str(body.rate_percentage)),
        description=body.description,
        is_default=body.is_default,
        gl_account_id=body.gl_account_id,
    )
    db.add(rate)
    db.commit()
    db.refresh(rate)

    # Fire onboarding hook
    try:
        from app.services.onboarding_service import check_completion
        check_completion(db, current_user.company_id, "setup_tax_rates")
        db.commit()
    except Exception:
        pass

    return {"id": rate.id}


@router.patch("/rates/{rate_id}")
def update_rate(
    rate_id: str, body: TaxRateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rate = db.query(TaxRate).filter(
        TaxRate.id == rate_id, TaxRate.tenant_id == current_user.company_id,
    ).first()
    if not rate:
        raise HTTPException(404, "Rate not found")

    if body.is_default and not rate.is_default:
        db.query(TaxRate).filter(
            TaxRate.tenant_id == current_user.company_id, TaxRate.is_default == True,
        ).update({"is_default": False})

    rate.rate_name = body.rate_name
    rate.rate_percentage = Decimal(str(body.rate_percentage))
    rate.description = body.description
    rate.is_default = body.is_default
    rate.gl_account_id = body.gl_account_id
    db.commit()
    return {"status": "updated"}


@router.post("/rates/{rate_id}/set-default")
def set_default_rate(
    rate_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(TaxRate).filter(
        TaxRate.tenant_id == current_user.company_id, TaxRate.is_default == True,
    ).update({"is_default": False})
    db.query(TaxRate).filter(
        TaxRate.id == rate_id, TaxRate.tenant_id == current_user.company_id,
    ).update({"is_default": True})
    db.commit()
    return {"status": "ok"}


@router.delete("/rates/{rate_id}")
def delete_rate(
    rate_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    in_use = db.query(TaxJurisdiction).filter(
        TaxJurisdiction.tax_rate_id == rate_id, TaxJurisdiction.is_active == True,
    ).count()
    if in_use > 0:
        raise HTTPException(400, f"Rate is used by {in_use} jurisdictions")
    db.query(TaxRate).filter(
        TaxRate.id == rate_id, TaxRate.tenant_id == current_user.company_id,
    ).delete()
    db.commit()
    return {"status": "deleted"}


# ── Jurisdictions ──

@router.get("/jurisdictions")
def list_jurisdictions(
    state: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(TaxJurisdiction).filter(TaxJurisdiction.tenant_id == current_user.company_id)
    if state:
        query = query.filter(TaxJurisdiction.state == state.upper())
    jurisdictions = query.order_by(TaxJurisdiction.state, TaxJurisdiction.county).all()
    return [
        {
            "id": j.id, "jurisdiction_name": j.jurisdiction_name,
            "state": j.state, "county": j.county,
            "zip_codes": j.zip_codes or [],
            "tax_rate_id": j.tax_rate_id,
            "rate_name": j.tax_rate.rate_name if j.tax_rate else None,
            "rate_percentage": float(j.tax_rate.rate_percentage) if j.tax_rate else None,
            "is_active": j.is_active,
        }
        for j in jurisdictions
    ]


@router.post("/jurisdictions")
def create_jurisdiction(
    body: JurisdictionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    j = TaxJurisdiction(
        tenant_id=current_user.company_id,
        jurisdiction_name=f"{body.county}, {body.state.upper()}",
        state=body.state.upper(),
        county=body.county.lower(),
        zip_codes=body.zip_codes if body.zip_codes else None,
        tax_rate_id=body.tax_rate_id,
    )
    db.add(j)
    db.commit()
    db.refresh(j)
    return {"id": j.id}


@router.patch("/jurisdictions/{j_id}")
def update_jurisdiction(
    j_id: str, body: JurisdictionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    j = db.query(TaxJurisdiction).filter(
        TaxJurisdiction.id == j_id, TaxJurisdiction.tenant_id == current_user.company_id,
    ).first()
    if not j:
        raise HTTPException(404, "Jurisdiction not found")
    j.state = body.state.upper()
    j.county = body.county.lower()
    j.jurisdiction_name = f"{body.county}, {body.state.upper()}"
    j.tax_rate_id = body.tax_rate_id
    j.zip_codes = body.zip_codes if body.zip_codes else None
    db.commit()
    return {"status": "updated"}


@router.delete("/jurisdictions/{j_id}")
def delete_jurisdiction(
    j_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(TaxJurisdiction).filter(
        TaxJurisdiction.id == j_id, TaxJurisdiction.tenant_id == current_user.company_id,
    ).delete()
    db.commit()
    return {"status": "deleted"}


# ── Tax Resolution ──

@router.post("/resolve-line")
def resolve_line(
    body: ResolveLineRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = _resolve_line_tax(
        db, current_user.company_id, body.customer_id, body.product_id,
        Decimal(str(body.line_amount)),
        body.delivery_state, body.delivery_county, body.delivery_zip,
    )
    return result


@router.post("/resolve-invoice")
def resolve_invoice(
    body: ResolveInvoiceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    line_results = []
    subtotal = Decimal(0)
    total_tax = Decimal(0)

    for line in body.lines:
        amount = Decimal(str(line.get("amount", 0)))
        result = _resolve_line_tax(
            db, current_user.company_id, body.customer_id,
            line.get("product_id"), amount,
            body.delivery_state, body.delivery_county, body.delivery_zip,
        )
        line_results.append(result)
        subtotal += amount
        total_tax += Decimal(str(result.get("tax_amount", 0)))

    # Tax breakdown by rate
    breakdown: dict[str, dict] = {}
    for r in line_results:
        rate_name = r.get("rate_name", "Unknown")
        if rate_name not in breakdown:
            breakdown[rate_name] = {"rate_name": rate_name, "rate_percentage": r.get("tax_rate_percentage", 0), "taxable_amount": 0, "tax_amount": 0}
        breakdown[rate_name]["taxable_amount"] += r.get("taxable_amount", 0)
        breakdown[rate_name]["tax_amount"] += r.get("tax_amount", 0)

    return {
        "lines": line_results,
        "subtotal_before_tax": float(subtotal),
        "total_tax_amount": float(total_tax),
        "total": float(subtotal + total_tax),
        "tax_breakdown": list(breakdown.values()),
    }


@router.get("/exemptions")
def list_exemptions(
    status: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Customer).filter(
        Customer.company_id == current_user.company_id,
        Customer.tax_status.in_(["exempt", "partial"]),
    )
    customers = query.all()
    today = date.today()
    from datetime import timedelta
    thirty_days = today + timedelta(days=30)

    results = []
    for c in customers:
        expiry = c.exemption_expiry
        is_expired = expiry and expiry < today
        is_expiring = expiry and not is_expired and expiry <= thirty_days
        missing_cert = not c.exemption_certificate

        if status == "expired" and not is_expired:
            continue
        if status == "expiring" and not is_expiring:
            continue
        if status == "missing_cert" and not missing_cert:
            continue

        results.append({
            "customer_id": c.id, "customer_name": c.name,
            "tax_status": c.tax_status,
            "exemption_certificate": c.exemption_certificate,
            "exemption_expiry": str(expiry) if expiry else None,
            "exemption_verified": c.exemption_verified,
            "is_expired": is_expired, "is_expiring": is_expiring,
            "missing_cert": missing_cert,
        })

    return results


# ── Tax Resolution Logic ──

def _resolve_jurisdiction(
    db: Session, tenant_id: str, state: str | None, county: str | None, zip_code: str | None,
) -> tuple[TaxJurisdiction | None, str | None]:
    """Find matching jurisdiction. Returns (jurisdiction, resolution_method)."""
    if not state:
        return None, None

    # Step 1: Zip match
    if zip_code:
        j = db.query(TaxJurisdiction).filter(
            TaxJurisdiction.tenant_id == tenant_id,
            func.upper(TaxJurisdiction.state) == state.upper(),
            TaxJurisdiction.is_active == True,
            TaxJurisdiction.zip_codes.any(zip_code),
        ).first()
        if j:
            return j, "jurisdiction_zip"

    # Step 2: County match
    if county:
        j = db.query(TaxJurisdiction).filter(
            TaxJurisdiction.tenant_id == tenant_id,
            func.upper(TaxJurisdiction.state) == state.upper(),
            func.lower(TaxJurisdiction.county) == county.lower(),
            TaxJurisdiction.is_active == True,
        ).first()
        if j:
            return j, "jurisdiction_county"

    return None, None


def _resolve_line_tax(
    db: Session, tenant_id: str, customer_id: str, product_id: str | None,
    line_amount: Decimal, delivery_state: str | None, delivery_county: str | None, delivery_zip: str | None,
) -> dict:
    """Full tax resolution for a single line."""
    from app.models.product import Product

    # Product check
    product = db.query(Product).filter(Product.id == product_id).first() if product_id else None
    if product and getattr(product, "taxability", "customer_based") == "non_taxable":
        return {
            "taxable": False, "tax_amount": 0, "tax_rate_percentage": 0,
            "tax_rate_id": None, "tax_jurisdiction_id": None,
            "tax_exempt_reason": "Product is non-taxable",
            "tax_resolution_method": "product_non_taxable",
            "taxable_amount": 0, "rate_name": "Non-taxable",
        }

    # Customer check
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if customer and customer.tax_status == "exempt":
        expiry = customer.exemption_expiry
        if not expiry or expiry >= date.today():
            cert = customer.exemption_certificate
            return {
                "taxable": False, "tax_amount": 0, "tax_rate_percentage": 0,
                "tax_rate_id": None, "tax_jurisdiction_id": None,
                "tax_exempt_reason": f"Customer exempt{' — cert #' + cert if cert else ' — no certificate'}",
                "tax_resolution_method": "customer_exempt",
                "taxable_amount": 0, "rate_name": "Exempt",
            }

    # Determine rate by priority
    rate = None
    jurisdiction = None
    method = None

    # A: Product override
    if product and getattr(product, "tax_rate_override_id", None):
        rate = db.query(TaxRate).filter(TaxRate.id == product.tax_rate_override_id).first()
        if rate:
            method = "product_override"

    # B: Jurisdiction
    if not rate:
        jurisdiction, j_method = _resolve_jurisdiction(db, tenant_id, delivery_state, delivery_county, delivery_zip)
        if jurisdiction:
            rate = db.query(TaxRate).filter(TaxRate.id == jurisdiction.tax_rate_id).first()
            method = j_method

    # C: Customer override
    if not rate and customer and getattr(customer, "tax_rate_override_id", None):
        rate = db.query(TaxRate).filter(TaxRate.id == customer.tax_rate_override_id).first()
        if rate:
            method = "customer_override"

    # D: Default
    if not rate:
        rate = db.query(TaxRate).filter(
            TaxRate.tenant_id == tenant_id, TaxRate.is_default == True, TaxRate.is_active == True,
        ).first()
        if rate:
            method = "default_rate"

    # E: No rate
    if not rate:
        return {
            "taxable": True, "tax_amount": 0, "tax_rate_percentage": 0,
            "tax_rate_id": None, "tax_jurisdiction_id": None,
            "tax_exempt_reason": None,
            "tax_resolution_method": "no_rate",
            "taxable_amount": float(line_amount), "rate_name": "No rate",
            "warning": "No tax rate configured for this jurisdiction.",
        }

    pct = rate.rate_percentage
    tax = (line_amount * pct / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "taxable": True,
        "tax_amount": float(tax),
        "tax_rate_percentage": float(pct),
        "tax_rate_id": rate.id,
        "tax_jurisdiction_id": jurisdiction.id if jurisdiction else None,
        "tax_exempt_reason": None,
        "tax_resolution_method": method,
        "taxable_amount": float(line_amount),
        "rate_name": rate.rate_name,
    }


# ── County Geographic Suggestions ──


@router.get("/jurisdictions/county-suggestions")
def get_county_suggestions(
    radius_miles: float = Query(100, ge=10, le=300),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get county suggestions with pre-filled tax rates based on tenant location."""
    from app.models.company import Company
    from app.services.county_geographic_service import build_suggestions

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    tenant_zip = (
        getattr(company, "facility_zip", None)
        or getattr(company, "address_zip", None)
    )
    tenant_state = (
        getattr(company, "facility_state", None)
        or getattr(company, "address_state", None)
    )

    # Get existing jurisdictions to mark as already configured
    existing = (
        db.query(TaxJurisdiction)
        .filter(TaxJurisdiction.tenant_id == current_user.company_id, TaxJurisdiction.is_active.is_(True))
        .all()
    )
    existing_jurisdictions = [{"county": j.county, "state": j.state} for j in existing]

    # Get customer counties from cemeteries (customers don't have a county field)
    customer_counties: list[dict] = []
    try:
        from app.models.cemetery import Cemetery
        cemetery_rows = (
            db.query(Cemetery.county, Cemetery.state)
            .filter(
                Cemetery.company_id == current_user.company_id,
                Cemetery.county.isnot(None),
                Cemetery.county != "",
                Cemetery.state.isnot(None),
            )
            .distinct()
            .all()
        )
        customer_counties = [{"county": r.county, "state": r.state} for r in cemetery_rows if r.county and r.state]
    except Exception:
        pass

    suggestions = build_suggestions(
        tenant_zip=tenant_zip,
        tenant_state=tenant_state,
        service_territory_counties=None,
        customer_counties=customer_counties if customer_counties else None,
        existing_jurisdictions=existing_jurisdictions,
        radius_miles=radius_miles,
    )

    return {
        "suggestions": suggestions,
        "tenant_state": tenant_state,
        "tenant_zip": tenant_zip,
        "has_service_territory": False,
        "existing_count": len(existing_jurisdictions),
    }


class BulkJurisdictionItem(BaseModel):
    state: str
    county: str
    rate_percentage: float


class BulkJurisdictionCreate(BaseModel):
    jurisdictions: list[BulkJurisdictionItem]


@router.post("/jurisdictions/bulk-onboarding")
def bulk_create_jurisdictions_onboarding(
    body: BulkJurisdictionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bulk create tax jurisdictions from onboarding — deduplicates rates automatically."""
    tenant_id = current_user.company_id
    created_count = 0

    # Get default GL account from existing tax rates
    default_gl = None
    existing_default_rate = (
        db.query(TaxRate)
        .filter(TaxRate.tenant_id == tenant_id, TaxRate.is_default.is_(True), TaxRate.is_active.is_(True))
        .first()
    )
    if existing_default_rate:
        default_gl = existing_default_rate.gl_account_id

    for item in body.jurisdictions:
        # Find or create rate with this percentage (deduplication)
        rate_pct = round(item.rate_percentage, 4)
        existing_rate = (
            db.query(TaxRate)
            .filter(
                TaxRate.tenant_id == tenant_id,
                TaxRate.is_active.is_(True),
                func.round(TaxRate.rate_percentage, 2) == round(rate_pct, 2),
            )
            .first()
        )

        if existing_rate:
            rate_id = existing_rate.id
        else:
            new_rate = TaxRate(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                rate_name=f"{item.county} County, {item.state.upper()} ({rate_pct}%)",
                rate_percentage=rate_pct,
                is_default=False,
                is_active=True,
                gl_account_id=default_gl,
            )
            db.add(new_rate)
            db.flush()
            rate_id = new_rate.id

        # Check if jurisdiction already exists
        existing_jur = (
            db.query(TaxJurisdiction)
            .filter(
                TaxJurisdiction.tenant_id == tenant_id,
                func.lower(TaxJurisdiction.county) == item.county.lower(),
                TaxJurisdiction.state == item.state.upper(),
            )
            .first()
        )
        if existing_jur:
            continue

        new_jur = TaxJurisdiction(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            jurisdiction_name=f"{item.county} County, {item.state.upper()}",
            state=item.state.upper(),
            county=item.county.lower(),
            tax_rate_id=rate_id,
            is_active=True,
        )
        db.add(new_jur)
        created_count += 1

    db.commit()

    # Fire onboarding hooks — bulk onboarding creates both rates and jurisdictions
    try:
        from app.services.onboarding_service import check_completion
        check_completion(db, tenant_id, "setup_tax_rates")
        check_completion(db, tenant_id, "setup_tax_jurisdictions")
        db.commit()
    except Exception:
        pass

    return {"created": created_count, "total_submitted": len(body.jurisdictions)}
