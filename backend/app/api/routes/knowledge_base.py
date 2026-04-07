"""Knowledge Base API routes.

Endpoints for managing KB categories, documents, pricing entries, retrieval,
and extension notifications.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.company import Company
from app.models.kb_category import KBCategory
from app.models.kb_chunk import KBChunk
from app.models.kb_document import KBDocument
from app.models.kb_pricing_entry import KBPricingEntry
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_FILE_TYPES = {"pdf", "docx", "csv", "txt"}


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class CategoryCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    icon: str | None = None
    display_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    display_order: int | None = None


class DocumentManualCreate(BaseModel):
    category_id: str
    title: str
    description: str | None = None
    content: str


class PricingEntryCreate(BaseModel):
    product_name: str
    product_code: str | None = None
    description: str | None = None
    standard_price: float | None = None
    contractor_price: float | None = None
    homeowner_price: float | None = None
    unit: str = "each"
    notes: str | None = None


class PricingEntryUpdate(BaseModel):
    product_name: str | None = None
    product_code: str | None = None
    description: str | None = None
    standard_price: float | None = None
    contractor_price: float | None = None
    homeowner_price: float | None = None
    unit: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class RetrieveRequest(BaseModel):
    query: str
    query_type: str = "general"
    caller_company_id: str | None = None


class SeedRequest(BaseModel):
    vertical: str = "manufacturing"
    extensions: list[str] | None = None


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

@router.get("/categories")
def list_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all KB categories for the tenant. Auto-seeds if empty."""
    categories = (
        db.query(KBCategory)
        .filter(KBCategory.tenant_id == current_user.company_id)
        .order_by(KBCategory.display_order, KBCategory.name)
        .all()
    )

    # Auto-seed system categories on first access
    if not categories:
        try:
            from app.services.kb_setup_service import seed_categories as do_seed

            company = db.query(Company).filter_by(id=current_user.company_id).first()
            vertical = "manufacturing"
            if company and hasattr(company, "settings"):
                vertical = (company.settings or {}).get("vertical", "manufacturing")

            do_seed(db=db, tenant_id=current_user.company_id, vertical=vertical)
            db.commit()

            categories = (
                db.query(KBCategory)
                .filter(KBCategory.tenant_id == current_user.company_id)
                .order_by(KBCategory.display_order, KBCategory.name)
                .all()
            )
        except Exception:
            logger.exception("Auto-seed KB categories failed")

    return [_serialize_category(c, db) for c in categories]


