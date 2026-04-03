"""Company entities API — unified CRM master entity endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import sqlalchemy as sa
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.company_entity import CompanyEntity
from app.models.company_migration_review import CompanyMigrationReview
from app.models.contact import Contact
from app.models.customer import Customer
from app.models.vendor import Vendor
from app.models.cemetery import Cemetery
from app.models.user import User
from app.services.crm import contact_service
from app.services.crm import activity_log_service
from app.services.crm import health_score_service
from app.services.crm import classification_service

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

def _ensure_classification_columns(db: Session) -> None:
    """Add classification columns to company_entities if they don't exist."""
    for col_sql in [
        "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS customer_type VARCHAR(50)",
        "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS contractor_type VARCHAR(50)",
        "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS is_aggregate BOOLEAN DEFAULT false",
        "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS classification_confidence DECIMAL(4,3)",
        "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS classification_source VARCHAR(30)",
        "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS classification_reasons JSONB DEFAULT '[]'",
        "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS classification_reviewed_by VARCHAR(36)",
        "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS classification_reviewed_at TIMESTAMPTZ",
        "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS is_active_customer BOOLEAN DEFAULT false",
        "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS first_order_year INTEGER",
        "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS google_places_id VARCHAR(200)",
        "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS google_places_type VARCHAR(100)",
        "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS original_name VARCHAR(500)",
        "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS name_cleanup_actions JSONB",
    ]:
        db.execute(sa.text(col_sql))


class CompanyEntityCreate(BaseModel):
    name: str
    legal_name: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    country: str = "US"
    is_customer: bool = False
    is_vendor: bool = False
    is_cemetery: bool = False
    is_funeral_home: bool = False
    is_licensee: bool = False
    is_crematory: bool = False
    is_print_shop: bool = False
    notes: str | None = None


class CompanyEntityUpdate(BaseModel):
    name: str | None = None
    legal_name: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    country: str | None = None
    is_customer: bool | None = None
    is_vendor: bool | None = None
    is_cemetery: bool | None = None
    is_funeral_home: bool | None = None
    is_licensee: bool | None = None
    is_crematory: bool | None = None
    is_print_shop: bool | None = None
    is_active: bool | None = None
    notes: str | None = None


class MergeReviewAction(BaseModel):
    action: str  # 'merge' | 'separate'


# ── Helpers ──────────────────────────────────────────────────────────────────

