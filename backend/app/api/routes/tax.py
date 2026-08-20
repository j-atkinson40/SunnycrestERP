"""Tax rate, jurisdiction, and resolution API routes."""

import logging
from datetime import date
from decimal import Decimal

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


# ⚠️ ResolveLineRequest / ResolveInvoiceRequest DELETED (TAX-3) along with the
# second tax engine they fed. See the deletion note above `list_exemptions`.


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


@router.get("/exemptions")
def list_exemptions(
    status: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Exemptions needing attention — expiring, expired, or unnumbered.

    ⚠️ THIS READ `customers.tax_status` AND RETURNED HTTP 500 ON EVERY CALL.
    Those columns (`tax_status`, `exemption_certificate`, `exemption_expiry`,
    `exemption_verified`) exist in the DATABASE — added by
    `s3a4b5c6d7e8_add_tax_system.py` — and were never mapped onto the `Customer`
    model, so `Customer.tax_status` raised AttributeError before any query ran.
    The caller (`tax-settings.tsx`) had a bare `.catch(() => {})`, so the tab
    rendered "No tax-exempt customers" on a failed request. **An empty list is
    what a working query with nothing to report looks like.**

    ⚠️ AND THE DELETED SECOND ENGINE READ THE SAME COLUMNS. `_resolve_line_tax`
    (this file, removed in the same change) would have exempted a customer on
    `tax_status == "exempt"` ALONE, rendering the reason
    `"Customer exempt — no certificate"` onto an invoice. It never ran — same
    AttributeError — but mapping those columns to "fix" the 500 would have
    turned unreachable code into reachable wrong code. Deleting is why that is
    now impossible rather than merely unlikely.

    Repointed at `TaxCertificate`, which is the model that actually holds this
    data and is already dated: `is_valid_on` does expiry properly, and
    job-scoped certificates are distinguishable from blanket ones. Same
    question, answered from the records that exist.
    """
    from datetime import timedelta

    from app.models.tax_filing import TaxCertificate

    today = date.today()
    thirty_days = today + timedelta(days=30)

    rows = (
        db.query(TaxCertificate, Customer.name)
        .join(Customer, Customer.id == TaxCertificate.customer_id)
        .filter(
            TaxCertificate.company_id == current_user.company_id,
            TaxCertificate.is_active == True,  # noqa: E712
        )
        .order_by(TaxCertificate.valid_through.is_(None), TaxCertificate.valid_through)
        .all()
    )

    results = []
    for cert, customer_name in rows:
        through = cert.valid_through
        is_expired = bool(through and through < today)
        is_expiring = bool(through and not is_expired and through <= thirty_days)
        # An open-dated certificate never expires — that is a real answer, not a
        # missing one, so it is neither expired nor expiring.
        missing_number = not cert.cert_number

        if status == "expired" and not is_expired:
            continue
        if status == "expiring" and not is_expiring:
            continue
        if status == "missing_cert" and not missing_number:
            continue

        results.append({
            "certificate_id": cert.id,
            "customer_id": cert.customer_id,
            "customer_name": customer_name,
            "cert_type": cert.cert_type,
            "cert_number": cert.cert_number,
            "scope": "job" if cert.sales_order_id else "blanket",
            "valid_through": through.isoformat() if through else None,
            "attached": cert.vault_document_id is not None,
            "is_expired": is_expired,
            "is_expiring": is_expiring,
            "missing_cert": missing_number,
        })

    return results


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
    # Normalize zip to 5 digits (strip ZIP+4 suffix)
    if tenant_zip:
        tenant_zip = tenant_zip.strip().split("-")[0][:5]
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


# ---------------------------------------------------------------------------
# Sales-tax arc — certificates, product taxability, the return
# ---------------------------------------------------------------------------


class CertificateCreate(BaseModel):
    customer_id: str
    sales_order_id: str | None = None  # set = job-level; NULL = blanket
    cert_type: str = "resale"
    cert_number: str | None = None
    state: str | None = None
    valid_from: str | None = None
    valid_through: str | None = None
    vault_document_id: str | None = None
    notes: str | None = None


def _cert_to_dict(c) -> dict:
    return {
        "id": c.id, "customer_id": c.customer_id,
        "customer_name": c.customer.name if c.customer else None,
        "sales_order_id": c.sales_order_id,
        "scope": "job" if c.sales_order_id else "blanket",
        "cert_type": c.cert_type, "cert_number": c.cert_number,
        "state": c.state,
        "valid_from": str(c.valid_from) if c.valid_from else None,
        "valid_through": str(c.valid_through) if c.valid_through else None,
        "vault_document_id": c.vault_document_id,
        "attached": c.vault_document_id is not None,
        "is_active": c.is_active,
        "notes": c.notes,
    }


@router.get("/certificates")
def list_certificates(
    customer_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.tax_filing import TaxCertificate
    q = db.query(TaxCertificate).filter(
        TaxCertificate.company_id == current_user.company_id,
        TaxCertificate.is_active.is_(True),
    )
    if customer_id:
        q = q.filter(TaxCertificate.customer_id == customer_id)
    return [_cert_to_dict(c) for c in q.order_by(TaxCertificate.created_at.desc()).all()]


@router.post("/certificates")
def create_certificate(
    body: CertificateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.tax_filing import CERT_TYPES, TaxCertificate

    if body.cert_type not in CERT_TYPES:
        raise HTTPException(400, f"cert_type must be one of {CERT_TYPES}")
    cust = db.query(Customer).filter(
        Customer.id == body.customer_id,
        Customer.company_id == current_user.company_id,
    ).first()
    if not cust:
        raise HTTPException(404, "Customer not found")
    if body.sales_order_id:
        from app.models.sales_order import SalesOrder
        so = db.query(SalesOrder).filter(
            SalesOrder.id == body.sales_order_id,
            SalesOrder.company_id == current_user.company_id,
        ).first()
        if not so:
            raise HTTPException(404, "Sales order not found")
    cert = TaxCertificate(
        company_id=current_user.company_id,
        customer_id=body.customer_id,
        sales_order_id=body.sales_order_id,
        cert_type=body.cert_type,
        cert_number=body.cert_number,
        state=(body.state or "").upper()[:2] or None,
        valid_from=date.fromisoformat(body.valid_from) if body.valid_from else None,
        valid_through=date.fromisoformat(body.valid_through) if body.valid_through else None,
        vault_document_id=body.vault_document_id,
        notes=body.notes,
        created_by=current_user.id,
    )
    db.add(cert)
    db.commit()
    db.refresh(cert)
    return _cert_to_dict(cert)


@router.delete("/certificates/{cert_id}")
def deactivate_certificate(
    cert_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.tax_filing import TaxCertificate
    cert = db.query(TaxCertificate).filter(
        TaxCertificate.id == cert_id,
        TaxCertificate.company_id == current_user.company_id,
    ).first()
    if not cert:
        raise HTTPException(404, "Certificate not found")
    cert.is_active = False
    db.commit()
    return {"status": "deactivated"}


# ── Product taxability (the operator's markup surface) ──


@router.get("/product-taxability")
def list_product_taxability(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.product import Product
    rows = (
        db.query(Product)
        .filter(Product.company_id == current_user.company_id,
                Product.is_active.is_(True))
        .order_by(Product.name)
        .all()
    )
    return [
        {"id": p.id, "name": p.name, "product_line": p.product_line,
         "tax_class": p.tax_class,
         "effective": "exempt" if p.tax_class == "exempt" else "taxable",
         "reviewed": p.tax_class != "inherit"}
        for p in rows
    ]


class TaxClassUpdate(BaseModel):
    tax_class: str


@router.patch("/product-taxability/{product_id}")
def set_product_tax_class(
    product_id: str,
    body: TaxClassUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.product import Product
    from app.models.tax_filing import PRODUCT_TAX_CLASSES
    if body.tax_class not in PRODUCT_TAX_CLASSES:
        raise HTTPException(400, f"tax_class must be one of {PRODUCT_TAX_CLASSES}")
    p = db.query(Product).filter(
        Product.id == product_id,
        Product.company_id == current_user.company_id,
    ).first()
    if not p:
        raise HTTPException(404, "Product not found")
    p.tax_class = body.tax_class
    db.commit()
    return {"id": p.id, "tax_class": p.tax_class}


# ── The return ──


@router.get("/returns/periods")
def list_return_periods(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.tax_filing_service import available_periods
    return available_periods(db, current_user.company_id)


@router.get("/returns/{period_key}")
def get_tax_return(
    period_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.tax_filing_service import get_return
    return get_return(db, current_user.company_id, period_key)


@router.post("/returns/{period_key}/accumulate")
def accumulate_return_period(
    period_key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.tax_filing_service import accumulate_period, get_return
    accumulate_period(db, current_user.company_id, period_key)
    return get_return(db, current_user.company_id, period_key)
