"""Company entities API — unified CRM master entity endpoints."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.company_entity import CompanyEntity
from app.models.company_migration_review import CompanyMigrationReview
from app.models.customer import Customer
from app.models.vendor import Vendor
from app.models.cemetery import Cemetery
from app.models.user import User

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

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
