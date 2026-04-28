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
  CheckSquare,
  Factory,
  FileCheck,
  FileText,
  FolderOpen,
  Home,
  Kanban,
  Layers,
  LayoutDashboard,
  ListChecks,
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
import { useAffinityVisit } from "@/hooks/useAffinityVisit";
import { useFocus } from "@/contexts/focus-context";
import { getWidgetRenderer } from "@/components/focus/canvas/widget-renderers";
import type { VariantId, WidgetDefinition } from "@/components/widgets/types";
import WidgetPicker from "@/components/widgets/WidgetPicker";
import apiClient from "@/lib/api-client";
import type { ResolvedPin } from "@/types/spaces";
import { cn } from "@/lib/utils";

// ── Widget pin → Focus summon mapping (Widget Library Phase W-2) ──
//
// When a user clicks a widget pin in the sidebar (Glance variant),
// the click summons the matching Focus where decisions happen
// (Section 12.6a Widget Interactivity Discipline: state changes
// widget-appropriate, decisions belong in Focus).
//
// This map is intentionally a flat lookup keyed on widget_id namespace
// prefix. Adding a new widget that should summon a Focus = one entry.
// The dot-namespace convention (`scheduling.ancillary-pool`,
// `crm.recent-activity`, etc.) gives us a natural grouping.
//
// Future iteration: extending the focus-registry with a
// `summonsForWidget` field would let widgets declare their summon
// target from the registration site rather than this lookup. Phase
// W-2 ships the lookup as the simplest working primitive; the
// generalization is a natural-touch refactor when a second widget
// declares spaces_pin support.
const WIDGET_FOCUS_SUMMON: Record<string, string> = {
  "scheduling.ancillary-pool": "funeral-scheduling",
};

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
  CheckSquare,
  Factory,
  FileCheck,
  FileText,
  FolderOpen,
  Home,
  Kanban,
  Layers,
  LayoutDashboard,
  Link: Layers, // the "Link" lucide icon isn't a space default
  ListChecks,
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
  const { activeSpace, addPin, removePin, reorderPins } = useSpaces();
  const { recordVisit } = useAffinityVisit();
  const location = useLocation();
  const [draggingId, setDraggingId] = useState<string | null>(null);
  // Widget Library Phase W-2 — picker state. The + Pin widget entry
  // point loads the surface-scoped widget catalog on first open and
  // surfaces them in the WidgetPicker (`destination="sidebar"`).
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerWidgets, setPickerWidgets] = useState<WidgetDefinition[] | null>(null);
  const [pickerLoading, setPickerLoading] = useState(false);

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

  // Widget Library Phase W-2 — open the WidgetPicker scoped to
  // sidebar. Lazy-loads the catalog on first open + caches for the
  // session; the picker filters out widgets already pinned on the
  // active space via `currentWidgetIds`.
  const handleOpenWidgetPicker = async () => {
    setPickerOpen(true);
    if (pickerWidgets === null && !pickerLoading) {
      setPickerLoading(true);
      try {
        const res = await apiClient.get<WidgetDefinition[]>(
          "/widgets/available-for-surface",
          { params: { surface: "spaces_pin" } },
        );
        setPickerWidgets(res.data);
      } catch (err) {
        console.error("Failed to load sidebar widget catalog:", err);
        setPickerWidgets([]);
      } finally {
        setPickerLoading(false);
      }
    }
  };

  const handlePinWidget = async (widgetId: string) => {
    if (!activeSpace) return;
    try {
      await addPin(activeSpace.space_id, {
        pin_type: "widget",
        target_id: widgetId,
        // variant_id omitted — backend defaults to "glance" per
        // §12.2 sidebar compatibility matrix.
      });
      // Close the picker after a successful pin so the user sees
      // the new sidebar entry without dismissing the panel.
      setPickerOpen(false);
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      console.error(
        "Failed to pin widget:",
        e?.response?.data?.detail ?? err,
      );
    }
  };

  // Currently-pinned widget ids — passed to the picker so already-
  // pinned widgets are filtered out of the catalog. Only widget pins
  // count (the picker's `currentWidgetIds` is per-space, not
  // cross-space).
  const pinnedWidgetIds = activeSpace.pins
    .filter((p) => p.pin_type === "widget")
    .map((p) => p.widget_id ?? p.target_id);

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
        {pins.map((pin) => {
          // Widget Library Phase W-2 — widget pins render via the
          // canvas widget framework's getWidgetRenderer (Glance
          // variant by sidebar contract). All other pin types use
          // the existing PinRow icon-row chrome.
          if (pin.pin_type === "widget") {
            return (
              <WidgetPinRow
                key={pin.pin_id}
                pin={pin}
                dragging={draggingId === pin.pin_id}
                onDragStart={handleDragStart(pin.pin_id)}
                onDragOver={handleDragOver}
                onDrop={handleDrop(pin.pin_id)}
                onRemove={() =>
                  void removePin(activeSpace.space_id, pin.pin_id)
                }
              />
            );
          }
          return (
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
              onNavigate={() => {
                // Phase 8e.1 — record affinity when user clicks a pin.
                // Fire-and-forget, no await. Widget pins are rendered
                // by WidgetPinRow above (separate branch); the affinity
                // target_type whitelist intentionally excludes
                // "widget" (widget summon is a Focus open, not a
                // navigate; scope-expansion would need separate audit
                // per SPACES_ARCHITECTURE.md §9.4 purpose-limitation).
                const affinityTargetId =
                  pin.pin_type === "saved_view"
                    ? pin.saved_view_id ?? pin.target_id
                    : pin.target_id;
                if (affinityTargetId) {
                  recordVisit({
                    targetType: pin.pin_type as
                      | "nav_item"
                      | "saved_view"
                      | "triage_queue",
                    targetId: affinityTargetId,
                  });
                }
              }}
            />
          );
        })}
      </div>
      {/* Widget Library Phase W-2 — + Pin widget affordance. Quiet
          entry point at the bottom of the pinned list; opens the
          WidgetPicker scoped to sidebar destination. Hidden while the
          picker is open so the click target doesn't compete with the
          picker's own close affordance. */}
      {!pickerOpen && (
        <button
          type="button"
          onClick={() => void handleOpenWidgetPicker()}
          className={cn(
            "mt-1 flex w-full items-center gap-2 rounded-md px-2.5 py-1.5",
            "text-caption text-muted-foreground/70",
            "hover:bg-sidebar-accent/40 hover:text-sidebar-foreground",
            "transition-colors",
            "focus-ring-accent outline-none",
          )}
          aria-label="Pin a widget to this space"
          data-testid="pinned-section-add-widget"
        >
          <Plus className="size-3.5 shrink-0" />
          <span>Pin widget</span>
        </button>
      )}
      {/* Subtle divider between pinned + base nav */}
      <div className="mt-1 border-t border-sidebar-border/50" />
      {pickerOpen && (
        <WidgetPicker
          available={pickerWidgets ?? []}
          currentWidgetIds={pinnedWidgetIds}
          onAdd={(widgetId) => void handlePinWidget(widgetId)}
          onClose={() => setPickerOpen(false)}
          destination="sidebar"
        />
      )}
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
  /** Phase 8e.1 — fires when the pin row is activated (Link click).
   *  Records topical affinity; fire-and-forget. */
  onNavigate: () => void;
}

