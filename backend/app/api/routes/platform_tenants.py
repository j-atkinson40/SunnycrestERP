"""Platform admin — tenant management routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_platform_role
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.services import super_admin_service

router = APIRouter()


@router.get("/dashboard")
def get_platform_dashboard(
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support", "viewer")),
    db: Session = Depends(get_db),
):
    """Full platform dashboard — system health, tenant list, billing summary."""
    return super_admin_service.get_super_dashboard(db)


@router.get("/")
def list_tenants(
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support", "viewer")),
    db: Session = Depends(get_db),
    search: str | None = Query(None),
    is_active: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all tenants with user counts and subscription status."""
    from app.models.company import Company
    from app.models.subscription import Subscription
    from app.models.user import User

    query = db.query(Company)
    if search:
        query = query.filter(Company.name.ilike(f"%{search}%"))
    if is_active is not None:
        query = query.filter(Company.is_active == is_active)

    total = query.count()
    companies = query.order_by(Company.name).offset(offset).limit(limit).all()

    items = []
    for c in companies:
        user_count = (
            db.query(User)
            .filter(User.company_id == c.id, User.is_active.is_(True))
            .count()
        )
        sub = (
            db.query(Subscription)
            .filter(
                Subscription.company_id == c.id,
                Subscription.status.in_(["active", "trialing", "past_due"]),
            )
            .first()
        )
        items.append({
            "id": c.id,
            "name": c.name,
            "slug": c.slug,
            "is_active": c.is_active,
            "user_count": user_count,
            "subscription_status": sub.status if sub else None,
            "plan_name": sub.plan.name if sub and sub.plan else None,
            "created_at": c.created_at,
        })

    return {"items": items, "total": total}


@router.get("/{tenant_id}")
def get_tenant(
    tenant_id: str,
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support", "viewer")),
    db: Session = Depends(get_db),
):
    """Get detailed tenant information."""
    from app.models.company import Company
    from app.models.company_module import CompanyModule
    from app.models.subscription import Subscription
    from app.models.sync_log import SyncLog
    from app.models.user import User

    company = db.query(Company).filter(Company.id == tenant_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Tenant not found")

    users = (
        db.query(User)
        .filter(User.company_id == tenant_id)
        .order_by(User.first_name)
        .all()
    )

    modules = (
        db.query(CompanyModule)
        .filter(CompanyModule.company_id == tenant_id)
        .all()
    )

    sub = (
        db.query(Subscription)
        .filter(Subscription.company_id == tenant_id)
        .order_by(Subscription.created_at.desc())
        .first()
    )

    recent_syncs = (
        db.query(SyncLog)
        .filter(SyncLog.company_id == tenant_id)
        .order_by(SyncLog.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "id": company.id,
        "name": company.name,
        "slug": company.slug,
        "is_active": company.is_active,
        "created_at": company.created_at,
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "is_active": u.is_active,
                "role_id": u.role_id,
            }
            for u in users
        ],
        "modules": [
            {"module": m.module, "enabled": m.enabled}
            for m in modules
        ],
        "subscription": {
            "status": sub.status,
            "plan_name": sub.plan.name if sub and sub.plan else None,
            "billing_interval": sub.billing_interval if sub else None,
        } if sub else None,
        "recent_syncs": [
            {
                "id": s.id,
                "direction": s.direction,
                "entity_type": s.entity_type,
                "status": s.status,
                "created_at": s.created_at,
                "records_synced": s.records_synced,
                "error_message": s.error_message,
            }
            for s in recent_syncs
        ],
    }


@router.delete("/{tenant_id}")
def delete_tenant(
    tenant_id: str,
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Permanently delete a tenant and ALL associated data. This is irreversible."""
    from sqlalchemy import text

    from app.models.company import Company

    import logging
    logger = logging.getLogger(__name__)

    # Use the ORM session to verify the tenant exists, then close it
    # so it doesn't interfere with raw SQL operations.
    company = db.query(Company).filter(Company.id == tenant_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant_name = company.name
    db.expunge(company)  # detach from session

    # Use session_replication_role = 'replica' to temporarily disable all
    # FK trigger checks for this session, then delete the company and all
    # referencing rows. This is the only reliable approach given 100+ FK
    # relationships across the schema.
    engine = db.get_bind()
    connection = engine.connect()
    try:
        trans = connection.begin()

        # Disable FK checks for this session
        connection.execute(text("SET session_replication_role = 'replica'"))

        # Delete all rows referencing this tenant across every table
        # First: find all tables with company_id or tenant_id columns
        ref_tables = connection.execute(text("""
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND column_name IN ('company_id', 'tenant_id')
              AND table_name != 'companies'
            ORDER BY table_name
        """)).fetchall()

        deleted_counts: dict[str, int] = {}
        for tbl, col in ref_tables:
            try:
                result = connection.execute(
                    text(f'DELETE FROM "{tbl}" WHERE "{col}" = :tid'),
                    {"tid": tenant_id},
                )
                if result.rowcount > 0:
                    deleted_counts[tbl] = deleted_counts.get(tbl, 0) + result.rowcount
            except Exception:
                pass  # Table might not exist on this deployment

        # Delete tables with other FK column names to companies
        for tbl, col in [
            ("fh_manufacturer_relationships", "funeral_home_tenant_id"),
            ("fh_manufacturer_relationships", "manufacturer_tenant_id"),
            ("fh_vault_orders", "manufacturer_tenant_id"),
            ("network_relationships", "requesting_company_id"),
            ("network_relationships", "target_company_id"),
            ("network_transactions", "source_company_id"),
            ("network_transactions", "target_company_id"),
            ("tenant_notifications", "source_tenant_id"),
            ("impersonation_sessions", "tenant_id"),
        ]:
            try:
                connection.execute(
                    text(f'DELETE FROM "{tbl}" WHERE "{col}" = :tid'),
                    {"tid": tenant_id},
                )
            except Exception:
                pass

        # Delete the company
        connection.execute(
            text("DELETE FROM companies WHERE id = :tid"),
            {"tid": tenant_id},
        )

        # Re-enable FK checks
        connection.execute(text("SET session_replication_role = 'origin'"))

        trans.commit()
        logger.info("Tenant %s (%s) deleted successfully", tenant_id, tenant_name)
    except Exception as e:
        logger.exception("Failed to delete tenant %s", tenant_id)
        try:
            connection.execute(text("SET session_replication_role = 'origin'"))
            trans.rollback()
        except Exception:
            pass
        raise HTTPException(
            status_code=500,
            detail=f"Delete failed: {type(e).__name__}: {str(e)[:500]}",
        )
    finally:
        connection.close()

    db.expire_all()

    return {
        "detail": f'Tenant "{tenant_name}" permanently deleted',
        "deleted_records": deleted_counts,
    }


@router.patch("/{tenant_id}")
def update_tenant(
    tenant_id: str,
    data: dict,
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Update tenant configuration — activate, deactivate, etc."""
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == tenant_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Tenant not found")

    allowed_fields = {"is_active", "name"}
    for key, value in data.items():
        if key in allowed_fields:
            setattr(company, key, value)

    db.commit()
    db.refresh(company)
    return {"id": company.id, "name": company.name, "is_active": company.is_active}
