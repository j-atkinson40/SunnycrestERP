/**
 * AccountingAdminLayout — Phase V-1e.
 *
 * Wraps the Accounting admin sub-tabs with a secondary tab bar. Renders inside
 * the Vault Hub's main content area (which is already itself wrapped in
 * VaultHubLayout one level up the route tree).
 *
 * Tabs:
 *   1. Periods & Locks       → /vault/accounting/periods        (admin)
 *   2. Completeness          → /vault/accounting/completeness   (admin + accountant)
 *   3. Agent Schedules       → /vault/accounting/agents         (admin)
 *   4. GL Classification     → /vault/accounting/classification (admin)
 *   5. Tax Config            → /vault/accounting/tax            (admin)
 *   6. Statement Templates   → /vault/accounting/statements     (admin)
 *   7. COA Templates         → /vault/accounting/coa            (admin)
 *
 * ⚠️ THE SUB-TREE IS NO LONGER UNIFORMLY ADMIN-ONLY, AND THE OLD COMMENT HERE
 * JUSTIFIED A GATE THAT WAS NEVER CHOSEN. V-1e wrapped the whole subtree in
 * `adminOnly` (`ba424db6`, April 2026) and said it matched "the gate the backend
 * uses on every endpoint under /api/v1/vault/accounting/*". CR-2's completeness
 * review then mounted inside that wrapper and inherited it — but its router is
 * mounted at `/api/v1/completeness`, NOT under that prefix, and every one of its
 * routes uses `get_current_user` rather than `require_admin`. So the stated
 * reason did not apply to the tab it was keeping out, and the arc's intended
 * reader — the accountant — could not open the surface built for them.
 *
 * Corrected rather than removed: the review belongs to whoever holds accounting
 * RESPONSIBILITY (`admin` or `accountant`), which is a narrower statement than
 * "any authenticated user" and a deliberate one. The other six tabs administer
 * the tenant's accounting configuration and stay admin-only.
 *
 * ⚠️ THE TAB BAR FILTERS BY ROLE, AND THAT IS NOT COSMETIC. Rendering six tabs
 * that bounce the clicker to /unauthorized is the built-and-unreachable failure
 * wearing a navigation costume — worse than hiding them, because it invites the
 * click. What a user can see here is what they can open.
 */

import { NavLink, Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { cn } from "@/lib/utils";

/**
 * Who may reach the Accounting area at all. Exported because `App.tsx` gates the
 * route with it — one list, so the route guard and the tab bar cannot disagree
 * about who is here. Two producers of one fact is this codebase's standing
 * defect; a second literal in the router would be exactly that.
 */
export const ACCOUNTING_ROLES = ["admin", "accountant"] as const;

interface AccountingTab {
  to: string;
  label: string;
  /** False for the tabs an accountant may open. */
  adminOnly: boolean;
}

const TABS: AccountingTab[] = [
  { to: "periods", label: "Periods & Locks", adminOnly: true },
  // CR-2 A-4. Sits beside Periods deliberately: completeness is only meaningful
  // against a window that can be final, and it READS that window through the
  // same projection rather than keeping its own idea of what is closed.
  { to: "completeness", label: "Completeness", adminOnly: false },
  { to: "agents", label: "Agent Schedules", adminOnly: true },
  { to: "classification", label: "GL Classification", adminOnly: true },
  { to: "tax", label: "Tax Config", adminOnly: true },
  { to: "statements", label: "Statement Templates", adminOnly: true },
  { to: "coa", label: "COA Templates", adminOnly: true },
];

/**
 * Where `/vault/accounting` lands, per role.
 *
 * ⚠️ A FIXED REDIRECT TO `periods` WOULD BOUNCE THE ACCOUNTANT STRAIGHT TO
 * /unauthorized — granting access and then landing them on the one page they
 * cannot open. The redirect has to know who is asking.
 */
export function AccountingLanding() {
  const { isAdmin } = useAuth();
  return <Navigate to={isAdmin ? "periods" : "completeness"} replace />;
}

export default function AccountingAdminLayout() {
  const { isAdmin } = useAuth();
  const visible = TABS.filter((tab) => isAdmin || !tab.adminOnly);

  return (
    <div className="flex h-full flex-col">
      <div className="border-b bg-white">
        <div className="flex items-center px-6 pt-4">
          <h1 className="text-xl font-semibold text-gray-900">
            Accounting admin
          </h1>
        </div>
        <nav
          aria-label="Accounting admin tabs"
          className="flex gap-1 overflow-x-auto px-4"
        >
          {visible.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive }) =>
                cn(
                  "whitespace-nowrap border-b-2 px-3 py-3 text-sm font-medium transition-colors",
                  isActive
                    ? "border-blue-600 text-blue-600"
                    : "border-transparent text-gray-600 hover:border-gray-300 hover:text-gray-900",
                )
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="flex-1 overflow-auto bg-gray-50 p-6">
        <Outlet />
      </div>
    </div>
  );
}
