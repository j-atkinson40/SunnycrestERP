from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.services.document_service import (
    delete_document,
    get_document,
    get_documents,
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
    doc = get_document(db, document_id, current_user.company_id)
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
