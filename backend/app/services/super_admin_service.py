"""Super-admin dashboard service — cross-tenant system overview."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.job_queue import Job
from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.models.sync_log import SyncLog
from app.models.user import User
from app.schemas.super_admin import SuperDashboard, SystemHealth, TenantOverview


def get_super_dashboard(db: Session) -> SuperDashboard:
    """Build the complete super-admin dashboard payload."""

    # --- System health ---
    total_tenants = db.query(Company).count()
    active_tenants = db.query(Company).filter(Company.is_active.is_(True)).count()
    inactive_tenants = total_tenants - active_tenants
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active.is_(True)).count()

    cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    total_jobs_24h = (
        db.query(Job).filter(Job.created_at >= cutoff_24h).count()
    )
    failed_jobs_24h = (
        db.query(Job)
        .filter(Job.created_at >= cutoff_24h, Job.status.in_(["failed", "dead"]))
        .count()
    )

    # Redis check
    redis_connected = False
    try:
        from app.core.redis import get_redis

        r = get_redis()
        if r:
            r.ping()
            redis_connected = True
    except Exception:
        pass

    system_health = SystemHealth(
        total_tenants=total_tenants,
        active_tenants=active_tenants,
        inactive_tenants=inactive_tenants,
        total_users=total_users,
        active_users=active_users,
        total_jobs_24h=total_jobs_24h,
        failed_jobs_24h=failed_jobs_24h,
        redis_connected=redis_connected,
        db_connected=True,  # If we got here, DB is connected
    )

    # --- Tenant overviews ---
    companies = db.query(Company).order_by(Company.name).all()
    tenants: list[TenantOverview] = []

    for company in companies:
        user_count = (
            db.query(User)
            .filter(User.company_id == company.id, User.is_active.is_(True))
            .count()
        )

        # Subscription info
        sub = (
            db.query(Subscription)
            .filter(
                Subscription.company_id == company.id,
                Subscription.status.in_(["active", "trialing", "past_due"]),
            )
            .first()
        )
        sub_status = sub.status if sub else None
        plan_name = None
        if sub and sub.plan:
            plan_name = sub.plan.name

        # Last sync
        last_sync = (
            db.query(SyncLog)
            .filter(SyncLog.company_id == company.id)
            .order_by(SyncLog.created_at.desc())
            .first()
        )
        last_sync_at = last_sync.created_at if last_sync else None

        # Simple sync health
        sync_status = None
        if last_sync:
            if last_sync.status == "error":
                sync_status = "red"
            elif last_sync_at and last_sync_at < datetime.now(timezone.utc) - timedelta(hours=6):
                sync_status = "yellow"
            else:
                sync_status = "green"

        tenants.append(
            TenantOverview(
                id=company.id,
                name=company.name,
                slug=company.slug,
                is_active=company.is_active,
                user_count=user_count,
                created_at=company.created_at,
                subscription_status=sub_status,
                plan_name=plan_name,
                last_sync_at=last_sync_at,
                sync_status=sync_status,
            )
        )

    # --- Billing summary ---
    mrr = Decimal("0.00")
    billing_active = 0
    billing_past_due = 0

    active_subs = (
        db.query(Subscription)
        .filter(Subscription.status.in_(["active", "trialing"]))
        .all()
    )
    billing_active = len(active_subs)
    for sub in active_subs:
        if sub.plan:
            if sub.billing_interval == "yearly":
                mrr += sub.plan.price_yearly / 12
            else:
                mrr += sub.plan.price_monthly

    billing_past_due = (
        db.query(Subscription).filter(Subscription.status == "past_due").count()
    )

    return SuperDashboard(
        system_health=system_health,
        tenants=tenants,
        billing_mrr=mrr,
        billing_active=billing_active,
        billing_past_due=billing_past_due,
    )
