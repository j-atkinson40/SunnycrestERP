/**
 * Admin sidebar navigation for the platform admin portal.
 *
 * Sections: Platform, Product, Operations, Platform Health, Billing, Settings.
 * Uses a dark sidebar with indigo accent and collapsible sections.
 */

import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { usePlatformAuth } from "@/contexts/platform-auth-context";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Building2,
  Network,
  Puzzle,
  TrendingUp,
  ClipboardList,
  Import,
  PhoneCall,
  StickyNote,
  Activity,
  RefreshCw,
  AlertTriangle,
  DollarSign,
  CreditCard,
  Settings,
  Users,
  ChevronDown,
  ChevronRight,
  LogOut,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const sections: NavSection[] = [
  {
    title: "Platform",
    items: [
      { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
      { label: "Tenants", href: "/tenants", icon: Building2 },
      { label: "Network", href: "/network", icon: Network },
    ],
  },
  {
    title: "Product",
    items: [
      { label: "Extension Catalog", href: "/extensions/demand", icon: Puzzle },
      { label: "Demand Signals", href: "/demand-signals", icon: TrendingUp },
      { label: "Onboarding Templates", href: "/onboarding-templates", icon: ClipboardList },
    ],
  },
  {
    title: "Operations",
    items: [
      { label: "White-Glove Imports", href: "/white-glove", icon: Import },
      { label: "Check-in Calls", href: "/check-in-calls", icon: PhoneCall },
      { label: "Support Notes", href: "/support-notes", icon: StickyNote },
    ],
  },
  {
    title: "Platform Health",
    items: [
      { label: "Integration Monitor", href: "/system", icon: Activity },
      { label: "Sync Jobs", href: "/sync-jobs", icon: RefreshCw },
      { label: "Error Log", href: "/error-log", icon: AlertTriangle },
    ],
  },
  {
    title: "Billing",
    items: [
      { label: "Revenue Dashboard", href: "/revenue", icon: DollarSign },
      { label: "Subscriptions", href: "/subscriptions", icon: CreditCard },
    ],
  },
  {
    title: "Settings",
    items: [
      { label: "Platform Settings", href: "/platform-settings", icon: Settings },
      { label: "Admin Users", href: "/users", icon: Users },
    ],
  },
];

export function AdminSidebar() {
  const { user, logout } = usePlatformAuth();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const isActive = (href: string) =>
    location.pathname === href || location.pathname.startsWith(href + "/");

  const toggleSection = (title: string) => {
    setCollapsed((prev) => ({ ...prev, [title]: !prev[title] }));
  };

  return (
    <aside className="flex h-full w-64 flex-col border-r border-slate-700 bg-slate-900">
      {/* Header */}
      <div className="flex h-14 items-center border-b border-slate-700 px-5">
        <Link
          to="/dashboard"
          className="flex items-center gap-2 text-lg font-semibold text-white"
        >
          <span className="inline-flex items-center rounded bg-indigo-600 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">
            Admin
          </span>
          <span>Platform</span>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <div className="space-y-4">
          {sections.map((section) => {
            const isCollapsed = collapsed[section.title] ?? false;
            return (
              <div key={section.title}>
                <button
                  onClick={() => toggleSection(section.title)}
                  className="flex w-full items-center justify-between px-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500 hover:text-slate-400"
                >
                  {section.title}
                  {isCollapsed ? (
                    <ChevronRight className="h-3 w-3" />
                  ) : (
                    <ChevronDown className="h-3 w-3" />
                  )}
                </button>
                {!isCollapsed && (
                  <div className="mt-1 space-y-0.5">
                    {section.items.map((item) => {
                      const Icon = item.icon;
                      return (
                        <Link
                          key={item.href}
                          to={item.href}
                          className={cn(
                            "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors",
                            isActive(item.href)
                              ? "bg-indigo-600/20 text-indigo-300"
                              : "text-slate-400 hover:bg-slate-800 hover:text-white"
                          )}
                        >
                          <Icon className="h-4 w-4 shrink-0" />
                          {item.label}
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </nav>

      {/* Footer */}
      <div className="border-t border-slate-700 p-4">
        <div className="mb-2 truncate text-xs text-slate-400">
          {user?.email}
        </div>
        <button
          onClick={logout}
          className="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-left text-sm text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
        >
          <LogOut className="h-3.5 w-3.5" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
