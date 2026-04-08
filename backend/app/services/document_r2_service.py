"""R2-backed document persistence service."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.document import Document
from app.services.legacy_r2_client import upload_bytes

logger = logging.getLogger(__name__)


def save_generated_document(
    db: Session,
    *,
    company_id: str,
    entity_type: str,
    entity_id: str,
    document_type: str,
    file_name: str,
    file_bytes: bytes,
    mime_type: str,
    generated_by: str | None = None,
    metadata: dict | None = None,
) -> Document:
    """Upload bytes to R2 and create a Document record. Returns the saved Document."""

    r2_key = f"tenants/{company_id}/{entity_type}s/{entity_id}/{document_type}/{file_name}"

    try:
        upload_bytes(file_bytes, r2_key, content_type=mime_type)
    except Exception as e:
        logger.error(f"R2 upload failed for {r2_key}: {e}")
        raise

    doc = Document(
        id=str(uuid.uuid4()),
        company_id=company_id,
        entity_type=entity_type,
        entity_id=entity_id,
        document_type=document_type,
        file_name=file_name,
        file_path=r2_key,  # keep file_path populated for backward compat
        r2_key=r2_key,
        file_size=len(file_bytes),
        mime_type=mime_type,
        uploaded_by=generated_by,
        metadata_json=metadata or {},
        created_at=datetime.now(timezone.utc),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def get_documents_for_entity(
    db: Session,
    company_id: str,
    entity_type: str,
    entity_id: str,
    document_type: str | None = None,
) -> list[Document]:
    """Fetch all documents for a given entity, optionally filtered by type."""
    q = db.query(Document).filter(
        Document.company_id == company_id,
        Document.entity_type == entity_type,
        Document.entity_id == entity_id,
        Document.r2_key.isnot(None),
    )
    if document_type:
        q = q.filter(Document.document_type == document_type)
    return q.order_by(Document.created_at.desc()).all()


def get_invoice_metadata_for_customer(
    db: Session,
    company_id: str,
    customer_id: str,
    limit: int = 10,
) -> list[dict]:
    """
    Pull recent invoice metadata for a customer — used by call overlay.
    Returns metadata_json dicts only (no PDF bytes needed at call time).
    """
    docs = (
        db.query(Document)
        .filter(
            Document.company_id == company_id,
            Document.entity_type == "invoice",
            Document.document_type == "invoice",
            Document.r2_key.isnot(None),
            Document.metadata_json.isnot(None),
        )
        .order_by(Document.created_at.desc())
        .limit(limit)
        .all()
    )
    # Filter to this customer using metadata_json
    return [
        doc.metadata_json
        for doc in docs
        if doc.metadata_json and doc.metadata_json.get("customer_id") == customer_id
    ]
