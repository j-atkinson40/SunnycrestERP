/**
 * KanbanPanel — one day's full scheduling board with drag-and-drop.
 *
 * Used by the Scheduling Board page to render each day as an independent
 * panel with its own data fetching, drag-and-drop context, and collapse state.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  DragDropContext,
  Droppable,
  type DropResult,
} from "@hello-pangea/dnd";
import { ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { InlineError } from "@/components/ui/inline-error";
// R-2.0 — OrderCard imported from the visual-editor entity-card
// registration shim. Pre-R-2.0 OrderCard was a nested function
// declaration in this file; extracting + importing the WRAPPED version
// gives the runtime editor a `data-component-name` boundary div around
// each rendered card so click-to-edit can resolve the kanban-panel
// OrderCard alongside the other entity cards. Direct import of
// `OrderCardRaw` from "@/components/delivery/OrderCard" is forbidden
// by the eslint rule registered in R-2.0 — bypasses runtime
// registration.
import { OrderCard } from "@/lib/visual-editor/registry/registrations/entity-cards";
import { deliveryService } from "@/services/delivery-service";
import type {
  KanbanCard,
  KanbanConfig,
  KanbanScheduleResponse,
} from "@/types/delivery";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const UNSCHEDULED_DROPPABLE = "unscheduled";

const DEFAULT_CONFIG: KanbanConfig = {
  default_view: "tomorrow",
  saturday_default: "monday",
  sunday_default: "monday",
  show_driver_count_badge: true,
  warn_driver_count: 4,
  card_show_cemetery: true,
  card_show_funeral_home: true,
  card_show_service_time: true,
  card_show_vault_type: true,
  card_show_family_name: true,
  critical_window_hours: 4,
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function parseDate(s: string): Date {
  return new Date(s + "T12:00:00");
}

function formatDisplayDate(dateStr: string): string {
  const d = parseDate(dateStr);
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}


// ---------------------------------------------------------------------------
// KanbanPanel — exported component
// ---------------------------------------------------------------------------

export interface KanbanPanelProps {
  dateStr: string;
  isToday: boolean;
  label: string;
  subtitle?: string;
  collapsed: boolean;
  onToggleCollapse?: () => void;
  collapsible?: boolean;
  /** De-emphasize empty state — used for Sunday in Saturday view */
  isOptionalDay?: boolean;
  /** Show "Plan ahead" badge — used for Monday in Saturday view */
  showPlanAheadBadge?: boolean;
  /** Unique prefix for drag IDs — prevents cross-panel ID collision */
  panelPrefix?: string;
}

