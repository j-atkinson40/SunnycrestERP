"""Family Portal API routes (unauthenticated, token-based access)."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import Depends

from app.database import get_db
from app.services import portal_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Request schemas (inline)
# ---------------------------------------------------------------------------


class ObituaryApproval(BaseModel):
    approved: bool
    change_notes: str | None = None


class PortalMessage(BaseModel):
    message: str


class PortalDocumentUpload(BaseModel):
    document_type: str
    document_name: str
    file_url: str


# ---------------------------------------------------------------------------
# Portal endpoints — no JWT auth, token-validated
# ---------------------------------------------------------------------------


@router.get("/{token}")
def get_portal_data(
    token: str,
    db: Session = Depends(get_db),
):
    """Validate portal token and return case data for family."""
    result = portal_service.validate_token(db, token)
    if not result:
        raise HTTPException(status_code=404, detail="Invalid or expired portal link")
    case_id, contact_id = result
    return portal_service.get_portal_data(db, case_id, contact_id)


@router.post("/{token}/obituary/approve")
def approve_obituary(
    token: str,
    data: ObituaryApproval,
    db: Session = Depends(get_db),
):
    """Approve or request changes to obituary via portal."""
    result = portal_service.validate_token(db, token)
    if not result:
        raise HTTPException(status_code=404, detail="Invalid or expired portal link")
    portal_service.submit_obituary_approval(
        db, token, data.approved, data.change_notes
    )
    return {"detail": "Obituary feedback submitted"}


@router.post("/{token}/message")
def send_message(
    token: str,
    data: PortalMessage,
    db: Session = Depends(get_db),
):
    """Send a message to the funeral director via portal."""
    result = portal_service.validate_token(db, token)
    if not result:
        raise HTTPException(status_code=404, detail="Invalid or expired portal link")
    portal_service.submit_message(db, token, data.message)
    return {"detail": "Message sent"}


@router.post("/{token}/documents", status_code=201)
def upload_document(
    token: str,
    data: PortalDocumentUpload,
    db: Session = Depends(get_db),
):
    """Upload a document via the family portal."""
    result = portal_service.validate_token(db, token)
    if not result:
        raise HTTPException(status_code=404, detail="Invalid or expired portal link")
    portal_service.upload_portal_document(
        db, token, data.document_type, data.document_name, data.file_url
    )
    return {"detail": "Document uploaded"}
