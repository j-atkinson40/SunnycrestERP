from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import audit, auth, companies, employee_profiles, inventory, notifications, products, roles, users
from app.config import settings

app = FastAPI(title="Sunnycrest ERP", version="0.2.0")

cors_kwargs = {
    "allow_origins": settings.cors_origins_list,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if settings.CORS_ORIGIN_REGEX:
    cors_kwargs["allow_origin_regex"] = settings.CORS_ORIGIN_REGEX

app.add_middleware(CORSMiddleware, **cors_kwargs)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["User Management"])
app.include_router(
    companies.router, prefix="/api/companies", tags=["Company Management"]
)
app.include_router(roles.router, prefix="/api/roles", tags=["Role Management"])
app.include_router(audit.router, prefix="/api/audit-logs", tags=["Audit Logs"])
app.include_router(
    employee_profiles.router,
    prefix="/api/employee-profiles",
    tags=["Employee Profiles"],
)
app.include_router(
    notifications.router,
    prefix="/api/notifications",
    tags=["Notifications"],
)
app.include_router(
    products.router,
    prefix="/api/products",
    tags=["Products"],
)
app.include_router(
    inventory.router,
    prefix="/api/inventory",
    tags=["Inventory"],
)


@app.get("/api/health")
def health_check():
    return {"status": "healthy"}
