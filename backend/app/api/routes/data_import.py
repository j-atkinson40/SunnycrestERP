"""Data Import API routes.

Historical data import with intelligent product/customer matching,
duplicate detection, and alias learning.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.company_resolver import get_current_company
from app.api.deps import get_current_user
from app.database import get_db
from app.models.company import Company
from app.models.user import User

router = APIRouter()


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class MatchProductsRequest(BaseModel):
    session_id: str
    unique_products: list[str]


class MatchCustomersRequest(BaseModel):
    session_id: str
    unique_customers: list[str]


class DetectDuplicatesRequest(BaseModel):
    session_id: str


class ExecuteImportRequest(BaseModel):
    session_id: str
    confirmed_product_matches: Optional[dict] = None
    confirmed_customer_matches: Optional[dict] = None
    duplicate_handling: Optional[dict] = None


class LearnAliasRequest(BaseModel):
    alias_text: str
    canonical_product_id: str


class IntelligenceSummaryRequest(BaseModel):
    session_id: str


# ---------------------------------------------------------------------------
# File analysis
# ---------------------------------------------------------------------------


@router.post("/analyze")
def analyze_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Upload and analyze a file for import. Returns structure analysis."""
    try:
        from app.services.import_alias_service import ImportAliasService

        result = ImportAliasService.analyze_file(
            db, company.id, file.file, file.filename, current_user.id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


@router.post("/match-products")
def match_products(
    data: MatchProductsRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Match imported product names to existing products."""
    try:
        from app.services.import_alias_service import ImportAliasService

        result = ImportAliasService.match_products(
            db, company.id, data.session_id, data.unique_products
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/match-customers")
def match_customers(
    data: MatchCustomersRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Match imported customer names to existing customers."""
    try:
        from app.services.import_alias_service import ImportAliasService

        result = ImportAliasService.match_customers(
            db, company.id, data.session_id, data.unique_customers
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/detect-duplicates")
def detect_duplicates(
    data: DetectDuplicatesRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Detect duplicates in the import data."""
    try:
        from app.services.import_alias_service import ImportAliasService

        result = ImportAliasService.detect_duplicates(
            db, company.id, data.session_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


@router.post("/execute")
def execute_import(
    data: ExecuteImportRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Execute the import with confirmed matches."""
    try:
        from app.services.import_alias_service import ImportAliasService

        result = ImportAliasService.execute_import(
            db,
            company.id,
            data.session_id,
            confirmed_product_matches=data.confirmed_product_matches,
            confirmed_customer_matches=data.confirmed_customer_matches,
            duplicate_handling=data.duplicate_handling,
        )
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


@router.get("/sessions")
def list_sessions(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """List import sessions for the company."""
    from app.models.data_import_session import DataImportSession

    sessions = (
        db.query(DataImportSession)
        .filter(DataImportSession.company_id == company.id)
        .order_by(DataImportSession.created_at.desc())
        .all()
    )
    return {"sessions": [_session_to_dict(s) for s in sessions]}


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get import session detail."""
    from app.models.data_import_session import DataImportSession

    session = (
        db.query(DataImportSession)
        .filter(
            DataImportSession.id == session_id,
            DataImportSession.company_id == company.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Import session not found")
    return _session_to_dict(session)


# ---------------------------------------------------------------------------
# Alias learning
# ---------------------------------------------------------------------------


@router.post("/learn-alias")
def learn_alias(
    data: LearnAliasRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Store a new product alias mapping."""
    try:
        from app.services.import_alias_service import ImportAliasService

        result = ImportAliasService.learn_alias(
            db, company.id, data.alias_text, data.canonical_product_id
        )
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/resolve/{name}")
def resolve_product_name(
    name: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Resolve a product name via the alias table."""
    try:
        from app.services.import_alias_service import ImportAliasService

        result = ImportAliasService.resolve_product_name(db, company.id, name)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Intelligence
# ---------------------------------------------------------------------------


@router.post("/intelligence/summary")
def generate_intelligence_summary(
    data: IntelligenceSummaryRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Generate business intelligence summary from import data."""
    try:
        from app.services.import_intelligence_service import ImportIntelligenceService

        result = ImportIntelligenceService.generate_business_summary(
            db, company.id, data.session_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _session_to_dict(session) -> dict:
    """Convert a DataImportSession to a response dict."""
    return {
        "id": session.id,
        "company_id": session.company_id,
        "filename": getattr(session, "filename", None),
        "status": getattr(session, "status", None),
        "row_count": getattr(session, "row_count", None),
        "imported_count": getattr(session, "imported_count", None),
        "error_count": getattr(session, "error_count", None),
        "metadata": getattr(session, "metadata_json", None),
        "created_at": str(session.created_at) if session.created_at else None,
    }
