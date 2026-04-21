import { useCallback, useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRightLeft,
  Award,
  BarChart3,
  Bell,
  BookOpen,
  Bot,
  Boxes,
  BrainCircuit,
  Building2,
  Calculator,
  Calendar,
  CalendarDays,
  ChevronDown,
  ChevronRight,
  CircleDollarSign,
  ClipboardCheck,
  ClipboardList,
  DollarSign,
  Factory,
  FileCheck,
  Files,
  FileText,
  FlaskConical,
  FolderOpen,
  Gem,
  GraduationCap,
  Home,
  Kanban,
  Landmark,
  LayoutDashboard,
  Library,
  Link as LinkIcon,
  ListOrdered,
  Lock,
  Map,
  MapPin,
  Megaphone,
  MessageSquare,
  Monitor,
  MoreHorizontal,
  Package,
  Percent,
  Phone,
  PhoneCall,
  PieChart,
  Plug,
  Plus,
  Puzzle,
  Receipt,
  Rocket,
  Scale,
  Settings2,
  Shield,
  ShieldAlert,
  ShieldCheck,
  ShoppingBag,
  Shovel,
  Skull,
  Snowflake,
  Sparkles,
  Store,
  Truck,
  Upload,
  UserCircle,
  Users,
  Vault,
  Wand2,
  Wrench,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { usePresetTheme } from "@/contexts/preset-theme-context";
import { useCommandBar } from "@/core/CommandBarProvider";
import { useLocations } from "@/contexts/location-context";
import { cn } from "@/lib/utils";
import { OnboardingSidebarWidget } from "@/components/onboarding/sidebar-widget";
import { LocationSelector } from "@/components/core/LocationSelector";
import { PinnedSection } from "@/components/spaces/PinnedSection";
import { DotNav } from "@/components/layout/DotNav";
import type { NavItem, NavSection } from "@/services/navigation-service";

// ---- Icon lookup ----
const ICON_MAP: Record<string, LucideIcon> = {
  AlertTriangle,
  ArrowRightLeft,
  Award,
  BarChart3,
  Bell,
  BookOpen,
  Bot,
  Boxes,
  BrainCircuit,
  Building2,
  Calculator,
  Calendar,
  CalendarDays,
  CircleDollarSign,
  ClipboardCheck,
  ClipboardList,
  DollarSign,
  Factory,
  FileCheck,
  Files,
  FileText,
  FlaskConical,
  FolderOpen,
  Gem,
  GraduationCap,
  Home,
  Kanban,
  Landmark,
  LayoutDashboard,
  Library,
  Link: LinkIcon,
  ListOrdered,
  Lock,
  Map,
  MapPin,
  Megaphone,
  MessageSquare,
  Monitor,
  MoreHorizontal,
  Package,
  Percent,
  Phone,
  PhoneCall,
  PieChart,
  Plug,
  Plus,
  Puzzle,
  Receipt,
  Rocket,
  Scale,
  Settings2,
  Shield,
  ShieldAlert,
  ShieldCheck,
  ShoppingBag,
  Shovel,
  Skull,
  Snowflake,
  Sparkles,
  Store,
  Truck,
  Upload,
  UserCircle,
  Users,
  Vault,
  Wand2,
  Wrench,
  Zap,
};

function resolveIcon(name: string): LucideIcon | null {
  return ICON_MAP[name] ?? null;
}

// ---- Collapsed sections persistence ----
const STORAGE_KEY = "sidebar-collapsed";

function loadCollapsed(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return new Set(JSON.parse(raw));
  } catch {
    // ignore
  }
  return new Set();
}

function saveCollapsed(collapsed: Set<string>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...collapsed]));
}

