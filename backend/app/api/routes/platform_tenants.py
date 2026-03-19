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


@router.post("/debug-delete/{tenant_id}")
def debug_delete_tenant(
    tenant_id: str,
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Debug version of delete that returns errors as 200 so CORS doesn't block."""
    import traceback
    from sqlalchemy import text as sa_text
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == tenant_id).first()
    if not company:
        return {"status": "error", "detail": "Tenant not found"}

    tenant_name = company.name
    db.expunge(company)
    steps = []

    try:
        def safe_run(label, stmt_str, params=None):
            nested = db.begin_nested()
            try:
                db.execute(sa_text(stmt_str), params or {})
                nested.commit()
                steps.append({"step": label, "status": "ok"})
            except Exception as e:
                nested.rollback()
                steps.append({"step": label, "status": "failed", "error": str(e)[:200]})

        # Get user/role IDs
        user_ids = [r[0] for r in db.execute(sa_text("SELECT id FROM users WHERE company_id = :tid"), {"tid": tenant_id}).fetchall()]
        role_ids = [r[0] for r in db.execute(sa_text("SELECT id FROM roles WHERE company_id = :tid"), {"tid": tenant_id}).fetchall()]
        steps.append({"step": "discovery", "users": len(user_ids), "roles": len(role_ids)})

        # Get all company/tenant ref tables
        ref_cols = db.execute(sa_text("""
            SELECT table_name, column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND column_name IN ('company_id', 'tenant_id')
            AND table_name != 'companies'
        """)).fetchall()
        steps.append({"step": "ref_discovery", "tables": len(ref_cols)})

        # Delete company refs
        for _ in range(3):
            for tbl, col in ref_cols:
                safe_run(f"del_{tbl}.{col}", f'DELETE FROM "{tbl}" WHERE "{col}" = :tid', {"tid": tenant_id})

        # Null user refs
        for uid in user_ids:
            safe_run(f"null_user_{uid[:8]}",
                "UPDATE users SET created_by = NULL, modified_by = NULL WHERE id = :uid",
                {"uid": uid})
            for tbl in ["employee_profiles", "user_permission_overrides"]:
                safe_run(f"del_{tbl}_{uid[:8]}",
                    f'DELETE FROM "{tbl}" WHERE user_id = :uid', {"uid": uid})

        # Null role refs
        for rid in role_ids:
            safe_run(f"null_role_{rid[:8]}",
                'UPDATE users SET role_id = NULL WHERE role_id = :rid', {"rid": rid})

        # Delete users
        safe_run("del_users", 'DELETE FROM users WHERE company_id = :tid', {"tid": tenant_id})
        safe_run("del_roles", 'DELETE FROM roles WHERE company_id = :tid', {"tid": tenant_id})

        # Final company ref cleanup
        for tbl, col in ref_cols:
            safe_run(f"final_{tbl}.{col}", f'DELETE FROM "{tbl}" WHERE "{col}" = :tid', {"tid": tenant_id})

        # Self refs
        safe_run("null_company_self",
            'UPDATE companies SET parent_company_id = NULL, created_by = NULL, modified_by = NULL WHERE id = :tid',
            {"tid": tenant_id})

        # Delete company
        db.execute(sa_text("DELETE FROM companies WHERE id = :tid"), {"tid": tenant_id})
        db.commit()
        steps.append({"step": "delete_company", "status": "ok"})

        return {"status": "success", "tenant": tenant_name, "steps": steps}
    except Exception as e:
        db.rollback()
        return {
            "status": "error",
            "detail": f"{type(e).__name__}: {str(e)[:500]}",
            "traceback": traceback.format_exc()[-1000:],
            "steps": steps,
        }


