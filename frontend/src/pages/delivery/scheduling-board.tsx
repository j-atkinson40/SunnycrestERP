/**
 * Scheduling Board — Two-panel Kanban view
 *
 * Shows today's full Kanban board stacked above the next delivery day's
 * Kanban board. The "next delivery day" is context-aware — on Saturday
 * it shows Monday when Sunday deliveries are disabled.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
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
import { useAuth } from "@/contexts/auth-context";
import { deliveryService } from "@/services/delivery-service";
import type {
  KanbanCard,
  KanbanConfig,
  KanbanScheduleResponse,
} from "@/types/delivery";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const UNSCHEDULED_DROPPABLE = "unscheduled";

function addDays(d: Date, n: number): Date {
  const result = new Date(d);
  result.setDate(result.getDate() + n);
  return result;
}

function subtractDays(d: Date, n: number): Date {
  return addDays(d, -n);
}

function formatDate(d: Date): string {
  return d.toISOString().split("T")[0];
}

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

function formatShortDate(dateStr: string): string {
  const d = parseDate(dateStr);
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

/** Get the next delivery day from a given date, respecting weekend settings. */
function getNextDeliveryDay(
  currentDateStr: string,
  saturdayEnabled: boolean,
  sundayEnabled: boolean,
): string {
  const current = parseDate(currentDateStr);
  const tomorrow = addDays(current, 1);
  const dayOfWeek = tomorrow.getDay(); // 0 = Sunday, 6 = Saturday

  // If tomorrow is Saturday and we don't deliver Saturdays — skip to Monday
  if (dayOfWeek === 6 && !saturdayEnabled) {
    return formatDate(addDays(current, 3));
  }

  // If tomorrow is Sunday and we don't deliver Sundays — skip to Monday
  if (dayOfWeek === 0 && !sundayEnabled) {
    return formatDate(addDays(current, 2));
  }

  // TODO: check company holidays when holiday calendar is built

  return formatDate(tomorrow);
}

/** Get the previous delivery day from a given date. */
function getPrevDeliveryDay(
  currentDateStr: string,
  saturdayEnabled: boolean,
  sundayEnabled: boolean,
): string {
  const current = parseDate(currentDateStr);
  const yesterday = subtractDays(current, 1);
  const dayOfWeek = yesterday.getDay();

  // If yesterday is Sunday and we don't deliver Sundays — go to Saturday or Friday
  if (dayOfWeek === 0 && !sundayEnabled) {
    if (saturdayEnabled) {
      return formatDate(subtractDays(current, 1)); // Still Sunday, need Saturday
    }
    return formatDate(subtractDays(current, 2)); // Skip to Friday
  }
  if (dayOfWeek === 0 && !sundayEnabled) {
    return formatDate(subtractDays(current, 2));
  }

  // If yesterday is Saturday and we don't deliver Saturdays — go to Friday
  if (dayOfWeek === 6 && !saturdayEnabled) {
    return formatDate(subtractDays(current, 2));
  }

  return formatDate(yesterday);
}

// ---------------------------------------------------------------------------
// Panel collapse persistence
// ---------------------------------------------------------------------------

function getCollapseKey(tenantId: string, userId: string): string {
  return `scheduling_board_tomorrow_collapsed_${tenantId}_${userId}`;
}

function loadCollapsed(tenantId: string, userId: string): boolean {
  try {
    return localStorage.getItem(getCollapseKey(tenantId, userId)) === "true";
  } catch {
    return false;
  }
}

