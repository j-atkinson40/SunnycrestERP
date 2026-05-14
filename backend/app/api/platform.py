"""
Platform admin router — aggregates all platform-level routes under /api/platform/.

These routes use platform JWT tokens (realm='platform') and are completely
isolated from tenant routes.  Tenant tokens are rejected at the dependency level.
"""

from fastapi import APIRouter

from app.api.routes import (
    platform_auth,
    platform_extensions,
    platform_feature_flags,
    platform_health,
    platform_impersonation,
    platform_incidents,
    platform_modules,
    platform_system,
    platform_tenants,
    platform_training,
    platform_users_mgmt,
)
from app.api.routes.admin import (
    impersonation as admin_impersonation,
    feature_flags as admin_feature_flags,
    staging as admin_staging,
    deployments as admin_deployments,
    kanban as admin_kanban,
    audit as admin_audit,
    migrations as admin_migrations,
    chat as admin_chat,
    arc_telemetry as admin_arc_telemetry,
    visual_editor_themes,
    visual_editor_components,
    visual_editor_workflows,
    visual_editor_classes,
    visual_editor_compositions,
    visual_editor_dashboard_layouts,
    focus_template_inheritance as admin_focus_template_inheritance,
    edge_panel_inheritance as admin_edge_panel_inheritance,
    plugin_registry as admin_plugin_registry,
    studio_inventory as admin_studio_inventory,
    verticals as admin_verticals,
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
platform_router.include_router(
    platform_modules.router,
    prefix="/modules",
    tags=["Platform Modules"],
)
platform_router.include_router(
    platform_extensions.router,
    prefix="/extensions",
    tags=["Platform Extensions"],
)
platform_router.include_router(
    platform_training.router,
    prefix="/training",
    tags=["Platform Training Content"],
)
platform_router.include_router(
    platform_incidents.router,
    tags=["Platform Incidents"],
)
platform_router.include_router(
    platform_health.router,
    prefix="/health",
    tags=["Platform Health"],
)

# ---------------------------------------------------------------------------
# New super admin portal routes (admin_01_super_admin_tables)
# ---------------------------------------------------------------------------
platform_router.include_router(
    admin_impersonation.router, prefix="/admin/impersonation", tags=["Admin Impersonation"]
)
platform_router.include_router(
    admin_feature_flags.router, prefix="/admin/feature-flags", tags=["Admin Feature Flags"]
)
platform_router.include_router(
    admin_staging.router, prefix="/admin/staging", tags=["Admin Staging Tenants"]
)
platform_router.include_router(
    admin_deployments.router, prefix="/admin/deployments", tags=["Admin Deployments"]
)
platform_router.include_router(
    admin_kanban.router, prefix="/admin/tenants", tags=["Admin Tenant Kanban"]
)
platform_router.include_router(
    admin_audit.router, prefix="/admin/audit", tags=["Admin Audit Runner"]
)
platform_router.include_router(
    admin_migrations.router, prefix="/admin/migrations", tags=["Admin Migrations"]
)
platform_router.include_router(
    admin_chat.router, prefix="/admin/chat", tags=["Admin Chat"]
)
platform_router.include_router(
    admin_arc_telemetry.router,
    prefix="/admin/arc-telemetry",
    tags=["Phase 7 Arc Telemetry"],
)

# ---------------------------------------------------------------------------
# Admin Visual Editor (Phase 2/3/4) — relocated from v1_router (May 2026).
# Token, component configuration, and workflow template editors gated by
# PlatformUser auth (realm='platform'). Service layer + storage unchanged;
# only the auth surface and route prefix moved. See:
#   - frontend/src/bridgeable-admin/pages/visual-editor/* for the UI
#   - backend/app/api/routes/admin/visual_editor_*.py for the routes
#   - backend/app/services/{platform_themes,component_config,workflow_templates}/*
#     for the unchanged service layer
# ---------------------------------------------------------------------------
platform_router.include_router(
    visual_editor_themes.router,
    prefix="/admin/visual-editor/themes",
    tags=["Visual Editor — Themes"],
)
platform_router.include_router(
    visual_editor_components.router,
    prefix="/admin/visual-editor/components",
    tags=["Visual Editor — Components"],
)
platform_router.include_router(
    visual_editor_workflows.router,
    prefix="/admin/visual-editor/workflows",
    tags=["Visual Editor — Workflows"],
)
platform_router.include_router(
    visual_editor_classes.router,
    prefix="/admin/visual-editor/classes",
    tags=["Visual Editor — Component Classes"],
)
platform_router.include_router(
    visual_editor_compositions.router,
    prefix="/admin/visual-editor/compositions",
    tags=["Visual Editor — Focus Compositions"],
)
platform_router.include_router(
    visual_editor_dashboard_layouts.router,
    prefix="/admin/visual-editor/dashboard-layouts",
    tags=["Visual Editor — Dashboard Layouts"],
)
# Focus Template Inheritance — sub-arc B-1 (May 2026). Three-tier
# inheritance (cores → templates → compositions) with delta-storage
# at Tier 3.
platform_router.include_router(
    admin_focus_template_inheritance.router,
    prefix="/admin/focus-template-inheritance",
    tags=["Focus Template Inheritance"],
)
# Edge Panel Inheritance — sub-arc B-1.5 (May 2026). Two-tier
# inheritance (templates → compositions, lazy fork) with recursive
# page-keyed delta-storage at Tier 3. Edge-panels are pure
# composition; no Tier 1 core analogue to FocusCore.
platform_router.include_router(
    admin_edge_panel_inheritance.router,
    prefix="/admin/edge-panel-inheritance",
    tags=["Edge Panel Inheritance"],
)
# R-8.y.d — Plugin Registry browser introspection endpoint.
platform_router.include_router(
    admin_plugin_registry.router,
    prefix="/admin/plugin-registry",
    tags=["Plugin Registry Browser"],
)

# Verticals-lite precursor arc — first-class registry for the 4
# canonical verticals (seeded via migration r92). Admin-only read
# + partial update; full CRUD lands when Studio shell needs it.
platform_router.include_router(
    admin_verticals.router,
    prefix="/admin/verticals",
    tags=["Admin Verticals"],
)

# Studio 1a-ii — overview inventory (per-section counts + recent
# edits feed) backing /studio + /studio/:vertical.
platform_router.include_router(
    admin_studio_inventory.router,
    prefix="/admin/studio/inventory",
    tags=["Studio — Inventory"],
)
