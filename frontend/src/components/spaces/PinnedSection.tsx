/**
 * PinnedSection — renders the active space's pins at the top of the
 * sidebar, ABOVE the standard vertical navigation.
 *
 * Conditional rendering: returns null when no active space or the
 * active space has no pins. The base nav below continues to work
 * unchanged — spaces ADD emphasis, they don't remove access.
 *
 * Pin behavior:
 *   - Available pin → regular link (Link to href).
 *   - Unavailable pin → grayed out, non-navigable, tooltip hints
 *     at cause, hover reveals a "remove" X button so the user can
 *     clean up stale pins.
 *   - Saved-view pins get a "Layers" icon, nav-item pins get the
 *     icon returned by the backend's static NAV_LABEL_TABLE.
 *
 * Drag-to-reorder: Phase 3 ships with a lightweight
 * HTML5-drag-and-drop handle. No dep added. For teams who want
 * polished DnD, Phase 7 polish can introduce dnd-kit.
 */

import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  BarChart3,
  Bell,
  BookOpen,
  Building2,
  Calculator,
  Calendar,
  Factory,
  FileText,
  FolderOpen,
  Home,
  Kanban,
  Layers,
  LayoutDashboard,
  type LucideIcon,
  MapPin,
  Phone,
  Plus,
  Receipt,
  Scale,
  ShieldCheck,
  ShoppingBag,
  Store,
  TrendingUp,
  Truck,
  Users,
  Wrench,
  X,
  Zap,
} from "lucide-react";

import { useSpaces } from "@/contexts/space-context";
import type { ResolvedPin } from "@/types/spaces";
import { cn } from "@/lib/utils";

// Subset of the sidebar ICON_MAP — includes every icon used by
// `registry.NAV_LABEL_TABLE` plus common lucide names. Unknown
// icons fall back to `Layers`.
const ICON_MAP: Record<string, LucideIcon> = {
  BarChart3,
  Bell,
  BookOpen,
  Building2,
  Calculator,
  Calendar,
  Factory,
  FileText,
  FolderOpen,
  Home,
  Kanban,
  Layers,
  LayoutDashboard,
  Link: Layers, // the "Link" lucide icon isn't a space default
  MapPin,
  Phone,
  Plus,
  Receipt,
  Scale,
  ShieldCheck,
  ShoppingBag,
  Store,
  TrendingUp,
  Truck,
  Users,
  Wrench,
  Zap,
};

function resolveIcon(name: string): LucideIcon {
  return ICON_MAP[name] ?? Layers;
}

// ── Main component ──────────────────────────────────────────────

export function PinnedSection() {
  const { activeSpace, removePin, reorderPins } = useSpaces();
  const location = useLocation();
  const [draggingId, setDraggingId] = useState<string | null>(null);

  if (!activeSpace || activeSpace.pins.length === 0) return null;

  const pins = [...activeSpace.pins].sort(
    (a, b) => a.display_order - b.display_order,
  );

  const handleDragStart = (id: string) => (e: React.DragEvent) => {
    setDraggingId(id);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", id);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  };

  const handleDrop = (targetId: string) => async (e: React.DragEvent) => {
    e.preventDefault();
    const sourceId = e.dataTransfer.getData("text/plain");
    if (!sourceId || sourceId === targetId) {
      setDraggingId(null);
      return;
    }
    const order = pins.map((p) => p.pin_id);
    const src = order.indexOf(sourceId);
    const dst = order.indexOf(targetId);
    if (src === -1 || dst === -1) return;
    order.splice(src, 1);
    order.splice(dst, 0, sourceId);
    setDraggingId(null);
    await reorderPins(activeSpace.space_id, order);
  };

  const isActiveHref = (href: string | null): boolean => {
    if (!href) return false;
    return (
      location.pathname === href ||
      location.pathname.startsWith(href + "/")
    );
  };

  return (
    <div className="pb-3" data-testid="pinned-section">
      <div className="flex items-center justify-between px-2 py-1">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">
          Pinned
        </span>
        <span
          className="text-[10px] uppercase tracking-wider"
          style={{ color: "var(--space-accent, var(--preset-accent))" }}
        >
          {activeSpace.name}
        </span>
      </div>
      <div className="mt-0.5 space-y-0.5">
        {pins.map((pin) => (
          <PinRow
            key={pin.pin_id}
            pin={pin}
            active={isActiveHref(pin.href)}
            dragging={draggingId === pin.pin_id}
            onDragStart={handleDragStart(pin.pin_id)}
            onDragOver={handleDragOver}
            onDrop={handleDrop(pin.pin_id)}
            onRemove={() =>
              void removePin(activeSpace.space_id, pin.pin_id)
            }
          />
        ))}
      </div>
      {/* Subtle divider between pinned + base nav */}
      <div className="mt-1 border-t border-sidebar-border/50" />
    </div>
  );
}

// ── PinRow ──────────────────────────────────────────────────────

interface PinRowProps {
  pin: ResolvedPin;
  active: boolean;
  dragging: boolean;
  onDragStart: (e: React.DragEvent) => void;
  onDragOver: (e: React.DragEvent) => void;
  onDrop: (e: React.DragEvent) => void;
  onRemove: () => void;
}

function PinRow({
  pin,
  active,
  dragging,
  onDragStart,
  onDragOver,
  onDrop,
  onRemove,
}: PinRowProps) {
  const Icon = resolveIcon(pin.icon);
  const [hover, setHover] = useState(false);

  const accentStyle = active
    ? {
        borderLeftColor: "var(--space-accent, var(--preset-accent))",
        backgroundColor:
          "color-mix(in srgb, var(--space-accent, var(--preset-accent)) 8%, transparent)",
      }
    : undefined;

  const containerClass = cn(
    "group flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm",
    "border-l-2 border-transparent transition-colors",
    pin.unavailable && "opacity-50 cursor-not-allowed",
    !pin.unavailable && !active &&
      "text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground",
    active && "font-medium text-sidebar-foreground",
    dragging && "opacity-40",
  );

  const body = (
    <>
      <Icon
        className="size-4 shrink-0"
        style={
          active
            ? { color: "var(--space-accent, var(--preset-accent))" }
            : undefined
        }
      />
      <span className="truncate flex-1">{pin.label}</span>
      {hover && !pin.unavailable && (
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onRemove();
          }}
          className="ml-auto size-4 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
          aria-label={`Unpin ${pin.label}`}
          data-testid={`pin-remove-${pin.pin_id}`}
        >
          <X className="size-3.5" />
        </button>
      )}
    </>
  );

  const shared = {
    draggable: true,
    onDragStart,
    onDragOver,
    onDrop,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    className: containerClass,
    style: accentStyle,
    "data-testid": `pin-row-${pin.pin_id}`,
    "data-pin-id": pin.pin_id,
    "data-unavailable": pin.unavailable ? "true" : "false",
  };

  if (pin.unavailable || !pin.href) {
    return (
      <div
        {...shared}
        title={
          pin.unavailable
            ? "This pin's target is no longer available. Hover and click × to remove it."
            : undefined
        }
      >
        {body}
      </div>
    );
  }

  return (
    <Link to={pin.href} {...shared}>
      {body}
    </Link>
  );
}
