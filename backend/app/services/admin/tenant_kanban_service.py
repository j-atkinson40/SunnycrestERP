"""Tenant kanban service — groups tenants by status + vertical with health state."""

from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.models.admin_staging_tenant import AdminStagingTenant
from app.models.company import Company
from app.models.sales_order import SalesOrder
from app.models.user import User
from app.services.admin import deployment_service


def _tenant_status(company: Company, staging_ids: set[str]) -> str:
    """Infer kanban status for a tenant.

    Statuses: waitlist | onboarding | live | churned | staging
    """
    if company.id in staging_ids:
        return "staging"
    if not company.is_active:
        return "churned"
    # Onboarding status from company field if present
    onboarding = getattr(company, "onboarding_status", None)
    if onboarding == "completed":
        return "live"
    if onboarding in ("pending", "in_progress"):
        return "onboarding"
    # Default live if has users
    return "live"


def _health_dot(db: Session, company: Company) -> tuple[str, str]:
    """Return (color, reason). Amber/red take precedence over green."""
    # Count untested deployments for this tenant's vertical
    vertical = (company.vertical or "manufacturing").lower()
    try:
        status = deployment_service.get_tenant_test_status(
            db=db,
            company_id=company.id,
            vertical=vertical,
            tenant_created_at=company.created_at or datetime.now(timezone.utc),
        )
        if not status["is_tested"]:
            return ("amber", f"{len(status['untested_deployments'])} untested deployments")
    except Exception:
        pass

    # Last login check (amber if no login 7+ days for active tenants)
    if company.is_active:
        last_user = (
            db.query(User)
            .filter(User.company_id == company.id)
            .order_by(User.last_login_at.desc().nullslast() if hasattr(User, "last_login_at") else User.created_at.desc())
            .first()
        )
        if last_user and hasattr(last_user, "last_login_at") and last_user.last_login_at:
            age = datetime.now(timezone.utc) - last_user.last_login_at
            if age > timedelta(days=7):
                return ("amber", "No logins in 7+ days")

    if not company.is_active:
        return ("grey", "Inactive")
    return ("green", "Healthy")


def _key_metric(db: Session, company: Company) -> str:
    vertical = (company.vertical or "manufacturing").lower()
    if vertical == "manufacturing":
        order_count = db.query(SalesOrder).filter(SalesOrder.company_id == company.id).count()
        return f"{order_count} orders"
    return "—"


def get_kanban(db: Session) -> dict:
    """Return {status: {vertical: [tenant_cards]}} structure."""
    staging_company_ids = {
        s.company_id for s in db.query(AdminStagingTenant)
        .filter(AdminStagingTenant.is_archived == False).all()  # noqa: E712
    }
    companies = db.query(Company).all()

    out = {"waitlist": {}, "onboarding": {}, "live": {}, "churned": {}, "staging": {}}

    for company in companies:
        vertical = (company.vertical or "manufacturing").lower()
        status = _tenant_status(company, staging_company_ids)
        dot_color, dot_reason = _health_dot(db, company)
        metric = _key_metric(db, company)

        card = {
            "id": company.id,
            "name": company.name,
            "slug": company.slug,
            "vertical": vertical,
            "status": status,
            "health": {"color": dot_color, "reason": dot_reason},
            "key_metric": metric,
            "is_staging": company.id in staging_company_ids,
            "created_at": company.created_at.isoformat() if company.created_at else None,
        }
        out[status].setdefault(vertical, []).append(card)

    return out


def get_tenant_detail(db: Session, company_id: str) -> dict:
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise ValueError("Tenant not found")
    vertical = (company.vertical or "manufacturing").lower()
    dot_color, dot_reason = _health_dot(db, company)

    # Recent users + last login
    user_count = db.query(User).filter(User.company_id == company.id).count()

    return {
        "id": company.id,
        "name": company.name,
        "slug": company.slug,
        "vertical": vertical,
        "is_active": company.is_active,
        "health": {"color": dot_color, "reason": dot_reason},
        "user_count": user_count,
        "created_at": company.created_at.isoformat() if company.created_at else None,
        "deployment_status": deployment_service.get_tenant_test_status(
            db=db,
            company_id=company.id,
            vertical=vertical,
            tenant_created_at=company.created_at or datetime.now(timezone.utc),
        ),
    }