// ---- Sidebar ----
export function Sidebar() {
  const { company } = useAuth();
  const { navigation, presetAccent, presetLabel } = usePresetTheme();
  const { isMultiLocation } = useLocations();
  const location = useLocation();

  // Filter out multi-location-only nav items for single-location companies
  const filteredNavigation = {
    ...navigation,
    sections: navigation.sections.map((section) => ({
      ...section,
      items: section.items.filter(
        (item) => !item.requiresMultiLocation || isMultiLocation
      ),
    })),
  };

  // Collapsed sections
  const [collapsed, setCollapsed] = useState<Set<string>>(() => {
    const saved = loadCollapsed();
    // Also collapse sections that default to collapsed
    for (const section of navigation.sections) {
      if (section.defaultCollapsed && !saved.has(section.title)) {
        saved.add(section.title);
      }
    }
    return saved;
  });

  const toggleSection = useCallback((title: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(title)) next.delete(title);
      else next.add(title);
      saveCollapsed(next);
      return next;
    });
  }, []);

  // Active route detection
  const isActive = useCallback(
    (href: string) =>
      location.pathname === href ||
      location.pathname.startsWith(href + "/"),
    [location.pathname],
  );

  // Auto-expand section containing active route
  useEffect(() => {
    for (const section of navigation.sections) {
      if (section.collapsible) {
        const hasActive = section.items.some(
          (item) => isActive(item.href) || item.children?.some((c) => isActive(c.href)),
        );
        if (hasActive && collapsed.has(section.title)) {
          setCollapsed((prev) => {
            const next = new Set(prev);
            next.delete(section.title);
            saveCollapsed(next);
            return next;
          });
        }
      }
    }
    // Run only on location change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  const { open: openCommandBar } = useCommandBar();

  return (
    <aside className="hidden md:flex h-full w-64 flex-col border-r border-border-subtle bg-surface-sunken font-plex-sans">
      {/* Company header */}
      <div className="flex h-14 shrink-0 items-center border-b border-border-subtle px-5">
        <Link
          to="/"
          className="truncate text-h4 font-medium text-content-strong focus-ring-brass rounded-sm"
        >
          {company?.name || (import.meta.env.VITE_APP_NAME || "Bridgeable")}
        </Link>
      </div>

      {/* Location selector — only renders for multi-location companies */}
      <div className="shrink-0 px-3 pt-2">
        <LocationSelector />
      </div>

      {/* Universal command bar trigger */}
      <div className="shrink-0 border-b border-border-subtle px-4 py-3">
        <button
          type="button"
          onClick={openCommandBar}
          className={cn(
            "flex w-full items-center gap-2 rounded border border-border-base bg-surface-raised py-1.5 pl-3 pr-2 text-body-sm",
            "text-content-muted hover:border-border-strong hover:text-content-base",
            "transition-colors duration-quick ease-settle cursor-pointer focus-ring-brass",
          )}
        >
          <Sparkles className="size-4 shrink-0 text-content-subtle" />
          <span className="flex-1 text-left truncate">Search or ask...</span>
          <kbd className="hidden sm:inline-flex items-center gap-0.5 rounded-sm border border-border-subtle bg-surface-base px-1.5 py-0.5 text-micro font-medium font-plex-mono text-content-subtle">
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Navigation sections */}
      <nav className="flex-1 overflow-y-auto px-3 py-3">
        {/* Phase 3 — Pinned section renders ABOVE the base nav when
            an active space has pins. Base nav stays visible below —
            spaces add emphasis, don't remove access. */}
        <PinnedSection />
        <div className="space-y-4">
          {filteredNavigation.sections.map((section, idx) => (
            <SidebarSection
              key={section.title || `section-${idx}`}
              section={section}
              collapsed={collapsed.has(section.title)}
              onToggle={() => toggleSection(section.title)}
              isActive={isActive}
              presetAccent={presetAccent}
            />
          ))}
        </div>
      </nav>

      {/* Onboarding widget */}
      <OnboardingSidebarWidget />

      {/* Workflow Arc Phase 8a — DotNav replaces the top-of-screen
          SpaceSwitcher. Horizontal dots at the bottom of the sidebar
          rail with a plus button at the end. Settings system space
          (when admin) appears leftmost. */}
      <DotNav />

      {/* Preset label */}
      <div className="shrink-0 border-t border-border-subtle px-5 py-2.5">
        <span className="text-micro font-medium uppercase tracking-wider text-content-subtle">
          {presetLabel}
        </span>
      </div>
    </aside>
  );
}

// ---- Section component ----
function SidebarSection({
  section,
  collapsed,
  onToggle,
  isActive,
  presetAccent,
}: {
  section: NavSection;
  collapsed: boolean;
  onToggle: () => void;
  isActive: (href: string) => boolean;
  presetAccent: string;
}) {
  if (section.items.length === 0) return null;

  const isCollapsible = section.collapsible ?? false;
  const isOpen = !collapsed;

  // Check if any item has settingsGroup — if so, render grouped layout
  const hasGroups = section.items.some((i) => i.settingsGroup);

  return (
    <div>
      {/* Section header — hidden for unnamed sections */}
      {section.title ? (
        isCollapsible ? (
          <button
            type="button"
            onClick={onToggle}
            className={cn(
              "flex w-full items-center justify-between rounded-sm px-2 py-1",
              "text-micro font-semibold uppercase tracking-wider",
              "text-content-subtle hover:text-content-muted transition-colors duration-quick ease-settle focus-ring-brass",
            )}
          >
            {section.title}
            <ChevronRight
              className={cn(
                "size-3.5 transition-transform duration-quick ease-settle",
                isOpen && "rotate-90",
              )}
            />
          </button>
        ) : (
          <div className="px-2 py-1 text-micro font-semibold uppercase tracking-wider text-content-subtle">
            {section.title}
          </div>
        )
      ) : null}

      {/* Items */}
      {isOpen && (
        hasGroups ? (
          <SettingsGroupedItems items={section.items} isActive={isActive} presetAccent={presetAccent} />
        ) : (
          <div className="mt-0.5 space-y-0.5">
            {section.items.map((item) => (
              <SidebarItemWithDividers
                key={item.href}
                item={item}
                isActive={isActive}
                presetAccent={presetAccent}
              />
            ))}
          </div>
        )
      )}
    </div>
  );
}