function saveCollapsed(
  tenantId: string,
  userId: string,
  collapsed: boolean,
): void {
  try {
    localStorage.setItem(
      getCollapseKey(tenantId, userId),
      String(collapsed),
    );
  } catch {
    /* noop */
  }
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
            card.is_warning && !card.is_critical && "border-amber-400 bg-amber-50",
          )}
        >
          <div className="flex items-start justify-between gap-2">
            {config.card_show_family_name && card.family_name && (
              <span className="text-sm font-semibold text-slate-900 leading-tight">
                {card.family_name}
              </span>
            )}
            {config.card_show_service_time && card.service_time_display && (
              <Badge
                variant="outline"
                className={cn(
                  "shrink-0 text-xs font-medium",
                  card.is_critical
                    ? "border-red-400 bg-red-100 text-red-800"
                    : card.is_warning
                      ? "border-amber-400 bg-amber-100 text-amber-800"
                      : "border-slate-300",
                )}
              >
                {card.service_time_display}
              </Badge>
            )}
          </div>

          <div className="mt-1.5 space-y-0.5 text-xs text-slate-600">
            {config.card_show_cemetery && card.cemetery_name && (
              <div className="flex items-center gap-1">
                <span className="text-slate-400">Cemetery:</span>
                <span className="truncate">{card.cemetery_name}</span>
              </div>
            )}
            {config.card_show_funeral_home && card.funeral_home_name && (
              <div className="flex items-center gap-1">
                <span className="text-slate-400">FH:</span>
                <span className="truncate">{card.funeral_home_name}</span>
              </div>
            )}
            {config.card_show_vault_type && card.vault_type && (
              <div className="flex items-center gap-1">
                <span className="text-slate-400">Vault:</span>
                <span>{card.vault_type}</span>
                {card.vault_personalization && (
                  <Badge
                    variant="secondary"
                    className="ml-1 text-[10px] px-1 py-0"
                  >
                    Custom
                  </Badge>
                )}
              </div>
            )}
          </div>

          {(card.required_window_start || card.required_window_end) && (
            <div className="mt-1.5 text-[11px] text-slate-500">
              Window: {card.required_window_start || "?"} –{" "}
              {card.required_window_end || "?"}
            </div>
          )}

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
// KanbanPanel — one day's full board with drag-and-drop
// ---------------------------------------------------------------------------

interface KanbanPanelProps {
  dateStr: string;
  isToday: boolean;
  label: string;
  subtitle?: string;
  collapsed: boolean;
  onToggleCollapse?: () => void;
  collapsible?: boolean;
}

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

