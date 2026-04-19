"""Public signer routes — Phase D-4.

Mounted at `/api/v1/sign/*`. NO authentication — the `signer_token` is
the sole auth mechanism and it's unique per party. Tokens are opaque
256-bit URL-safe strings; a successful lookup proves the caller holds
a valid invite.

Rate limit: 10 requests/minute per token (simple in-process token
bucket). If the app is ever scaled out horizontally, this becomes
per-worker — acceptable for D-4 because the signing flow is
low-volume; D-5+ swaps in Redis-backed limiting if needed.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.canonical_document import Document
from app.models.company import Company
from app.models.signature import SignatureParty
from app.schemas.signing import (
    ConsentRequest,
    DeclineRequest,
    SignActionResponse,
    SignerStatusResponse,
    SignRequest,
)
from app.services import legacy_r2_client
from app.services.signing import signature_service

router = APIRouter()


# ── Rate limiting ────────────────────────────────────────────────────
# Simple in-process token bucket keyed by signer_token. Good enough for
# D-4 single-worker deployment; scale-out will need a Redis upgrade.

_RATE_WINDOW_SECONDS = 60
_RATE_MAX_REQUESTS = 10
_REQUEST_LOG: dict[str, deque[float]] = defaultdict(deque)


def _check_rate_limit(token: str) -> None:
    now = time.time()
    window_start = now - _RATE_WINDOW_SECONDS
    log = _REQUEST_LOG[token]
    while log and log[0] < window_start:
        log.popleft()
    if len(log) >= _RATE_MAX_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Too many requests — signing endpoints are limited to "
                f"{_RATE_MAX_REQUESTS} requests per minute per token."
            ),
        )
    log.append(now)


def _get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _get_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


# ── Party resolution helper ──────────────────────────────────────────


def _get_active_party(db: Session, token: str) -> SignatureParty:
    """Resolve token → party. 404s if token is unknown OR envelope is
    in a terminal state where no signing action is permitted.

    For status-only GETs we use `_get_party_readonly` instead which
    allows lookup even on voided/expired envelopes so the signer sees
    the correct state message."""
    party = signature_service.get_party_by_token(db, token)
    if party is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired signing link",
        )
    # Terminal party states still resolvable (for status GET) but
    # action endpoints will re-check.
    return party


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("/{token}/status", response_model=SignerStatusResponse)
def get_signer_status(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """What state is this signer in? Used by the frontend to render the
    correct screen (welcome / review / consent / sign / complete / etc)."""
    _check_rate_limit(token)
    party = _get_active_party(db, token)
    envelope = party.envelope

    parties_sorted = sorted(
        envelope.parties, key=lambda p: p.signing_order
    )

    # Sequential: "my turn" means all prior parties have signed
    is_my_turn = True
    if envelope.routing_type == "sequential":
        for prior in parties_sorted:
            if prior.signing_order >= party.signing_order:
                break
            if prior.status != "signed":
                is_my_turn = False
                break

    signed_by_previous = [
        {
            "display_name": p.display_name,
            "role": p.role,
            "signed_at": p.signed_at.isoformat() if p.signed_at else None,
        }
        for p in parties_sorted
        if p.status == "signed" and p.signing_order < party.signing_order
    ]

    doc = db.query(Document).filter_by(id=envelope.document_id).first()
    company = db.query(Company).filter_by(id=envelope.company_id).first()

    return SignerStatusResponse(
        envelope_status=envelope.status,
        party_status=party.status,
        envelope_subject=envelope.subject,
        envelope_description=envelope.description,
        party_display_name=party.display_name,
        party_role=party.role,
        signing_order=party.signing_order,
        routing_type=envelope.routing_type,
        expires_at=envelope.expires_at,
        is_my_turn=is_my_turn,
        document_title=doc.title if doc else "",
        company_name=company.name if company else "",
        signed_by_previous_parties=signed_by_previous,
    )


@router.get("/{token}/document")
def download_document_for_signer(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """307 redirect to a presigned R2 URL for the document being signed.
    First call records a `link_viewed` event."""
    _check_rate_limit(token)
    party = _get_active_party(db, token)

    # Record first-view before redirecting
    signature_service.record_party_view(
        db,
        party,
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
    )
    db.commit()

    doc = db.query(Document).filter_by(id=party.envelope.document_id).first()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    try:
        url = legacy_r2_client.generate_signed_url(
            doc.storage_key, expires_in=3600
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not generate document URL: {exc}",
        )
    return RedirectResponse(url=url, status_code=307)


@router.post("/{token}/consent", response_model=SignActionResponse)
def record_consent(
    token: str,
    body: ConsentRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Record ESIGN-compliant consent before accepting a signature."""
    _check_rate_limit(token)
    party = _get_active_party(db, token)
    try:
        signature_service.record_party_consent(
            db,
            party,
            consent_text=body.consent_text,
            ip_address=_get_client_ip(request),
            user_agent=_get_user_agent(request),
        )
    except signature_service.SignatureServiceError as exc:
        raise HTTPException(exc.http_status, str(exc))
    db.commit()
    db.refresh(party)
    return SignActionResponse(
        party_status=party.status,
        envelope_status=party.envelope.status,
        message="Consent recorded",
    )


@router.post("/{token}/sign", response_model=SignActionResponse)
def sign_envelope(
    token: str,
    body: SignRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Capture the party's signature + field values. Advances routing."""
    _check_rate_limit(token)
    party = _get_active_party(db, token)
    try:
        signature_service.record_party_signature(
            db,
            party,
            signature_type=body.signature_type,
            signature_data=body.signature_data,
            typed_signature_name=body.typed_signature_name,
            field_values=body.field_values,
            ip_address=_get_client_ip(request),
            user_agent=_get_user_agent(request),
        )
    except signature_service.SignatureServiceError as exc:
        raise HTTPException(exc.http_status, str(exc))
    db.commit()
    db.refresh(party)
    return SignActionResponse(
        party_status=party.status,
        envelope_status=party.envelope.status,
        message="Signature captured",
    )


@router.post("/{token}/decline", response_model=SignActionResponse)
def decline_envelope(
    token: str,
    body: DeclineRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Decline to sign. Cancels the envelope."""
    _check_rate_limit(token)
    party = _get_active_party(db, token)
    try:
        signature_service.record_party_decline(
            db,
            party,
            reason=body.reason,
            ip_address=_get_client_ip(request),
            user_agent=_get_user_agent(request),
        )
    except signature_service.SignatureServiceError as exc:
        raise HTTPException(exc.http_status, str(exc))
    db.commit()
    db.refresh(party)
    return SignActionResponse(
        party_status=party.status,
        envelope_status=party.envelope.status,
        message="Decline recorded",
    )