def _serialize(e: CompanyEntity, db: Session) -> dict:
    # Find linked record IDs
    customer = db.query(Customer.id).filter(Customer.master_company_id == e.id).first()
    vendor = db.query(Vendor.id).filter(Vendor.master_company_id == e.id).first()
    cemetery = db.query(Cemetery.id).filter(Cemetery.master_company_id == e.id).first()

    roles = []
    if e.is_customer: roles.append("customer")
    if e.is_vendor: roles.append("vendor")
    if e.is_cemetery: roles.append("cemetery")
    if e.is_funeral_home: roles.append("funeral_home")
    if e.is_licensee: roles.append("licensee")
    if e.is_crematory: roles.append("crematory")
    if e.is_print_shop: roles.append("print_shop")

    return {
        "id": e.id,
        "name": e.name,
        "legal_name": e.legal_name,
        "phone": e.phone,
        "email": e.email,
        "website": e.website,
        "address_line1": e.address_line1,
        "address_line2": e.address_line2,
        "city": e.city,
        "state": e.state,
        "zip": e.zip,
        "country": e.country,
        "roles": roles,
        "is_customer": e.is_customer,
        "is_vendor": e.is_vendor,
        "is_cemetery": e.is_cemetery,
        "is_funeral_home": e.is_funeral_home,
        "is_licensee": e.is_licensee,
        "is_crematory": e.is_crematory,
        "is_print_shop": e.is_print_shop,
        "is_active": e.is_active,
        "notes": e.notes,
        "linked_customer_id": customer[0] if customer else None,
        "linked_vendor_id": vendor[0] if vendor else None,
        "linked_cemetery_id": cemetery[0] if cemetery else None,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


def _ensure_role_records(db: Session, entity: CompanyEntity, company_id: str) -> dict:
    """Create customer/vendor/cemetery records when role flags are set."""
    created = {}

    if entity.is_customer:
        existing = db.query(Customer).filter(Customer.master_company_id == entity.id).first()
        if not existing:
            c = Customer(
                id=str(uuid.uuid4()),
                company_id=company_id,
                name=entity.name,
                phone=entity.phone,
                email=entity.email,
                website=entity.website,
                address_line1=entity.address_line1,
                address_line2=entity.address_line2,
                city=entity.city,
                state=entity.state,
                zip_code=entity.zip,
                country=entity.country,
                master_company_id=entity.id,
            )
            db.add(c)
            db.flush()
            created["customer_id"] = c.id

    if entity.is_vendor:
        existing = db.query(Vendor).filter(Vendor.master_company_id == entity.id).first()
        if not existing:
            v = Vendor(
                id=str(uuid.uuid4()),
                company_id=company_id,
                name=entity.name,
                phone=entity.phone,
                email=entity.email,
                website=entity.website,
                address_line1=entity.address_line1,
                address_line2=entity.address_line2,
                city=entity.city,
                state=entity.state,
                zip_code=entity.zip,
                country=entity.country,
                master_company_id=entity.id,
            )
            db.add(v)
            db.flush()
            created["vendor_id"] = v.id

    if entity.is_cemetery:
        existing = db.query(Cemetery).filter(Cemetery.master_company_id == entity.id).first()
        if not existing:
            cem = Cemetery(
                id=str(uuid.uuid4()),
                company_id=company_id,
                name=entity.name,
                phone=entity.phone,
                address=entity.address_line1,
                city=entity.city,
                state=entity.state,
                zip_code=entity.zip,
                master_company_id=entity.id,
            )
            db.add(cem)
            db.flush()
            created["cemetery_id"] = cem.id

    return created


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/run-migration")
def run_company_migration(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Populate company_entities from existing customers, vendors, cemeteries.

    Idempotent — skips records that already have master_company_id set.
    Run this once after deploying the company_entities table.
    """
    import uuid as _uuid
    import traceback

    tenant_id = current_user.company_id
    stats = {"customers": 0, "vendors": 0, "cemeteries": 0, "skipped": 0}

    # Auto-create tables if Alembic migrations haven't run
    try:
        db.execute(sa.text("SELECT 1 FROM company_entities LIMIT 0"))
    except Exception:
        db.rollback()
        db.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS company_entities (
                id VARCHAR(36) PRIMARY KEY,
                company_id VARCHAR(36) NOT NULL REFERENCES companies(id),
                name VARCHAR(500) NOT NULL,
                legal_name VARCHAR(500),
                phone VARCHAR(50), email VARCHAR(500), website VARCHAR(500),
                address_line1 VARCHAR(500), address_line2 VARCHAR(500),
                city VARCHAR(200), state VARCHAR(100), zip VARCHAR(20),
                country VARCHAR(100) DEFAULT 'US',
                is_customer BOOLEAN DEFAULT false, is_vendor BOOLEAN DEFAULT false,
                is_cemetery BOOLEAN DEFAULT false, is_funeral_home BOOLEAN DEFAULT false,
                is_licensee BOOLEAN DEFAULT false, is_crematory BOOLEAN DEFAULT false,
                is_print_shop BOOLEAN DEFAULT false, is_active BOOLEAN DEFAULT true,
                customer_type VARCHAR(50), contractor_type VARCHAR(50),
                is_aggregate BOOLEAN DEFAULT false,
                classification_confidence DECIMAL(4,3),
                classification_source VARCHAR(30),
                classification_reasons JSONB DEFAULT '[]',
                classification_reviewed_by VARCHAR(36),
                classification_reviewed_at TIMESTAMPTZ,
                is_active_customer BOOLEAN DEFAULT false,
                first_order_year INTEGER,
                google_places_id VARCHAR(200), google_places_type VARCHAR(100),
                notes TEXT, created_by VARCHAR(36),
                created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now()
            )
        """))
        db.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_company_entities_tenant ON company_entities(company_id)"))
        db.commit()

    # Add classification columns if missing (for tables created before r50)
    try:
        db.execute(sa.text("SELECT customer_type FROM company_entities LIMIT 0"))
    except Exception:
        db.rollback()
        for col_sql in [
            "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS customer_type VARCHAR(50)",
            "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS contractor_type VARCHAR(50)",
            "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS is_aggregate BOOLEAN DEFAULT false",
            "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS classification_confidence DECIMAL(4,3)",
            "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS classification_source VARCHAR(30)",
            "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS classification_reasons JSONB DEFAULT '[]'",
            "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS classification_reviewed_by VARCHAR(36)",
            "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS classification_reviewed_at TIMESTAMPTZ",
            "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS is_active_customer BOOLEAN DEFAULT false",
            "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS first_order_year INTEGER",
            "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS google_places_id VARCHAR(200)",
            "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS google_places_type VARCHAR(100)",
            "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS original_name VARCHAR(500)",
            "ALTER TABLE company_entities ADD COLUMN IF NOT EXISTS name_cleanup_actions JSONB",
        ]:
            db.execute(sa.text(col_sql))
        db.commit()

    try:
        db.execute(sa.text("SELECT master_company_id FROM customers LIMIT 0"))
    except Exception:
        db.rollback()
        db.execute(sa.text("ALTER TABLE customers ADD COLUMN IF NOT EXISTS master_company_id VARCHAR(36) REFERENCES company_entities(id)"))
        db.execute(sa.text("ALTER TABLE vendors ADD COLUMN IF NOT EXISTS master_company_id VARCHAR(36) REFERENCES company_entities(id)"))
        db.execute(sa.text("ALTER TABLE cemeteries ADD COLUMN IF NOT EXISTS master_company_id VARCHAR(36) REFERENCES company_entities(id)"))
        db.commit()

    # Create contacts table if missing
    try:
        db.execute(sa.text("SELECT 1 FROM contacts LIMIT 0"))
    except Exception:
        db.rollback()
        db.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS contacts (
                id VARCHAR(36) PRIMARY KEY,
                company_id VARCHAR(36) NOT NULL REFERENCES companies(id),
                master_company_id VARCHAR(36) NOT NULL REFERENCES company_entities(id) ON DELETE CASCADE,
                name VARCHAR(500) NOT NULL, title VARCHAR(200),
                phone VARCHAR(50), phone_ext VARCHAR(20), mobile VARCHAR(50), email VARCHAR(500),
                role VARCHAR(50), is_primary BOOLEAN DEFAULT false, is_active BOOLEAN DEFAULT true,
                receives_invoices BOOLEAN DEFAULT false, receives_legacy_proofs BOOLEAN DEFAULT false,
                linked_user_id VARCHAR(36), linked_auto BOOLEAN DEFAULT false,
                notes TEXT, created_by VARCHAR(36),
                created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now()
            )
        """))
        db.commit()

    # Create activity_log if missing
    try:
        db.execute(sa.text("SELECT 1 FROM activity_log LIMIT 0"))
    except Exception:
        db.rollback()
        db.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id VARCHAR(36) PRIMARY KEY,
                tenant_id VARCHAR(36) NOT NULL,
                master_company_id VARCHAR(36) NOT NULL REFERENCES company_entities(id),
                contact_id VARCHAR(36), logged_by VARCHAR(36),
                activity_type VARCHAR(30) NOT NULL, is_system_generated BOOLEAN DEFAULT false,
                title VARCHAR(500), body TEXT, outcome TEXT,
                follow_up_date DATE, follow_up_assigned_to VARCHAR(36),
                follow_up_completed BOOLEAN DEFAULT false, follow_up_completed_at TIMESTAMPTZ,
                related_order_id VARCHAR(36), related_invoice_id VARCHAR(36), related_legacy_proof_id VARCHAR(36),
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """))
        db.commit()

    # Create manufacturer_company_profiles if missing
    try:
        db.execute(sa.text("SELECT 1 FROM manufacturer_company_profiles LIMIT 0"))
    except Exception:
        db.rollback()
        db.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS manufacturer_company_profiles (
                id VARCHAR(36) PRIMARY KEY,
                company_id VARCHAR(36) NOT NULL REFERENCES companies(id),
                master_company_id VARCHAR(36) NOT NULL UNIQUE REFERENCES company_entities(id) ON DELETE CASCADE,
                avg_days_between_orders DECIMAL(8,2), last_order_date DATE,
                order_count_12mo INTEGER DEFAULT 0, order_count_all_time INTEGER DEFAULT 0,
                total_revenue_12mo DECIMAL(12,2) DEFAULT 0, total_revenue_all_time DECIMAL(12,2) DEFAULT 0,
                most_ordered_vault_id VARCHAR(36), most_ordered_vault_name VARCHAR(200),
                avg_days_to_pay_recent DECIMAL(8,2), avg_days_to_pay_prior DECIMAL(8,2),
                health_score VARCHAR(20) DEFAULT 'unknown', health_reasons JSONB DEFAULT '[]',
                health_last_calculated TIMESTAMPTZ, last_briefed_at TIMESTAMPTZ,
                preferred_contact_method VARCHAR(20), notes TEXT,
                created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now()
            )
        """))
        db.commit()

    # Create crm_settings if missing
    try:
        db.execute(sa.text("SELECT 1 FROM crm_settings LIMIT 0"))
    except Exception:
        db.rollback()
        db.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS crm_settings (
                id VARCHAR(36) PRIMARY KEY,
                company_id VARCHAR(36) NOT NULL UNIQUE REFERENCES companies(id),
                pipeline_enabled BOOLEAN DEFAULT false, health_scoring_enabled BOOLEAN DEFAULT true,
                activity_log_enabled BOOLEAN DEFAULT true,
                at_risk_days_multiplier DECIMAL(4,2) DEFAULT 2.0,
                at_risk_payment_trend_days INTEGER DEFAULT 7, at_risk_payment_threshold_days INTEGER DEFAULT 30,
                created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now()
            )
        """))
        db.commit()

    # Create crm_opportunities if missing
    try:
        db.execute(sa.text("SELECT 1 FROM crm_opportunities LIMIT 0"))
    except Exception:
        db.rollback()
        db.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS crm_opportunities (
                id VARCHAR(36) PRIMARY KEY,
                company_id VARCHAR(36) NOT NULL REFERENCES companies(id),
                master_company_id VARCHAR(36) REFERENCES company_entities(id),
                prospect_name VARCHAR(500), prospect_city VARCHAR(200), prospect_state VARCHAR(100),
                title VARCHAR(500) NOT NULL, stage VARCHAR(30) NOT NULL DEFAULT 'prospect',
                estimated_annual_value DECIMAL(12,2), assigned_to VARCHAR(36),
                expected_close_date DATE, notes TEXT, lost_reason TEXT, created_by VARCHAR(36),
                created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now()
            )
        """))
        db.commit()

    try:
        return _do_migration(db, tenant_id)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Migration error: {type(e).__name__}: {e}")


def _do_migration(db: Session, tenant_id: str) -> dict:
    import uuid as _uuid
    stats = {"customers": 0, "vendors": 0, "cemeteries": 0, "skipped": 0}

    # Migrate customers
    customers = db.query(Customer).filter(
        Customer.company_id == tenant_id, Customer.is_active == True,
    ).all()
    for c in customers:
        if c.master_company_id:
            stats["skipped"] += 1
            continue
        eid = str(_uuid.uuid4())
        is_fh = (getattr(c, "customer_type", None) or "").lower() in ("funeral_home", "funeral home")
        entity = CompanyEntity(
            id=eid, company_id=tenant_id, name=c.name,
            phone=c.phone, email=c.email, website=c.website,
            address_line1=c.address_line1, address_line2=c.address_line2,
            city=c.city, state=c.state, zip=c.zip_code, country=c.country or "US",
            is_customer=True, is_funeral_home=is_fh,
        )
        db.add(entity)
        c.master_company_id = eid
        stats["customers"] += 1

    # Migrate vendors
    vendors = db.query(Vendor).filter(
        Vendor.company_id == tenant_id, Vendor.is_active == True,
    ).all()
    for v in vendors:
        if v.master_company_id:
            stats["skipped"] += 1
            continue
        # Check for name match with existing entity
        existing = db.query(CompanyEntity).filter(
            CompanyEntity.company_id == tenant_id,
            CompanyEntity.name == v.name,
        ).first()
        if existing:
            existing.is_vendor = True
            v.master_company_id = existing.id
            stats["vendors"] += 1
            continue
        eid = str(_uuid.uuid4())
        entity = CompanyEntity(
            id=eid, company_id=tenant_id, name=v.name,
            phone=v.phone, email=v.email, website=v.website,
            address_line1=v.address_line1, address_line2=v.address_line2,
            city=v.city, state=v.state, zip=v.zip_code, country=v.country or "US",
            is_vendor=True,
        )
        db.add(entity)
        v.master_company_id = eid
        stats["vendors"] += 1

    # Migrate cemeteries
    from app.models.cemetery import Cemetery as _Cem
    cemeteries = db.query(_Cem).filter(
        _Cem.company_id == tenant_id, _Cem.is_active == True,
    ).all()
    for cem in cemeteries:
        if cem.master_company_id:
            stats["skipped"] += 1
            continue
        existing = db.query(CompanyEntity).filter(
            CompanyEntity.company_id == tenant_id,
            CompanyEntity.name == cem.name,
        ).first()
        if existing:
            existing.is_cemetery = True
            cem.master_company_id = existing.id
            stats["cemeteries"] += 1
            continue
        eid = str(_uuid.uuid4())
        entity = CompanyEntity(
            id=eid, company_id=tenant_id, name=cem.name,
            phone=cem.phone, address_line1=getattr(cem, "address", None),
            city=cem.city, state=cem.state, zip=cem.zip_code,
            is_cemetery=True,
        )
        db.add(entity)
        cem.master_company_id = eid
        stats["cemeteries"] += 1

    # Seed manufacturer profiles for new entities
    from app.models.manufacturer_company_profile import ManufacturerCompanyProfile
    new_customer_entities = db.query(CompanyEntity).filter(
        CompanyEntity.company_id == tenant_id,
        CompanyEntity.is_customer == True,
    ).all()
    profiles_created = 0
    for ce in new_customer_entities:
        existing_profile = db.query(ManufacturerCompanyProfile).filter(
            ManufacturerCompanyProfile.master_company_id == ce.id
        ).first()
        if not existing_profile:
            db.add(ManufacturerCompanyProfile(
                id=str(_uuid.uuid4()), company_id=tenant_id, master_company_id=ce.id,
            ))
            profiles_created += 1

    db.commit()
    stats["profiles_created"] = profiles_created
    stats["total_entities"] = stats["customers"] + stats["vendors"] + stats["cemeteries"]
    return stats


@router.get("")
def list_companies(
    q: str = Query("", description="Search by name"),
    role: str = Query("", description="Filter by role: customer, vendor, cemetery, funeral_home, licensee"),
    is_active: bool = Query(True),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(CompanyEntity).filter(
        CompanyEntity.company_id == current_user.company_id,
        CompanyEntity.is_active == is_active,
    )
    if q:
        query = query.filter(CompanyEntity.name.ilike(f"%{q}%"))
    if role:
        role_col = {
            "customer": CompanyEntity.is_customer,
            "vendor": CompanyEntity.is_vendor,
            "cemetery": CompanyEntity.is_cemetery,
            "funeral_home": CompanyEntity.is_funeral_home,
            "licensee": CompanyEntity.is_licensee,
            "crematory": CompanyEntity.is_crematory,
            "print_shop": CompanyEntity.is_print_shop,
        }.get(role)
        if role_col is not None:
            query = query.filter(role_col == True)

    total = query.count()
    items = query.order_by(CompanyEntity.name).offset((page - 1) * per_page).limit(per_page).all()

    return {
        "items": [_serialize(e, db) for e in items],
        "total": total,
        "page": page,
        "pages": (total + per_page - 1) // per_page,
    }


@router.get("/search")
def search_companies(
    q: str = Query("", min_length=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unified search across all company roles. Returns top 15 matches."""
    if len(q) < 2:
        return []

    results = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.company_id == current_user.company_id,
            CompanyEntity.is_active == True,
            CompanyEntity.name.ilike(f"%{q}%"),
        )
        .order_by(CompanyEntity.name)
        .limit(15)
        .all()
    )

    out = []
    for e in results:
        customer = db.query(Customer.id).filter(Customer.master_company_id == e.id).first()
        vendor = db.query(Vendor.id).filter(Vendor.master_company_id == e.id).first()

        roles = []
        if e.is_customer: roles.append("customer")
        if e.is_vendor: roles.append("vendor")
        if e.is_cemetery: roles.append("cemetery")
        if e.is_funeral_home: roles.append("funeral_home")
        if e.is_licensee: roles.append("licensee")

        out.append({
            "company_id": e.id,
            "name": e.name,
            "roles": roles,
            "customer_id": customer[0] if customer else None,
            "vendor_id": vendor[0] if vendor else None,
            "phone": e.phone,
            "city": e.city,
            "state": e.state,
        })

    return out


