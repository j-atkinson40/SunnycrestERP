"""Legacy Studio API — library, CRUD, versions, convert-to-order."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.legacy_proof import LegacyProof, LegacyProofVersion
from app.models.customer import Customer
from app.models.user import User

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreateLegacyProof(BaseModel):
    source: str = "standalone"
    legacy_type: str
    print_name: str | None = None
    is_urn: bool = False
    customer_id: str | None = None
    deceased_name: str | None = None
    service_date: str | None = None
    inscription_name: str | None = None
    inscription_dates: str | None = None
    inscription_additional: str | None = None


class UpdateLegacyProof(BaseModel):
    status: str | None = None
    approved_layout: dict | None = None
    proof_url: str | None = None
    tif_url: str | None = None
    customer_id: str | None = None
    deceased_name: str | None = None
    service_date: str | None = None
    inscription_name: str | None = None
    inscription_dates: str | None = None
    inscription_additional: str | None = None


class ReviseRequest(BaseModel):
    keep_original: bool = True
    notes: str | None = None


class ConvertRequest(BaseModel):
    existing_order_id: str | None = None


class ApproveRequest(BaseModel):
    notes: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _serialize(lp: LegacyProof, db: Session) -> dict:
    customer = db.query(Customer).filter(Customer.id == lp.customer_id).first() if lp.customer_id else None
    version_count = db.query(func.count(LegacyProofVersion.id)).filter(LegacyProofVersion.legacy_proof_id == lp.id).scalar() or 0

    # Resolve order number for order-linked proofs
    order_number = None
    if lp.order_id:
        from app.models.sales_order import SalesOrder
        order_row = db.query(SalesOrder.number).filter(SalesOrder.id == lp.order_id).first()
        order_number = order_row[0] if order_row else None

    return {
        "id": lp.id,
        "source": lp.source,
        "legacy_type": lp.legacy_type,
        "print_name": lp.print_name,
        "is_urn": lp.is_urn,
        "inscription_name": lp.inscription_name,
        "inscription_dates": lp.inscription_dates,
        "inscription_additional": lp.inscription_additional,
        "customer_id": lp.customer_id,
        "customer_name": customer.name if customer else None,
        "deceased_name": lp.deceased_name,
        "service_date": lp.service_date.isoformat() if lp.service_date else None,
        "status": lp.status,
        "proof_url": lp.proof_url,
        "tif_url": lp.tif_url,
        "background_url": lp.background_url,
        "approved_layout": lp.approved_layout,
        "family_approved": lp.family_approved,
        "approved_at": lp.approved_at.isoformat() if lp.approved_at else None,
        "proof_emailed_at": lp.proof_emailed_at.isoformat() if lp.proof_emailed_at else None,
        "version_count": version_count,
        "order_id": lp.order_id,
        "order_number": order_number,
        "created_at": lp.created_at.isoformat() if lp.created_at else None,
        "updated_at": lp.updated_at.isoformat() if lp.updated_at else None,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/library")
def list_library(
    q: str = Query("", description="Search name, FH, print"),
    status_filter: str = Query("", alias="status"),
    customer_id: str = Query("", description="Filter by FH"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List legacy proofs with search and filters."""
    query = db.query(LegacyProof).filter(LegacyProof.company_id == current_user.company_id)

    if q:
        search = f"%{q}%"
        query = query.outerjoin(Customer, LegacyProof.customer_id == Customer.id).filter(
            or_(
                LegacyProof.inscription_name.ilike(search),
                LegacyProof.print_name.ilike(search),
                LegacyProof.deceased_name.ilike(search),
                Customer.name.ilike(search),
            )
        )

    if status_filter:
        query = query.filter(LegacyProof.status == status_filter)
    if customer_id:
        query = query.filter(LegacyProof.customer_id == customer_id)

    total = query.count()
    items = (
        query.order_by(LegacyProof.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {
        "items": [_serialize(lp, db) for lp in items],
        "total": total,
        "page": page,
        "pages": (total + per_page - 1) // per_page,
    }


@router.get("/{legacy_id}")
def get_legacy_proof(
    legacy_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full legacy proof record with versions."""
    lp = db.query(LegacyProof).filter(
        LegacyProof.id == legacy_id, LegacyProof.company_id == current_user.company_id
    ).first()
    if not lp:
        raise HTTPException(status_code=404, detail="Legacy proof not found")

    result = _serialize(lp, db)
    result["versions"] = [
        {
            "id": v.id,
            "version_number": v.version_number,
            "proof_url": v.proof_url,
            "tif_url": v.tif_url,
            "inscription_name": v.inscription_name,
            "print_name": v.print_name,
            "notes": v.notes,
            "kept": v.kept,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in (lp.versions or [])
    ]
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
def create_legacy_proof(
    data: CreateLegacyProof,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new standalone legacy proof."""
    from datetime import date as _date

    lp = LegacyProof(
        id=str(uuid.uuid4()),
        company_id=current_user.company_id,
        source=data.source,
        legacy_type=data.legacy_type,
        print_name=data.print_name,
        is_urn=data.is_urn,
        customer_id=data.customer_id,
        deceased_name=data.deceased_name,
        service_date=_date.fromisoformat(data.service_date) if data.service_date else None,
        inscription_name=data.inscription_name,
        inscription_dates=data.inscription_dates,
        inscription_additional=data.inscription_additional,
        status="draft",
        created_by=current_user.id,
    )
    db.add(lp)
    db.commit()
    db.refresh(lp)
    return _serialize(lp, db)


@router.patch("/{legacy_id}")
def update_legacy_proof(
    legacy_id: str,
    data: UpdateLegacyProof,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update legacy proof fields."""
    lp = db.query(LegacyProof).filter(
        LegacyProof.id == legacy_id, LegacyProof.company_id == current_user.company_id
    ).first()
    if not lp:
        raise HTTPException(status_code=404, detail="Not found")

    for field, val in data.model_dump(exclude_none=True).items():
        setattr(lp, field, val)
    lp.updated_at = datetime.now(timezone.utc)
    db.commit()
    return _serialize(lp, db)


@router.post("/{legacy_id}/approve")
def approve_legacy(
    legacy_id: str,
    data: ApproveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve a legacy proof."""
    lp = db.query(LegacyProof).filter(
        LegacyProof.id == legacy_id, LegacyProof.company_id == current_user.company_id
    ).first()
    if not lp:
        raise HTTPException(status_code=404, detail="Not found")

    lp.status = "approved"
    lp.approved_by = current_user.id
    lp.approved_at = datetime.now(timezone.utc)
    db.commit()

    # Trigger auto-delivery (Dropbox/Drive) if configured
    try:
        from app.services.legacy_delivery import run_auto_delivery
        run_auto_delivery(db, legacy_id, current_user.company_id)
    except Exception:
        pass  # Non-blocking — delivery failures don't block approval

    return {"approved": True}


@router.post("/{legacy_id}/mark-printed")
def mark_printed(
    legacy_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lp = db.query(LegacyProof).filter(
        LegacyProof.id == legacy_id, LegacyProof.company_id == current_user.company_id
    ).first()
    if not lp:
        raise HTTPException(status_code=404, detail="Not found")
    lp.status = "printed"
    db.commit()
    return {"printed": True}


@router.post("/{legacy_id}/revise")
def revise_legacy(
    legacy_id: str,
    data: ReviseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new version from current state, reset for re-editing."""
    lp = db.query(LegacyProof).filter(
        LegacyProof.id == legacy_id, LegacyProof.company_id == current_user.company_id
    ).first()
    if not lp:
        raise HTTPException(status_code=404, detail="Not found")

    max_ver = db.query(func.max(LegacyProofVersion.version_number)).filter(
        LegacyProofVersion.legacy_proof_id == lp.id
    ).scalar() or 0

    version = LegacyProofVersion(
        id=str(uuid.uuid4()),
        legacy_proof_id=lp.id,
        company_id=lp.company_id,
        version_number=max_ver + 1,
        approved_layout=lp.approved_layout,
        proof_url=lp.proof_url,
        tif_url=lp.tif_url,
        inscription_name=lp.inscription_name,
        inscription_dates=lp.inscription_dates,
        inscription_additional=lp.inscription_additional,
        print_name=lp.print_name,
        created_by=current_user.id,
        notes=data.notes,
        kept=data.keep_original,
    )
    db.add(version)

    # Reset parent for re-editing
    lp.proof_url = None
    lp.tif_url = None
    lp.approved_layout = None
    lp.status = "draft"
    lp.approved_at = None
    lp.approved_by = None
    lp.updated_at = datetime.now(timezone.utc)
    db.commit()

    return _serialize(lp, db)


@router.post("/{legacy_id}/convert-to-order")
def convert_to_order(
    legacy_id: str,
    data: ConvertRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or link to a sales order from this legacy proof."""
    lp = db.query(LegacyProof).filter(
        LegacyProof.id == legacy_id, LegacyProof.company_id == current_user.company_id
    ).first()
    if not lp:
        raise HTTPException(status_code=404, detail="Not found")

    if data.existing_order_id:
        from app.models.sales_order import SalesOrder
        order = db.query(SalesOrder).filter(SalesOrder.id == data.existing_order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        lp.order_id = order.id
        db.commit()
        return {"order_id": order.id, "action": "linked"}

    # Create new draft order
    from app.models.sales_order import SalesOrder
    order = SalesOrder(
        id=str(uuid.uuid4()),
        company_id=current_user.company_id,
        number=f"SO-LEGACY-{str(uuid.uuid4())[:6].upper()}",
        customer_id=lp.customer_id,
        status="draft",
        order_date=datetime.now(timezone.utc),
        deceased_name=lp.deceased_name or lp.inscription_name,
        notes=f"Created from Legacy Studio proof — {lp.print_name or 'Custom'}",
        created_by=current_user.id,
    )
    if lp.service_date:
        order.scheduled_date = lp.service_date
    db.add(order)
    db.flush()

    lp.order_id = order.id
    db.commit()

    return {"order_id": order.id, "action": "created"}


@router.get("/{legacy_id}/versions")
def list_versions(
    legacy_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    versions = (
        db.query(LegacyProofVersion)
        .filter(LegacyProofVersion.legacy_proof_id == legacy_id)
        .order_by(LegacyProofVersion.version_number.desc())
        .all()
    )
    return [
        {
            "id": v.id,
            "version_number": v.version_number,
            "proof_url": v.proof_url,
            "inscription_name": v.inscription_name,
            "print_name": v.print_name,
            "notes": v.notes,
            "kept": v.kept,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in versions
    ]


@router.delete("/{legacy_id}")
def delete_legacy_proof(
    legacy_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a legacy proof. Only drafts and proof_generated can be deleted."""
    lp = (
        db.query(LegacyProof)
        .filter(
            LegacyProof.id == legacy_id,
            LegacyProof.company_id == current_user.company_id,
        )
        .first()
    )
    if not lp:
        raise HTTPException(status_code=404, detail="Legacy proof not found")

    if lp.status not in ("draft", "proof_generated"):
        raise HTTPException(status_code=400, detail="Only draft or generated proofs can be deleted")

    # Delete versions first
    db.query(LegacyProofVersion).filter(LegacyProofVersion.legacy_proof_id == legacy_id).delete(synchronize_session="fetch")
    db.delete(lp)
    db.commit()
    return {"deleted": True}
