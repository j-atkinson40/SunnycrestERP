import { Link, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  href: string;
  permission?: string;
}

const allNavItems: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", permission: "dashboard.view" },
  { label: "User Management", href: "/admin/users", permission: "users.view" },
  { label: "Role Management", href: "/admin/roles", permission: "roles.view" },
  { label: "Audit Logs", href: "/admin/audit-logs", permission: "audit.view" },
  // Future: { label: "Products", href: "/products", permission: "products.view" },
  // Future: { label: "Inventory", href: "/inventory", permission: "inventory.view" },
];

export function Sidebar() {
  const { company, hasPermission } = useAuth();
  const location = useLocation();

  const navItems = allNavItems.filter(
    (item) => !item.permission || hasPermission(item.permission)
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
              location.pathname === item.href
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
