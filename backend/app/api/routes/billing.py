"""Billing routes — subscription plans, subscriptions, and billing events."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.billing import (
    BillingStats,
    ChangePlanRequest,
    PaginatedBillingEvents,
    PaginatedSubscriptions,
    SubscriptionCreate,
    SubscriptionPlanCreate,
    SubscriptionPlanResponse,
    SubscriptionPlanUpdate,
    SubscriptionResponse,
)
from app.services import billing_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------


@router.get("/plans", response_model=list[SubscriptionPlanResponse])
def list_plans(
    include_inactive: bool = False,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all subscription plans."""
    return billing_service.get_plans(db, include_inactive)


@router.post("/plans", response_model=SubscriptionPlanResponse)
def create_plan(
    body: SubscriptionPlanCreate,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new subscription plan."""
    plan = billing_service.create_plan(db, body)
    return SubscriptionPlanResponse.model_validate(plan)


@router.get("/plans/{plan_id}", response_model=SubscriptionPlanResponse)
def get_plan(
    plan_id: str,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get a single plan."""
    plan = billing_service.get_plan(db, plan_id)
    return SubscriptionPlanResponse.model_validate(plan)


@router.patch("/plans/{plan_id}", response_model=SubscriptionPlanResponse)
def update_plan(
    plan_id: str,
    body: SubscriptionPlanUpdate,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a plan."""
    plan = billing_service.update_plan(db, plan_id, body)
    return SubscriptionPlanResponse.model_validate(plan)


@router.delete("/plans/{plan_id}", status_code=204)
def delete_plan(
    plan_id: str,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Deactivate or delete a plan."""
    billing_service.delete_plan(db, plan_id)


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=BillingStats)
def get_billing_stats(
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get billing overview statistics."""
    return billing_service.get_billing_stats(db)


@router.get("/subscriptions", response_model=PaginatedSubscriptions)
def list_subscriptions(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    status: str | None = None,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all subscriptions."""
    items, total = billing_service.get_subscriptions(db, page, per_page, status)
    return PaginatedSubscriptions(
        items=items, total=total, page=page, per_page=per_page
    )


@router.post("/subscriptions", response_model=SubscriptionResponse)
def create_subscription(
    body: SubscriptionCreate,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new subscription for a company."""
    sub = billing_service.create_subscription(db, body)
    resp = SubscriptionResponse.model_validate(sub)
    if sub.plan:
        resp.plan = SubscriptionPlanResponse.model_validate(sub.plan)
    if sub.company:
        resp.company_name = sub.company.name
    return resp


@router.get("/subscriptions/{sub_id}", response_model=SubscriptionResponse)
def get_subscription(
    sub_id: str,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get a single subscription."""
    from sqlalchemy.orm import Session as S

    sub = db.query(billing_service.Subscription).filter(
        billing_service.Subscription.id == sub_id
    ).first()
    if not sub:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    resp = SubscriptionResponse.model_validate(sub)
    if sub.plan:
        resp.plan = SubscriptionPlanResponse.model_validate(sub.plan)
    if sub.company:
        resp.company_name = sub.company.name
    return resp


@router.post(
    "/subscriptions/{sub_id}/change-plan",
    response_model=SubscriptionResponse,
)
def change_plan(
    sub_id: str,
    body: ChangePlanRequest,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Change a subscription's plan."""
    sub = billing_service.change_plan(db, sub_id, body.plan_id, body.billing_interval)
    resp = SubscriptionResponse.model_validate(sub)
    if sub.plan:
        resp.plan = SubscriptionPlanResponse.model_validate(sub.plan)
    return resp


@router.post(
    "/subscriptions/{sub_id}/cancel",
    response_model=SubscriptionResponse,
)
def cancel_subscription(
    sub_id: str,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Cancel a subscription."""
    sub = billing_service.cancel_subscription(db, sub_id)
    return SubscriptionResponse.model_validate(sub)


@router.post(
    "/subscriptions/{sub_id}/reactivate",
    response_model=SubscriptionResponse,
)
def reactivate_subscription(
    sub_id: str,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Reactivate a canceled or past-due subscription."""
    sub = billing_service.reactivate_subscription(db, sub_id)
    return SubscriptionResponse.model_validate(sub)


# ---------------------------------------------------------------------------
# Billing Events
# ---------------------------------------------------------------------------


@router.get("/events", response_model=PaginatedBillingEvents)
def list_billing_events(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    company_id: str | None = None,
    event_type: str | None = None,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List billing events with optional filters."""
    items, total = billing_service.get_billing_events(
        db, page, per_page, company_id, event_type
    )
    return PaginatedBillingEvents(
        items=items, total=total, page=page, per_page=per_page
    )
