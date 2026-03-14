"""Cross-tenant network relationship and transaction routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.network import (
    NetworkRelationshipCreate,
    NetworkRelationshipResponse,
    NetworkRelationshipUpdate,
    NetworkStats,
    NetworkTransactionCreate,
    NetworkTransactionResponse,
    PaginatedRelationships,
    PaginatedTransactions,
)
from app.services import network_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=NetworkStats)
def get_network_stats(
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get network statistics for the current company."""
    return network_service.get_network_stats(db, user.company_id)


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------


@router.get("/relationships", response_model=PaginatedRelationships)
def list_relationships(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    status: str | None = None,
    relationship_type: str | None = None,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List cross-tenant relationships for the current company."""
    items, total = network_service.get_relationships(
        db, user.company_id, page, per_page, status, relationship_type
    )
    return PaginatedRelationships(
        items=items, total=total, page=page, per_page=per_page
    )


@router.post("/relationships", response_model=NetworkRelationshipResponse)
def create_relationship(
    body: NetworkRelationshipCreate,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Request a new cross-tenant relationship."""
    rel = network_service.create_relationship(db, body, user.company_id, user.id)
    return NetworkRelationshipResponse.model_validate(rel)


@router.get(
    "/relationships/{relationship_id}",
    response_model=NetworkRelationshipResponse,
)
def get_relationship(
    relationship_id: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get a single relationship."""
    rel = network_service.get_relationship(db, relationship_id, user.company_id)
    return NetworkRelationshipResponse.model_validate(rel)


@router.patch(
    "/relationships/{relationship_id}",
    response_model=NetworkRelationshipResponse,
)
def update_relationship(
    relationship_id: str,
    body: NetworkRelationshipUpdate,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a relationship."""
    rel = network_service.update_relationship(
        db, relationship_id, body, user.company_id
    )
    return NetworkRelationshipResponse.model_validate(rel)


@router.post(
    "/relationships/{relationship_id}/approve",
    response_model=NetworkRelationshipResponse,
)
def approve_relationship(
    relationship_id: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Approve a pending relationship request."""
    rel = network_service.approve_relationship(
        db, relationship_id, user.company_id, user.id
    )
    return NetworkRelationshipResponse.model_validate(rel)


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


@router.get("/transactions", response_model=PaginatedTransactions)
def list_transactions(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    relationship_id: str | None = None,
    transaction_type: str | None = None,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List cross-tenant transactions."""
    items, total = network_service.get_transactions(
        db, user.company_id, page, per_page, relationship_id, transaction_type
    )
    return PaginatedTransactions(
        items=items, total=total, page=page, per_page=per_page
    )


@router.post("/transactions", response_model=NetworkTransactionResponse)
def create_transaction(
    body: NetworkTransactionCreate,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a cross-tenant transaction."""
    tx = network_service.create_transaction(db, body, user.company_id, user.id)
    return NetworkTransactionResponse.model_validate(tx)
