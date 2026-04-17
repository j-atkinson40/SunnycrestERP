"""VaultDocument API — native tenant-facing document layer.

Separate from the legacy documents.py route (which handles the older
document entity). New code should use this router mounted at /vault-documents.
"""

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.services import vault_document_service


router = APIRouter()


def _serialize(doc) -> dict:
    return {
        "id": doc.id,
        "related_entity_type": doc.related_entity_type,
        "related_entity_id": doc.related_entity_id,
        "document_type": doc.document_type,
        "display_name": doc.display_name,
        "mime_type": doc.mime_type,
        "file_size_bytes": doc.file_size_bytes,
        "is_family_accessible": doc.is_family_accessible,
        "workflow_run_id": doc.workflow_run_id,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        # file_key deliberately omitted — R2 details never leave the server
    }


@router.get("")
def list_documents(
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    document_type: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if entity_type and entity_id:
        docs = vault_document_service.list_for_entity(
            db, current_user.company_id, entity_type, entity_id, document_type
        )
    else:
        docs = vault_document_service.list_for_company(
            db, current_user.company_id, document_type
        )
    return [_serialize(d) for d in docs]


@router.get("/{document_id}/download")
def get_download_url(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        url = vault_document_service.get_signed_url(
            db, document_id, current_user.company_id, expires_seconds=3600
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=3600)).isoformat()
    return {"url": url, "expires_at": expires_at}


@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        vault_document_service.soft_delete(db, document_id, current_user.company_id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"deleted": True}