// ---- Settings grouped items ----
function SettingsGroupedItems({
  items,
  isActive,
  presetAccent,
}: {
  items: NavItem[];
  isActive: (href: string) => boolean;
  presetAccent: string;
}) {
  // Group items by settingsGroup
  const groups: { label: string; items: NavItem[] }[] = [];
  let currentGroup: string | undefined;

  for (const item of items) {
    const group = item.settingsGroup || "Other";
    if (group !== currentGroup) {
      groups.push({ label: group, items: [] });
      currentGroup = group;
    }
    groups[groups.length - 1].items.push(item);
  }

  return (
    <div className="mt-1 space-y-3">
      {groups.map((group) => (
        <div key={group.label}>
          <div className="px-2 py-0.5 text-micro font-semibold uppercase tracking-wider text-content-subtle/80">
            {group.label}
          </div>
          <div className="mt-0.5 space-y-0.5">
            {group.items.map((item) => (
              <SidebarItem
                key={item.href}
                item={item}
                active={isActive(item.href)}
                presetAccent={presetAccent}
                isActive={isActive}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---- Item with divider support ----
function SidebarItemWithDividers({
  item,
  isActive,
  presetAccent,
}: {
  item: NavItem;
  isActive: (href: string) => boolean;
  presetAccent: string;
}) {
  return (
    <>
      {item.isDividerBefore && (
        <div className="my-1.5 border-t border-border-subtle" />
      )}
      <SidebarItem
        item={item}
        active={isActive(item.href)}
        presetAccent={presetAccent}
        isActive={isActive}
      />
      {item.isDividerAfter && (
        <div className="my-1.5 border-t border-border-subtle" />
      )}
    </>
  );
}

// ---- Item component ----
function SidebarItem({
  item,
  active,
  presetAccent,
  isActive,
}: {
  item: NavItem;
  active: boolean;
  presetAccent: string;
  isActive?: (href: string) => boolean;
}) {
  const Icon = resolveIcon(item.icon);
  const [expanded, setExpanded] = useState(false);
  const hasChildren = item.children && item.children.length > 0;

  // Auto-expand if any child is active
  const childActive = hasChildren && isActive
    ? item.children!.some((c) => isActive(c.href))
    : false;

  useEffect(() => {
    if (childActive) setExpanded(true);
  }, [childActive]);

  // Use inline style for the accent color so it adapts to preset
  // Note: Aesthetic Arc Session 2 — opacity bumped from 10 to 18 (hex)
  // to give the preset accent enough presence against the new
  // bg-surface-sunken sidebar background. The sunken tone is visually
  // quieter than the old bg-sidebar, so active-state fill needs a
  // small lift to stay legible without reading as "too bright."
  const activeStyle = (active && !hasChildren)
    ? {
        borderLeftColor: presetAccent,
        backgroundColor: `${presetAccent}18`,
      }
    : undefined;

  if (hasChildren) {
    const parentActive = active || childActive;
    return (
      <div>
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className={cn(
            "flex w-full items-center gap-2.5 rounded px-2.5 py-1.5 text-body-sm transition-colors duration-quick ease-settle focus-ring-brass",
            "border-l-2 border-transparent",
            parentActive
              ? "font-medium text-content-strong"
              : "text-content-muted hover:bg-brass-subtle hover:text-content-strong",
          )}
          style={parentActive ? { borderLeftColor: presetAccent, backgroundColor: `${presetAccent}12` } : undefined}
        >
          {Icon && (
            <Icon
              className="size-4 shrink-0"
              style={parentActive ? { color: presetAccent } : undefined}
            />
          )}
          <span className="truncate flex-1 text-left">{item.label}</span>
          <ChevronDown
            className={cn(
              "size-3.5 shrink-0 transition-transform duration-quick ease-settle text-content-subtle",
              !expanded && "-rotate-90",
            )}
          />
        </button>
        {expanded && (
          <div className="ml-4 mt-0.5 space-y-0.5 border-l border-border-subtle pl-2">
            {item.children!.map((child) => (
              <SidebarItem
                key={child.href}
                item={child}
                active={isActive ? isActive(child.href) : false}
                presetAccent={presetAccent}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <Link
      to={item.href}
      className={cn(
        "flex items-center gap-2.5 rounded px-2.5 py-1.5 text-body-sm transition-colors duration-quick ease-settle focus-ring-brass",
        "border-l-2 border-transparent",
        active
          ? "font-medium text-content-strong"
          : "text-content-muted hover:bg-brass-subtle hover:text-content-strong",
      )}
      style={activeStyle}
    >
      {Icon && (
        <Icon
          className="size-4 shrink-0"
          style={active ? { color: presetAccent } : undefined}
        />
      )}
      <span className="truncate">{item.label}</span>
      {item.badge != null && (
        <span
          className={cn(
            "ml-auto inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-micro font-medium font-plex-mono",
            "bg-brass-muted text-content-on-brass",
          )}
        >
          {item.badge}
        </span>
      )}
    </Link>
  );
}
