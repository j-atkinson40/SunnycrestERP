"""Cemetery plot + map endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.fh import cemetery_plot_service


router = APIRouter()


class ReservePlotRequest(BaseModel):
    case_id: str


@router.get("/{cemetery_company_id}/map")
def get_map(
    cemetery_company_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return map config + plots for the given cemetery tenant."""
    return cemetery_plot_service.get_map_data(db, cemetery_company_id)


@router.get("/{cemetery_company_id}/plots")
def list_plots(
    cemetery_company_id: str,
    status: str | None = Query(None),
    plot_type: str | None = Query(None),
    section: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = cemetery_plot_service.list_plots(db, cemetery_company_id, status, plot_type, section)
    return [cemetery_plot_service._serialize_plot(p) for p in rows]


@router.post("/plots/{plot_id}/reserve")
def reserve_plot(
    plot_id: str,
    data: ReservePlotRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return cemetery_plot_service.reserve_plot(
            db, plot_id, data.case_id, fh_company_id=current_user.company_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/plots/{plot_id}/complete-payment")
def complete_payment(
    plot_id: str,
    data: ReservePlotRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return cemetery_plot_service.complete_reservation_payment(
            db, plot_id, data.case_id, fh_company_id=current_user.company_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
