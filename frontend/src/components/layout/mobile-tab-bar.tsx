import { useCallback, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Award,
  Bell,
  Building2,
  Calendar,
  ClipboardList,
  Factory,
  FileText,
  FolderOpen,
  Kanban,
  LayoutDashboard,
  Link as LinkIcon,
  ListOrdered,
  Map,
  MapPin,
  MoreHorizontal,
  Package,
  Plug,
  Plus,
  Puzzle,
  Receipt,
  Scale,
  ShieldCheck,
  Truck,
  UserCircle,
  Users,
  Wrench,
  X,
  type LucideIcon,
} from "lucide-react";
import { usePresetTheme } from "@/contexts/preset-theme-context";
import { useLayout } from "@/contexts/layout-context";
import { cn } from "@/lib/utils";
import type { NavItem } from "@/services/navigation-service";

// Same icon map as sidebar — shared lookup
const ICON_MAP: Record<string, LucideIcon> = {
  Award,
  Bell,
  Building2,
  Calendar,
  ClipboardList,
  Factory,
  FileText,
  FolderOpen,
  Kanban,
  LayoutDashboard,
  Link: LinkIcon,
  ListOrdered,
  Map,
  MapPin,
  MoreHorizontal,
  Package,
  Plug,
  Plus,
  Puzzle,
  Receipt,
  Scale,
  ShieldCheck,
  Truck,
  UserCircle,
  Users,
  Wrench,
};

function resolveIcon(name: string): LucideIcon | null {
  return ICON_MAP[name] ?? null;
}

export function MobileTabBar() {
  const { navigation, presetAccent } = usePresetTheme();
  const { hideTabBar } = useLayout();
  const location = useLocation();
  const [moreOpen, setMoreOpen] = useState(false);

  const isActive = useCallback(
    (href: string) =>
      href !== "#more" &&
      (location.pathname === href ||
        location.pathname.startsWith(href + "/")),
    [location.pathname],
  );

  const handleMoreToggle = useCallback(() => {
    setMoreOpen((prev) => !prev);
  }, []);

  const handleCloseMore = useCallback(() => {
    setMoreOpen(false);
  }, []);

  if (hideTabBar) return null;

  return (
    <>
      {/* Full-screen "More" overlay */}
      {moreOpen && (
        <div className="fixed inset-0 z-50 flex flex-col bg-surface-base font-sans md:hidden">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-border-subtle px-4 py-3">
            <span className="text-h4 font-medium text-content-strong">All Sections</span>
            <button
              type="button"
              onClick={handleCloseMore}
              className="rounded p-2 text-content-muted hover:bg-accent-subtle hover:text-content-strong focus-ring-accent transition-colors duration-quick ease-settle"
              aria-label="Close all sections"
            >
              <X className="size-5" />
            </button>
          </div>

          {/* All nav items */}
          <div className="flex-1 overflow-y-auto p-4">
            <div className="space-y-5">
              {navigation.sections.map((section) => (
                <div key={section.title}>
                  <div className="mb-1.5 text-micro font-semibold uppercase tracking-wider text-content-subtle">
                    {section.title}
                  </div>
                  <div className="space-y-0.5">
                    {section.items.map((item) => {
                      const Icon = resolveIcon(item.icon);
                      const active = isActive(item.href);
                      return (
                        <Link
                          key={item.href}
                          to={item.href}
                          onClick={handleCloseMore}
                          className={cn(
                            // Mobile touch targets: min-h-11 (44px) per WCAG AA touch-target + Apple HIG.
                            "flex items-center gap-3 min-h-11 rounded px-3 py-2.5 text-body-sm transition-colors duration-quick ease-settle focus-ring-accent",
                            active
                              ? "font-medium"
                              : "text-content-muted hover:bg-accent-subtle hover:text-content-strong",
                          )}
                          style={
                            active
                              ? { color: presetAccent, backgroundColor: `${presetAccent}18` }
                              : undefined
                          }
                        >
                          {Icon && <Icon className="size-5 shrink-0" />}
                          <span>{item.label}</span>
                        </Link>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Bottom tab bar */}
      <nav
        className={cn(
          "fixed bottom-0 left-0 right-0 z-40 border-t border-border-subtle bg-surface-elevated font-sans md:hidden",
          "safe-area-inset-bottom",
        )}
      >
        <div className="flex items-stretch justify-around">
          {navigation.mobileTabs.map((tab) => (
            <MobileTab
              key={tab.href}
              item={tab}
              active={tab.href === "#more" ? moreOpen : isActive(tab.href)}
              presetAccent={presetAccent}
              onClick={
                tab.href === "#more" ? handleMoreToggle : handleCloseMore
              }
            />
          ))}
        </div>
      </nav>
    </>
  );
}

function MobileTab({
  item,
  active,
  presetAccent,
  onClick,
}: {
  item: NavItem;
  active: boolean;
  presetAccent: string;
  onClick?: () => void;
}) {
  const Icon = resolveIcon(item.icon);

  if (item.href === "#more") {
    return (
      <button
        type="button"
        onClick={onClick}
        className={cn(
          "flex flex-1 flex-col items-center gap-0.5 py-2 min-h-11 text-micro transition-colors duration-quick ease-settle focus-ring-accent",
          active ? "font-medium" : "text-content-muted hover:text-content-strong",
        )}
        style={active ? { color: presetAccent } : undefined}
      >
        {Icon && <Icon className="size-5" />}
        <span>{item.label}</span>
      </button>
    );
  }

  return (
    <Link
      to={item.href}
      onClick={onClick}
      className={cn(
        "flex flex-1 flex-col items-center gap-0.5 py-2 min-h-11 text-micro transition-colors duration-quick ease-settle focus-ring-accent",
        active ? "font-medium" : "text-content-muted hover:text-content-strong",
      )}
      style={active ? { color: presetAccent } : undefined}
    >
      {Icon && <Icon className="size-5" />}
      <span>{item.label}</span>
    </Link>
  );
}
