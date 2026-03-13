import os
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.document import Document

# Base upload directory — each company gets a subdirectory
UPLOAD_BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


async def upload_document(
    db: Session,
    file: UploadFile,
    company_id: str,
    entity_type: str,
    entity_id: str,
    uploaded_by: str | None = None,
) -> Document:
    """Save an uploaded file to the filesystem and record metadata in the DB."""
    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {MAX_FILE_SIZE // (1024 * 1024)} MB",
        )

    # Ensure the company upload directory exists
    company_dir = os.path.join(UPLOAD_BASE_DIR, company_id, entity_type)
    os.makedirs(company_dir, exist_ok=True)

    # Generate a unique filename to avoid collisions
    ext = os.path.splitext(file.filename or "file")[1]
    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(company_dir, unique_name)

    with open(file_path, "wb") as f:
        f.write(content)

    doc = Document(
        company_id=company_id,
        entity_type=entity_type,
        entity_id=entity_id,
        file_name=file.filename or "unnamed",
        file_path=file_path,
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
    """Get a single document by ID."""
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.company_id == company_id)
        .first()
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    return doc


def delete_document(db: Session, document_id: str, company_id: str) -> None:
    """Delete a document record and its file from disk."""
    doc = get_document(db, document_id, company_id)

    # Remove file from disk
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    db.delete(doc)
    db.commit()
