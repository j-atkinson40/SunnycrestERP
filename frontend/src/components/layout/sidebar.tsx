import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  href: string;
  permission?: string;
  module?: string;
  adminOnly?: boolean;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

type NavEntry = NavItem | NavGroup;

function isGroup(entry: NavEntry): entry is NavGroup {
  return "items" in entry;
}

const navigation: NavEntry[] = [
  { label: "Dashboard", href: "/dashboard", permission: "dashboard.view" },
  { label: "My Profile", href: "/profile" },
  { label: "Products", href: "/products", permission: "products.view", module: "products" },
  {
    label: "Sales & AR",
    items: [
      { label: "Customers", href: "/customers", permission: "customers.view", module: "sales" },
      { label: "Quotes", href: "/ar/quotes", permission: "ar.view", module: "sales" },
      { label: "Sales Orders", href: "/ar/orders", permission: "ar.view", module: "sales" },
      { label: "Invoices", href: "/ar/invoices", permission: "ar.view", module: "sales" },
      { label: "Payments", href: "/ar/payments", permission: "ar.view", module: "sales" },
      { label: "AR Aging", href: "/ar/aging", permission: "ar.view", module: "sales" },
    ],
  },
  {
    label: "Purchasing & AP",
    items: [
      { label: "Vendors", href: "/vendors", permission: "vendors.view", module: "purchasing" },
      { label: "Purchase Orders", href: "/ap/purchase-orders", permission: "ap.view", module: "purchasing" },
      { label: "Bills", href: "/ap/bills", permission: "ap.view", module: "purchasing" },
      { label: "Payments", href: "/ap/payments", permission: "ap.view", module: "purchasing" },
      { label: "AP Aging", href: "/ap/aging", permission: "ap.view", module: "purchasing" },
    ],
  },
  {
    label: "Delivery & Logistics",
    items: [
      { label: "Dispatch", href: "/delivery/dispatch", permission: "delivery.view", module: "driver_delivery" },
      { label: "Operations", href: "/delivery/operations", permission: "delivery.view", module: "driver_delivery" },
      { label: "History", href: "/delivery/history", permission: "delivery.view", module: "driver_delivery" },
      { label: "Vault Scheduling", href: "/delivery/funeral-scheduling", permission: "delivery.view", module: "driver_delivery" },
      { label: "Carriers", href: "/delivery/carriers", permission: "carriers.view", module: "driver_delivery" },
      { label: "Settings", href: "/delivery/settings", permission: "delivery.view", module: "driver_delivery" },
    ],
  },
  {
    label: "Inventory",
    items: [
      { label: "Overview", href: "/inventory", permission: "inventory.view", module: "inventory" },
      { label: "Production Entry", href: "/inventory/production", permission: "inventory.create", module: "inventory" },
      { label: "Write-offs", href: "/inventory/write-offs", permission: "inventory.view", module: "inventory" },
      { label: "Sage Export", href: "/inventory/sage-exports", permission: "inventory.view", module: "inventory" },
    ],
  },
  {
    label: "Administration",
    items: [
      { label: "User Management", href: "/admin/users", permission: "users.view" },
      { label: "Role Management", href: "/admin/roles", permission: "roles.view" },
      { label: "Company Settings", href: "/admin/settings", permission: "company.view" },
      { label: "Audit Logs", href: "/admin/audit-logs", permission: "audit.view" },
      { label: "Modules", href: "/admin/modules", adminOnly: true },
      { label: "API Keys", href: "/admin/api-keys", adminOnly: true },
      { label: "Accounting", href: "/admin/accounting", adminOnly: true },
    ],
  },
];

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      className={cn(
        "h-4 w-4 shrink-0 transition-transform duration-200",
        open && "rotate-90",
      )}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m9 18 6-6-6-6" />
    </svg>
  );
}

export function Sidebar() {
  const { company, hasPermission, hasModule, isAdmin } = useAuth();
  const location = useLocation();

  const canAccess = (item: NavItem) =>
    (!item.permission || hasPermission(item.permission)) &&
    (!item.module || hasModule(item.module)) &&
    (!item.adminOnly || isAdmin);

  const isActive = (href: string) =>
    location.pathname === href || location.pathname.startsWith(href + "/");

  // Auto-open groups that contain the active page
  const initialOpen = new Set<string>();
  for (const entry of navigation) {
    if (isGroup(entry)) {
      for (const item of entry.items) {
        if (isActive(item.href)) {
          initialOpen.add(entry.label);
          break;
        }
      }
    }
  }

  const [openGroups, setOpenGroups] = useState<Set<string>>(initialOpen);

  const toggleGroup = (label: string) => {
    setOpenGroups((prev) => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  };

  const linkClass = (href: string) =>
    cn(
      "flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors",
      isActive(href)
        ? "bg-sidebar-accent text-sidebar-accent-foreground"
        : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
    );

  return (
    <aside className="flex h-full w-64 flex-col border-r bg-sidebar">
      <div className="flex h-14 items-center border-b px-6">
        <Link to="/" className="text-lg font-semibold text-sidebar-foreground">
          {company?.name || "ERP Platform"}
        </Link>
      </div>
      <nav className="flex-1 overflow-y-auto p-4">
        <div className="space-y-1">
          {navigation.map((entry) => {
            if (!isGroup(entry)) {
              if (!canAccess(entry)) return null;
              return (
                <Link key={entry.href} to={entry.href} className={linkClass(entry.href)}>
                  {entry.label}
                </Link>
              );
            }

            // Filter group items by access
            const visibleItems = entry.items.filter(canAccess);
            if (visibleItems.length === 0) return null;

            const open = openGroups.has(entry.label);

            return (
              <div key={entry.label}>
                <button
                  onClick={() => toggleGroup(entry.label)}
                  className={cn(
                    "flex w-full items-center justify-between rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                  )}
                >
                  {entry.label}
                  <ChevronIcon open={open} />
                </button>
                {open && (
                  <div className="ml-3 space-y-1 border-l border-sidebar-accent pl-2">
                    {visibleItems.map((item) => (
                      <Link key={item.href} to={item.href} className={linkClass(item.href)}>
                        {item.label}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </nav>
    </aside>
  );
}
