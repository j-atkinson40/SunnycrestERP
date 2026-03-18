"""Daily production log routes — entries, today view, and summaries."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_module
from app.api.company_resolver import get_current_company
from app.database import get_db
from app.models.company import Company
from app.models.user import User
from app.schemas.production_log import (
    ProductionLogEntryCreate,
    ProductionLogEntryResponse,
    ProductionLogEntryUpdate,
    ProductionLogSummaryResponse,
)
from app.services import production_log_service

router = APIRouter()

MODULE = "daily_production_log"


# ---------------------------------------------------------------------------
# List entries
# ---------------------------------------------------------------------------


@router.get("/production-log", response_model=list[ProductionLogEntryResponse])
def list_production_log(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    product_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
):
    entries = production_log_service.list_entries(
        db,
        company.id,
        start_date=start_date,
        end_date=end_date,
        product_id=product_id,
        limit=limit,
        offset=offset,
    )
    return [ProductionLogEntryResponse.model_validate(e) for e in entries]


# ---------------------------------------------------------------------------
# Today view
# ---------------------------------------------------------------------------


@router.get("/production-log/today")
def get_today(
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
):
    entries = production_log_service.get_today_entries(db, company.id)
    total = production_log_service.get_today_total(db, company.id)
    return {
        "date": date.today().isoformat(),
        "total_units": total,
        "entry_count": len(entries),
        "entries": [ProductionLogEntryResponse.model_validate(e) for e in entries],
    }


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------


@router.get("/production-log/summary", response_model=list[ProductionLogSummaryResponse])
def get_summary(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
):
    summaries = production_log_service.get_summaries(db, company.id, start_date, end_date)
    return [ProductionLogSummaryResponse.model_validate(s) for s in summaries]


# ---------------------------------------------------------------------------
# Create entry
# ---------------------------------------------------------------------------


@router.post("/production-log", status_code=201, response_model=ProductionLogEntryResponse)
def create_entry(
    data: ProductionLogEntryCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
):
    try:
        entry = production_log_service.create_entry(
            db,
            company.id,
            current_user.id,
            product_id=data.product_id,
            quantity_produced=data.quantity_produced,
            log_date=data.log_date,
            mix_design_id=data.mix_design_id,
            batch_count=data.batch_count,
            notes=data.notes,
            entry_method=data.entry_method,
        )
        return ProductionLogEntryResponse.model_validate(entry)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Update entry
# ---------------------------------------------------------------------------


@router.put("/production-log/{entry_id}", response_model=ProductionLogEntryResponse)
def update_entry(
    entry_id: str,
    data: ProductionLogEntryUpdate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
):
    try:
        entry = production_log_service.update_entry(
            db,
            company.id,
            entry_id,
            **data.model_dump(exclude_unset=True),
        )
        return ProductionLogEntryResponse.model_validate(entry)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Delete entry
# ---------------------------------------------------------------------------


@router.delete("/production-log/{entry_id}")
def delete_entry(
    entry_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
):
    success = production_log_service.delete_entry(db, company.id, entry_id)
    if not success:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"detail": "Entry deleted and inventory adjusted"}
