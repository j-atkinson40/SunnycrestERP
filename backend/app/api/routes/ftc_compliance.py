"""FTC Compliance Dashboard API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_module, require_permission
from app.database import get_db
from app.models.user import User
from app.services import ftc_compliance_service

router = APIRouter(
    dependencies=[Depends(require_module("funeral_home"))],
)


# ---------------------------------------------------------------------------
# FTC Compliance endpoints
# ---------------------------------------------------------------------------


@router.get("/compliance-score")
def get_compliance_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_compliance.view")),
):
    """Get full FTC compliance dashboard with scoring."""
    return ftc_compliance_service.get_compliance_dashboard(
        db, current_user.company_id
    )


@router.get("/gpl-history")
def get_gpl_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_compliance.view")),
):
    """Get GPL version history."""
    return ftc_compliance_service.get_gpl_versions(db, current_user.company_id)
