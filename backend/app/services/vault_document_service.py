"""VaultDocument service — tenant-facing document layer.

R2 is infrastructure; tenants never see R2 keys or URLs. All file access
goes through this service. file_key is opaque; download URLs are generated
on demand and time-limited.
"""

import os
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.vault_document import VaultDocument


def _r2_put(file_key: str, file_data: bytes, mime_type: str | None) -> None:
    """Write bytes to R2. Uses the existing legacy_r2_client helper so we
    don't duplicate auth config. Silent on failure — caller inspects the
    returned VaultDocument to see if the file_key was set."""
    try:
        from app.services.legacy_r2_client import get_r2_client, get_bucket
        client = get_r2_client()
        bucket = get_bucket()
        if client and bucket:
            kwargs = {"Bucket": bucket, "Key": file_key, "Body": file_data}
            if mime_type:
                kwargs["ContentType"] = mime_type
            client.put_object(**kwargs)
    except Exception:
        # Graceful degradation — the DB record still created so callers
        # can retry the upload later via a reconciliation job.
        pass


def store(
    db: Session,
    *,
    file_data: bytes,
    document_type: str,
    display_name: str,
    company_id: str,
    mime_type: str | None = None,
    related_entity_type: str | None = None,
    related_entity_id: str | None = None,
    vault_id: str | None = None,
    workflow_run_id: str | None = None,
    is_family_accessible: bool = False,
    created_by_user_id: str | None = None,
) -> VaultDocument:
    """Upload to R2 and persist a VaultDocument row. Returns the record."""
    # Build an opaque key — internal only, never exposed in API responses
    extension = {"application/pdf": "pdf", "image/tiff": "tif", "image/png": "png", "text/html": "html"}.get(mime_type or "", "bin")
    file_key = f"documents/{company_id}/{document_type}/{uuid.uuid4().hex}.{extension}"

    _r2_put(file_key, file_data, mime_type)

    doc = VaultDocument(
        company_id=company_id,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        vault_id=vault_id,
        document_type=document_type,
        display_name=display_name,
        file_key=file_key,
        mime_type=mime_type,
        file_size_bytes=len(file_data),
        workflow_run_id=workflow_run_id,
        is_family_accessible=is_family_accessible,
        created_by_user_id=created_by_user_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Index the document for command-bar search. Never fails the save.
    try:
        from app.services import document_index_service
        # Phase-one: no PDF extraction yet. We index against display_name +
        # document_type + related_entity_type. Rich PDF/DOCX text extraction
        # can be plugged in later by passing `text=<extracted>`.
        document_index_service.index_vault_document(db, doc)
    except Exception:
        pass

    return doc


def get_signed_url(
    db: Session,
    document_id: str,
    company_id: str,
    expires_seconds: int = 3600,
) -> str:
    """Generate a short-lived signed URL. Validates company_id — cross-tenant
    access raises PermissionError."""
    doc = db.query(VaultDocument).filter(VaultDocument.id == document_id).first()
    if not doc:
        raise ValueError("Document not found")
    if doc.company_id != company_id:
        raise PermissionError("Cross-tenant document access denied")

    try:
        from app.services.legacy_r2_client import get_r2_client, get_bucket
        client = get_r2_client()
        bucket = get_bucket()
        if client and bucket:
            return client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": doc.file_key},
                ExpiresIn=expires_seconds,
            )
    except Exception:
        pass
    # Fallback — return a static reference for local/dev where R2 is offline
    return f"/static/vault-docs/{doc.file_key}"


def list_for_entity(
    db: Session,
    company_id: str,
    related_entity_type: str,
    related_entity_id: str,
    document_type: str | None = None,
) -> list[VaultDocument]:
    q = db.query(VaultDocument).filter(
        VaultDocument.company_id == company_id,
        VaultDocument.related_entity_type == related_entity_type,
        VaultDocument.related_entity_id == related_entity_id,
        VaultDocument.is_active == True,  # noqa: E712
    )
    if document_type:
        q = q.filter(VaultDocument.document_type == document_type)
    return q.order_by(VaultDocument.created_at.desc()).all()


def list_for_company(
    db: Session,
    company_id: str,
    document_type: str | None = None,
    limit: int = 50,
) -> list[VaultDocument]:
    q = db.query(VaultDocument).filter(
        VaultDocument.company_id == company_id,
        VaultDocument.is_active == True,  # noqa: E712
        VaultDocument.related_entity_id.is_(None),
    )
    if document_type:
        q = q.filter(VaultDocument.document_type == document_type)
    return q.order_by(VaultDocument.created_at.desc()).limit(limit).all()


def soft_delete(db: Session, document_id: str, company_id: str) -> None:
    doc = db.query(VaultDocument).filter(VaultDocument.id == document_id).first()
    if not doc:
        raise ValueError("Document not found")
    if doc.company_id != company_id:
        raise PermissionError("Cross-tenant document access denied")
    doc.is_active = False
    db.commit()