@router.get("/debug-tenant/{slug}")
def debug_tenant_by_slug(
    slug: str,
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Debug: check what data exists for a given slug."""
    from sqlalchemy import text
    conn = db.get_bind().connect()
    try:
        # Check companies
        companies = conn.execute(
            text("SELECT id, name, slug, is_active FROM companies WHERE slug = :s"),
            {"s": slug},
        ).fetchall()

        # Check users with emails containing the slug
        users = conn.execute(
            text("SELECT id, email, company_id FROM users WHERE email LIKE :pattern"),
            {"pattern": f"%{slug.replace('-', '')}%"},
        ).fetchall()

        # Check all companies
        all_companies = conn.execute(
            text("SELECT id, name, slug, is_active FROM companies ORDER BY name"),
        ).fetchall()

        return {
            "matching_companies": [
                {"id": c[0], "name": c[1], "slug": c[2], "is_active": c[3]}
                for c in companies
            ],
            "matching_users": [
                {"id": u[0], "email": u[1], "company_id": u[2]}
                for u in users
            ],
            "all_companies": [
                {"id": c[0], "name": c[1], "slug": c[2], "is_active": c[3]}
                for c in all_companies
            ],
        }
    finally:
        conn.close()


@router.delete("/{tenant_id}")
def delete_tenant(
    tenant_id: str,
    _user: PlatformUser = Depends(require_platform_role("super_admin")),
    db: Session = Depends(get_db),
):
    """Permanently delete a tenant and ALL associated data. Uses the same
    logic as the debug-delete endpoint which is proven to work on Railway."""
    from sqlalchemy import text as sa_text
    from app.models.company import Company
    import logging
    logger = logging.getLogger(__name__)

    company = db.query(Company).filter(Company.id == tenant_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant_name = company.name
    db.expunge(company)

    try:
        def safe_run(stmt_str, params=None):
            nested = db.begin_nested()
            try:
                db.execute(sa_text(stmt_str), params or {})
                nested.commit()
            except Exception:
                nested.rollback()

        user_ids = [r[0] for r in db.execute(sa_text("SELECT id FROM users WHERE company_id = :tid"), {"tid": tenant_id}).fetchall()]
        role_ids = [r[0] for r in db.execute(sa_text("SELECT id FROM roles WHERE company_id = :tid"), {"tid": tenant_id}).fetchall()]

        ref_cols = db.execute(sa_text("""
            SELECT table_name, column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND column_name IN ('company_id', 'tenant_id')
            AND table_name != 'companies'
        """)).fetchall()

        # Delete company refs (3 rounds)
        for _ in range(3):
            for tbl, col in ref_cols:
                safe_run(f'DELETE FROM "{tbl}" WHERE "{col}" = :tid', {"tid": tenant_id})

        # Non-standard FK columns
        for tbl, col in [
            ("fh_manufacturer_relationships", "funeral_home_tenant_id"),
            ("fh_manufacturer_relationships", "manufacturer_tenant_id"),
            ("fh_vault_orders", "manufacturer_tenant_id"),
            ("network_relationships", "requesting_company_id"),
            ("network_relationships", "target_company_id"),
            ("network_transactions", "source_company_id"),
            ("network_transactions", "target_company_id"),
            ("tenant_notifications", "source_tenant_id"),
        ]:
            safe_run(f'DELETE FROM "{tbl}" WHERE "{col}" = :tid', {"tid": tenant_id})

        # Clean user refs
        for uid in user_ids:
            safe_run("UPDATE users SET created_by = NULL, modified_by = NULL WHERE id = :uid", {"uid": uid})
            for tbl in ["employee_profiles", "user_permission_overrides"]:
                safe_run(f'DELETE FROM "{tbl}" WHERE user_id = :uid', {"uid": uid})

        # Clean role refs
        for rid in role_ids:
            safe_run('UPDATE users SET role_id = NULL WHERE role_id = :rid', {"rid": rid})

        # Delete users and roles
        safe_run('DELETE FROM users WHERE company_id = :tid', {"tid": tenant_id})
        safe_run('DELETE FROM roles WHERE company_id = :tid', {"tid": tenant_id})

        # Final company ref cleanup
        for tbl, col in ref_cols:
            safe_run(f'DELETE FROM "{tbl}" WHERE "{col}" = :tid', {"tid": tenant_id})

        # Self refs
        safe_run('UPDATE companies SET parent_company_id = NULL, created_by = NULL, modified_by = NULL WHERE id = :tid', {"tid": tenant_id})

        # Delete company
        db.execute(sa_text("DELETE FROM companies WHERE id = :tid"), {"tid": tenant_id})
        db.commit()
        logger.info("Tenant %s (%s) deleted", tenant_id, tenant_name)
    except Exception as e:
        logger.exception("Delete tenant failed: %s", tenant_id)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Delete failed: {type(e).__name__}: {str(e)[:500]}")

    return {"detail": f'Tenant "{tenant_name}" permanently deleted'}

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