export function KanbanPanel({
  dateStr,
  isToday,
  label,
  subtitle,
  collapsed,
  onToggleCollapse,
  collapsible = false,
  isOptionalDay = false,
  showPlanAheadBadge = false,
  panelPrefix = isToday ? "today" : "next",
}: KanbanPanelProps) {
  const [data, setData] = useState<KanbanScheduleResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch schedule data
  const fetchSchedule = useCallback(
    async (showLoading = true) => {
      if (!dateStr) return;
      if (showLoading) setLoading(true);
      setError(false);
      try {
        const result = await deliveryService.getKanbanSchedule(dateStr);
        setData(result);
      } catch {
        if (showLoading) setError(true);
      } finally {
        setLoading(false);
      }
    },
    [dateStr],
  );

  useEffect(() => {
    fetchSchedule();
  }, [fetchSchedule]);

  // Poll every 60 seconds
  useEffect(() => {
    if (!dateStr) return;
    pollRef.current = setInterval(() => {
      fetchSchedule(false);
    }, 60_000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [dateStr, fetchSchedule]);

  // Drag-and-drop handler
  const handleDragEnd = useCallback(
    async (result: DropResult) => {
      if (!data || !result.destination) return;

      const { source, destination, draggableId } = result;
      const deliveryId = draggableId.replace(`${panelPrefix}-`, "");

      if (
        source.droppableId === destination.droppableId &&
        source.index === destination.index
      ) {
        return;
      }

      const prevData = structuredClone(data);
      const newData = structuredClone(data);

      let movedCard: KanbanCard | undefined;
      const srcDropId = source.droppableId.replace(`${panelPrefix}-`, "");
      const destDropId = destination.droppableId.replace(
        `${panelPrefix}-`,
        "",
      );

      if (srcDropId === UNSCHEDULED_DROPPABLE) {
        movedCard = newData.unscheduled.splice(source.index, 1)[0];
      } else {
        const srcLane = newData.drivers.find(
          (d) => d.driver_id === srcDropId,
        );
        if (srcLane) {
          movedCard = srcLane.deliveries.splice(source.index, 1)[0];
          srcLane.delivery_count = srcLane.deliveries.length;
        }
      }

      if (!movedCard) return;

      if (destDropId === UNSCHEDULED_DROPPABLE) {
        movedCard.status = "pending";
        newData.unscheduled.splice(destination.index, 0, movedCard);
      } else {
        const destLane = newData.drivers.find(
          (d) => d.driver_id === destDropId,
        );
        if (destLane) {
          movedCard.status = "scheduled";
          destLane.deliveries.splice(destination.index, 0, movedCard);
          destLane.delivery_count = destLane.deliveries.length;
        }
      }

      setData(newData);

      try {
        await deliveryService.assignKanban({
          delivery_id: deliveryId,
          driver_id: destDropId === UNSCHEDULED_DROPPABLE ? null : destDropId,
          date: dateStr,
          sequence: destination.index + 1,
        });
      } catch {
        setData(prevData);
        toast.error("Failed to update assignment");
      }
    },
    [data, dateStr, panelPrefix],
  );

  // Stats
  const stats = useMemo(() => {
    if (!data) return { total: 0, drivers: 0, unassigned: 0 };
    const total =
      data.unscheduled.length +
      data.drivers.reduce((sum, d) => sum + d.delivery_count, 0);
    const drivers = data.drivers.filter((d) => d.delivery_count > 0).length;
    return { total, drivers, unassigned: data.unscheduled.length };
  }, [data]);

  const config = data?.config ?? DEFAULT_CONFIG;
  const isEmpty = stats.total === 0;

  // ── Panel header ──
  const panelHeader = (
    <div
      className={cn(
        "flex items-center justify-between rounded-t-xl border px-5 py-3",
        isToday
          ? "border-border-base bg-surface-sunken"
          : isOptionalDay && isEmpty
            ? "border-border-subtle bg-surface-sunken/60"
            : "border-border-subtle bg-surface-sunken",
        collapsed && "rounded-b-xl",
      )}
    >
      <div className="flex items-center gap-3">
        {collapsible && (
          <button
            onClick={onToggleCollapse}
            className="rounded p-0.5 transition-colors duration-quick ease-settle hover:bg-surface-elevated focus-ring-accent"
            aria-label={collapsed ? "Expand panel" : "Collapse panel"}
          >
            <ChevronRight
              className={cn(
                "h-4 w-4 text-content-muted transition-transform duration-200",
                !collapsed && "rotate-90",
              )}
              aria-hidden="true"
            />
          </button>
        )}
        <div>
          <div className="flex items-center gap-2">
            <h2
              className={cn(
                "text-sm font-bold",
                isOptionalDay && isEmpty
                  ? "text-content-muted"
                  : "text-content-strong",
              )}
            >
              {formatDisplayDate(dateStr)}
            </h2>
            <span className="text-sm text-content-muted">·</span>
            <span
              className={cn(
                "text-sm font-medium",
                isToday
                  ? "text-accent"
                  : isOptionalDay && isEmpty
                    ? "text-content-subtle"
                    : "text-content-base",
              )}
            >
              {label}
            </span>
            {showPlanAheadBadge && (
              <Badge variant="info" className="text-[10px] font-medium">
                Plan ahead
              </Badge>
            )}
          </div>
          {subtitle && (
            <p className="text-xs text-content-subtle mt-0.5">{subtitle}</p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3 text-xs text-content-muted">
        {!loading && (
          <>
            {isOptionalDay && isEmpty ? (
              <span className="text-content-subtle">
                No deliveries scheduled
              </span>
            ) : (
              <>
                <span>{stats.total} deliveries</span>
                <span className="text-content-subtle">·</span>
                <span>{stats.drivers} drivers</span>
                <span className="text-content-subtle">·</span>
                <span
                  className={cn(
                    stats.unassigned > 0
                      ? "font-semibold text-status-warning"
                      : "text-content-muted",
                  )}
                >
                  {stats.unassigned} unassigned
                </span>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );

  // ── Collapsed view ──
  if (collapsed) {
    return <div className="rounded-xl">{panelHeader}</div>;
  }

  // ── Error state ──
  // Phase II Batch 1b — migrated to shared InlineError primitive.
  // Prior ad-hoc bg-white panel with hardcoded text-red-600 + Retry
  // Button is the exact "failed to load + retry" pattern the Phase 7
  // InlineError primitive was designed for.
  if (error) {
    return (
      <div className="rounded-xl border border-border-subtle">
        {panelHeader}
        <div className="flex h-48 items-center justify-center rounded-b-xl border-t border-border-subtle bg-surface-elevated p-4">
          <InlineError
            message="Couldn't load the delivery schedule."
            hint="Check your connection, then retry."
            onRetry={() => fetchSchedule()}
            className="max-w-md"
          />
        </div>
      </div>
    );
  }

  // ── Loading state ──
  if (loading) {
    return (
      <div className="rounded-xl border border-border-subtle">
        {panelHeader}
        <div className="flex h-48 items-center justify-center rounded-b-xl border-t border-border-subtle bg-surface-elevated">
          <p className="text-sm text-content-muted">Loading schedule...</p>
        </div>
      </div>
    );
  }

  // ── Empty state ──
  if (!data || (isEmpty && data.drivers.length === 0)) {
    return (
      <div
        className={cn(
          "rounded-xl border border-border-subtle",
          isOptionalDay && "opacity-75",
        )}
      >
        {panelHeader}
        <div
          className={cn(
            "flex h-28 items-center justify-center rounded-b-xl border-t border-border-subtle",
            isOptionalDay ? "bg-surface-sunken/50" : "bg-surface-elevated",
          )}
        >
          <div className="text-center">
            <p
              className={cn(
                "text-sm",
                isOptionalDay ? "text-content-subtle" : "text-content-muted",
              )}
            >
              {isToday
                ? "No deliveries scheduled for today."
                : isOptionalDay
                  ? `No deliveries scheduled${isEmpty ? "" : ` for ${formatDisplayDate(dateStr)}`}.`
                  : `Nothing scheduled for ${formatDisplayDate(dateStr)} yet.`}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // ── Full Kanban board ──
  // Phase II Batch 1b — droppable-over indigo → accent-subtle per
  // approved platform interaction language. Accent is the consistent
  // "active surface" signal across focus rings, hover states, and
  // now DnD drop zones.
  return (
    <div className="rounded-xl border border-border-subtle">
      {panelHeader}
      <div className="rounded-b-xl border-t border-border-subtle bg-surface-elevated">
        <DragDropContext onDragEnd={handleDragEnd}>
          <div className="flex min-h-[200px] gap-4 overflow-x-auto p-4">
            {/* Unscheduled pool */}
            <div className="flex w-64 shrink-0 flex-col">
              <div className="flex items-center justify-between rounded-t-lg border border-b-0 border-border-subtle bg-surface-sunken px-3 py-2">
                <span className="text-sm font-semibold text-content-strong">
                  Unscheduled
                </span>
                <Badge
                  variant={
                    data.unscheduled.length > 0 ? "error" : "secondary"
                  }
                  className="text-xs"
                >
                  {data.unscheduled.length}
                </Badge>
              </div>
              <Droppable
                droppableId={`${panelPrefix}-${UNSCHEDULED_DROPPABLE}`}
                direction="vertical"
              >
                {(provided, snapshot) => (
                  <div
                    ref={provided.innerRef}
                    {...provided.droppableProps}
                    className={cn(
                      "flex min-h-[120px] flex-1 flex-col gap-2 rounded-b-lg border border-t-0 p-2 transition-colors",
                      snapshot.isDraggingOver
                        ? "border-accent bg-accent-subtle"
                        : "border-border-subtle bg-surface-elevated",
                    )}
                  >
                    {data.unscheduled.map((card, idx) => (
                      <OrderCard
                        key={card.delivery_id}
                        card={card}
                        config={config}
                        index={idx}
                        panelPrefix={panelPrefix}
                      />
                    ))}
                    {provided.placeholder}
                    {data.unscheduled.length === 0 &&
                      !snapshot.isDraggingOver && (
                        <div className="flex flex-1 items-center justify-center text-xs text-content-subtle">
                          All orders scheduled
                        </div>
                      )}
                  </div>
                )}
              </Droppable>
            </div>

            {/* Driver lanes */}
            {data.drivers.map((lane) => {
              const overWarning =
                config.show_driver_count_badge &&
                lane.delivery_count >= config.warn_driver_count;

              return (
                <div
                  key={lane.driver_id}
                  className="flex w-64 shrink-0 flex-col"
                >
                  <div
                    className={cn(
                      "flex items-center justify-between rounded-t-lg border border-b-0 px-3 py-2",
                      overWarning
                        ? "border-status-warning bg-status-warning-muted"
                        : "border-border-subtle bg-surface-sunken",
                    )}
                  >
                    <span className="text-sm font-semibold text-content-strong truncate">
                      {lane.name}
                    </span>
                    {config.show_driver_count_badge && (
                      <Badge
                        variant={overWarning ? "warning" : "secondary"}
                        className="ml-2 text-xs"
                      >
                        {lane.delivery_count}
                      </Badge>
                    )}
                  </div>
                  <Droppable
                    droppableId={`${panelPrefix}-${lane.driver_id}`}
                    direction="vertical"
                  >
                    {(provided, snapshot) => (
                      <div
                        ref={provided.innerRef}
                        {...provided.droppableProps}
                        className={cn(
                          "flex min-h-[120px] flex-1 flex-col gap-2 rounded-b-lg border border-t-0 p-2 transition-colors",
                          snapshot.isDraggingOver
                            ? "border-accent bg-accent-subtle"
                            : "border-border-subtle bg-surface-elevated",
                        )}
                      >
                        {lane.deliveries.map((card, idx) => (
                          <OrderCard
                            key={card.delivery_id}
                            card={card}
                            config={config}
                            index={idx}
                            panelPrefix={panelPrefix}
                          />
                        ))}
                        {provided.placeholder}
                        {lane.deliveries.length === 0 &&
                          !snapshot.isDraggingOver && (
                            <div className="flex flex-1 items-center justify-center text-xs text-content-subtle">
                              Drop orders here
                            </div>
                          )}
                      </div>
                    )}
                  </Droppable>
                </div>
              );
            })}

            {data.drivers.length === 0 && (
              <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
                No active drivers found. Add drivers in Delivery &amp;
                Logistics settings.
              </div>
            )}
          </div>
        </DragDropContext>
      </div>
    </div>
  );
}
