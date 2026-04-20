"""Vault Hub service registry — Phase V-1a.

Tracks which cross-cutting platform services appear in the Vault Hub
sidebar. Each registered service surfaces a secondary-nav item + a
route_prefix the frontend owns.

Registration is module-level (singleton dict). V-1a registers
Documents + Intelligence. Subsequent V-1 phases register CRM,
Notifications, and Accounting admin.

The frontend has its own mirrored registry at
`frontend/src/services/vault-hub-registry.ts`. The backend registry
is the source of truth once overview-widget data-aggregation needs
server-side service-awareness (V-1b). Until then both are populated
in lockstep at code level.

Filtering semantics (matches the existing navigation-service
permission layer at `frontend/src/services/navigation-service.ts`):

  - `required_permission` — if set and user is not admin, gate on the
    permission string.
  - `required_module` — tenant must have the module enabled.
  - `required_extension` — tenant extension must be active.

An unspecified gate means "always visible to authenticated users"; the
route-level `require_admin` / `require_permission` dependencies still
apply per-endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VaultServiceDescriptor:
    """One entry in the Vault Hub sidebar."""

    service_key: str
    display_name: str
    icon: str              # lucide-react name — matches ICON_MAP in sidebar
    route_prefix: str      # frontend route, e.g. "/vault/documents"
    required_permission: str | None = None
    required_module: str | None = None
    required_extension: str | None = None
    overview_widget_ids: list[str] = field(default_factory=list)
    sort_order: int = 100


# Module-level registry. Lazily seeded on first import via
# `_seed_default_services()` below.
_registry: dict[str, VaultServiceDescriptor] = {}
_seeded: bool = False


def register_service(descriptor: VaultServiceDescriptor) -> None:
    """Register or replace a service by `service_key`.

    Replacement is intentional — extensions and test code can override
    core contributors by registering with the same key.
    """
    _registry[descriptor.service_key] = descriptor


def list_services() -> list[VaultServiceDescriptor]:
    """Return services ordered by `sort_order`, then `service_key` for
    stable ties."""
    _ensure_seeded()
    return sorted(
        _registry.values(),
        key=lambda d: (d.sort_order, d.service_key),
    )


def reset_registry() -> None:
    """Test-only — clear the registry and mark it unseeded."""
    global _seeded
    _registry.clear()
    _seeded = False


def _ensure_seeded() -> None:
    global _seeded
    if _seeded:
        return
    _seed_default_services()
    _seeded = True


def _seed_default_services() -> None:
    """V-1a — Documents + Intelligence.
    V-1b — populates `overview_widget_ids` for the Vault landing page;
    adds a `notifications` proto-service so its widget appears in the
    Vault Overview.
    V-1c adds CRM.
    V-1d promotes Notifications from proto-service to full Vault
    service (owns `/vault/notifications`, replaces top-level
    /notifications).
    V-1e adds Accounting admin (fifth full Vault service — platform-
    admin surfaces only; the tenant-facing Financials Hub stays in
    the vertical nav). Each later phase calls `register_service()`
    from its own seed path.

    `overview_widget_ids` values correspond to `widget_id` rows seeded
    by `app.services.widgets.widget_registry.WIDGET_DEFINITIONS` with
    `page_contexts=["vault_overview"]`. Source of truth for which
    widget belongs to which service lives here; source of truth for
    widget availability + default layout lives in the widget framework.
    """
    register_service(
        VaultServiceDescriptor(
            service_key="documents",
            display_name="Documents",
            icon="FileText",
            route_prefix="/vault/documents",
            required_permission=None,
            overview_widget_ids=[
                "vault_recent_documents",
                "vault_pending_signatures",
                "vault_unread_inbox",
                "vault_recent_deliveries",
            ],
            sort_order=10,
        )
    )
    # V-1c: CRM becomes the third full Vault service (lift-and-shift
    # from /crm/* to /vault/crm/*). Gated on customers.view —
    # preserves the existing CRM permission semantics that the old
    # top-level nav entry had.
    register_service(
        VaultServiceDescriptor(
            service_key="crm",
            display_name="CRM",
            icon="Building2",
            route_prefix="/vault/crm",
            required_permission="customers.view",
            overview_widget_ids=[
                "vault_crm_recent_activity",
                "at_risk_accounts",
            ],
            sort_order=15,
        )
    )
    register_service(
        VaultServiceDescriptor(
            service_key="intelligence",
            display_name="Intelligence",
            icon="Sparkles",
            route_prefix="/vault/intelligence",
            required_permission=None,
            # V-1b: no Intelligence-owned widgets. A future phase may
            # add one (execution volume, experiment status).
            overview_widget_ids=[],
            sort_order=20,
        )
    )
    # V-1d: Notifications is now a full Vault service. Replaces the
    # former top-level /notifications route (redirected). Owns the
    # `vault_notifications` overview widget that surfaces the same
    # unread feed as the full page.
    register_service(
        VaultServiceDescriptor(
            service_key="notifications",
            display_name="Notifications",
            icon="Bell",
            route_prefix="/vault/notifications",
            required_permission=None,
            overview_widget_ids=["vault_notifications"],
            sort_order=30,
        )
    )
    # V-1e: Accounting — fifth full Vault service. Platform-admin
    # consolidation surface: periods+locks, agent schedules, GL
    # classification review, tax config, statement templates, COA
    # templates. Tenant-facing Financials Hub (invoices/AR/AP/JEs)
    # remains in the vertical nav — NOT part of this service.
    # Gated on `admin` since every sub-tab is platform configuration.
    register_service(
        VaultServiceDescriptor(
            service_key="accounting",
            display_name="Accounting",
            icon="Calculator",
            route_prefix="/vault/accounting",
            required_permission="admin",
            overview_widget_ids=[
                "vault_pending_period_close",
                "vault_gl_classification_review",
                "vault_agent_recent_activity",
            ],
            sort_order=40,
        )
    )
