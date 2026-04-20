/**
 * AccountingAdminLayout — Phase V-1e.
 *
 * Wraps all six Accounting admin sub-tabs with a secondary tab bar.
 * Renders inside the Vault Hub's main content area (which is already
 * itself wrapped in VaultHubLayout one level up the route tree).
 *
 * Tabs:
 *   1. Periods & Locks       → /vault/accounting/periods
 *   2. Agent Schedules       → /vault/accounting/agents
 *   3. GL Classification     → /vault/accounting/classification
 *   4. Tax Config            → /vault/accounting/tax
 *   5. Statement Templates   → /vault/accounting/statements
 *   6. COA Templates         → /vault/accounting/coa
 */

import { NavLink, Outlet } from "react-router-dom";
import { cn } from "@/lib/utils";

const TABS = [
  { to: "periods", label: "Periods & Locks" },
  { to: "agents", label: "Agent Schedules" },
  { to: "classification", label: "GL Classification" },
  { to: "tax", label: "Tax Config" },
  { to: "statements", label: "Statement Templates" },
  { to: "coa", label: "COA Templates" },
];

export default function AccountingAdminLayout() {
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
          {TABS.map((tab) => (
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
