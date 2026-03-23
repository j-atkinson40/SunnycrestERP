"""Statement API routes — runs, generation, sending."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.statement_service import (
    generate_all_for_run,
    get_customer_statement_history,
    get_eligible_customers,
    get_run_history,
    get_run_status,
    get_templates,
    initiate_run,
    send_all_digital,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class InitiateRunRequest(BaseModel):
    month: int
    year: int
    custom_message: str | None = None


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


@router.get("/templates")
def list_templates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_templates(db, current_user.company_id)


# ---------------------------------------------------------------------------
# Eligible customers
# ---------------------------------------------------------------------------


@router.get("/eligible-customers")
def list_eligible(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_eligible_customers(db, current_user.company_id)


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


@router.post("/runs")
def start_run(
    body: InitiateRunRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Initiate a statement run for a given month/year."""
    run = initiate_run(
        db,
        current_user.company_id,
        current_user.id,
        body.month,
        body.year,
        body.custom_message,
    )
    # Generate all statements in background
    background_tasks.add_task(
        generate_all_for_run, db, run.id, current_user.company_id
    )
    return {"id": run.id, "status": run.status}


@router.get("/runs/{run_id}/status")
def run_status(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = get_run_status(db, run_id, current_user.company_id)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@router.post("/runs/{run_id}/send-digital")
def send_digital(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send all digital statements in a run."""
    result = send_all_digital(db, run_id, current_user.company_id)
    return result


@router.post("/runs/{run_id}/deliver-platform")
def deliver_platform(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deliver all platform statements in a run cross-tenant."""
    from app.services.cross_tenant_statement_service import deliver_all_platform_for_run
    return deliver_all_platform_for_run(db, run_id, current_user.company_id)


@router.post("/runs/{run_id}/send-all")
def send_all(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """One-button send: platform + digital + mail."""
    from app.services.cross_tenant_statement_service import deliver_all_platform_for_run
    platform_result = deliver_all_platform_for_run(db, run_id, current_user.company_id)
    digital_result = send_all_digital(db, run_id, current_user.company_id)
    return {
        "platform": platform_result,
        "digital": digital_result,
    }


@router.get("/runs/history")
def run_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_run_history(db, current_user.company_id)


# ---------------------------------------------------------------------------
# Customer statement history
# ---------------------------------------------------------------------------


@router.get("/customer/{customer_id}/history")
def customer_history(
    customer_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_customer_statement_history(db, customer_id, current_user.company_id)


# ---------------------------------------------------------------------------
# Received statements (funeral home side)
# ---------------------------------------------------------------------------


class RecordPaymentRequest(BaseModel):
    amount: float
    payment_method: str
    payment_date: str
    payment_reference: str | None = None
    notes: str | None = None


class DisputeRequest(BaseModel):
    notes: str


@router.get("/received")
def list_received(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.cross_tenant_statement_service import get_received_statements
    return get_received_statements(db, current_user.company_id)


@router.get("/received/unread-count")
def received_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.cross_tenant_statement_service import get_unread_count
    return {"count": get_unread_count(db, current_user.company_id)}


@router.get("/received/{statement_id}")
def received_detail(
    statement_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.cross_tenant_statement_service import get_received_statement_detail
    result = get_received_statement_detail(db, statement_id, current_user.company_id)
    if not result:
        raise HTTPException(status_code=404, detail="Statement not found")
    return result


@router.post("/received/{statement_id}/pay")
def pay_received(
    statement_id: str,
    body: RecordPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.cross_tenant_statement_service import record_payment
    from decimal import Decimal
    payment = record_payment(
        db, current_user.company_id, statement_id, current_user.id,
        Decimal(str(body.amount)), body.payment_method, body.payment_date,
        body.payment_reference, body.notes,
    )
    if not payment:
        raise HTTPException(status_code=400, detail="Could not record payment")
    return {"id": payment.id, "status": "ok"}


@router.post("/received/{statement_id}/dispute")
def dispute_received(
    statement_id: str,
    body: DisputeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.cross_tenant_statement_service import dispute_statement
    if not dispute_statement(db, current_user.company_id, statement_id, body.notes):
        raise HTTPException(status_code=404, detail="Statement not found")
    return {"status": "ok"}
