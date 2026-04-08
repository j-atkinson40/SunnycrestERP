from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.services.document_service import (
    bulk_migrate_local_documents,
    delete_document,
    get_document,
    get_documents,
    get_download_url,
    upload_document,
)

router = APIRouter()


@router.post("/upload", status_code=201, response_model=DocumentResponse)
async def upload(
    file: UploadFile,
    entity_type: str = Query(..., description="e.g. employee, product, company"),
    entity_id: str = Query(..., description="ID of the parent entity"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.edit")),
):
    doc = await upload_document(
        db,
        file,
        company_id=current_user.company_id,
        entity_type=entity_type,
        entity_id=entity_id,
        uploaded_by=current_user.id,
    )
    return DocumentResponse.model_validate(doc)


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.view")),
):
    docs = get_documents(
        db,
        company_id=current_user.company_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    return [DocumentResponse.model_validate(d) for d in docs]


@router.get("/{document_id}/download")
def download(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.view")),
):
    """Download a document. Returns a 307 redirect to a signed R2 URL.

    Falls back to streaming from local disk for legacy documents that
    haven't been migrated yet.
    """
    doc, signed_url = get_download_url(db, document_id, current_user.company_id)

    if signed_url:
        return RedirectResponse(url=signed_url, status_code=307)

    # Fallback: serve local file directly (pre-R2 legacy document)
    return FileResponse(
        path=doc.file_path,
        filename=doc.file_name,
        media_type=doc.mime_type,
    )


@router.delete("/{document_id}")
def remove(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("employees.edit")),
):
    delete_document(db, document_id, current_user.company_id)
    return {"detail": "Document deleted"}


@router.post("/admin/migrate-local-docs")
def migrate_local_docs(
    company_id: str | None = Query(None, description="Scope to a specific tenant (optional)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Bulk-migrate all remaining local-path documents to R2.

    Admin-only endpoint. Scans for Document records with no r2_key,
    reads the local file, uploads to R2, and updates the record.
    """
    stats = bulk_migrate_local_documents(db, company_id=company_id)
    return stats
