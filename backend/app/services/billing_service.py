"""Subscription billing service — plan management, subscriptions, billing events."""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.subscription import BillingEvent, Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User
from app.schemas.billing import (
    BillingEventResponse,
    BillingStats,
    SubscriptionCreate,
    SubscriptionPlanCreate,
    SubscriptionPlanResponse,
    SubscriptionPlanUpdate,
    SubscriptionResponse,
)


# ---------------------------------------------------------------------------
# Plans CRUD
# ---------------------------------------------------------------------------


def get_plans(db: Session, include_inactive: bool = False) -> list[SubscriptionPlanResponse]:
    q = db.query(SubscriptionPlan)
    if not include_inactive:
        q = q.filter(SubscriptionPlan.is_active.is_(True))
    plans = q.order_by(SubscriptionPlan.sort_order).all()
    return [SubscriptionPlanResponse.model_validate(p) for p in plans]


def get_plan(db: Session, plan_id: str) -> SubscriptionPlan:
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return plan


def create_plan(db: Session, data: SubscriptionPlanCreate) -> SubscriptionPlan:
    existing = db.query(SubscriptionPlan).filter(SubscriptionPlan.slug == data.slug).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Plan slug already exists"
        )
    plan = SubscriptionPlan(**data.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def update_plan(
    db: Session, plan_id: str, data: SubscriptionPlanUpdate
) -> SubscriptionPlan:
    plan = get_plan(db, plan_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(plan, key, value)
    db.commit()
    db.refresh(plan)
    return plan


def delete_plan(db: Session, plan_id: str) -> None:
    plan = get_plan(db, plan_id)
    # Soft-delete: deactivate instead of hard delete if subscriptions exist
    active_subs = (
        db.query(Subscription)
        .filter(Subscription.plan_id == plan_id, Subscription.status == "active")
        .count()
    )
    if active_subs > 0:
        plan.is_active = False
        db.commit()
    else:
        db.delete(plan)
        db.commit()


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


def get_subscriptions(
    db: Session,
    page: int = 1,
    per_page: int = 25,
    status_filter: str | None = None,
) -> tuple[list[SubscriptionResponse], int]:
    q = db.query(Subscription)
    if status_filter:
        q = q.filter(Subscription.status == status_filter)
    total = q.count()
    rows = (
        q.order_by(Subscription.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    items = []
    for sub in rows:
        resp = SubscriptionResponse.model_validate(sub)
        if sub.plan:
            resp.plan = SubscriptionPlanResponse.model_validate(sub.plan)
        if sub.company:
            resp.company_name = sub.company.name
        items.append(resp)
    return items, total


def get_company_subscription(db: Session, company_id: str) -> Subscription | None:
    return (
        db.query(Subscription)
        .filter(
            Subscription.company_id == company_id,
            Subscription.status.in_(["active", "trialing", "past_due"]),
        )
        .first()
    )


def create_subscription(db: Session, data: SubscriptionCreate) -> Subscription:
    # Check for existing active subscription
    existing = get_company_subscription(db, data.company_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company already has an active subscription",
        )
    plan = get_plan(db, data.plan_id)
    now = datetime.now(timezone.utc)

    sub = Subscription(
        company_id=data.company_id,
        plan_id=data.plan_id,
        billing_interval=data.billing_interval,
        stripe_customer_id=data.stripe_customer_id,
        current_period_start=now,
        current_period_end=now + timedelta(days=30 if data.billing_interval == "monthly" else 365),
    )
    db.add(sub)

    # Log billing event
    event = BillingEvent(
        company_id=data.company_id,
        subscription_id=sub.id,
        event_type="subscription_created",
        metadata_json=json.dumps({"plan": plan.slug, "interval": data.billing_interval}),
    )
    db.add(event)
    db.commit()
    db.refresh(sub)
    return sub


def change_plan(
    db: Session, subscription_id: str, new_plan_id: str, billing_interval: str | None = None
) -> Subscription:
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    old_plan_id = sub.plan_id
    new_plan = get_plan(db, new_plan_id)

    sub.plan_id = new_plan_id
    if billing_interval:
        sub.billing_interval = billing_interval

    event = BillingEvent(
        company_id=sub.company_id,
        subscription_id=sub.id,
        event_type="plan_changed",
        metadata_json=json.dumps({
            "old_plan_id": old_plan_id,
            "new_plan_id": new_plan_id,
            "new_plan": new_plan.slug,
        }),
    )
    db.add(event)
    db.commit()
    db.refresh(sub)
    return sub


def cancel_subscription(db: Session, subscription_id: str) -> Subscription:
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    sub.status = "canceled"
    sub.canceled_at = datetime.now(timezone.utc)

    event = BillingEvent(
        company_id=sub.company_id,
        subscription_id=sub.id,
        event_type="subscription_canceled",
    )
    db.add(event)
    db.commit()
    db.refresh(sub)
    return sub


def reactivate_subscription(db: Session, subscription_id: str) -> Subscription:
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    if sub.status not in ("canceled", "past_due"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reactivate subscription with status '{sub.status}'",
        )
    now = datetime.now(timezone.utc)
    sub.status = "active"
    sub.canceled_at = None
    sub.current_period_start = now
    sub.current_period_end = now + timedelta(
        days=30 if sub.billing_interval == "monthly" else 365
    )

    event = BillingEvent(
        company_id=sub.company_id,
        subscription_id=sub.id,
        event_type="subscription_reactivated",
    )
    db.add(event)
    db.commit()
    db.refresh(sub)
    return sub


# ---------------------------------------------------------------------------
# Usage metering
# ---------------------------------------------------------------------------


def update_usage_counts(db: Session, company_id: str) -> None:
    """Refresh user count and storage usage for a company's subscription."""
    sub = get_company_subscription(db, company_id)
    if not sub:
        return
    user_count = (
        db.query(User)
        .filter(User.company_id == company_id, User.is_active.is_(True))
        .count()
    )
    sub.current_user_count = user_count
    # Storage tracking placeholder — would integrate with file storage service
    db.commit()


# ---------------------------------------------------------------------------
# Billing Events
# ---------------------------------------------------------------------------


def get_billing_events(
    db: Session,
    page: int = 1,
    per_page: int = 25,
    company_id: str | None = None,
    event_type: str | None = None,
) -> tuple[list[BillingEventResponse], int]:
    q = db.query(BillingEvent)
    if company_id:
        q = q.filter(BillingEvent.company_id == company_id)
    if event_type:
        q = q.filter(BillingEvent.event_type == event_type)
    total = q.count()
    rows = (
        q.order_by(BillingEvent.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    items = [BillingEventResponse.model_validate(r) for r in rows]
    return items, total


def record_billing_event(
    db: Session,
    company_id: str,
    event_type: str,
    amount: Decimal | None = None,
    stripe_event_id: str | None = None,
    stripe_invoice_id: str | None = None,
    subscription_id: str | None = None,
    metadata: dict | None = None,
) -> BillingEvent:
    event = BillingEvent(
        company_id=company_id,
        subscription_id=subscription_id,
        event_type=event_type,
        amount=amount,
        stripe_event_id=stripe_event_id,
        stripe_invoice_id=stripe_invoice_id,
        metadata_json=json.dumps(metadata) if metadata else None,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def get_billing_stats(db: Session) -> BillingStats:
    total = db.query(Subscription).count()
    active = db.query(Subscription).filter(Subscription.status == "active").count()
    past_due = db.query(Subscription).filter(Subscription.status == "past_due").count()
    canceled = db.query(Subscription).filter(Subscription.status == "canceled").count()

    # MRR: sum of monthly-equivalent prices for active subscriptions
    mrr = Decimal("0.00")
    active_subs = (
        db.query(Subscription)
        .filter(Subscription.status.in_(["active", "trialing"]))
        .all()
    )
    for sub in active_subs:
        if sub.plan:
            if sub.billing_interval == "yearly":
                mrr += sub.plan.price_yearly / 12
            else:
                mrr += sub.plan.price_monthly

    # Revenue last 30 days
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    revenue_result = (
        db.query(func.coalesce(func.sum(BillingEvent.amount), 0))
        .filter(
            BillingEvent.event_type == "payment_succeeded",
            BillingEvent.created_at >= cutoff,
        )
        .scalar()
    )
    total_revenue = Decimal(str(revenue_result))

    return BillingStats(
        total_subscriptions=total,
        active_subscriptions=active,
        past_due=past_due,
        canceled=canceled,
        mrr=mrr,
        total_revenue_30d=total_revenue,
    )
