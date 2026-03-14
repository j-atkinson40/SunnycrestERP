"""Super-admin dashboard routes — system-wide overview for platform admins."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.super_admin import SuperDashboard
from app.services import super_admin_service

router = APIRouter()


@router.get("/dashboard", response_model=SuperDashboard)
def get_super_dashboard(
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get the complete super-admin dashboard with system health, tenant overview, and billing summary."""
    return super_admin_service.get_super_dashboard(db)