function PinRow({
  pin,
  active,
  dragging,
  onDragStart,
  onDragOver,
  onDrop,
  onRemove,
  onNavigate,
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

  // Phase 3 follow-up 1 — pending-item badge for triage_queue pins.
  // Only renders when the queue is available AND has pending items.
  // Hidden on hover so the remove X has room without layout shift.
  const showQueueBadge =
    pin.pin_type === "triage_queue" &&
    !pin.unavailable &&
    typeof pin.queue_item_count === "number" &&
    pin.queue_item_count > 0;

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
      {showQueueBadge && !hover && (
        <span
          className="ml-auto inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[10px] font-semibold tabular-nums"
          style={{
            backgroundColor:
              "color-mix(in srgb, var(--space-accent, var(--preset-accent)) 18%, transparent)",
            color: "var(--space-accent, var(--preset-accent))",
          }}
          aria-label={`${pin.queue_item_count} pending items`}
          data-testid={`pin-queue-count-${pin.pin_id}`}
        >
          {pin.queue_item_count! > 99 ? "99+" : pin.queue_item_count}
        </span>
      )}
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
    <Link to={pin.href} onClick={onNavigate} {...shared}>
      {body}
    </Link>
  );
}


// ── WidgetPinRow ─────────────────────────────────────────────────
//
// Widget Library Phase W-2 — render a widget pin's Glance variant in
// the sidebar. Click summons the matching Focus per Section 12.6a
// (decisions belong in Focus; Glance is the summon affordance).
// Drag-to-reorder is shared with non-widget pins via the same
// HTML5 drag handlers.
//
// When the widget is unavailable (catalog removed, user lost access),
// fall back to a graceful icon row matching the rest of the
// pinned-section visual vocabulary so the user can identify + unpin.

