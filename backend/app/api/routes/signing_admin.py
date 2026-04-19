"""Admin signing routes — Phase D-4.

Mounted at `/api/v1/admin/signing/*`. Admin-gated, tenant-scoped.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models.canonical_document import Document
from app.models.signature import (
    SignatureEnvelope,
    SignatureEvent,
    SignatureParty,
)
from app.models.user import User
from app.schemas.signing import (
    EnvelopeCreateRequest,
    EnvelopeDetailResponse,
    EnvelopeListItem,
    EnvelopeVoidRequest,
    PartyResponse,
    SignatureEventResponse,
)
from app.services.signing import signature_service

router = APIRouter()


# ── Envelope CRUD ────────────────────────────────────────────────────


@router.post(
    "/envelopes",
    response_model=EnvelopeDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_envelope(
    body: EnvelopeCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new envelope in draft status."""
    # Verify the document belongs to the caller's tenant
    doc = (
        db.query(Document)
        .filter(
            Document.id == body.document_id,
            Document.company_id == current_user.company_id,
        )
        .first()
    )
    if doc is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Document not found or not visible to this tenant",
        )
    try:
        envelope = signature_service.create_envelope(
            db,
            document_id=body.document_id,
            company_id=current_user.company_id,
            created_by_user_id=current_user.id,
            subject=body.subject,
            description=body.description,
            parties=[
                signature_service.PartyInput(**p.model_dump())
                for p in body.parties
            ],
            fields=[
                signature_service.FieldInput(**f.model_dump())
                for f in body.fields
            ],
            routing_type=body.routing_type,
            expires_in_days=body.expires_in_days,
        )
    except signature_service.SignatureServiceError as exc:
        raise HTTPException(exc.http_status, str(exc))
    db.commit()
    db.refresh(envelope)
    return envelope


@router.post(
    "/envelopes/{envelope_id}/send",
    response_model=EnvelopeDetailResponse,
)
def send_envelope_endpoint(
    envelope_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Transition envelope from draft to sent. Notifies the first party
    (sequential) or all parties (parallel)."""
    _get_envelope_for_tenant(db, envelope_id, current_user.company_id)
    try:
        envelope = signature_service.send_envelope(
            db, envelope_id, actor_user_id=current_user.id
        )
    except signature_service.SignatureServiceError as exc:
        raise HTTPException(exc.http_status, str(exc))
    db.commit()
    db.refresh(envelope)
    return envelope


@router.get("/envelopes", response_model=list[EnvelopeListItem])
def list_envelopes(
    status_filter: str | None = Query(None, alias="status"),
    document_id: str | None = Query(None),
    created_after: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List envelopes for the current tenant."""
    q = db.query(SignatureEnvelope).filter(
        SignatureEnvelope.company_id == current_user.company_id
    )
    if status_filter:
        q = q.filter(SignatureEnvelope.status == status_filter)
    if document_id:
        q = q.filter(SignatureEnvelope.document_id == document_id)
    if created_after:
        q = q.filter(SignatureEnvelope.created_at >= created_after)
    return (
        q.order_by(desc(SignatureEnvelope.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get(
    "/envelopes/{envelope_id}", response_model=EnvelopeDetailResponse
)
def get_envelope(
    envelope_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Full envelope detail — parties + fields."""
    return _get_envelope_for_tenant(
        db, envelope_id, current_user.company_id
    )


@router.post(
    "/envelopes/{envelope_id}/void",
    response_model=EnvelopeDetailResponse,
)
def void_envelope_endpoint(
    envelope_id: str,
    body: EnvelopeVoidRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Void a non-terminal envelope. Cancels pending parties."""
    _get_envelope_for_tenant(db, envelope_id, current_user.company_id)
    try:
        envelope = signature_service.void_envelope(
            db,
            envelope_id,
            reason=body.reason,
            voided_by_user_id=current_user.id,
        )
    except signature_service.SignatureServiceError as exc:
        raise HTTPException(exc.http_status, str(exc))
    db.commit()
    db.refresh(envelope)
    return envelope


@router.post(
    "/parties/{party_id}/resend",
    response_model=PartyResponse,
)
def resend_notification(
    party_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Resend signing-link email to the party."""
    party = db.query(SignatureParty).filter_by(id=party_id).first()
    if party is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Party not found")
    # Tenant-scope via envelope
    if party.envelope.company_id != current_user.company_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Party not found")
    try:
        party = signature_service.resend_notification(
            db, party_id, actor_user_id=current_user.id
        )
    except signature_service.SignatureServiceError as exc:
        raise HTTPException(exc.http_status, str(exc))
    db.commit()
    db.refresh(party)
    return party


@router.get(
    "/envelopes/{envelope_id}/events",
    response_model=list[SignatureEventResponse],
)
def list_events(
    envelope_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Paginated audit timeline for this envelope."""
    _get_envelope_for_tenant(db, envelope_id, current_user.company_id)
    return (
        db.query(SignatureEvent)
        .filter(SignatureEvent.envelope_id == envelope_id)
        .order_by(SignatureEvent.sequence_number)
        .offset(offset)
        .limit(limit)
        .all()
    )


# ── Helpers ──────────────────────────────────────────────────────────


def _get_envelope_for_tenant(
    db: Session, envelope_id: str, company_id: str
) -> SignatureEnvelope:
    env = signature_service.get_envelope_for_tenant(
        db, envelope_id, company_id
    )
    if env is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Envelope not found"
        )
    return env