@router.get("/migration-reviews")
def list_migration_reviews(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List pending migration reviews for this tenant."""
    reviews = (
        db.query(CompanyMigrationReview)
        .filter(
            CompanyMigrationReview.tenant_id == current_user.company_id,
            CompanyMigrationReview.status == "pending",
        )
        .order_by(CompanyMigrationReview.created_at)
        .all()
    )
    total_pending = len(reviews)
    total_all = (
        db.query(func.count(CompanyMigrationReview.id))
        .filter(CompanyMigrationReview.tenant_id == current_user.company_id)
        .scalar() or 0
    )

    return {
        "items": [
            {
                "id": r.id,
                "source_type": r.source_type,
                "source_id": r.source_id,
                "source_name": r.source_name,
                "suggested_company_id": r.suggested_company_id,
                "suggested_company_name": r.suggested_company_name,
                "similarity_score": float(r.similarity_score) if r.similarity_score else None,
                "current_company_id": r.current_company_id,
                "status": r.status,
            }
            for r in reviews
        ],
        "pending": total_pending,
        "total": total_all,
    }


@router.post("/merge-review/{review_id}")
def resolve_merge_review(
    review_id: str,
    data: MergeReviewAction,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resolve a migration review — merge or keep separate."""
    review = (
        db.query(CompanyMigrationReview)
        .filter(
            CompanyMigrationReview.id == review_id,
            CompanyMigrationReview.tenant_id == current_user.company_id,
        )
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if data.action == "merge":
        # Merge: point the source record to the suggested company
        if review.source_type == "vendor":
            db.query(Vendor).filter(Vendor.id == review.source_id).update(
                {"master_company_id": review.suggested_company_id}
            )
            db.query(CompanyEntity).filter(CompanyEntity.id == review.suggested_company_id).update(
                {"is_vendor": True}
            )
        elif review.source_type == "cemetery":
            db.query(Cemetery).filter(Cemetery.id == review.source_id).update(
                {"master_company_id": review.suggested_company_id}
            )
            db.query(CompanyEntity).filter(CompanyEntity.id == review.suggested_company_id).update(
                {"is_cemetery": True}
            )

        # Delete the fallback entity that was created during migration
        if review.current_company_id and review.current_company_id != review.suggested_company_id:
            db.query(CompanyEntity).filter(CompanyEntity.id == review.current_company_id).delete()

        review.status = "confirmed_merge"

    elif data.action == "separate":
        review.status = "confirmed_separate"
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    review.resolved_by = current_user.id
    review.resolved_at = datetime.now(timezone.utc)
    db.commit()

    return {"status": review.status}


@router.get("/{entity_id}")
def get_company(
    entity_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entity = (
        db.query(CompanyEntity)
        .filter(CompanyEntity.id == entity_id, CompanyEntity.company_id == current_user.company_id)
        .first()
    )
    if not entity:
        raise HTTPException(status_code=404, detail="Company not found")
    return _serialize(entity, db)


@router.post("", status_code=201)
def create_company(
    data: CompanyEntityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entity = CompanyEntity(
        id=str(uuid.uuid4()),
        company_id=current_user.company_id,
        created_by=current_user.id,
        **data.model_dump(),
    )
    db.add(entity)
    db.flush()

    # Create role-specific records
    created = _ensure_role_records(db, entity, current_user.company_id)
    db.commit()
    db.refresh(entity)

    result = _serialize(entity, db)
    result.update(created)
    return result


@router.patch("/{entity_id}")
def update_company(
    entity_id: str,
    data: CompanyEntityUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entity = (
        db.query(CompanyEntity)
        .filter(CompanyEntity.id == entity_id, CompanyEntity.company_id == current_user.company_id)
        .first()
    )
    if not entity:
        raise HTTPException(status_code=404, detail="Company not found")

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(entity, field, value)

    # Create role records if new role flags were set
    _ensure_role_records(db, entity, current_user.company_id)

    db.commit()
    db.refresh(entity)
    return _serialize(entity, db)


# ── Contact endpoints ────────────────────────────────────────────────────────

class ContactCreate(BaseModel):
    name: str
    title: str | None = None
    phone: str | None = None
    phone_ext: str | None = None
    mobile: str | None = None
    email: str | None = None
    role: str | None = None
    is_primary: bool = False
    receives_invoices: bool = False
    receives_legacy_proofs: bool = False
    notes: str | None = None


class ContactUpdate(BaseModel):
    name: str | None = None
    title: str | None = None
    phone: str | None = None
    phone_ext: str | None = None
    mobile: str | None = None
    email: str | None = None
    role: str | None = None
    is_primary: bool | None = None
    receives_invoices: bool | None = None
    receives_legacy_proofs: bool | None = None
    notes: str | None = None


def _serialize_contact(c: Contact) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "title": c.title,
        "phone": c.phone,
        "phone_ext": c.phone_ext,
        "mobile": c.mobile,
        "email": c.email,
        "role": c.role,
        "is_primary": c.is_primary,
        "is_active": c.is_active,
        "receives_invoices": c.receives_invoices,
        "receives_legacy_proofs": c.receives_legacy_proofs,
        "linked_user_id": c.linked_user_id,
        "linked_auto": c.linked_auto,
        "notes": c.notes,
        "linked_user": None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("/{entity_id}/contacts")
def list_contacts(
    entity_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = contact_service.get_contacts(db, entity_id, current_user.company_id)
    return {
        "confirmed": [_serialize_contact(c) for c in result["confirmed"]],
        "suggested": [_serialize_contact(c) for c in result["suggested"]],
    }


@router.post("/{entity_id}/contacts", status_code=201)
def create_contact_endpoint(
    entity_id: str,
    data: ContactCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contact = contact_service.create_contact(
        db, entity_id, current_user.company_id,
        data.model_dump(), created_by=current_user.id,
    )
    db.commit()
    return _serialize_contact(contact)


@router.patch("/{entity_id}/contacts/{contact_id}")
def update_contact_endpoint(
    entity_id: str,
    contact_id: str,
    data: ContactUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.master_company_id == entity_id,
        Contact.company_id == current_user.company_id,
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    contact = contact_service.update_contact(db, contact, data.model_dump(exclude_unset=True))
    db.commit()
    return _serialize_contact(contact)


@router.delete("/{entity_id}/contacts/{contact_id}")
def delete_contact_endpoint(
    entity_id: str,
    contact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.master_company_id == entity_id,
        Contact.company_id == current_user.company_id,
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    contact_service.soft_delete_contact(db, contact)
    db.commit()
    return {"deleted": True}


@router.post("/{entity_id}/contacts/{contact_id}/confirm")
def confirm_contact_endpoint(
    entity_id: str,
    contact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.master_company_id == entity_id,
        Contact.company_id == current_user.company_id,
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    contact = contact_service.confirm_contact(db, contact)
    db.commit()
    return _serialize_contact(contact)


@router.post("/{entity_id}/contacts/{contact_id}/dismiss")
def dismiss_contact_endpoint(
    entity_id: str,
    contact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.master_company_id == entity_id,
        Contact.company_id == current_user.company_id,
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    contact_service.hard_delete_contact(db, contact)
    db.commit()
    return {"dismissed": True}


# ── Activity log endpoints ───────────────────────────────────────────────────

class ActivityCreate(BaseModel):
    activity_type: str
    contact_id: str | None = None
    title: str
    body: str | None = None
    outcome: str | None = None
    follow_up_date: str | None = None
    follow_up_assigned_to: str | None = None


class ActivityUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    outcome: str | None = None
    follow_up_date: str | None = None
    follow_up_assigned_to: str | None = None


@router.get("/{entity_id}/activity")
def list_activity(
    entity_id: str,
    type: str = Query("", alias="type"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return activity_log_service.get_feed(
        db, entity_id, activity_type=type or None, page=page, per_page=per_page,
    )


@router.post("/{entity_id}/activity", status_code=201)
def create_activity(
    entity_id: str,
    data: ActivityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = activity_log_service.log_manual_activity(
        db,
        tenant_id=current_user.company_id,
        master_company_id=entity_id,
        activity_type=data.activity_type,
        title=data.title,
        logged_by=current_user.id,
        body=data.body,
        outcome=data.outcome,
        contact_id=data.contact_id,
        follow_up_date=data.follow_up_date,
        follow_up_assigned_to=data.follow_up_assigned_to,
    )
    db.commit()
    return activity_log_service._serialize(entry)


@router.patch("/{entity_id}/activity/{activity_id}")
def update_activity(
    entity_id: str,
    activity_id: str,
    data: ActivityUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.activity_log import ActivityLog
    entry = db.query(ActivityLog).filter(
        ActivityLog.id == activity_id,
        ActivityLog.master_company_id == entity_id,
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Activity not found")
    if entry.is_system_generated:
        raise HTTPException(status_code=403, detail="Cannot edit system-generated activity")

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(entry, field, value)
    db.commit()
    return activity_log_service._serialize(entry)


@router.post("/{entity_id}/activity/{activity_id}/complete-followup")
def complete_followup_endpoint(
    entity_id: str,
    activity_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = activity_log_service.complete_followup(db, activity_id, current_user.id)
    db.commit()
    return activity_log_service._serialize(entry)


@router.delete("/{entity_id}/activity/{activity_id}")
def delete_activity(
    entity_id: str,
    activity_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.activity_log import ActivityLog
    entry = db.query(ActivityLog).filter(
        ActivityLog.id == activity_id,
        ActivityLog.master_company_id == entity_id,
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Activity not found")
    if entry.is_system_generated:
        raise HTTPException(status_code=403, detail="Cannot delete system-generated activity")
    db.delete(entry)
    db.commit()
    return {"deleted": True}


# ── Health score endpoints ───────────────────────────────────────────────────

@router.get("/health-summary")
def get_health_summary_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return health_score_service.get_health_summary(db, current_user.company_id)


@router.get("/{entity_id}/health")
def get_health(
    entity_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.manufacturer_company_profile import ManufacturerCompanyProfile
    profile = db.query(ManufacturerCompanyProfile).filter(
        ManufacturerCompanyProfile.master_company_id == entity_id,
    ).first()
    if not profile:
        return {"health_score": "unknown", "health_reasons": []}
    return {
        "health_score": profile.health_score,
        "health_reasons": profile.health_reasons or [],
        "health_last_calculated": profile.health_last_calculated.isoformat() if profile.health_last_calculated else None,
        "avg_days_between_orders": float(profile.avg_days_between_orders) if profile.avg_days_between_orders else None,
        "avg_days_to_pay_recent": float(profile.avg_days_to_pay_recent) if profile.avg_days_to_pay_recent else None,
        "avg_days_to_pay_prior": float(profile.avg_days_to_pay_prior) if profile.avg_days_to_pay_prior else None,
        "last_order_date": profile.last_order_date.isoformat() if profile.last_order_date else None,
        "order_count_12mo": profile.order_count_12mo,
        "total_revenue_12mo": float(profile.total_revenue_12mo) if profile.total_revenue_12mo else 0,
        "most_ordered_vault_name": profile.most_ordered_vault_name,
    }


@router.post("/{entity_id}/health/recalculate")
def recalculate_health(
    entity_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    health_score_service.calculate_health_score(db, entity_id, current_user.company_id)
    db.commit()
    return get_health(entity_id, current_user, db)


# ── Funeral Homes endpoint ───────────────────────────────────────────────────

@router.get("/funeral-homes")
def list_funeral_homes(
    health: str = Query(""),
    q: str = Query(""),
    sort: str = Query("last_order"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List customer companies with health data for the Funeral Homes dashboard."""
    from app.models.manufacturer_company_profile import ManufacturerCompanyProfile

    query = (
        db.query(CompanyEntity, ManufacturerCompanyProfile)
        .outerjoin(ManufacturerCompanyProfile, ManufacturerCompanyProfile.master_company_id == CompanyEntity.id)
        .filter(
            CompanyEntity.company_id == current_user.company_id,
            CompanyEntity.is_customer == True,
            CompanyEntity.is_active == True,
        )
    )
    if q:
        query = query.filter(CompanyEntity.name.ilike(f"%{q}%"))
    if health:
        query = query.filter(ManufacturerCompanyProfile.health_score == health)

    total = query.count()

    # Sort
    if sort == "name":
        query = query.order_by(CompanyEntity.name)
    elif sort == "revenue":
        query = query.order_by(ManufacturerCompanyProfile.total_revenue_12mo.desc().nullslast())
    elif sort == "health":
        query = query.order_by(
            func.case(
                (ManufacturerCompanyProfile.health_score == "at_risk", 0),
                (ManufacturerCompanyProfile.health_score == "watch", 1),
                (ManufacturerCompanyProfile.health_score == "unknown", 2),
                else_=3,
            )
        )
    else:  # last_order
        query = query.order_by(ManufacturerCompanyProfile.last_order_date.desc().nullslast())

    items = query.offset((page - 1) * per_page).limit(per_page).all()

    # Get primary contacts
    result = []
    for entity, profile in items:
        primary = db.query(Contact).filter(
            Contact.master_company_id == entity.id,
            Contact.is_primary == True,
            Contact.is_active == True,
        ).first()

        result.append({
            "id": entity.id,
            "name": entity.name,
            "city": entity.city,
            "state": entity.state,
            "is_funeral_home": entity.is_funeral_home,
            "primary_contact": {"name": primary.name, "phone": primary.phone} if primary else None,
            "health_score": profile.health_score if profile else "unknown",
            "health_reasons": (profile.health_reasons or []) if profile else [],
            "last_order_date": profile.last_order_date.isoformat() if profile and profile.last_order_date else None,
            "order_count_12mo": profile.order_count_12mo if profile else 0,
            "total_revenue_12mo": float(profile.total_revenue_12mo) if profile and profile.total_revenue_12mo else 0,
            "avg_days_to_pay_recent": float(profile.avg_days_to_pay_recent) if profile and profile.avg_days_to_pay_recent else None,
            "most_ordered_vault_name": profile.most_ordered_vault_name if profile else None,
        })

    return {"items": result, "total": total, "page": page, "pages": (total + per_page - 1) // per_page}


# ── CRM Settings endpoints ──────────────────────────────────────────────────

@router.get("/crm-settings")
def get_crm_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = health_score_service._get_or_create_settings(db, current_user.company_id)
    db.commit()
    return {
        "pipeline_enabled": settings.pipeline_enabled,
        "health_scoring_enabled": settings.health_scoring_enabled,
        "activity_log_enabled": settings.activity_log_enabled,
        "at_risk_days_multiplier": float(settings.at_risk_days_multiplier),
        "at_risk_payment_trend_days": settings.at_risk_payment_trend_days,
        "at_risk_payment_threshold_days": settings.at_risk_payment_threshold_days,
    }


@router.patch("/crm-settings")
def update_crm_settings(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = health_score_service._get_or_create_settings(db, current_user.company_id)
    for field in ("pipeline_enabled", "health_scoring_enabled", "activity_log_enabled",
                  "at_risk_days_multiplier", "at_risk_payment_trend_days", "at_risk_payment_threshold_days"):
        if field in data:
            setattr(settings, field, data[field])
    db.commit()
    return get_crm_settings(current_user, db)


# ── Pipeline/Opportunity endpoints ───────────────────────────────────────────

class OpportunityCreate(BaseModel):
    master_company_id: str | None = None
    prospect_name: str | None = None
    prospect_city: str | None = None
    prospect_state: str | None = None
    title: str
    stage: str = "prospect"
    estimated_annual_value: float | None = None
    assigned_to: str | None = None
    expected_close_date: str | None = None
    notes: str | None = None


class OpportunityUpdate(BaseModel):
    title: str | None = None
    stage: str | None = None
    estimated_annual_value: float | None = None
    assigned_to: str | None = None
    expected_close_date: str | None = None
    notes: str | None = None
    lost_reason: str | None = None


@router.get("/opportunities")
def list_opportunities(
    stage: str = Query(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.crm_opportunity import CrmOpportunity
    query = db.query(CrmOpportunity).filter(CrmOpportunity.company_id == current_user.company_id)
    if stage:
        query = query.filter(CrmOpportunity.stage == stage)
    items = query.order_by(CrmOpportunity.created_at.desc()).all()

    STAGES = ["prospect", "contacted", "meeting_scheduled", "proposal_sent", "negotiating", "won", "lost"]
    grouped = {s: [] for s in STAGES}
    for opp in items:
        s = opp.stage if opp.stage in STAGES else "prospect"
        grouped[s].append({
            "id": opp.id,
            "title": opp.title,
            "company_name": opp.prospect_name,
            "master_company_id": opp.master_company_id,
            "city": opp.prospect_city,
            "state": opp.prospect_state,
            "stage": opp.stage,
            "estimated_annual_value": float(opp.estimated_annual_value) if opp.estimated_annual_value else None,
            "assigned_to": opp.assigned_to,
            "expected_close_date": opp.expected_close_date.isoformat() if opp.expected_close_date else None,
            "notes": opp.notes,
            "created_at": opp.created_at.isoformat() if opp.created_at else None,
        })
    return {"stages": grouped, "total": len(items)}


@router.post("/opportunities", status_code=201)
def create_opportunity(
    data: OpportunityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.crm_opportunity import CrmOpportunity
    opp = CrmOpportunity(
        id=str(uuid.uuid4()),
        company_id=current_user.company_id,
        created_by=current_user.id,
        **data.model_dump(),
    )
    db.add(opp)
    db.commit()
    db.refresh(opp)
    return {"id": opp.id, "title": opp.title, "stage": opp.stage}


@router.patch("/opportunities/{opp_id}")
def update_opportunity(
    opp_id: str,
    data: OpportunityUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.crm_opportunity import CrmOpportunity
    opp = db.query(CrmOpportunity).filter(
        CrmOpportunity.id == opp_id, CrmOpportunity.company_id == current_user.company_id
    ).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(opp, field, value)
    db.commit()
    return {"id": opp.id, "stage": opp.stage}


@router.delete("/opportunities/{opp_id}")
def delete_opportunity(
    opp_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.crm_opportunity import CrmOpportunity
    opp = db.query(CrmOpportunity).filter(
        CrmOpportunity.id == opp_id, CrmOpportunity.company_id == current_user.company_id
    ).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    db.delete(opp)
    db.commit()
    return {"deleted": True}


# ── Classification endpoints ─────────────────────────────────────────────────

@router.get("/classify/run-bulk")
def run_bulk_classification_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run bulk classification on all unclassified companies. Returns stats."""
    # Ensure ALL classification columns exist (r50 + name cleanup)
    try:
        db.execute(sa.text("SELECT classification_source, original_name FROM company_entities LIMIT 0"))
    except Exception:
        db.rollback()
        _ensure_classification_columns(db)
        db.commit()

    try:
        result = classification_service.run_bulk_classification(db, current_user.company_id, use_google_places=False)
        return result
    except Exception as e:
        db.rollback()
        import traceback
        return {"error": True, "detail": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-500:]}


@router.get("/classify/review-queue")
def get_review_queue(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    customer_type: str = Query(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List companies pending classification review."""
    # Check if classification columns exist
    try:
        db.execute(sa.text("SELECT classification_source FROM company_entities LIMIT 0"))
    except Exception:
        db.rollback()
        _ensure_classification_columns(db)
        db.commit()

    query = db.query(CompanyEntity).filter(
        CompanyEntity.company_id == current_user.company_id,
        CompanyEntity.classification_source == "pending_review",
        CompanyEntity.is_aggregate == False,
    )
    if customer_type:
        query = query.filter(CompanyEntity.customer_type == customer_type)

    total = query.count()
    items = (
        query.order_by(CompanyEntity.classification_confidence.asc().nullsfirst())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {
        "items": [
            {
                "id": e.id,
                "name": e.name,
                "city": e.city,
                "state": e.state,
                "customer_type": e.customer_type,
                "contractor_type": e.contractor_type,
                "classification_confidence": float(e.classification_confidence) if e.classification_confidence else None,
                "classification_reasons": e.classification_reasons or [],
                "classification_source": e.classification_source,
                "is_active_customer": e.is_active_customer,
                "first_order_year": e.first_order_year,
                "original_name": e.original_name,
                "name_cleanup_actions": e.name_cleanup_actions,
            }
            for e in items
        ],
        "total": total,
        "page": page,
        "pages": (total + per_page - 1) // per_page,
    }


@router.post("/{entity_id}/classify/confirm")
def confirm_classification(
    entity_id: str,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually confirm or override classification."""
    entity = db.query(CompanyEntity).filter(
        CompanyEntity.id == entity_id, CompanyEntity.company_id == current_user.company_id,
    ).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Company not found")

    entity.customer_type = data.get("customer_type", entity.customer_type)
    entity.contractor_type = data.get("contractor_type")
    entity.classification_source = "manual"
    entity.classification_reviewed_by = current_user.id
    entity.classification_reviewed_at = datetime.now(timezone.utc)

    if entity.customer_type == "funeral_home":
        entity.is_funeral_home = True
    if entity.customer_type == "cemetery":
        entity.is_cemetery = True

    db.commit()
    return {"confirmed": True, "customer_type": entity.customer_type}


@router.post("/classify/confirm-bulk")
def confirm_bulk_classification(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Batch confirm classifications as-is."""
    company_ids = data.get("company_ids", [])
    if not company_ids:
        raise HTTPException(status_code=400, detail="No company IDs provided")

    updated = 0
    for cid in company_ids:
        entity = db.query(CompanyEntity).filter(
            CompanyEntity.id == cid, CompanyEntity.company_id == current_user.company_id,
        ).first()
        if entity:
            entity.classification_source = "manual"
            entity.classification_reviewed_by = current_user.id
            entity.classification_reviewed_at = datetime.now(timezone.utc)
            updated += 1

    db.commit()
    return {"confirmed": updated}


@router.get("/{entity_id}/classify/reclassify")
def reclassify_company(
    entity_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-run classification on a single company."""
    result = classification_service.classify_company(db, entity_id)
    db.commit()
    return result


@router.get("/classify/summary")
def get_classification_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get classification breakdown for this tenant."""
    try:
        db.execute(sa.text("SELECT classification_source FROM company_entities LIMIT 0"))
    except Exception:
        db.rollback()
        return {"by_source": {}, "by_type": {}, "total": 0, "message": "Classification columns not yet created."}

    entities = db.query(CompanyEntity).filter(CompanyEntity.company_id == current_user.company_id).all()

    summary = {"auto_high": 0, "auto_google": 0, "pending_review": 0, "manual": 0, "unclassified": 0}
    types = {}

    for e in entities:
        src = e.classification_source or "unclassified"
        if src in summary:
            summary[src] += 1
        else:
            summary["unclassified"] += 1

        ct = e.customer_type or "unclassified"
        types[ct] = types.get(ct, 0) + 1

    return {"by_source": summary, "by_type": types, "total": len(entities)}


@router.post("/{entity_id}/revert-name")
def revert_company_name_endpoint(
    entity_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revert a company name to its original pre-cleanup value."""
    entity = db.query(CompanyEntity).filter(
        CompanyEntity.id == entity_id, CompanyEntity.company_id == current_user.company_id,
    ).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Company not found")

    result = classification_service.revert_company_name(db, entity_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result.get("message", result["error"]))

    db.commit()
    return result