@router.post("/categories", status_code=status.HTTP_201_CREATED)
def create_category(
    data: CategoryCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a custom KB category."""
    cat = KBCategory(
        id=str(uuid.uuid4()),
        tenant_id=current_user.company_id,
        name=data.name,
        slug=data.slug,
        description=data.description,
        display_order=data.display_order,
        is_system=False,
        icon=data.icon,
    )
    db.add(cat)
    db.commit()
    return _serialize_category(cat, db)


@router.put("/categories/{category_id}")
def update_category(
    category_id: str,
    data: CategoryUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a KB category."""
    cat = _get_category(db, current_user.company_id, category_id)
    if data.name is not None:
        cat.name = data.name
    if data.description is not None:
        cat.description = data.description
    if data.icon is not None:
        cat.icon = data.icon
    if data.display_order is not None:
        cat.display_order = data.display_order
    db.commit()
    return _serialize_category(cat, db)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a custom KB category (system categories cannot be deleted)."""
    cat = _get_category(db, current_user.company_id, category_id)
    if cat.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete system categories")
    # Delete associated chunks and documents
    doc_ids = [d.id for d in db.query(KBDocument.id).filter(KBDocument.category_id == category_id).all()]
    if doc_ids:
        db.query(KBChunk).filter(KBChunk.document_id.in_(doc_ids)).delete(synchronize_session=False)
        db.query(KBDocument).filter(KBDocument.id.in_(doc_ids)).delete(synchronize_session=False)
    db.delete(cat)
    db.commit()


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@router.get("/documents")
def list_documents(
    category_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List KB documents, optionally filtered by category."""
    q = db.query(KBDocument).filter(
        KBDocument.tenant_id == current_user.company_id,
        KBDocument.is_active == True,  # noqa: E712
    )
    if category_id:
        q = q.filter(KBDocument.category_id == category_id)
    docs = q.order_by(KBDocument.created_at.desc()).all()
    return [_serialize_document(d) for d in docs]


@router.get("/documents/{document_id}")
def get_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single KB document with parsed content."""
    doc = _get_document(db, current_user.company_id, document_id)
    result = _serialize_document(doc)
    if doc.parsed_content:
        try:
            result["parsed_content"] = json.loads(doc.parsed_content)
        except (json.JSONDecodeError, TypeError):
            result["parsed_content"] = None
    return result


@router.post("/documents/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    category_id: str = Query(...),
    title: str = Query(...),
    description: str | None = Query(None),
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Upload a document file for parsing."""
    # Validate file type
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if file.filename else ""
    if ext not in ALLOWED_FILE_TYPES:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' not supported. Use: {', '.join(ALLOWED_FILE_TYPES)}")

    # Validate category exists
    _get_category(db, current_user.company_id, category_id)

    # Read file
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 10 MB limit")

    # Extract raw text
    from app.services.kb_parsing_service import extract_raw_text

    raw_text = extract_raw_text(content, ext)

    doc = KBDocument(
        id=str(uuid.uuid4()),
        tenant_id=current_user.company_id,
        category_id=category_id,
        title=title,
        description=description,
        file_name=file.filename,
        file_type=ext,
        file_size_bytes=len(content),
        raw_content=raw_text,
        parsing_status="pending",
        uploaded_by_user_id=current_user.id,
    )
    db.add(doc)
    db.commit()

    # Trigger parsing
    from app.services.kb_parsing_service import parse_document

    parse_result = parse_document(
        db=db,
        document_id=doc.id,
        tenant_id=current_user.company_id,
    )

    return {**_serialize_document(doc), "parse_result": parse_result}


@router.post("/documents/manual", status_code=status.HTTP_201_CREATED)
def create_manual_document(
    data: DocumentManualCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a document from manually entered text."""
    _get_category(db, current_user.company_id, data.category_id)

    doc = KBDocument(
        id=str(uuid.uuid4()),
        tenant_id=current_user.company_id,
        category_id=data.category_id,
        title=data.title,
        description=data.description,
        file_type="manual",
        raw_content=data.content,
        parsing_status="pending",
        uploaded_by_user_id=current_user.id,
    )
    db.add(doc)
    db.commit()

    from app.services.kb_parsing_service import parse_document

    parse_result = parse_document(
        db=db,
        document_id=doc.id,
        tenant_id=current_user.company_id,
    )

    return {**_serialize_document(doc), "parse_result": parse_result}


@router.post("/documents/{document_id}/reparse")
def reparse_document(
    document_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Re-run parsing on an existing document."""
    doc = _get_document(db, current_user.company_id, document_id)

    from app.services.kb_parsing_service import parse_document

    result = parse_document(
        db=db,
        document_id=doc.id,
        tenant_id=current_user.company_id,
    )
    return result


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Soft-delete a KB document."""
    doc = _get_document(db, current_user.company_id, document_id)
    doc.is_active = False
    db.commit()


# ---------------------------------------------------------------------------
# Pricing entries
# ---------------------------------------------------------------------------

@router.get("/pricing")
def list_pricing_entries(
    search: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List pricing entries with optional search."""
    q = db.query(KBPricingEntry).filter(
        KBPricingEntry.tenant_id == current_user.company_id,
        KBPricingEntry.is_active == True,  # noqa: E712
    )
    if search:
        from sqlalchemy import func
        pattern = f"%{search.lower()}%"
        q = q.filter(
            func.lower(KBPricingEntry.product_name).like(pattern)
            | func.lower(KBPricingEntry.product_code).like(pattern)
        )
    entries = q.order_by(KBPricingEntry.product_name).limit(200).all()
    return [_serialize_pricing_entry(e) for e in entries]


@router.post("/pricing", status_code=status.HTTP_201_CREATED)
def create_pricing_entry(
    data: PricingEntryCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a manual pricing entry."""
    entry = KBPricingEntry(
        id=str(uuid.uuid4()),
        tenant_id=current_user.company_id,
        product_name=data.product_name,
        product_code=data.product_code,
        description=data.description,
        standard_price=data.standard_price,
        contractor_price=data.contractor_price,
        homeowner_price=data.homeowner_price,
        unit=data.unit,
        notes=data.notes,
    )
    db.add(entry)
    db.commit()
    return _serialize_pricing_entry(entry)


@router.put("/pricing/{entry_id}")
def update_pricing_entry(
    entry_id: str,
    data: PricingEntryUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a pricing entry."""
    entry = (
        db.query(KBPricingEntry)
        .filter(
            KBPricingEntry.id == entry_id,
            KBPricingEntry.tenant_id == current_user.company_id,
        )
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Pricing entry not found")

    for field in ("product_name", "product_code", "description", "standard_price",
                  "contractor_price", "homeowner_price", "unit", "notes", "is_active"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(entry, field, val)

    db.commit()
    return _serialize_pricing_entry(entry)


@router.delete("/pricing/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pricing_entry(
    entry_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Soft-delete a pricing entry."""
    entry = (
        db.query(KBPricingEntry)
        .filter(
            KBPricingEntry.id == entry_id,
            KBPricingEntry.tenant_id == current_user.company_id,
        )
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Pricing entry not found")
    entry.is_active = False
    db.commit()


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

@router.post("/retrieve")
def retrieve_knowledge(
    data: RetrieveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve KB information for a query (used by call overlay and general search)."""
    from app.services.kb_retrieval_service import retrieve_for_call

    result = retrieve_for_call(
        db=db,
        tenant_id=current_user.company_id,
        query=data.query,
        query_type=data.query_type,
        caller_company_id=data.caller_company_id,
    )

    return {
        "query": result.query,
        "query_type": result.query_type,
        "synthesis": result.synthesis,
        "confidence": result.confidence,
        "source_documents": result.source_documents,
        "pricing": [
            {
                "product_name": p.product_name,
                "product_code": p.product_code,
                "price": str(p.price) if p.price else None,
                "price_tier": p.price_tier,
                "unit": p.unit,
                "notes": p.notes,
            }
            for p in result.pricing_results
        ],
        "chunks_count": len(result.results),
    }


# ---------------------------------------------------------------------------
# Setup / seeding
# ---------------------------------------------------------------------------

@router.post("/seed")
def seed_categories(
    data: SeedRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Seed system KB categories for the tenant."""
    from app.services.kb_setup_service import seed_categories as do_seed

    count = do_seed(
        db=db,
        tenant_id=current_user.company_id,
        vertical=data.vertical,
        enabled_extensions=data.extensions,
    )
    db.commit()
    return {"categories_created": count}


# ---------------------------------------------------------------------------
# Extension notifications
# ---------------------------------------------------------------------------

@router.get("/notifications")
def get_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get pending KB extension notifications."""
    from app.services.kb_setup_service import get_pending_notifications

    return get_pending_notifications(db, current_user.company_id)


@router.post("/notifications/{notification_id}/acknowledge")
def acknowledge_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Acknowledge a KB extension notification."""
    from app.services.kb_setup_service import acknowledge_notification as do_ack

    success = do_ack(db, notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    db.commit()
    return {"acknowledged": True}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats")
def get_kb_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get KB statistics for the tenant."""
    tenant_id = current_user.company_id
    from sqlalchemy import func

    doc_count = db.query(func.count(KBDocument.id)).filter(
        KBDocument.tenant_id == tenant_id, KBDocument.is_active == True  # noqa: E712
    ).scalar() or 0

    chunk_count = db.query(func.count(KBChunk.id)).filter(
        KBChunk.tenant_id == tenant_id
    ).scalar() or 0

    pricing_count = db.query(func.count(KBPricingEntry.id)).filter(
        KBPricingEntry.tenant_id == tenant_id, KBPricingEntry.is_active == True  # noqa: E712
    ).scalar() or 0

    category_count = db.query(func.count(KBCategory.id)).filter(
        KBCategory.tenant_id == tenant_id
    ).scalar() or 0

    return {
        "documents": doc_count,
        "chunks": chunk_count,
        "pricing_entries": pricing_count,
        "categories": category_count,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_category(db: Session, tenant_id: str, category_id: str) -> KBCategory:
    cat = (
        db.query(KBCategory)
        .filter(KBCategory.id == category_id, KBCategory.tenant_id == tenant_id)
        .first()
    )
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return cat


def _get_document(db: Session, tenant_id: str, document_id: str) -> KBDocument:
    doc = (
        db.query(KBDocument)
        .filter(
            KBDocument.id == document_id,
            KBDocument.tenant_id == tenant_id,
            KBDocument.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _serialize_category(cat: KBCategory, db: Session) -> dict:
    from sqlalchemy import func

    doc_count = db.query(func.count(KBDocument.id)).filter(
        KBDocument.category_id == cat.id,
        KBDocument.is_active == True,  # noqa: E712
    ).scalar() or 0

    return {
        "id": cat.id,
        "name": cat.name,
        "slug": cat.slug,
        "description": cat.description,
        "display_order": cat.display_order,
        "is_system": cat.is_system,
        "icon": cat.icon,
        "document_count": doc_count,
        "created_at": cat.created_at.isoformat() if cat.created_at else None,
    }


def _serialize_document(doc: KBDocument) -> dict:
    return {
        "id": doc.id,
        "category_id": doc.category_id,
        "title": doc.title,
        "description": doc.description,
        "file_name": doc.file_name,
        "file_type": doc.file_type,
        "file_size_bytes": doc.file_size_bytes,
        "parsing_status": doc.parsing_status,
        "parsing_error": doc.parsing_error,
        "chunk_count": doc.chunk_count,
        "last_parsed_at": doc.last_parsed_at.isoformat() if doc.last_parsed_at else None,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


def _serialize_pricing_entry(entry: KBPricingEntry) -> dict:
    return {
        "id": entry.id,
        "product_name": entry.product_name,
        "product_code": entry.product_code,
        "description": entry.description,
        "standard_price": str(entry.standard_price) if entry.standard_price else None,
        "contractor_price": str(entry.contractor_price) if entry.contractor_price else None,
        "homeowner_price": str(entry.homeowner_price) if entry.homeowner_price else None,
        "unit": entry.unit,
        "notes": entry.notes,
        "is_active": entry.is_active,
        "document_id": entry.document_id,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
    }
