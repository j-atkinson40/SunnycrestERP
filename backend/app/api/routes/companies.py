from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.company import CompanyRegisterRequest, CompanyResponse
from app.schemas.user import UserResponse
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
