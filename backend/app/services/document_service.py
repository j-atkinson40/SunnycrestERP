import logging
import os
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.document import Document
from app.services.legacy_r2_client import (
    delete_object,
    download_bytes,
    generate_signed_url,
    upload_bytes,
)

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# Legacy upload dir — only used for lazy migration of pre-R2 files
UPLOAD_BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")


def _build_r2_key(company_id: str, entity_type: str, entity_id: str, filename: str) -> str:
    """Build the R2 key for a document upload."""
    ext = os.path.splitext(filename)[1]
    unique_name = f"{uuid.uuid4()}{ext}"
    return f"tenants/{company_id}/{entity_type}s/{entity_id}/{unique_name}"


def _lazy_migrate_to_r2(db: Session, doc: Document) -> bool:
    """If a document has a local file_path but no r2_key, migrate it to R2 on access.

    Returns True if migration succeeded or was unnecessary, False if the local file is missing.
    """
    if doc.r2_key:
        return True  # Already on R2

    local_path = doc.file_path
    if not local_path or not local_path.startswith(("uploads", "/", ".")):
        return False

    # Normalize relative paths
    if not os.path.isabs(local_path):
        local_path = os.path.join(UPLOAD_BASE_DIR, "..", "..", local_path)

    if not os.path.exists(local_path):
        logger.warning(
            "Lazy migration: local file missing for document %s (path=%s)",
            doc.id,
            doc.file_path,
        )
        return False

    try:
        with open(local_path, "rb") as f:
            content = f.read()

        r2_key = f"tenants/{doc.company_id}/{doc.entity_type}s/{doc.entity_id}/{os.path.basename(local_path)}"
        upload_bytes(content, r2_key, content_type=doc.mime_type or "application/octet-stream")

        doc.r2_key = r2_key
        doc.file_path = r2_key  # Update for backward compat
        db.commit()

        logger.info("Lazy migrated document %s to R2: %s", doc.id, r2_key)
        return True
    except Exception as e:
        logger.error("Lazy migration failed for document %s: %s", doc.id, e)
        return False


async def upload_document(
    db: Session,
    file: UploadFile,
    company_id: str,
    entity_type: str,
    entity_id: str,
    uploaded_by: str | None = None,
) -> Document:
    """Upload a file to R2 and record metadata in the DB."""
    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {MAX_FILE_SIZE // (1024 * 1024)} MB",
        )

    filename = file.filename or "unnamed"
    r2_key = _build_r2_key(company_id, entity_type, entity_id, filename)

    upload_bytes(content, r2_key, content_type=file.content_type or "application/octet-stream")

    doc = Document(
        company_id=company_id,
        entity_type=entity_type,
        entity_id=entity_id,
        file_name=filename,
        file_path=r2_key,  # backward compat — same as r2_key
        r2_key=r2_key,
        file_size=len(content),
        mime_type=file.content_type or "application/octet-stream",
        uploaded_by=uploaded_by,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def get_documents(
    db: Session,
    company_id: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> list[Document]:
    """List documents, optionally filtered by entity type/id."""
    query = db.query(Document).filter(Document.company_id == company_id)
    if entity_type:
        query = query.filter(Document.entity_type == entity_type)
    if entity_id:
        query = query.filter(Document.entity_id == entity_id)
    return query.order_by(Document.created_at.desc()).all()


def get_document(db: Session, document_id: str, company_id: str) -> Document:
    """Get a single document by ID. Triggers lazy migration if needed."""
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.company_id == company_id)
        .first()
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    # Lazy migrate old local-path documents to R2 on first access
    if not doc.r2_key:
        _lazy_migrate_to_r2(db, doc)

    return doc


def get_download_url(db: Session, document_id: str, company_id: str) -> tuple[Document, str]:
    """Get a document and its signed download URL.

    Returns (doc, signed_url). Falls back to local file path for legacy docs
    that couldn't be migrated.
    """
    doc = get_document(db, document_id, company_id)

    if doc.r2_key:
        url = generate_signed_url(doc.r2_key, expires_in=3600)
        return doc, url

    # Fallback: local file still exists but migration failed
    if os.path.exists(doc.file_path):
        return doc, ""  # Empty URL signals caller to serve locally

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Document file not found — local file missing and R2 migration failed",
    )


def delete_document(db: Session, document_id: str, company_id: str) -> None:
    """Delete a document from R2 (or local disk) and remove the DB record."""
    doc = get_document(db, document_id, company_id)

    # Delete from R2
    if doc.r2_key:
        try:
            delete_object(doc.r2_key)
        except Exception as e:
            logger.warning("R2 delete failed for %s: %s (proceeding with DB delete)", doc.r2_key, e)

    # Also clean up local file if it exists (legacy)
    local_path = doc.file_path
    if local_path and not local_path.startswith("tenants/") and os.path.exists(local_path):
        try:
            os.remove(local_path)
        except OSError:
            pass

    db.delete(doc)
    db.commit()


def bulk_migrate_local_documents(db: Session, company_id: str | None = None) -> dict:
    """Migrate all remaining local-path documents to R2 in bulk.

    Returns stats dict with total, migrated, failed, already_on_r2 counts.
    """
    query = db.query(Document).filter(Document.r2_key.is_(None))
    if company_id:
        query = query.filter(Document.company_id == company_id)

    docs = query.all()
    stats = {"total": len(docs), "migrated": 0, "failed": 0, "already_on_r2": 0, "errors": []}

    for doc in docs:
        if doc.r2_key:
            stats["already_on_r2"] += 1
            continue

        success = _lazy_migrate_to_r2(db, doc)
        if success:
            stats["migrated"] += 1
        else:
            stats["failed"] += 1
            stats["errors"].append({"id": doc.id, "file_name": doc.file_name, "file_path": doc.file_path})

    return stats
