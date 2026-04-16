"""Wilbert Program Management API routes.

Manage Wilbert program enrollments, territories, and product selections
for a tenant.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
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


class EnrollProgramRequest(BaseModel):
    territory_ids: Optional[list[str]] = None
    uses_vault_territory: Optional[bool] = None
    enabled_product_ids: Optional[list[str]] = None


class UpdateTerritoryRequest(BaseModel):
    territory_ids: list[str]
    uses_vault_territory: bool


class UpdateProductsRequest(BaseModel):
    enabled_product_ids: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/")
def list_programs(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """List company's enrolled programs."""
    try:
        from app.services.wilbert_program_service import WilbertProgramService

        programs = WilbertProgramService.get_company_programs(db, company.id)
        return {"programs": programs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{code}/enroll", status_code=201)
def enroll_in_program(
    code: str,
    data: EnrollProgramRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Enroll in a Wilbert program."""
    try:
        from app.services.wilbert_program_service import WilbertProgramService

        result = WilbertProgramService.enroll_in_program(
            db,
            company.id,
            code,
            territory_ids=data.territory_ids,
            uses_vault_territory=data.uses_vault_territory,
            enabled_product_ids=data.enabled_product_ids,
        )
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{code}/territory")
def update_program_territory(
    code: str,
    data: UpdateTerritoryRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Update territory for an enrolled program."""
    try:
        from app.services.wilbert_program_service import WilbertProgramService

        result = WilbertProgramService.configure_program_territory(
            db,
            company.id,
            code,
            territory_ids=data.territory_ids,
            uses_vault_territory=data.uses_vault_territory,
        )
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{code}/products")
def update_program_products(
    code: str,
    data: UpdateProductsRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Update enabled products for an enrolled program."""
    try:
        from app.services.wilbert_program_service import WilbertProgramService

        result = WilbertProgramService.configure_program_products(
            db, company.id, code, enabled_product_ids=data.enabled_product_ids
        )
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{code}")
def unenroll_from_program(
    code: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Unenroll from a Wilbert program."""
    try:
        from app.services.wilbert_program_service import WilbertProgramService

        WilbertProgramService.unenroll_from_program(db, company.id, code)
        db.commit()
        return {"status": "ok", "program_code": code}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
