"""Cross-tenant network relationship and transaction service."""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.network_relationship import NetworkRelationship
from app.models.network_transaction import NetworkTransaction
from app.schemas.network import (
    CompanySummary,
    NetworkRelationshipCreate,
    NetworkRelationshipResponse,
    NetworkRelationshipUpdate,
    NetworkStats,
    NetworkTransactionCreate,
    NetworkTransactionResponse,
)


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------


def get_relationships(
    db: Session,
    company_id: str,
    page: int = 1,
    per_page: int = 25,
    status_filter: str | None = None,
    relationship_type: str | None = None,
) -> tuple[list[NetworkRelationshipResponse], int]:
    """List relationships where the company is either requesting or target."""
    q = db.query(NetworkRelationship).filter(
        (NetworkRelationship.requesting_company_id == company_id)
        | (NetworkRelationship.target_company_id == company_id)
    )
    if status_filter:
        q = q.filter(NetworkRelationship.status == status_filter)
    if relationship_type:
        q = q.filter(NetworkRelationship.relationship_type == relationship_type)

    total = q.count()
    rows = q.order_by(NetworkRelationship.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    items = []
    for r in rows:
        req_co = db.query(Company).filter(Company.id == r.requesting_company_id).first()
        tgt_co = db.query(Company).filter(Company.id == r.target_company_id).first()
        resp = NetworkRelationshipResponse.model_validate(r)
        if req_co:
            resp.requesting_company = CompanySummary.model_validate(req_co)
        if tgt_co:
            resp.target_company = CompanySummary.model_validate(tgt_co)
        items.append(resp)

    return items, total


def get_relationship(
    db: Session, relationship_id: str, company_id: str
) -> NetworkRelationship:
    """Get a single relationship, verifying the company is a party."""
    rel = db.query(NetworkRelationship).filter(
        NetworkRelationship.id == relationship_id
    ).first()
    if not rel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found")
    if rel.requesting_company_id != company_id and rel.target_company_id != company_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this relationship")
    return rel


def create_relationship(
    db: Session, data: NetworkRelationshipCreate, company_id: str, actor_id: str
) -> NetworkRelationship:
    """Create a new cross-tenant relationship request."""
    if data.target_company_id == company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create a relationship with yourself",
        )
    target = db.query(Company).filter(Company.id == data.target_company_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target company not found")

    # Check for existing relationship
    existing = db.query(NetworkRelationship).filter(
        NetworkRelationship.requesting_company_id == company_id,
        NetworkRelationship.target_company_id == data.target_company_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Relationship already exists between these companies",
        )

    rel = NetworkRelationship(
        requesting_company_id=company_id,
        target_company_id=data.target_company_id,
        relationship_type=data.relationship_type,
        permissions=data.permissions,
        notes=data.notes,
        created_by=actor_id,
    )
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return rel


def update_relationship(
    db: Session,
    relationship_id: str,
    data: NetworkRelationshipUpdate,
    company_id: str,
) -> NetworkRelationship:
    """Update a relationship (status, permissions, notes)."""
    rel = get_relationship(db, relationship_id, company_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rel, key, value)
    db.commit()
    db.refresh(rel)
    return rel


def approve_relationship(
    db: Session, relationship_id: str, company_id: str, actor_id: str
) -> NetworkRelationship:
    """Approve a pending relationship (target company approves)."""
    rel = get_relationship(db, relationship_id, company_id)
    if rel.target_company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the target company can approve",
        )
    if rel.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve a relationship with status '{rel.status}'",
        )
    rel.status = "active"
    rel.approved_by = actor_id
    rel.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rel)
    return rel


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


def get_transactions(
    db: Session,
    company_id: str,
    page: int = 1,
    per_page: int = 25,
    relationship_id: str | None = None,
    transaction_type: str | None = None,
) -> tuple[list[NetworkTransactionResponse], int]:
    """List transactions where the company is source or target."""
    q = db.query(NetworkTransaction).filter(
        (NetworkTransaction.source_company_id == company_id)
        | (NetworkTransaction.target_company_id == company_id)
    )
    if relationship_id:
        q = q.filter(NetworkTransaction.relationship_id == relationship_id)
    if transaction_type:
        q = q.filter(NetworkTransaction.transaction_type == transaction_type)

    total = q.count()
    rows = q.order_by(NetworkTransaction.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    items = [NetworkTransactionResponse.model_validate(r) for r in rows]
    return items, total


def create_transaction(
    db: Session, data: NetworkTransactionCreate, company_id: str, actor_id: str
) -> NetworkTransaction:
    """Create a cross-tenant transaction."""
    # Verify relationship exists and is active
    rel = db.query(NetworkRelationship).filter(
        NetworkRelationship.id == data.relationship_id
    ).first()
    if not rel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found")
    if rel.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Relationship is not active",
        )
    # Verify company is a party
    if rel.requesting_company_id != company_id and rel.target_company_id != company_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a party to this relationship")

    tx = NetworkTransaction(
        relationship_id=data.relationship_id,
        source_company_id=company_id,
        target_company_id=data.target_company_id,
        transaction_type=data.transaction_type,
        source_record_type=data.source_record_type,
        source_record_id=data.source_record_id,
        target_record_type=data.target_record_type,
        target_record_id=data.target_record_id,
        payload=data.payload,
        created_by=actor_id,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def get_network_stats(db: Session, company_id: str) -> NetworkStats:
    """Aggregate network stats for a company."""
    base = db.query(NetworkRelationship).filter(
        (NetworkRelationship.requesting_company_id == company_id)
        | (NetworkRelationship.target_company_id == company_id)
    )
    total_rels = base.count()
    active_rels = base.filter(NetworkRelationship.status == "active").count()
    pending_rels = base.filter(NetworkRelationship.status == "pending").count()

    tx_base = db.query(NetworkTransaction).filter(
        (NetworkTransaction.source_company_id == company_id)
        | (NetworkTransaction.target_company_id == company_id)
    )
    total_txs = tx_base.count()
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    txs_30d = tx_base.filter(NetworkTransaction.created_at >= cutoff).count()

    return NetworkStats(
        total_relationships=total_rels,
        active_relationships=active_rels,
        pending_relationships=pending_rels,
        total_transactions=total_txs,
        transactions_30d=txs_30d,
    )
