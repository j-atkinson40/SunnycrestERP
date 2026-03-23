import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  AlertTriangle,
  Award,
  Bell,
  BookOpen,
  BrainCircuit,
  Building2,
  Calculator,
  Calendar,
  CalendarDays,
  ChevronDown,
  ChevronRight,
  ClipboardCheck,
  ClipboardList,
  Factory,
  FileText,
  FlaskConical,
  FolderOpen,
  Gem,
  Kanban,
  LayoutDashboard,
  Link as LinkIcon,
  ListOrdered,
  Lock,
  Map,
  MapPin,
  Megaphone,
  MessageSquare,
  MoreHorizontal,
  Package,
  Plug,
  Plus,
  Puzzle,
  Receipt,
  Scale,
  ShieldAlert,
  ShieldCheck,
  Snowflake,
  Sparkles,
  Truck,
  UserCircle,
  Users,
  Wrench,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { usePresetTheme } from "@/contexts/preset-theme-context";
import { cn } from "@/lib/utils";
import { OnboardingSidebarWidget } from "@/components/onboarding/sidebar-widget";
import type { NavItem, NavSection } from "@/services/navigation-service";

// ---- Icon lookup ----
const ICON_MAP: Record<string, LucideIcon> = {
  AlertTriangle,
  Award,
  Bell,
  BookOpen,
  BrainCircuit,
  Building2,
  Calculator,
  Calendar,
  CalendarDays,
  ClipboardCheck,
  ClipboardList,
  Factory,
  FileText,
  FlaskConical,
  FolderOpen,
  Gem,
  Kanban,
  LayoutDashboard,
  Link: LinkIcon,
  ListOrdered,
  Lock,
  Map,
  MapPin,
  Megaphone,
  MessageSquare,
  MoreHorizontal,
  Package,
  Plug,
  Plus,
  Puzzle,
  Receipt,
  Scale,
  ShieldAlert,
  ShieldCheck,
  Snowflake,
  Sparkles,
  Truck,
  UserCircle,
  Users,
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
  const location = useLocation();

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
        const hasActive = section.items.some((item) => isActive(item.href));
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

  // AI command bar state
  const [commandFocused, setCommandFocused] = useState(false);
  const [commandValue, setCommandValue] = useState("");
  const commandRef = useRef<HTMLInputElement>(null);

  const showQuickPrompts = commandFocused && !commandValue;

  return (
    <aside className="hidden md:flex h-full w-64 flex-col border-r bg-sidebar">
      {/* Company header */}
      <div className="flex h-14 shrink-0 items-center border-b px-5">
        <Link
          to="/"
          className="truncate text-lg font-semibold text-sidebar-foreground"
        >
          {company?.name || "ERP Platform"}
        </Link>
      </div>

      {/* AI command bar */}
      <div className="shrink-0 border-b px-4 py-3">
        <div className="relative">
          <Sparkles
            className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          />
          <input
            ref={commandRef}
            type="text"
            value={commandValue}
            onChange={(e) => setCommandValue(e.target.value)}
            onFocus={() => setCommandFocused(true)}
            onBlur={() => setTimeout(() => setCommandFocused(false), 150)}
            placeholder={navigation.commandBarPlaceholder}
            className={cn(
              "w-full rounded-md border bg-background py-1.5 pl-9 pr-3 text-sm",
              "placeholder:text-muted-foreground/60",
              "focus:outline-none focus:ring-1 focus:ring-ring",
            )}
          />
        </div>
        {/* Quick prompts */}
        {showQuickPrompts && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {navigation.quickPrompts.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault();
                  setCommandValue(prompt);
                  commandRef.current?.focus();
                }}
                className={cn(
                  "rounded-full border px-2.5 py-0.5 text-xs",
                  "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                  "transition-colors",
                )}
              >
                {prompt}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Navigation sections */}
      <nav className="flex-1 overflow-y-auto px-3 py-3">
        <div className="space-y-4">
          {navigation.sections.map((section) => (
            <SidebarSection
              key={section.title}
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

      {/* Preset label */}
      <div className="shrink-0 border-t px-5 py-2.5">
        <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/50">
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

  return (
    <div>
      {/* Section header */}
      {isCollapsible ? (
        <button
          type="button"
          onClick={onToggle}
          className={cn(
            "flex w-full items-center justify-between rounded-md px-2 py-1",
            "text-[11px] font-semibold uppercase tracking-wider",
            "text-muted-foreground/60 hover:text-muted-foreground transition-colors",
          )}
        >
          {section.title}
          <ChevronRight
            className={cn(
              "size-3.5 transition-transform duration-200",
              isOpen && "rotate-90",
            )}
          />
        </button>
      ) : (
        <div className="px-2 py-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">
          {section.title}
        </div>
      )}

      {/* Items */}
      {isOpen && (
        <div className="mt-0.5 space-y-0.5">
          {section.items.map((item) => (
            <SidebarItem
              key={item.href}
              item={item}
              active={isActive(item.href)}
              presetAccent={presetAccent}
              isActive={isActive}
            />
          ))}
        </div>
      )}
    </div>
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
  const activeStyle = (active && !hasChildren)
    ? {
        borderLeftColor: presetAccent,
        backgroundColor: `${presetAccent}10`,
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
            "flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors",
            "border-l-2 border-transparent",
            parentActive
              ? "font-medium text-sidebar-foreground"
              : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground",
          )}
          style={parentActive ? { borderLeftColor: presetAccent, backgroundColor: `${presetAccent}08` } : undefined}
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
              "size-3.5 shrink-0 transition-transform duration-200 text-muted-foreground/50",
              !expanded && "-rotate-90",
            )}
          />
        </button>
        {expanded && (
          <div className="ml-4 mt-0.5 space-y-0.5 border-l border-sidebar-border pl-2">
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
        "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors",
        "border-l-2 border-transparent",
        active
          ? "font-medium text-sidebar-foreground"
          : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground",
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
            "ml-auto inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[10px] font-medium",
            "bg-muted text-muted-foreground",
          )}
        >
          {item.badge}
        </span>
      )}
    </Link>
  );
}
