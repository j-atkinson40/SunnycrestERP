"""Social Service Certificate API routes.

Endpoints for listing, approving, voiding, and previewing
Social Service Delivery Certificates.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_permission
from app.models.user import User
from app.schemas.social_service_certificate import VoidCertificateRequest
from app.services.social_service_certificate_service import (
    SocialServiceCertificateService,
)

router = APIRouter()


@router.get("/pending")
def list_pending(
    current_user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    """List all pending_approval certificates for the current tenant."""
    return SocialServiceCertificateService.get_pending(db, current_user.company_id)


@router.get("/all")
def list_all(
    status: str | None = Query(None, description="Filter by status"),
    current_user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    """List all certificates (any status) for the management page."""
    return SocialServiceCertificateService.get_all(
        db, current_user.company_id, status_filter=status
    )


@router.get("/{certificate_id}")
def get_certificate(
    certificate_id: str,
    current_user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    """Get a single certificate with full details."""
    detail = SocialServiceCertificateService.get_detail(
        db, certificate_id, current_user.company_id
    )
    if not detail:
        raise HTTPException(status_code=404, detail="Certificate not found")
    return detail


@router.post("/{certificate_id}/approve")
def approve_certificate(
    certificate_id: str,
    current_user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    """Approve a pending certificate and send it to the funeral home."""
    try:
        cert = SocialServiceCertificateService.approve(
            certificate_id, current_user.id, db
        )
        return {
            "id": cert.id,
            "status": cert.status,
            "certificate_number": cert.certificate_number,
            "email_sent_to": cert.email_sent_to,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{certificate_id}/void")
def void_certificate(
    certificate_id: str,
    body: VoidCertificateRequest,
    current_user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    """Void a pending or approved certificate."""
    try:
        cert = SocialServiceCertificateService.void(
            certificate_id, current_user.id, body.reason, db
        )
        return {
            "id": cert.id,
            "status": cert.status,
            "certificate_number": cert.certificate_number,
            "void_reason": cert.void_reason,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{certificate_id}/pdf")
def get_pdf_url(
    certificate_id: str,
    current_user: User = Depends(require_permission("invoice.approve")),
    db: Session = Depends(get_db),
):
    """Return a presigned R2 URL for the certificate PDF."""
    from app.models.social_service_certificate import SocialServiceCertificate as SSC

    cert = (
        db.query(SSC)
        .filter(
            SSC.id == certificate_id,
            SSC.company_id == current_user.company_id,
        )
        .first()
    )
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if not cert.pdf_r2_key:
        raise HTTPException(status_code=404, detail="PDF not available")

    from app.services.legacy_r2_client import generate_signed_url

    url = generate_signed_url(cert.pdf_r2_key, expires_in=3600)
    return {"url": url}
