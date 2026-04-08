"""Disinterment case management API endpoints.

Covers: CRUD, intake review, quote acceptance, signature triggers,
scheduling, and completion.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_module, require_permission
from app.models.user import User
from app.schemas.disinterment import (
    DisintermentCaseCreate,
    DisintermentCaseResponse,
    DisintermentCaseUpdate,
    DisintermentScheduleRequest,
    PaginatedDisintermentCases,
)
from app.services import disinterment_service

router = APIRouter()


@router.post("", status_code=201)
def create_case(
    data: DisintermentCaseCreate | None = None,
    db: Session = Depends(get_db),
    _mod: User = Depends(require_module("disinterment_management")),
    current_user: User = Depends(require_permission("disinterments.manage")),
):
    """Create a new disinterment case shell. Returns case + intake_token."""
    decedent = data.decedent_name if data else "Pending Intake"
    return disinterment_service.create_case(
        db, current_user.company_id, current_user.id, decedent
    )


@router.get("")
def list_cases(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    _mod: User = Depends(require_module("disinterment_management")),
    current_user: User = Depends(require_permission("disinterments.view")),
):
    """List cases for tenant, filterable by status and search."""
    return disinterment_service.list_cases(
        db, current_user.company_id, page, per_page, status, search
    )


@router.get("/{case_id}")
def get_case(
    case_id: str,
    db: Session = Depends(get_db),
    _mod: User = Depends(require_module("disinterment_management")),
    current_user: User = Depends(require_permission("disinterments.view")),
):
    """Get full case detail with pipeline state."""
    return disinterment_service.get_case(db, case_id, current_user.company_id)


@router.patch("/{case_id}/intake")
def update_intake(
    case_id: str,
    data: DisintermentCaseUpdate,
    db: Session = Depends(get_db),
    _mod: User = Depends(require_module("disinterment_management")),
    current_user: User = Depends(require_permission("disinterments.manage")),
):
    """Staff review/edit of submitted intake data."""
    return disinterment_service.update_intake(
        db, case_id, current_user.company_id, data
    )


@router.post("/{case_id}/accept-quote")
def accept_quote(
    case_id: str,
    quote_id: str = Query(...),
    quote_amount: float = Query(...),
    has_hazard_pay: bool = Query(False),
    db: Session = Depends(get_db),
    _mod: User = Depends(require_module("disinterment_management")),
    current_user: User = Depends(require_permission("disinterments.manage")),
):
    """Accept a quote for this case — advances to quote_accepted."""
    result = disinterment_service.accept_quote(
        db, case_id, current_user.company_id, quote_id, quote_amount
    )
    # Set hazard pay flag if specified
    if has_hazard_pay:
        from app.models.disinterment_case import DisintermentCase
        case = db.query(DisintermentCase).filter(DisintermentCase.id == case_id).first()
        if case:
            case.has_hazard_pay = True
            db.commit()
            result = disinterment_service.get_case(db, case_id, current_user.company_id)
    return result


@router.post("/{case_id}/send-signatures")
def send_for_signatures(
    case_id: str,
    db: Session = Depends(get_db),
    _mod: User = Depends(require_module("disinterment_management")),
    current_user: User = Depends(require_permission("disinterments.manage")),
):
    """Trigger DocuSign envelope creation with 4 signers."""
    return disinterment_service.send_for_signatures(
        db, case_id, current_user.company_id
    )


@router.post("/{case_id}/schedule")
def schedule_case(
    case_id: str,
    data: DisintermentScheduleRequest,
    db: Session = Depends(get_db),
    _mod: User = Depends(require_module("disinterment_management")),
    current_user: User = Depends(require_permission("disinterments.schedule")),
):
    """Schedule a disinterment — guarded by signatures_complete."""
    return disinterment_service.schedule_case(
        db,
        case_id,
        current_user.company_id,
        data.scheduled_date,
        data.assigned_driver_id,
        data.assigned_crew,
        current_user.id,
    )


@router.post("/{case_id}/complete")
def complete_case(
    case_id: str,
    db: Session = Depends(get_db),
    _mod: User = Depends(require_module("disinterment_management")),
    current_user: User = Depends(require_permission("disinterments.manage")),
):
    """Mark case as complete."""
    return disinterment_service.complete_case(
        db, case_id, current_user.company_id
    )


@router.post("/{case_id}/cancel")
def cancel_case(
    case_id: str,
    db: Session = Depends(get_db),
    _mod: User = Depends(require_module("disinterment_management")),
    current_user: User = Depends(require_permission("disinterments.manage")),
):
    """Cancel a case from any non-complete stage."""
    return disinterment_service.cancel_case(
        db, case_id, current_user.company_id
    )