interface WidgetPinRowProps {
  pin: ResolvedPin;
  dragging: boolean;
  onDragStart: (e: React.DragEvent) => void;
  onDragOver: (e: React.DragEvent) => void;
  onDrop: (e: React.DragEvent) => void;
  onRemove: () => void;
}


function WidgetPinRow({
  pin,
  dragging,
  onDragStart,
  onDragOver,
  onDrop,
  onRemove,
}: WidgetPinRowProps) {
  const focus = useFocus();
  const [hover, setHover] = useState(false);

  // Unavailable widget — graceful fallback to icon row pattern so the
  // user can still see + unpin. Mirrors how saved_view pins handle
  // missing-view state. Dispatch back into the standard PinRow shape
  // would be cleanest, but PinRow expects a Link with href; the
  // unavailable branch there assumes navigation, so we inline the
  // minimal icon-row rendering here.
  if (pin.unavailable) {
    const Icon = resolveIcon(pin.icon);
    return (
      <div
        draggable
        onDragStart={onDragStart}
        onDragOver={onDragOver}
        onDrop={onDrop}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        title="This widget is no longer available. Hover and click × to remove it."
        className={cn(
          "group flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm",
          "border-l-2 border-transparent",
          "opacity-50 cursor-not-allowed",
          dragging && "opacity-40",
        )}
        data-testid={`pin-row-${pin.pin_id}`}
        data-pin-id={pin.pin_id}
        data-unavailable="true"
        data-pin-type="widget"
      >
        <Icon className="size-4 shrink-0" />
        <span className="truncate flex-1">{pin.label}</span>
        {hover && (
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
      </div>
    );
  }

  // Available widget — render via the canvas widget framework.
  // getWidgetRenderer returns the registered component for the
  // widget_id; falls back to MockSavedViewWidget if the registration
  // module didn't import (defensive — shouldn't happen at app boot
  // but the fallback prevents a crash if it does).
  const widgetId = pin.widget_id ?? pin.target_id;
  const variantId = (pin.variant_id as VariantId | null) ?? "glance";
  const WidgetComponent = getWidgetRenderer(widgetId, variantId);

  // Click handler — summon the matching Focus per Section 12.6a.
  // The lookup table maps widget_id → focus_id; future widgets
  // declaring spaces_pin support add their entries above. If no
  // mapping exists, the click is a no-op (graceful) — the widget
  // still renders, but clicking does nothing because there's no
  // declared summon target.
  const summonFocusId = WIDGET_FOCUS_SUMMON[widgetId];
  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    if (summonFocusId) {
      focus.open(summonFocusId);
    }
  };

  // Keyboard summon — Enter/Space activates the click handler when
  // the wrapper has focus. Mirrors the role=button + tabIndex=0 the
  // Glance tablet itself declares (the wrapper is just an event
  // collector here; the inner tablet provides the a11y semantics).
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (summonFocusId) {
        focus.open(summonFocusId);
      }
    }
  };

  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDrop={onDrop}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      // Widget pins use a different visual vocabulary than icon-row
      // pins — the Glance tablet IS the visual chrome. Wrapper is
      // structural only: drag + click + hover-X handling. No left
      // border accent (the tablet's surface treatment carries its
      // own identity), no padding (tablet handles its own spacing).
      // Position relative so the unpin X can absolute-position
      // without disturbing tablet layout.
      className={cn(
        "group relative",
        dragging && "opacity-40",
      )}
      role="presentation"
      data-testid={`pin-row-${pin.pin_id}`}
      data-pin-id={pin.pin_id}
      data-pin-type="widget"
      data-pin-widget-id={widgetId}
      data-pin-variant-id={variantId}
    >
      <WidgetComponent
        widgetId={widgetId}
        variant_id={variantId}
        surface="spaces_pin"
        config={pin.config ?? undefined}
      />
      {hover && (
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onRemove();
          }}
          // Absolute-position the unpin X over the top-right of the
          // tablet. opacity-0 → group-hover:opacity-100 keeps chrome
          // discreet (Section 0 Restraint principle: visible only
          // when the user reaches for it).
          className={cn(
            "absolute top-1 right-1 z-10 size-5 rounded-sm",
            "flex items-center justify-center",
            "opacity-0 group-hover:opacity-100 transition-opacity",
            "bg-surface-elevated/90 backdrop-blur-sm",
            "text-muted-foreground hover:text-destructive",
            "shadow-sm",
          )}
          aria-label={`Unpin ${pin.label}`}
          data-testid={`pin-remove-${pin.pin_id}`}
        >
          <X className="size-3" />
        </button>
      )}
    </div>
  );
}