function KanbanPanel({
  dateStr,
  isToday,
  label,
  subtitle,
  collapsed,
  onToggleCollapse,
  collapsible = false,
}: KanbanPanelProps) {
  const [data, setData] = useState<KanbanScheduleResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const panelPrefix = isToday ? "today" : "next";

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
      // Strip panel prefix from draggable ID to get actual delivery ID
      const deliveryId = draggableId.replace(`${panelPrefix}-`, "");

      if (
        source.droppableId === destination.droppableId &&
        source.index === destination.index
      ) {
        return;
      }

      const prevData = structuredClone(data);
      const newData = structuredClone(data);

      // Remove card from source
      let movedCard: KanbanCard | undefined;
      const srcDropId = source.droppableId.replace(`${panelPrefix}-`, "");
      const destDropId = destination.droppableId.replace(
        `${panelPrefix}-`,
        "",
      );

      if (srcDropId === UNSCHEDULED_DROPPABLE) {
        movedCard = newData.unscheduled.splice(source.index, 1)[0];
      } else {
        const srcLane = newData.drivers.find((d) => d.driver_id === srcDropId);
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
    return {
      total,
      drivers,
      unassigned: data.unscheduled.length,
    };
  }, [data]);

  const config = data?.config ?? DEFAULT_CONFIG;

  // ── Panel header ──
  const panelHeader = (
    <div
      className={cn(
        "flex items-center justify-between rounded-t-xl border px-5 py-3",
        isToday
          ? "border-slate-300 bg-slate-100"
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
            <h2 className="text-sm font-bold text-slate-900">
              {formatDisplayDate(dateStr)}
            </h2>
            <span className="text-sm text-slate-500">·</span>
            <span
              className={cn(
                "text-sm font-medium",
                isToday ? "text-blue-700" : "text-slate-600",
              )}
            >
              {label}
            </span>
          </div>
          {subtitle && (
            <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3 text-xs text-slate-600">
        {!loading && (
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
  if (!data || (stats.total === 0 && data.drivers.length === 0)) {
    return (
      <div className="rounded-xl border">
        {panelHeader}
        <div className="flex h-36 items-center justify-center rounded-b-xl border-t bg-white">
          <div className="text-center">
            <p className="text-sm text-slate-500">
              {isToday
                ? "No deliveries scheduled for today."
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

// ---------------------------------------------------------------------------
// Main Scheduling Board Page
// ---------------------------------------------------------------------------

export default function SchedulingBoardPage() {
  const { user, company } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  // Tenant settings for weekend delivery
  const tenantSettings = (company as unknown as Record<string, unknown>) ?? {};
  const saturdayEnabled =
    (tenantSettings.saturday_delivery_enabled as boolean) ?? true;
  const sundayEnabled =
    (tenantSettings.sunday_delivery_enabled as boolean) ?? false;

  // Date state
  const todayStr = formatDate(new Date());
  const dateParam = searchParams.get("date");
  const [primaryDate, setPrimaryDate] = useState<string>(
    dateParam || todayStr,
  );

  // Compute next delivery day from primary date
  const nextDate = useMemo(
    () => getNextDeliveryDay(primaryDate, saturdayEnabled, sundayEnabled),
    [primaryDate, saturdayEnabled, sundayEnabled],
  );

  // Whether we're viewing the default (today) pair
  const isDefaultView = primaryDate === todayStr;

  // Panel 2 label logic
  const nextDateInfo = useMemo(() => {
    const tomorrow = formatDate(addDays(parseDate(primaryDate), 1));
    const isConsecutive = nextDate === tomorrow;
    const dayLabel = nextDate === formatDate(addDays(new Date(), 1))
      ? "Tomorrow"
      : formatDisplayDate(nextDate).split(",")[0]; // Weekday name

    return {
      label: nextDate === formatDate(addDays(new Date(), 1))
        ? "Tomorrow"
        : "Next delivery day",
      subtitle: !isConsecutive
        ? `Showing ${dayLabel} \u2014 next delivery day`
        : undefined,
    };
  }, [nextDate, primaryDate]);

  // Collapse state for panel 2
  const tenantId = company?.id || "default";
  const userId = user?.id || "default";
  const [tomorrowCollapsed, setTomorrowCollapsed] = useState(() =>
    loadCollapsed(tenantId, userId),
  );

  const handleToggleCollapse = useCallback(() => {
    setTomorrowCollapsed((prev) => {
      const next = !prev;
      saveCollapsed(tenantId, userId, next);
      return next;
    });
  }, [tenantId, userId]);

  // Navigation handlers
  const goNext = useCallback(() => {
    const next = getNextDeliveryDay(
      primaryDate,
      saturdayEnabled,
      sundayEnabled,
    );
    setPrimaryDate(next);
    setSearchParams(next === todayStr ? {} : { date: next });
  }, [primaryDate, saturdayEnabled, sundayEnabled, todayStr, setSearchParams]);

  const goPrev = useCallback(() => {
    const prev = getPrevDeliveryDay(
      primaryDate,
      saturdayEnabled,
      sundayEnabled,
    );
    setPrimaryDate(prev);
    setSearchParams(prev === todayStr ? {} : { date: prev });
  }, [primaryDate, saturdayEnabled, sundayEnabled, todayStr, setSearchParams]);

  const goToday = useCallback(() => {
    setPrimaryDate(todayStr);
    setSearchParams({});
  }, [todayStr, setSearchParams]);

  const handleDateChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = e.target.value;
      if (val) {
        setPrimaryDate(val);
        setSearchParams(val === todayStr ? {} : { date: val });
      }
    },
    [todayStr, setSearchParams],
  );

  // Sync with URL params on mount
  useEffect(() => {
    if (dateParam && dateParam !== primaryDate) {
      setPrimaryDate(dateParam);
    }
  }, [dateParam]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex h-full flex-col gap-6 p-6">
      {/* ── Page Header ── */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Scheduling Board
          </h1>
          <p className="text-sm text-muted-foreground">
            {isDefaultView
              ? `Today \u2014 ${formatShortDate(todayStr)}`
              : formatShortDate(primaryDate)}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Back to today pill */}
          {!isDefaultView && (
            <button
              onClick={goToday}
              className="flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100 transition-colors"
            >
              <span>↩</span>
              Back to today
            </button>
          )}

          {/* Navigation arrows + date picker */}
          <button
            onClick={goPrev}
            className="rounded-md border px-2.5 py-1.5 text-sm hover:bg-slate-100 transition-colors"
            aria-label="Previous delivery day"
          >
            ←
          </button>
          <input
            type="date"
            value={primaryDate}
            onChange={handleDateChange}
            className="rounded-md border px-3 py-1.5 text-sm"
          />
          <button
            onClick={goNext}
            className="rounded-md border px-2.5 py-1.5 text-sm hover:bg-slate-100 transition-colors"
            aria-label="Next delivery day"
          >
            →
          </button>
        </div>
      </div>

      {/* ── Panel 1: Primary date (today by default) ── */}
      <KanbanPanel
        dateStr={primaryDate}
        isToday={primaryDate === todayStr}
        label={primaryDate === todayStr ? "Today" : formatDisplayDate(primaryDate).split(",")[0]}
        collapsed={false}
      />

      {/* ── Panel 2: Next delivery day ── */}
      <KanbanPanel
        dateStr={nextDate}
        isToday={false}
        label={nextDateInfo.label}
        subtitle={nextDateInfo.subtitle}
        collapsed={tomorrowCollapsed}
        onToggleCollapse={handleToggleCollapse}
        collapsible
      />
    </div>
  );
}
