"""Spring Burial management routes."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.company_resolver import get_current_company
from app.api.deps import get_current_user
from app.database import get_db
from app.models.company import Company
from app.models.user import User
from app.schemas.spring_burial import (
    BulkScheduleRequest,
    MarkSpringBurialRequest,
    ScheduleSpringBurialRequest,
)
from app.services import spring_burial_service

router = APIRouter()


@router.get("/spring-burials")
def list_spring_burials(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
    group_by: str = Query("funeral_home", pattern="^(funeral_home|cemetery)$"),
    funeral_home_id: str | None = Query(None),
):
    """List all spring burial orders, grouped by funeral home or cemetery."""
    return spring_burial_service.list_spring_burials(
        db, company.id, group_by=group_by, funeral_home_id=funeral_home_id
    )


@router.get("/spring-burials/stats")
def get_stats(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get spring burial summary stats."""
    return spring_burial_service.get_stats(db, company.id)


@router.post("/spring-burials/{order_id}")
def mark_spring_burial(
    order_id: str,
    data: MarkSpringBurialRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Mark an order as spring burial."""
    try:
        return spring_burial_service.mark_as_spring_burial(
            db, company.id, order_id, current_user.id, notes=data.notes
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/spring-burials/{order_id}/schedule")
def schedule_spring_burial(
    order_id: str,
    data: ScheduleSpringBurialRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Schedule a single spring burial for delivery."""
    try:
        return spring_burial_service.schedule_spring_burial(
            db, company.id, order_id, current_user.id,
            delivery_date=data.delivery_date,
            time_preference=data.time_preference,
            driver_id=data.driver_id,
            instructions=data.instructions,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/spring-burials/bulk-schedule")
def bulk_schedule(
    data: BulkScheduleRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Bulk schedule multiple spring burials."""
    items = [item.model_dump() for item in data.orders]
    return spring_burial_service.bulk_schedule(db, company.id, current_user.id, items)


@router.delete("/spring-burials/{order_id}")
def remove_spring_burial(
    order_id: str,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Remove spring burial status — return order to confirmed."""
    try:
        return spring_burial_service.remove_spring_burial(
            db, company.id, order_id, current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/spring-burials/report")
def get_report(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
    year: int | None = Query(None),
):
    """Spring burial summary report."""
    return spring_burial_service.get_report(db, company.id, year=year)
