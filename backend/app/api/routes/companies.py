from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.company import CompanyRegisterRequest, CompanyResponse, CompanyUpdate
from app.schemas.user import UserResponse
from app.services import company_service
from app.services.auth_service import register_company

router = APIRouter()


@router.post("/register", status_code=201)
def register_new_company(
    data: CompanyRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Public endpoint (no auth required).
    Creates a new company and its first admin user.
    """
    result = register_company(db, data)
    return {
        "company": CompanyResponse.model_validate(result["company"]),
        "user": UserResponse.model_validate(result["user"]),
    }


@router.get("/settings")
def get_company_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("company.view")),
):
    """View current company settings."""
    company = company_service.get_company(db, current_user.company_id)
    return CompanyResponse.model_validate(company)


@router.patch("/settings")
def update_company_settings(
    data: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("company.edit")),
):
    """Update company settings (name, address, contact info, timezone)."""
    company = company_service.update_company(
        db, current_user.company_id, data, actor_id=current_user.id
    )
    return CompanyResponse.model_validate(company)
