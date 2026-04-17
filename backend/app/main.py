from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text as sa_text
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.platform import platform_router
from app.api.v1 import v1_router
from app.config import settings

# ---------------------------------------------------------------------------
# OpenAPI / docs configuration
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Multi-tenant SaaS business management platform. "
        "Supports manufacturing, death care, and hospitality verticals."
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    contact={
        "name": f"{settings.APP_NAME} Support",
        "email": settings.SUPPORT_EMAIL,
    },
    license_info={
        "name": "Proprietary",
    },
    openapi_tags=[
        {"name": "Accounting Integration", "description": "Accounting provider management, sync, and account mapping"},
        {"name": "Authentication", "description": "Login, registration, token refresh"},
        {"name": "User Management", "description": "User CRUD and password management"},
        {"name": "Company Management", "description": "Tenant registration and settings"},
        {"name": "Role Management", "description": "Roles, permissions, and RBAC"},
        {"name": "Modules", "description": "Module enablement per tenant"},
        {"name": "Feature Flags", "description": "Feature flag registry and tenant overrides"},
        {"name": "Departments", "description": "Department CRUD"},
        {"name": "Employee Profiles", "description": "Employee profile management"},
        {"name": "Performance Notes", "description": "Employee performance tracking"},
        {"name": "Equipment", "description": "Equipment asset management"},
        {"name": "Documents", "description": "Document storage and management"},
        {"name": "Notifications", "description": "In-app notification system"},
        {"name": "Onboarding", "description": "Employee onboarding workflows"},
        {"name": "Customers", "description": "Customer CRUD, contacts, and notes"},
        {"name": "Products", "description": "Product catalog, categories, and price tiers"},
        {"name": "Inventory", "description": "Inventory management and adjustments"},
        {"name": "Job Queue", "description": "Background job queue, dead letter, and sync monitoring"},
        {"name": "Vendors", "description": "Vendor CRUD, contacts, and notes"},
        {"name": "Purchase Orders", "description": "Purchase order lifecycle"},
        {"name": "Vendor Bills", "description": "Vendor bill entry and approval"},
        {"name": "Vendor Payments", "description": "Vendor payment recording"},
        {"name": "Accounts Payable", "description": "AP aging, Sage export, and reporting"},
        {"name": "Sales & AR", "description": "Quotes, sales orders, invoices, customer payments, and AR aging"},
        {"name": "Sage Exports", "description": "Sage 100 CSV data exports"},
        {"name": "Sync Logs", "description": "Import/export sync tracking"},
        {"name": "AI", "description": "AI-powered command parsing"},
        {"name": "API Keys", "description": "API key management for external integrations"},
        {"name": "Audit Logs", "description": "System audit trail"},
        {"name": "Org Hierarchy", "description": "Organizational company hierarchy management"},
        {"name": "Network", "description": "Cross-tenant relationships and transactions"},
        {"name": "Platform Fees", "description": "Platform fee configuration and management"},
        {"name": "Billing", "description": "Subscription plans, billing, and payment management"},
        {"name": "Super Admin", "description": "Platform-wide admin dashboard and system health"},
    ],
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
cors_kwargs = {
    "allow_origins": settings.cors_origins_list,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
# Use explicit regex if set; otherwise default to known patterns in non-dev
cors_regex = settings.CORS_ORIGIN_REGEX
if not cors_regex and settings.ENVIRONMENT != "dev":
    cors_regex = r"https://.*\.(up\.railway\.app|getbridgeable\.com)"
if cors_regex:
    cors_kwargs["allow_origin_regex"] = cors_regex

app.add_middleware(CORSMiddleware, **cors_kwargs)


# ---------------------------------------------------------------------------
# Deprecation middleware — adds header for bare /api/ requests
# ---------------------------------------------------------------------------
class DeprecationMiddleware(BaseHTTPMiddleware):
    """Adds a Deprecation header to responses served via the bare /api/ prefix.

    Clients should migrate to /api/v1/.  The bare prefix will be removed in a
    future release.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        path = request.url.path
        # Only tag bare /api/ that is NOT /api/v1/, /api/docs, /api/redoc, /api/openapi.json
        if path.startswith("/api/") and not path.startswith(("/api/v1/", "/api/platform/", "/api/docs", "/api/redoc", "/api/openapi.json", "/api/health")):
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = "2026-09-01"
            response.headers["Link"] = f'</api/v1{path[4:]}>; rel="successor-version"'
        # Add API-Version header to all versioned responses
        if path.startswith("/api/v1/"):
            response.headers["API-Version"] = "v1"
        return response


app.add_middleware(DeprecationMiddleware)

# ---------------------------------------------------------------------------
# Route mounting
# ---------------------------------------------------------------------------

# Primary: /api/v1/
app.include_router(v1_router, prefix="/api/v1")

# Platform admin: /api/platform/
app.include_router(platform_router, prefix="/api/platform")

# Deprecated alias: /api/ (same routes, triggers deprecation headers)
app.include_router(v1_router, prefix="/api")

# Static files — safety training templates
import os
from fastapi.staticfiles import StaticFiles

_static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.on_event("startup")
def seed_platform_admin():
    """Create the initial platform admin user if configured via env vars."""
    if settings.PLATFORM_ADMIN_EMAIL and settings.PLATFORM_ADMIN_PASSWORD:
        from app.database import SessionLocal
        from app.services.platform_auth_service import get_or_create_initial_admin

        db = SessionLocal()
        try:
            get_or_create_initial_admin(
                db,
                email=settings.PLATFORM_ADMIN_EMAIL,
                password=settings.PLATFORM_ADMIN_PASSWORD,
            )

            from app.services.tenant_module_service import seed_all as seed_modules
            seed_modules(db)

            from app.services.extension_service import seed_extensions, seed_tenant_extension_defaults
            try:
                seed_extensions(db)
                seed_tenant_extension_defaults(db)
                db.commit()
            except Exception as exc:
                print(f"WARNING: Extension seeding failed — {exc}")
                db.rollback()

            from app.services.catalog_template_seeder import seed_wilbert_templates
            seed_wilbert_templates(db)

            from app.services.functional_area_service import seed_functional_areas
            seed_functional_areas(db)

            from app.services.onboarding_service import fix_checklist_targets
            fix_checklist_targets(db)

            db.commit()
        finally:
            db.close()


@app.on_event("startup")
def run_data_seeders():
    """Run data seeders that should always execute, regardless of platform admin config."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        from app.services.onboarding_service import fix_checklist_targets
        fix_checklist_targets(db)
        db.commit()
    except Exception as exc:
        print(f"WARNING: Checklist backfill failed — {exc}")
        db.rollback()

    try:
        from app.services.safety_training_seeder import seed_training_topics
        seed_training_topics(db)
    except Exception as exc:
        print(f"WARNING: Safety training topic seeding failed — {exc}")
        db.rollback()

    try:
        from app.services.widgets.widget_registry import seed_widget_definitions
        seed_widget_definitions(db)
    except Exception as exc:
        print(f"WARNING: Widget definition seeding failed — {exc}")
        db.rollback()

    try:
        # Workflow Engine Phase W-1 — seed default workflows (idempotent upsert
        # by workflow id). Without this the /workflows/command-bar endpoint
        # returns empty on fresh deployments.
        from app.data.seed_workflows import seed_default_workflows
        result = seed_default_workflows(db)
        print(f"Workflow defaults: {result}")
    except Exception as exc:
        print(f"WARNING: Default workflow seeding failed — {exc}")
        db.rollback()

    finally:
        db.close()


@app.on_event("startup")
def backfill_migration_checklist_completions():
    """Mark data_migration checklist item complete for any tenant that has a
    finished DataMigrationRun.  Idempotent — check_completion skips items that
    are already completed."""
    from app.database import SessionLocal
    from sqlalchemy import text as _text

    bfdb = SessionLocal()
    try:
        rows = bfdb.execute(_text(
            "SELECT DISTINCT tenant_id FROM data_migration_runs "
            "WHERE status IN ('complete', 'partial')"
        )).fetchall()
        if not rows:
            return

        from app.services.onboarding_service import check_completion
        for (tenant_id,) in rows:
            try:
                check_completion(bfdb, tenant_id, "data_migration")
            except Exception as exc:
                print(f"WARNING: backfill check_completion failed for {tenant_id} — {exc}")
                try:
                    bfdb.rollback()
                except Exception:
                    pass
    except Exception as exc:
        print(f"WARNING: Migration checklist backfill failed — {exc}")
    finally:
        bfdb.close()


@app.on_event("startup")
def patch_migrated_invoice_statuses():
    """One-time patch: migrated invoices imported with status='open' must be 'sent'
    so the financials board (which queries sent/partial/overdue) can find them."""
    from app.database import SessionLocal
    from sqlalchemy import text as _text
    patch_db = SessionLocal()
    try:
        result = patch_db.execute(_text(
            "UPDATE invoices SET status = 'sent' "
            "WHERE status = 'open' AND sage_invoice_id IS NOT NULL"
        ))
        patch_db.commit()
        rows = result.rowcount if hasattr(result, "rowcount") else "?"
        if rows:
            print(f"INFO: Patched {rows} migrated invoice(s) from status=open to sent")
    except Exception as exc:
        print(f"WARNING: Invoice status patch failed — {exc}")
        patch_db.rollback()
    finally:
        patch_db.close()


@app.on_event("startup")
def backfill_default_modules():
    """Ensure all companies have CompanyModule rows for default-enabled modules.

    Companies created before a module was added to AVAILABLE_MODULES won't have
    a row for it, causing get_enabled_module_keys() to exclude it even though
    default_enabled=True.  This runs idempotently on every deploy.
    """
    try:
        from app.database import SessionLocal
        from app.models.company import Company
        from app.services.module_service import seed_company_modules

        db = SessionLocal()
        try:
            companies = db.query(Company).filter(Company.is_active == True).all()  # noqa: E712
            for company in companies:
                seed_company_modules(db, company.id)
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        print(f"WARNING: Module backfill failed — {exc}")


@app.on_event("startup")
def check_weasyprint():
    """Log WeasyPrint availability — PDF generation degrades gracefully if absent."""
    import logging
    _log = logging.getLogger(__name__)
    try:
        from weasyprint import HTML  # noqa: F401
        _log.info("WeasyPrint available — PDF generation enabled")
    except ImportError:
        _log.warning("WeasyPrint not available — PDF generation will be disabled")


@app.on_event("startup")
def start_job_scheduler():
    """Start the APScheduler background scheduler for all agent jobs."""
    try:
        from app.scheduler import start_scheduler
        start_scheduler()
    except Exception as exc:
        print(f"WARNING: Job scheduler failed to start — {exc}")


@app.on_event("shutdown")
def stop_job_scheduler():
    """Gracefully shut down the APScheduler."""
    try:
        from app.scheduler import shutdown_scheduler
        shutdown_scheduler()
    except Exception:
        pass


@app.get("/api/health", tags=["System"])
def health_check():
    """Health check endpoint — used by Railway, load balancers, and CI."""
    health: dict = {
        "status": "healthy",
        "api_version": "v1",
        "environment": settings.ENVIRONMENT,
    }

    # Quick DB check
    try:
        from app.database import SessionLocal

        db = SessionLocal()
        db.execute(sa_text("SELECT 1"))
        db.close()
        health["db"] = "connected"
    except Exception:
        health["db"] = "unreachable"
        health["status"] = "degraded"

    # Quick Redis check
    try:
        from app.core.redis import get_redis

        r = get_redis()
        if r:
            r.ping()
            health["redis"] = "connected"
        else:
            health["redis"] = "not_configured"
    except Exception:
        health["redis"] = "unreachable"

    return health
