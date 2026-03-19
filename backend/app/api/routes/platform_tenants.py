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

    # Use a server-side PL/pgSQL function that iterates through all FK
    # references and deletes them in dependency order. This works on
    # managed PostgreSQL (Railway) without superuser privileges.
    engine = db.get_bind()
    connection = engine.connect()
    try:
        trans = connection.begin()

        # Create a temporary function that cascades deletes through all FKs
        connection.execute(text("""
            CREATE OR REPLACE FUNCTION _delete_tenant_cascade(p_tenant_id text)
            RETURNS void AS $$
            DECLARE
                r RECORD;
                sql_stmt text;
                pass_num int := 0;
                max_passes int := 10;
                rows_deleted int;
            BEGIN
                -- Multi-pass deletion: keep trying until nothing references the tenant
                LOOP
                    pass_num := pass_num + 1;
                    rows_deleted := 0;

                    -- Find all FK constraints that reference companies.id
                    FOR r IN
                        SELECT DISTINCT
                            src.relname AS src_table,
                            a.attname AS src_column
                        FROM pg_constraint c
                        JOIN pg_class src ON c.conrelid = src.oid
                        JOIN pg_class tgt ON c.confrelid = tgt.oid
                        JOIN pg_attribute a ON a.attrelid = src.oid
                            AND a.attnum = ANY(c.conkey)
                        JOIN pg_namespace ns ON src.relnamespace = ns.oid
                        WHERE c.contype = 'f'
                          AND tgt.relname = 'companies'
                          AND ns.nspname = 'public'
                          AND src.relname != 'companies'
                    LOOP
                        sql_stmt := format(
                            'DELETE FROM %I WHERE %I = $1',
                            r.src_table, r.src_column
                        );
                        BEGIN
                            EXECUTE sql_stmt USING p_tenant_id;
                            GET DIAGNOSTICS rows_deleted = rows_deleted + ROW_COUNT;
                        EXCEPTION WHEN OTHERS THEN
                            -- FK violation means we need another pass
                            NULL;
                        END;
                    END LOOP;

                    -- Also handle users table FK refs: null out all user references
                    -- then delete users
                    BEGIN
                        UPDATE users SET created_by = NULL, modified_by = NULL
                        WHERE company_id = p_tenant_id;

                        -- Null out user refs in other tables
                        FOR r IN
                            SELECT DISTINCT
                                src.relname AS src_table,
                                a.attname AS src_column
                            FROM pg_constraint c
                            JOIN pg_class src ON c.conrelid = src.oid
                            JOIN pg_class tgt ON c.confrelid = tgt.oid
                            JOIN pg_attribute a ON a.attrelid = src.oid
                                AND a.attnum = ANY(c.conkey)
                            JOIN pg_namespace ns ON src.relnamespace = ns.oid
                            WHERE c.contype = 'f'
                              AND tgt.relname = 'users'
                              AND ns.nspname = 'public'
                              AND src.relname != 'users'
                        LOOP
                            sql_stmt := format(
                                'UPDATE %I SET %I = NULL WHERE %I IN (SELECT id FROM users WHERE company_id = $1)',
                                r.src_table, r.src_column, r.src_column
                            );
                            BEGIN
                                EXECUTE sql_stmt USING p_tenant_id;
                            EXCEPTION WHEN OTHERS THEN
                                NULL;
                            END;
                        END LOOP;

                        DELETE FROM users WHERE company_id = p_tenant_id;
                    EXCEPTION WHEN OTHERS THEN
                        NULL;
                    END;

                    -- Try to delete roles
                    BEGIN
                        DELETE FROM roles WHERE company_id = p_tenant_id;
                    EXCEPTION WHEN OTHERS THEN
                        NULL;
                    END;

                    -- Try to delete the company
                    BEGIN
                        DELETE FROM companies WHERE id = p_tenant_id;
                        -- If we get here, it worked
                        RETURN;
                    EXCEPTION WHEN OTHERS THEN
                        -- Still blocked — continue to next pass
                        IF pass_num >= max_passes THEN
                            RAISE EXCEPTION 'Could not delete tenant after % passes', max_passes;
                        END IF;
                    END;
                END LOOP;
            END;
            $$ LANGUAGE plpgsql;
        """))

        # Execute the cascade delete function
        connection.execute(
            text("SELECT _delete_tenant_cascade(:tid)"),
            {"tid": tenant_id},
        )

        # Clean up the function
        connection.execute(text("DROP FUNCTION IF EXISTS _delete_tenant_cascade(text)"))

        trans.commit()
        logger.info("Tenant %s (%s) deleted successfully", tenant_id, tenant_name)
    except Exception as e:
        logger.exception("Failed to delete tenant %s", tenant_id)
        try:
            trans.rollback()
        except Exception:
            pass
        # Clean up function on failure too
        try:
            conn2 = engine.connect()
            conn2.execute(text("DROP FUNCTION IF EXISTS _delete_tenant_cascade(text)"))
            conn2.close()
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
