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

    # Delete all tenant data using explicit table list in dependency order.
    # This is more reliable than dynamic FK discovery which can miss tables
    # due to permission or schema visibility issues on managed PostgreSQL.
    #
    # Tables are listed leaf-first (no other table depends on them) to avoid
    # FK violations. Multiple groups handle the ordering.

    # Group 1: Leaf tables (no other tenant table references these)
    LEAF_TABLES = [
        # Onboarding
        ("onboarding_help_dismissals", "tenant_id"),
        ("onboarding_scenario_steps", "tenant_id"),
        ("onboarding_checklist_items", "tenant_id"),
        ("onboarding_scenarios", "tenant_id"),
        ("tenant_onboarding_checklists", "tenant_id"),
        ("onboarding_data_imports", "tenant_id"),
        ("onboarding_integration_setups", "tenant_id"),
        # Production log
        ("production_log_entries", "tenant_id"),
        ("production_log_summaries", "tenant_id"),
        # Funeral home (leaf first)
        ("fh_portal_sessions", "company_id"),
        ("fh_case_activities", "company_id"),
        ("fh_documents", "company_id"),
        ("fh_payments", "company_id"),
        ("fh_invoices", "company_id"),
        ("fh_obituaries", "company_id"),
        ("fh_vault_orders", "company_id"),
        ("fh_services", "company_id"),
        ("fh_case_contacts", "company_id"),
        ("fh_cases", "company_id"),
        ("fh_price_list_versions", "company_id"),
        ("fh_price_list", "company_id"),
        ("fh_manufacturer_relationships", "funeral_home_tenant_id"),
        ("fh_manufacturer_relationships", "manufacturer_tenant_id"),
        # Extensions & flags
        ("extension_activity_log", "tenant_id"),
        ("extension_notify_requests", "tenant_id"),
        ("tenant_extensions", "tenant_id"),
        ("tenant_feature_flags", "tenant_id"),
        ("flag_audit_logs", "tenant_id"),
        ("tenant_module_configs", "tenant_id"),
        # Audit & notifications
        ("audit_logs", "company_id"),
        ("notifications", "company_id"),
        ("tenant_notifications", "company_id"),
        ("tenant_notifications", "source_tenant_id"),
        ("impersonation_sessions", "tenant_id"),
        ("sync_logs", "company_id"),
        ("api_keys", "company_id"),
        # Jobs
        ("jobs", "company_id"),
        # Safety (leaf tables first)
        ("safety_inspection_results", "company_id"),
        ("safety_inspection_items", "company_id"),
        ("safety_inspections", "company_id"),
        ("safety_inspection_templates", "company_id"),
        ("safety_incidents", "company_id"),
        ("safety_alerts", "company_id"),
        ("safety_chemicals", "company_id"),
        ("safety_loto_procedures", "company_id"),
        ("employee_training_records", "company_id"),
        ("safety_training_events", "company_id"),
        ("safety_training_requirements", "company_id"),
        ("safety_programs", "company_id"),
        # QC
        ("qc_step_results", "company_id"),
        ("qc_media", "company_id"),
        ("qc_rework_records", "company_id"),
        ("qc_dispositions", "company_id"),
        ("qc_inspections", "company_id"),
        ("qc_inspection_steps", "company_id"),
        ("qc_inspection_templates", "company_id"),
        ("qc_defect_types", "company_id"),
        # Production
        ("batch_tickets", "company_id"),
        ("pour_event_work_orders", "company_id"),
        ("pour_events", "company_id"),
        ("mix_designs", "company_id"),
        ("cure_schedules", "company_id"),
        ("work_order_products", "company_id"),
        ("work_orders", "company_id"),
        ("bill_of_materials", "company_id"),
        # Delivery
        ("delivery_media", "company_id"),
        ("delivery_events", "company_id"),
        ("delivery_stops", "company_id"),
        ("deliveries", "company_id"),
        ("delivery_routes", "company_id"),
        ("delivery_settings", "company_id"),
        ("delivery_zones", "company_id"),
        ("delivery_type_definitions", "company_id"),
        ("drivers", "company_id"),
        ("vehicles", "company_id"),
        ("carriers", "company_id"),
        # Finance
        ("vendor_payments", "company_id"),
        ("vendor_bill_lines", "company_id"),
        ("vendor_bills", "company_id"),
        ("vendor_contacts", "company_id"),
        ("vendor_notes", "company_id"),
        ("vendors", "company_id"),
        ("customer_payments", "company_id"),
        ("balance_adjustments", "company_id"),
        ("invoice_lines", "company_id"),
        ("invoices", "company_id"),
        ("sales_orders", "company_id"),
        ("quotes", "company_id"),
        ("purchase_orders", "company_id"),
        ("customer_contacts", "company_id"),
        ("customer_notes", "company_id"),
        ("customers", "company_id"),
        # Inventory
        ("inventory_transactions", "company_id"),
        ("inventory_items", "company_id"),
        ("stock_replenishment_rules", "company_id"),
        # Products
        ("product_price_tiers", "company_id"),
        ("products", "company_id"),
        ("product_categories", "company_id"),
        # Network
        ("network_transactions", "source_company_id"),
        ("network_transactions", "target_company_id"),
        ("network_relationships", "requesting_company_id"),
        ("network_relationships", "target_company_id"),
        # HR
        ("onboarding_checklists", "company_id"),
        ("onboarding_templates", "company_id"),
        ("performance_notes", "company_id"),
        ("documents", "company_id"),
        ("equipment", "company_id"),
        ("departments", "company_id"),
        # Projects
        ("projects", "company_id"),
        # Config
        ("sage_export_configs", "company_id"),
        ("billing_events", "company_id"),
        ("subscriptions", "company_id"),
        ("company_modules", "company_id"),
    ]

    # Group 2: Auth tables — special handling needed
    # users has self-referential FKs (created_by, modified_by → users.id)
    # and many tables have created_by/modified_by → users.id FKs

    engine = db.get_bind()
    connection = engine.connect()
    deleted_counts: dict[str, int] = {}
    try:
        trans = connection.begin()

        # Phase 1: Delete all leaf tables
        for table_name, col_name in LEAF_TABLES:
            sp = connection.begin_nested()
            try:
                result = connection.execute(
                    text(f'DELETE FROM "{table_name}" WHERE "{col_name}" = :tid'),
                    {"tid": tenant_id},
                )
                sp.commit()
                if result.rowcount > 0:
                    deleted_counts[table_name] = (
                        deleted_counts.get(table_name, 0) + result.rowcount
                    )
                    logger.info("Deleted %d from %s", result.rowcount, table_name)
            except Exception as e:
                sp.rollback()
                logger.debug("Skipped %s.%s: %s", table_name, col_name, str(e)[:100])

        # Phase 2: Get user IDs for this tenant, then null out all
        # created_by / modified_by / entered_by / completed_by references
        user_ids = [
            r[0] for r in connection.execute(
                text("SELECT id FROM users WHERE company_id = :tid"),
                {"tid": tenant_id},
            ).fetchall()
        ]

        if user_ids:
            # Null out all columns across the DB that reference these user IDs.
            # Uses a hardcoded list of common FK column names that point to users.
            USER_REF_COLUMNS = [
                "created_by", "modified_by", "updated_by", "entered_by",
                "completed_by", "assigned_to", "assigned_director_id",
                "approved_by", "reviewed_by", "performed_by",
                "signed_by_user_id", "reported_by",
            ]

            # Get all tables in the schema
            all_tbl_rows = connection.execute(text("""
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND column_name = ANY(:cols)
            """), {"cols": USER_REF_COLUMNS}).fetchall()

            for tbl, col in all_tbl_rows:
                sp = connection.begin_nested()
                try:
                    connection.execute(
                        text(f'UPDATE "{tbl}" SET "{col}" = NULL WHERE "{col}" = ANY(:ids)'),
                        {"ids": user_ids},
                    )
                    sp.commit()
                except Exception:
                    sp.rollback()

            # Also null out self-referential FKs on users table itself
            for col in ["created_by", "modified_by"]:
                sp = connection.begin_nested()
                try:
                    connection.execute(
                        text(f'UPDATE users SET "{col}" = NULL WHERE company_id = :tid'),
                        {"tid": tenant_id},
                    )
                    sp.commit()
                except Exception:
                    sp.rollback()

        # Phase 3: Try to delete users — if it fails, report exactly why
        # First attempt
        sp = connection.begin_nested()
        try:
            result = connection.execute(
                text("DELETE FROM permission_overrides WHERE company_id = :tid"),
                {"tid": tenant_id},
            )
            sp.commit()
        except Exception:
            sp.rollback()

        sp = connection.begin_nested()
        try:
            result = connection.execute(
                text("DELETE FROM users WHERE company_id = :tid"),
                {"tid": tenant_id},
            )
            sp.commit()
            deleted_counts["users"] = result.rowcount
            logger.info("Deleted %d users", result.rowcount)
        except Exception as users_err:
            sp.rollback()
            # Users delete failed — find out what still references them
            logger.warning("Users delete failed: %s", str(users_err)[:300])

            # Try to find what's blocking: check all FK refs to users
            blocking_info = []
            if user_ids:
                for ref_tbl, ref_col in [
                    ("users", "created_by"), ("users", "modified_by"),
                    ("audit_logs", "user_id"), ("roles", "created_by"),
                    ("fh_cases", "assigned_director_id"),
                    ("fh_case_activities", "user_id"),
                    ("impersonation_sessions", "impersonated_user_id"),
                    ("impersonation_sessions", "platform_user_id"),
                ]:
                    sp2 = connection.begin_nested()
                    try:
                        cnt = connection.execute(
                            text(f'SELECT count(*) FROM "{ref_tbl}" WHERE "{ref_col}" = ANY(:ids)'),
                            {"ids": user_ids},
                        ).scalar()
                        sp2.commit()
                        if cnt and cnt > 0:
                            blocking_info.append(f"{ref_tbl}.{ref_col}={cnt}")
                    except Exception:
                        sp2.rollback()

            if blocking_info:
                logger.warning("Blocking refs: %s", ", ".join(blocking_info))

            # Force-null ALL nullable FK columns that reference any of these user IDs
            # by querying information_schema for ALL columns in ALL tables
            if user_ids:
                all_cols = connection.execute(text("""
                    SELECT table_name, column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND data_type IN ('character varying', 'text', 'uuid')
                    AND is_nullable = 'YES'
                """)).fetchall()

                for tbl, col in all_cols:
                    if col in ("id", "tenant_id", "company_id", "slug", "email", "name"):
                        continue
                    sp2 = connection.begin_nested()
                    try:
                        connection.execute(
                            text(f'UPDATE "{tbl}" SET "{col}" = NULL WHERE "{col}" = ANY(:ids)'),
                            {"ids": user_ids},
                        )
                        sp2.commit()
                    except Exception:
                        sp2.rollback()

                # Retry users delete
                result = connection.execute(
                    text("DELETE FROM users WHERE company_id = :tid"),
                    {"tid": tenant_id},
                )
                deleted_counts["users"] = result.rowcount
                logger.info("Deleted %d users on retry", result.rowcount)

        # Delete roles
        sp = connection.begin_nested()
        try:
            result = connection.execute(
                text("DELETE FROM roles WHERE company_id = :tid"),
                {"tid": tenant_id},
            )
            sp.commit()
            if result.rowcount > 0:
                deleted_counts["roles"] = result.rowcount
        except Exception:
            sp.rollback()

        # Phase 4: Delete the company itself
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
