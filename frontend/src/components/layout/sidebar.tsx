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

const allNavItems: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", permission: "dashboard.view" },
  { label: "My Profile", href: "/profile" },
  { label: "Products", href: "/products", permission: "products.view", module: "products" },
  { label: "Customers", href: "/customers", permission: "customers.view", module: "sales" },
  { label: "Quotes", href: "/ar/quotes", permission: "ar.view", module: "sales" },
  { label: "Sales Orders", href: "/ar/orders", permission: "ar.view", module: "sales" },
  { label: "Invoices", href: "/ar/invoices", permission: "ar.view", module: "sales" },
  { label: "Payments (AR)", href: "/ar/payments", permission: "ar.view", module: "sales" },
  { label: "AR Aging", href: "/ar/aging", permission: "ar.view", module: "sales" },
  { label: "Vendors", href: "/vendors", permission: "vendors.view", module: "purchasing" },
  { label: "Purchase Orders", href: "/ap/purchase-orders", permission: "ap.view", module: "purchasing" },
  { label: "Bills", href: "/ap/bills", permission: "ap.view", module: "purchasing" },
  { label: "Payments", href: "/ap/payments", permission: "ap.view", module: "purchasing" },
  { label: "AP Aging", href: "/ap/aging", permission: "ap.view", module: "purchasing" },
  { label: "Inventory", href: "/inventory", permission: "inventory.view", module: "inventory" },
  { label: "Production Entry", href: "/inventory/production", permission: "inventory.create", module: "inventory" },
  { label: "Write-offs", href: "/inventory/write-offs", permission: "inventory.view", module: "inventory" },
  { label: "Sage Export", href: "/inventory/sage-exports", permission: "inventory.view", module: "inventory" },
  { label: "User Management", href: "/admin/users", permission: "users.view" },
  { label: "Role Management", href: "/admin/roles", permission: "roles.view" },
  { label: "Company Settings", href: "/admin/settings", permission: "company.view" },
  { label: "Audit Logs", href: "/admin/audit-logs", permission: "audit.view" },
  { label: "Feature Flags", href: "/admin/feature-flags", adminOnly: true },
  { label: "API Keys", href: "/admin/api-keys", adminOnly: true },
  { label: "Accounting", href: "/admin/accounting", adminOnly: true },
  { label: "Sync Monitor", href: "/admin/sync-dashboard", adminOnly: true },
  { label: "Org Hierarchy", href: "/admin/hierarchy", adminOnly: true },
  { label: "Partner Network", href: "/admin/network", adminOnly: true },
  { label: "Platform Fees", href: "/admin/platform-fees", adminOnly: true },
  { label: "Billing", href: "/admin/billing", adminOnly: true },
  { label: "Platform Overview", href: "/admin/super-dashboard", adminOnly: true },
];

export function Sidebar() {
  const { company, hasPermission, hasModule, isAdmin } = useAuth();
  const location = useLocation();

  const navItems = allNavItems.filter(
    (item) =>
      (!item.permission || hasPermission(item.permission)) &&
      (!item.module || hasModule(item.module)) &&
      (!item.adminOnly || isAdmin)
  );

  return (
    <aside className="flex h-full w-64 flex-col border-r bg-sidebar">
      <div className="flex h-14 items-center border-b px-6">
        <Link to="/" className="text-lg font-semibold text-sidebar-foreground">
          {company?.name || "Sunnycrest ERP"}
        </Link>
      </div>
      <nav className="flex-1 space-y-1 p-4">
        {navItems.map((item) => (
          <Link
            key={item.href}
            to={item.href}
            className={cn(
              "flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors",
              location.pathname === item.href ||
              location.pathname.startsWith(item.href + "/")
                ? "bg-sidebar-accent text-sidebar-accent-foreground"
                : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            )}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
