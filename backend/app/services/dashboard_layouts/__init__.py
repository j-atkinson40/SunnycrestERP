"""Dashboard Layouts service — Phase R-0 of the Runtime-Aware Editor.

3-tier scope-inheritance for dashboard widget arrangements
(`platform_default → vertical_default → tenant_default`). Layered
under `user_widget_layouts` (the user-override tier, unchanged).

Public API mirrors `platform_themes.theme_service` shape:
  - list_layouts / get_layout / get_layout_by_id
  - create_layout (with write-side versioning)
  - update_layout
  - resolve_layout (full inheritance walk for read paths)
"""

from app.services.dashboard_layouts.layouts_service import (
    DashboardLayoutNotFound,
    DashboardLayoutScopeMismatch,
    DashboardLayoutServiceError,
    InvalidDashboardLayoutShape,
    SCOPE_PLATFORM_DEFAULT,
    SCOPE_TENANT_DEFAULT,
    SCOPE_VERTICAL_DEFAULT,
    Scope,
    create_layout,
    get_layout_by_id,
    list_layouts,
    resolve_layout,
    update_layout,
)


__all__ = [
    "DashboardLayoutNotFound",
    "DashboardLayoutScopeMismatch",
    "DashboardLayoutServiceError",
    "InvalidDashboardLayoutShape",
    "SCOPE_PLATFORM_DEFAULT",
    "SCOPE_TENANT_DEFAULT",
    "SCOPE_VERTICAL_DEFAULT",
    "Scope",
    "create_layout",
    "get_layout_by_id",
    "list_layouts",
    "resolve_layout",
    "update_layout",
]
