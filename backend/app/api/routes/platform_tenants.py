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

    # Simple multi-pass approach: discover FK refs via pg_constraint,
    # delete in passes until the company can be removed.
    engine = db.get_bind()
    connection = engine.connect()
    try:
        trans = connection.begin()

        # Discover ALL tables that FK-reference companies
        company_refs = connection.execute(text("""
            SELECT DISTINCT src.relname, a.attname
            FROM pg_constraint c
            JOIN pg_class src ON c.conrelid = src.oid
            JOIN pg_class tgt ON c.confrelid = tgt.oid
            JOIN pg_attribute a ON a.attrelid = src.oid AND a.attnum = ANY(c.conkey)
            JOIN pg_namespace ns ON src.relnamespace = ns.oid
            WHERE c.contype = 'f' AND tgt.relname = 'companies'
              AND ns.nspname = 'public' AND src.relname != 'companies'
        """)).fetchall()

        # Discover ALL tables that FK-reference users
        user_refs = connection.execute(text("""
            SELECT DISTINCT src.relname, a.attname
            FROM pg_constraint c
            JOIN pg_class src ON c.conrelid = src.oid
            JOIN pg_class tgt ON c.confrelid = tgt.oid
            JOIN pg_attribute a ON a.attrelid = src.oid AND a.attnum = ANY(c.conkey)
            JOIN pg_namespace ns ON src.relnamespace = ns.oid
            WHERE c.contype = 'f' AND tgt.relname = 'users'
              AND ns.nspname = 'public'
        """)).fetchall()

        # Get user IDs for this tenant
        user_ids = [
            r[0] for r in connection.execute(
                text("SELECT id FROM users WHERE company_id = :tid"),
                {"tid": tenant_id},
            ).fetchall()
        ]

        # Pass 1: Null out all user references so users can be deleted
        if user_ids:
            for tbl, col in user_refs:
                try:
                    # Check if column is nullable
                    is_nullable = connection.execute(text("""
                        SELECT is_nullable FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = :tbl AND column_name = :col
                    """), {"tbl": tbl, "col": col}).scalar()

                    if is_nullable == 'YES':
                        connection.execute(
                            text(f'UPDATE "{tbl}" SET "{col}" = NULL WHERE "{col}" = ANY(:ids)'),
                            {"ids": user_ids},
                        )
                    else:
                        # Non-nullable FK to users — must delete the row
                        connection.execute(
                            text(f'DELETE FROM "{tbl}" WHERE "{col}" = ANY(:ids)'),
                            {"ids": user_ids},
                        )
                except Exception as e:
                    logger.debug("Pass 1 skip %s.%s: %s", tbl, col, str(e)[:80])

        # Pass 2: Delete users and roles
        if user_ids:
            try:
                connection.execute(text("DELETE FROM users WHERE company_id = :tid"), {"tid": tenant_id})
            except Exception as e:
                logger.warning("Users delete failed: %s", str(e)[:200])
        try:
            connection.execute(text("DELETE FROM roles WHERE company_id = :tid"), {"tid": tenant_id})
        except Exception as e:
            logger.debug("Roles delete: %s", str(e)[:80])

        # Pass 3: Delete all company-referencing rows (3 attempts for circular deps)
        for attempt in range(3):
            for tbl, col in company_refs:
                try:
                    connection.execute(
                        text(f'DELETE FROM "{tbl}" WHERE "{col}" = :tid'),
                        {"tid": tenant_id},
                    )
                except Exception:
                    pass

        # Pass 4: Delete the company
        connection.execute(
            text("DELETE FROM companies WHERE id = :tid"),
            {"tid": tenant_id},
        )

        trans.commit()
        logger.info("Tenant %s (%s) deleted successfully", tenant_id, tenant_name)
    except Exception as e:
        logger.exception("Failed to delete tenant %s", tenant_id)
        try:
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
