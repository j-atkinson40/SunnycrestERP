/**
 * Vault Hub service + widget registry — Phase V-1a frontend mirror,
 * extended by V-1b to track widget component registrations.
 *
 * Cross-cutting platform services that appear in the Vault Hub
 * secondary sidebar. Each service owns a route_prefix; child routes
 * for the service are registered in `App.tsx` under that prefix.
 *
 * Widget registration (V-1b): each registered Vault service can own
 * one or more overview widgets (Recent Documents, Pending Signatures,
 * etc.). Widgets register their React component here; the Vault
 * Overview's WidgetGrid resolves widget_id → component via this map.
 *
 * The backend registry (`backend/app/services/vault/hub_registry.py`)
 * is the source of truth for **which widgets belong to which service**
 * and the list_services response. The frontend registry tracks the
 * React components themselves (since those can't live on the backend).
 * Both are populated in lockstep at code level.
 *
 * Registration is module-level — importing this file registers the
 * default services once; importing `components/widgets/vault/index.ts`
 * registers the widget components once.
 */

import type { ComponentType } from "react";

export interface VaultServiceRegistration {
  service_key: string;
  display_name: string;
  icon: string; // lucide-react name present in sidebar.tsx ICON_MAP
  route_prefix: string;
  overview_widget_ids?: string[];
  sort_order?: number;
}

/**
 * Widget component registration. The `widget_id` must match the
 * `widget_id` used in `backend/app/services/widgets/widget_registry.py`
 * WIDGET_DEFINITIONS with `page_contexts: ["vault_overview"]`.
 */
export interface VaultWidgetRegistration {
  widget_id: string;
  service_key: string;
  // The component expects the same internal-prop shape ops-board widgets
  // consume (_editMode, _size, _dragHandleProps, _onRemove, etc.) — it
  // passes them through to WidgetWrapper. Typing deliberately loose
  // here; WidgetGrid's WidgetComponentMap has a tighter signature.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  component: ComponentType<any>;
}

class VaultHubRegistry {
  private services = new Map<string, VaultServiceRegistration>();

  register(reg: VaultServiceRegistration): void {
    // Replacement is intentional — extensions and test code can
    // override core contributors by registering with the same key.
    this.services.set(reg.service_key, reg);
  }

  getServices(): VaultServiceRegistration[] {
    return Array.from(this.services.values()).sort((a, b) => {
      const orderA = a.sort_order ?? 100;
      const orderB = b.sort_order ?? 100;
      if (orderA !== orderB) return orderA - orderB;
      return a.service_key.localeCompare(b.service_key);
    });
  }

  getService(serviceKey: string): VaultServiceRegistration | undefined {
    return this.services.get(serviceKey);
  }

  /**
   * Find the service whose route_prefix is a prefix of `path`.
   * Used by the sidebar to highlight the active service on
   * deep-linked sub-pages (e.g. /vault/documents/templates/abc-123
   * → Documents active).
   */
  findServiceForPath(path: string): VaultServiceRegistration | undefined {
    // Longest-prefix match so future services with nested prefixes
    // resolve correctly.
    return this.getServices()
      .filter((s) => path === s.route_prefix || path.startsWith(s.route_prefix + "/"))
      .sort((a, b) => b.route_prefix.length - a.route_prefix.length)[0];
  }

  // ── Widget registrations (V-1b) ───────────────────────────────────

  private widgets = new Map<string, VaultWidgetRegistration>();

  registerWidget(reg: VaultWidgetRegistration): void {
    // Replacement intentional — same-key registrations override. Lets
    // extensions + tests swap widget implementations.
    this.widgets.set(reg.widget_id, reg);
  }

  getWidget(widgetId: string): VaultWidgetRegistration | undefined {
    return this.widgets.get(widgetId);
  }

  getAllWidgets(): VaultWidgetRegistration[] {
    return Array.from(this.widgets.values());
  }

  /**
   * Build a `widget_id → Component` map for `WidgetGrid`'s componentMap
   * prop. Empty for tests / SSR before widget files are imported.
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  getComponentMap(): Record<string, ComponentType<any>> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const map: Record<string, ComponentType<any>> = {};
    for (const [key, reg] of this.widgets) {
      map[key] = reg.component;
    }
    return map;
  }

  /** Test-only — clear the registry. */
  reset(): void {
    this.services.clear();
    this.widgets.clear();
  }
}

export const vaultHubRegistry = new VaultHubRegistry();

// ── V-1a default services ────────────────────────────────────────────
// V-1c adds "crm". V-1d adds "notifications". V-1e adds "accounting".

vaultHubRegistry.register({
  service_key: "documents",
  display_name: "Documents",
  icon: "FileText",
  route_prefix: "/vault/documents",
  sort_order: 10,
});

// V-1c: CRM becomes the third full Vault service.
// Backend gates on `customers.view`; frontend mirrors that gate via
// the /services endpoint filtering, so users without the permission
// see no CRM entry in the sidebar.
vaultHubRegistry.register({
  service_key: "crm",
  display_name: "CRM",
  icon: "Building2",
  route_prefix: "/vault/crm",
  sort_order: 15,
});

vaultHubRegistry.register({
  service_key: "intelligence",
  display_name: "Intelligence",
  icon: "Sparkles",
  route_prefix: "/vault/intelligence",
  sort_order: 20,
});

// V-1d: Notifications promoted from proto-service to full Vault
// service. Owns /vault/notifications; the old top-level /notifications
// path 301-redirects to here.
vaultHubRegistry.register({
  service_key: "notifications",
  display_name: "Notifications",
  icon: "Bell",
  route_prefix: "/vault/notifications",
  sort_order: 30,
});

// V-1e: Accounting — fifth full Vault service (platform admin
// consolidation). Gated on `admin` in the backend hub_registry;
// frontend mirrors that via the /services endpoint filter, so
// non-admin users don't see the sidebar entry.
vaultHubRegistry.register({
  service_key: "accounting",
  display_name: "Accounting",
  icon: "Calculator",
  route_prefix: "/vault/accounting",
  sort_order: 40,
});
