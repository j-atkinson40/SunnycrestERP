/**
 * Layout for the platform admin interface.
 *
 * Uses a dark sidebar with indigo accent to visually distinguish
 * from the tenant-facing interface.
 */

import { Link, Outlet, useLocation } from "react-router-dom";
import { usePlatformAuth } from "@/contexts/platform-auth-context";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  href: string;
  roles?: string[];
}

const navigation: NavItem[] = [
  { label: "Dashboard", href: "/dashboard" },
  { label: "Tenants", href: "/tenants" },
  { label: "Onboard Tenant", href: "/tenants/new", roles: ["super_admin"] },
  { label: "Extension Demand", href: "/extensions/demand", roles: ["super_admin"] },
  { label: "Feature Flags", href: "/feature-flags", roles: ["super_admin"] },
  { label: "System Health", href: "/system" },
  { label: "Impersonation Log", href: "/impersonation", roles: ["super_admin"] },
  { label: "Platform Users", href: "/users", roles: ["super_admin"] },
];

export function PlatformLayout() {
  const { user, logout } = usePlatformAuth();
  const location = useLocation();

  const isActive = (href: string) =>
    location.pathname === href || location.pathname.startsWith(href + "/");

  const visibleNav = navigation.filter(
    (item) => !item.roles || (user && item.roles.includes(user.role))
  );

  return (
    <div className="flex h-screen">
      {/* Dark sidebar */}
      <aside className="flex h-full w-64 flex-col border-r border-slate-700 bg-slate-900">
        <div className="flex h-14 items-center border-b border-slate-700 px-6">
          <Link
            to="/"
            className="flex items-center gap-2 text-lg font-semibold text-white"
          >
            <span className="inline-flex items-center rounded bg-indigo-600 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">
              Admin
            </span>
            <span>Platform</span>
          </Link>
        </div>
        <nav className="flex-1 overflow-y-auto p-4">
          <div className="space-y-1">
            {visibleNav.map((item) => (
              <Link
                key={item.href}
                to={item.href}
                className={cn(
                  "flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive(item.href)
                    ? "bg-indigo-600/20 text-indigo-300"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                )}
              >
                {item.label}
              </Link>
            ))}
          </div>
        </nav>
        <div className="border-t border-slate-700 p-4">
          <div className="mb-2 truncate text-xs text-slate-400">
            {user?.email}
          </div>
          <button
            onClick={logout}
            className="w-full rounded-md px-3 py-1.5 text-left text-sm text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-slate-50">
        <div className="p-6 lg:p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
