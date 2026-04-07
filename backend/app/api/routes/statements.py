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
    try:
        run = initiate_run(
            db,
            current_user.company_id,
            current_user.id,
            body.month,
            body.year,
            body.custom_message,
        )
    except Exception as e:
        logger.error(f"Statement run initiation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Statement run failed: {str(e)}")

    # Check if this was an existing run (idempotent return)
    if getattr(run, "_already_existed", False):
        return {
            "id": run.id,
            "status": "already_exists",
            "existing_status": run.status,
            "message": f"Statements already generated for {body.month}/{body.year}. View existing run or generate for a different period.",
        }

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


@router.get("/runs/current")
def get_current_run_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get active or most recent statement run with items."""
    from app.services.statement_generation_service import get_current_run as get_current
    run = get_current(db, current_user.company_id)
    if not run:
        return {"run": None, "items": []}
    from app.models.statement_run import StatementRunItem
    from app.models.customer import Customer
    items = db.query(StatementRunItem).filter(StatementRunItem.statement_run_id == run.id).all()
    return {
        "run": {
            "id": run.id, "run_date": str(run.run_date),
            "period_start": str(run.period_start), "period_end": str(run.period_end),
            "status": run.status, "total_customers": run.total_customers,
            "total_amount": float(run.total_amount or 0), "flagged_count": run.flagged_count,
            "sent_count": run.sent_count, "failed_count": run.failed_count,
        },
        "items": [
            {
                "id": i.id, "customer_id": i.customer_id,
                "customer_name": (db.query(Customer).filter(Customer.id == i.customer_id).first() or type("C", (), {"name": "Unknown"})).name,
                "opening_balance": float(i.opening_balance or 0),
                "invoices_total": float(i.invoices_total or 0),
                "payments_total": float(i.payments_total or 0),
                "closing_balance": float(i.closing_balance or 0),
                "due_date": str(i.due_date) if i.due_date else None,
                "flagged": i.flagged, "flag_reasons": i.flag_reasons or [],
                "review_status": i.review_status,
                "delivery_method": i.delivery_method,
                "delivery_status": i.delivery_status,
                "sent_at": i.sent_at.isoformat() if i.sent_at else None,
            }
            for i in items
        ],
    }


class GenerateRunRequest(BaseModel):
    period_start: str
    period_end: str


@router.post("/runs/generate")
def generate_run(
    body: GenerateRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a new statement run with agent flagging."""
    from datetime import date
    from app.services.statement_generation_service import generate_statement_run
    ps = date.fromisoformat(body.period_start)
    pe = date.fromisoformat(body.period_end)
    run = generate_statement_run(db, current_user.company_id, current_user.id, ps, pe)
    return {"id": run.id, "status": run.status, "total_customers": run.total_customers, "flagged_count": run.flagged_count}


class ReviewNote(BaseModel):
    note: str | None = None


@router.post("/runs/{run_id}/items/{item_id}/approve")
def approve_item_endpoint(
    run_id: str, item_id: str,
    body: ReviewNote = ReviewNote(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.statement_generation_service import approve_item
    if not approve_item(db, item_id, current_user.company_id, current_user.id, body.note):
        raise HTTPException(404, "Item not found")
    return {"status": "approved"}


@router.post("/runs/{run_id}/items/{item_id}/skip")
def skip_item_endpoint(
    run_id: str, item_id: str,
    body: ReviewNote = ReviewNote(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.statement_generation_service import skip_item
    if not skip_item(db, item_id, current_user.company_id, current_user.id, body.note):
        raise HTTPException(404, "Item not found")
    return {"status": "skipped"}


@router.post("/runs/{run_id}/approve-all-unflagged")
def approve_unflagged(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.statement_generation_service import approve_all_unflagged
    count = approve_all_unflagged(db, run_id, current_user.company_id, current_user.id)
    return {"approved": count}


@router.get("/customers/eligible-count")
def eligible_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.customer import Customer
    count = db.query(Customer).filter(
        Customer.company_id == current_user.company_id,
        Customer.receives_monthly_statement == True,
    ).count()
    return {"count": count}


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
