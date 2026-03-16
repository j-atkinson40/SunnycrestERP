from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text as sa_text
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import v1_router
from app.config import settings

# ---------------------------------------------------------------------------
# OpenAPI / docs configuration
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Sunnycrest ERP",
    description=(
        "Multi-tenant SaaS business management platform. "
        "Supports manufacturing, death care, and hospitality verticals."
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    contact={
        "name": "Sunnycrest ERP Support",
        "email": "support@sunnycrest.dev",
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
if settings.CORS_ORIGIN_REGEX:
    cors_kwargs["allow_origin_regex"] = settings.CORS_ORIGIN_REGEX

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
        if path.startswith("/api/") and not path.startswith(("/api/v1/", "/api/docs", "/api/redoc", "/api/openapi.json", "/api/health")):
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

# Deprecated alias: /api/ (same routes, triggers deprecation headers)
app.include_router(v1_router, prefix="/api")


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
