/**
 * Vault Hub layout — Phase V-1a.
 *
 * Wraps all /vault/* routes. Renders a secondary sidebar listing
 * registered Vault services (from `vaultHubRegistry`) plus the
 * Overview entry, and outlets the active child route on the right.
 *
 * Responsive behavior:
 *   - ≥1024px (lg): sidebar expanded (240px).
 *   - <1024px: sidebar collapsed to icons only (default) with an
 *     expanded-on-hover tooltip. A hamburger toggle + drawer
 *     treatment for <768px is planned; V-1a keeps the icon-strip
 *     behavior simple and matches the existing mobile sidebar pattern.
 */

import {
  Link,
  NavLink,
  Outlet,
  useLocation,
} from "react-router-dom";
import {
  Bell,
  Boxes,
  Building2,
  Calculator,
  ChevronRight,
  FileCheck,
  FileText,
  Files,
  FlaskConical,
  LayoutDashboard,
  Megaphone,
  Sparkles,
  Truck,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { vaultHubRegistry } from "@/services/vault-hub-registry";

// Icon map for vault-sidebar entries. Keep small — only icons used
// by services registered in the Vault Hub. Add as V-1c/d/e register
// more services.
const VAULT_ICON_MAP: Record<string, LucideIcon> = {
  Bell,
  Boxes,
  Building2,
  Calculator,
  FileCheck,
  FileText,
  Files,
  FlaskConical,
  LayoutDashboard,
  Megaphone,
  Sparkles,
  Truck,
};

function resolveIcon(name: string): LucideIcon {
  return VAULT_ICON_MAP[name] ?? Boxes;
}

export default function VaultHubLayout() {
  const location = useLocation();
  const services = vaultHubRegistry.getServices();
  const activeService = vaultHubRegistry.findServiceForPath(
    location.pathname,
  );

  return (
    <div className="flex h-[calc(100vh-theme(spacing.14))] min-h-0 gap-4 p-4">
      {/* Secondary sidebar */}
      <aside
        aria-label="Vault sidebar"
        className={cn(
          "flex-shrink-0",
          "w-14 lg:w-60",
          "rounded-lg border bg-card",
          "flex flex-col",
        )}
      >
        <div
          className={cn(
            "flex items-center gap-2 border-b px-3 py-3",
            "lg:px-4",
          )}
        >
          <Boxes className="size-5 text-primary flex-shrink-0" aria-hidden />
          <span className="hidden lg:inline font-semibold">
            Bridgeable Vault
          </span>
        </div>

        <nav className="flex flex-col gap-1 p-2" aria-label="Vault services">
          <NavLink
            to="/vault"
            end
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2 rounded-md px-2 py-2 text-sm",
                "hover:bg-muted transition-colors",
                isActive
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-foreground",
              )
            }
            title="Overview"
          >
            <LayoutDashboard className="size-4 flex-shrink-0" aria-hidden />
            <span className="hidden lg:inline">Overview</span>
          </NavLink>

          {services.map((service) => {
            const Icon = resolveIcon(service.icon);
            const isActive = activeService?.service_key === service.service_key;
            return (
              <NavLink
                key={service.service_key}
                to={service.route_prefix}
                className={cn(
                  "flex items-center gap-2 rounded-md px-2 py-2 text-sm",
                  "hover:bg-muted transition-colors",
                  isActive
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-foreground",
                )}
                title={service.display_name}
              >
                <Icon className="size-4 flex-shrink-0" aria-hidden />
                <span className="hidden lg:inline">
                  {service.display_name}
                </span>
              </NavLink>
            );
          })}
        </nav>

        <div
          className={cn(
            "mt-auto border-t px-3 py-2 text-[10px]",
            "text-muted-foreground hidden lg:block",
          )}
        >
          Platform infrastructure · V-1a
        </div>
      </aside>

      {/* Content area */}
      <main className="flex-1 min-w-0 overflow-auto">
        <VaultBreadcrumbs activeService={activeService ?? null} />
        <Outlet />
      </main>
    </div>
  );
}

// ── Breadcrumbs ──────────────────────────────────────────────────────

function VaultBreadcrumbs({
  activeService,
}: {
  activeService: import("@/services/vault-hub-registry").VaultServiceRegistration | null;
}) {
  return (
    <nav
      aria-label="Vault breadcrumbs"
      className="mb-4 flex items-center gap-1 text-sm text-muted-foreground"
    >
      <Link to="/vault" className="hover:text-foreground transition-colors">
        Vault
      </Link>
      {activeService && (
        <>
          <ChevronRight
            className="size-3 text-muted-foreground/50"
            aria-hidden
          />
          <Link
            to={activeService.route_prefix}
            className={cn(
              "hover:text-foreground transition-colors",
              "text-foreground font-medium",
            )}
          >
            {activeService.display_name}
          </Link>
        </>
      )}
    </nav>
  );
}
