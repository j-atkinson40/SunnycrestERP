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
  Draggable,
  type DropResult,
} from "@hello-pangea/dnd";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
// OrderCard — individual delivery card (Draggable)
// ---------------------------------------------------------------------------

interface OrderCardProps {
  card: KanbanCard;
  config: KanbanConfig;
  index: number;
  panelPrefix: string;
}

function OrderCard({ card, config, index, panelPrefix }: OrderCardProps) {
  return (
    <Draggable
      draggableId={`${panelPrefix}-${card.delivery_id}`}
      index={index}
    >
      {(provided, snapshot) => (
        <div
          ref={provided.innerRef}
          {...provided.draggableProps}
          {...provided.dragHandleProps}
          className={cn(
            "rounded-lg border bg-white p-3 shadow-sm transition-shadow",
            snapshot.isDragging && "shadow-lg ring-2 ring-indigo-400",
            card.is_critical && "border-red-400 bg-red-50",
            card.is_warning &&
              !card.is_critical &&
              "border-amber-400 bg-amber-50",
          )}
        >
          {/* Funeral home name */}
          {config.card_show_funeral_home && card.funeral_home_name && (
            <div className="text-sm font-semibold text-slate-900 leading-tight">
              {card.funeral_home_name}
            </div>
          )}

          {/* Deceased name */}
          {card.deceased_name && (
            <div className="text-xs text-slate-500 mt-0.5">
              RE: {card.deceased_name}
            </div>
          )}

          {/* Vault · Equipment */}
          {(card.vault_type || card.equipment_summary) && (
            <div className="mt-1.5 text-xs text-slate-700">
              {[card.vault_type, card.equipment_summary].filter(Boolean).join(" · ")}
              {card.vault_personalization && (
                <Badge variant="secondary" className="ml-1 text-[10px] px-1 py-0">
                  Custom
                </Badge>
              )}
            </div>
          )}

          {/* Service location → Cemetery + times */}
          <div className="mt-1.5 text-xs text-slate-600 space-y-0.5">
            {/* Location line */}
            {(card.service_location || card.cemetery_name) && (
              <div className="flex items-center gap-1">
                <span className="text-slate-400 text-[11px]">
                  {card.service_location === "church" ? "⛪" :
                   card.service_location === "funeral_home" ? "🏛" :
                   card.service_location === "graveside" ? "⚰" : "📍"}
                </span>
                {card.service_location === "graveside" ? (
                  <span>Graveside · {card.cemetery_name || "TBD"}</span>
                ) : (
                  <span>
                    {card.service_location === "church" ? "Church" :
                     card.service_location === "funeral_home" ? "Funeral Home" :
                     card.service_location_other || "Service"}
                    {card.cemetery_name ? ` → ${card.cemetery_name}` : ""}
                  </span>
                )}
              </div>
            )}
            {!card.service_location && card.cemetery_name && (
              <div className="truncate">{card.cemetery_name}</div>
            )}

            {/* Time line */}
            {card.service_location === "graveside" ? (
              card.service_time_display ? (
                <div className="font-medium">{card.service_time_display}</div>
              ) : (
                <div className="text-amber-600">Time TBD</div>
              )
            ) : card.service_time_display ? (
              <div>
                Service: {card.service_time_display}
                {card.eta_display ? (
                  <span className="font-medium ml-2">ETA: {card.eta_display}</span>
                ) : (
                  <span className="text-amber-600 ml-2">ETA: TBD</span>
                )}
              </div>
            ) : (
              <div className="text-amber-600">Time TBD</div>
            )}
          </div>

          {/* Hours countdown */}
          {card.hours_until_service !== null &&
            card.hours_until_service > 0 && (
              <div className="mt-1.5">
                <Badge
                  variant="outline"
                  className={cn(
                    "text-[10px]",
                    card.is_critical
                      ? "border-red-400 text-red-700 animate-pulse"
                      : card.is_warning
                        ? "border-amber-400 text-amber-700"
                        : "border-slate-200 text-slate-500",
                  )}
                >
                  {card.hours_until_service < 1
                    ? `${Math.round(card.hours_until_service * 60)}m until service`
                    : `${card.hours_until_service}h until service`}
                </Badge>
              </div>
            )}

          {card.notes && (
            <div className="mt-1.5 truncate text-[11px] italic text-slate-400">
              {card.notes}
            </div>
          )}
        </div>
      )}
    </Draggable>
  );
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
          ? "border-slate-300 bg-slate-100"
          : isOptionalDay && isEmpty
            ? "border-slate-200 bg-slate-50/60"
            : "border-slate-200 bg-slate-50",
        collapsed && "rounded-b-xl",
      )}
    >
      <div className="flex items-center gap-3">
        {collapsible && (
          <button
            onClick={onToggleCollapse}
            className="rounded p-0.5 hover:bg-slate-200 transition-colors"
            aria-label={collapsed ? "Expand panel" : "Collapse panel"}
          >
            <svg
              className={cn(
                "h-4 w-4 text-slate-500 transition-transform duration-200",
                !collapsed && "rotate-90",
              )}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="m9 18 6-6-6-6" />
            </svg>
          </button>
        )}
        <div>
          <div className="flex items-center gap-2">
            <h2
              className={cn(
                "text-sm font-bold",
                isOptionalDay && isEmpty
                  ? "text-slate-500"
                  : "text-slate-900",
              )}
            >
              {formatDisplayDate(dateStr)}
            </h2>
            <span className="text-sm text-slate-500">·</span>
            <span
              className={cn(
                "text-sm font-medium",
                isToday
                  ? "text-blue-700"
                  : isOptionalDay && isEmpty
                    ? "text-slate-400"
                    : "text-slate-600",
              )}
            >
              {label}
            </span>
            {showPlanAheadBadge && (
              <Badge
                variant="outline"
                className="border-indigo-200 bg-indigo-50 text-indigo-600 text-[10px] font-medium"
              >
                Plan ahead
              </Badge>
            )}
          </div>
          {subtitle && (
            <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3 text-xs text-slate-600">
        {!loading && (
          <>
            {isOptionalDay && isEmpty ? (
              <span className="text-slate-400">
                No deliveries scheduled
              </span>
            ) : (
              <>
                <span>{stats.total} deliveries</span>
                <span className="text-slate-300">·</span>
                <span>{stats.drivers} drivers</span>
                <span className="text-slate-300">·</span>
                <span
                  className={cn(
                    stats.unassigned > 0
                      ? "font-semibold text-amber-600"
                      : "text-slate-500",
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
  if (error) {
    return (
      <div className="rounded-xl border">
        {panelHeader}
        <div className="flex h-48 items-center justify-center rounded-b-xl border-t bg-white">
          <div className="text-center">
            <p className="text-sm text-red-600 font-medium">
              Failed to load schedule
            </p>
            <Button
              variant="outline"
              size="sm"
              className="mt-2"
              onClick={() => fetchSchedule()}
            >
              Retry
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // ── Loading state ──
  if (loading) {
    return (
      <div className="rounded-xl border">
        {panelHeader}
        <div className="flex h-48 items-center justify-center rounded-b-xl border-t bg-white">
          <p className="text-sm text-muted-foreground">Loading schedule...</p>
        </div>
      </div>
    );
  }

  // ── Empty state ──
  if (!data || (isEmpty && data.drivers.length === 0)) {
    return (
      <div
        className={cn(
          "rounded-xl border",
          isOptionalDay && "opacity-75",
        )}
      >
        {panelHeader}
        <div
          className={cn(
            "flex h-28 items-center justify-center rounded-b-xl border-t",
            isOptionalDay ? "bg-slate-50/50" : "bg-white",
          )}
        >
          <div className="text-center">
            <p
              className={cn(
                "text-sm",
                isOptionalDay ? "text-slate-400" : "text-slate-500",
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
  return (
    <div className="rounded-xl border">
      {panelHeader}
      <div className="rounded-b-xl border-t bg-white">
        <DragDropContext onDragEnd={handleDragEnd}>
          <div className="flex min-h-[200px] gap-4 overflow-x-auto p-4">
            {/* Unscheduled pool */}
            <div className="flex w-64 shrink-0 flex-col">
              <div className="flex items-center justify-between rounded-t-lg border border-b-0 border-slate-200 bg-slate-100 px-3 py-2">
                <span className="text-sm font-semibold text-slate-800">
                  Unscheduled
                </span>
                <Badge
                  variant={
                    data.unscheduled.length > 0 ? "destructive" : "secondary"
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
                        ? "border-indigo-300 bg-indigo-50/50"
                        : "border-slate-200 bg-white",
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
                        <div className="flex flex-1 items-center justify-center text-xs text-slate-400">
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
                        ? "border-amber-300 bg-amber-50"
                        : "border-slate-200 bg-slate-100",
                    )}
                  >
                    <span className="text-sm font-semibold text-slate-800 truncate">
                      {lane.name}
                    </span>
                    {config.show_driver_count_badge && (
                      <Badge
                        variant={overWarning ? "destructive" : "secondary"}
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
                            ? "border-indigo-300 bg-indigo-50/50"
                            : "border-slate-200 bg-white",
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
                            <div className="flex flex-1 items-center justify-center text-xs text-slate-400">
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
