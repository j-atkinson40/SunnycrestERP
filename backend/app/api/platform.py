"""
Platform admin router — aggregates all platform-level routes under /api/platform/.

These routes use platform JWT tokens (realm='platform') and are completely
isolated from tenant routes.  Tenant tokens are rejected at the dependency level.
"""

from fastapi import APIRouter

from app.api.routes import (
    platform_auth,
    platform_feature_flags,
    platform_impersonation,
    platform_system,
    platform_tenants,
    platform_users_mgmt,
)

platform_router = APIRouter()

platform_router.include_router(
    platform_auth.router, prefix="/auth", tags=["Platform Auth"]
)
platform_router.include_router(
    platform_tenants.router, prefix="/tenants", tags=["Platform Tenants"]
)
platform_router.include_router(
    platform_feature_flags.router,
    prefix="/feature-flags",
    tags=["Platform Feature Flags"],
)
platform_router.include_router(
    platform_system.router, prefix="/system", tags=["Platform System"]
)
platform_router.include_router(
    platform_users_mgmt.router, prefix="/users", tags=["Platform Users"]
)
platform_router.include_router(
    platform_impersonation.router,
    prefix="/impersonation",
    tags=["Platform Impersonation"],
)
