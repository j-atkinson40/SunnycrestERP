/**
 * Funeral Vault Kanban Scheduler
 *
 * Date-focused Kanban board for scheduling funeral vault deliveries by driver.
 * Unscheduled orders sit in a pool on the left; driver swimlanes fill the right.
 * Drag-and-drop assigns/reorders deliveries across drivers.
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
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { deliveryService } from "@/services/delivery-service";
import type {
  KanbanCard,
  KanbanConfig,
  KanbanDriverLane,
  KanbanScheduleResponse,
} from "@/types/delivery";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const UNSCHEDULED_DROPPABLE = "unscheduled";

/** Compute the smart default date based on config + day-of-week logic. */
function getDefaultDate(config?: KanbanConfig): string {
  const now = new Date();
  const day = now.getDay(); // 0=Sun, 6=Sat

  if (!config || config.default_view === "today") {
    return formatDate(now);
  }

  if (config.default_view === "tomorrow") {
    // Respect saturday_default and sunday_default overrides
    if (day === 6) {
      // Saturday
      if (config.saturday_default === "monday") {
        return formatDate(addDays(now, 2)); // Monday
      }
      return formatDate(addDays(now, 1)); // Sunday
    }
    if (day === 0) {
      // Sunday
      if (config.sunday_default === "monday") {
        return formatDate(addDays(now, 1)); // Monday
      }
      return formatDate(addDays(now, 1)); // Monday anyway for "tomorrow"
    }
    return formatDate(addDays(now, 1));
  }

  // "custom" — default to tomorrow
  return formatDate(addDays(now, 1));
}

function addDays(d: Date, n: number): Date {
  const result = new Date(d);
  result.setDate(result.getDate() + n);
  return result;
}

function formatDate(d: Date): string {
  return d.toISOString().split("T")[0];
}

function formatDisplayDate(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00");
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

// ---------------------------------------------------------------------------
// Order Card Component
// ---------------------------------------------------------------------------

interface OrderCardProps {
  card: KanbanCard;
  config: KanbanConfig;
  index: number;
}

function OrderCard({ card, config, index }: OrderCardProps) {
  return (
    <Draggable draggableId={card.delivery_id} index={index}>
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
          {/* Header row: family name + service time */}
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

          {/* Details */}
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
                  <Badge variant="secondary" className="ml-1 text-[10px] px-1 py-0">
                    Custom
                  </Badge>
                )}
              </div>
            )}
          </div>

          {/* Time window */}
          {(card.required_window_start || card.required_window_end) && (
            <div className="mt-1.5 text-[11px] text-slate-500">
              Window: {card.required_window_start || "?"} – {card.required_window_end || "?"}
            </div>
          )}

          {/* Countdown badge */}
          {card.hours_until_service !== null && card.hours_until_service > 0 && (
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

          {/* Notes indicator */}
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
// Driver Lane Component
// ---------------------------------------------------------------------------

interface DriverLaneProps {
  lane: KanbanDriverLane;
  config: KanbanConfig;
}

function DriverLane({ lane, config }: DriverLaneProps) {
  const overWarning =
    config.show_driver_count_badge &&
    lane.delivery_count >= config.warn_driver_count;

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      {/* Lane header */}
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

      {/* Droppable area */}
      <Droppable droppableId={lane.driver_id} direction="vertical">
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
              />
            ))}
            {provided.placeholder}
            {lane.deliveries.length === 0 && !snapshot.isDraggingOver && (
              <div className="flex flex-1 items-center justify-center text-xs text-slate-400">
                Drop orders here
              </div>
            )}
          </div>
        )}
      </Droppable>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Date Selector
// ---------------------------------------------------------------------------

interface DateSelectorProps {
  value: string;
  onChange: (date: string) => void;
}

function DateSelector({ value, onChange }: DateSelectorProps) {
  const goDay = (offset: number) => {
    const d = new Date(value + "T12:00:00");
    d.setDate(d.getDate() + offset);
    onChange(formatDate(d));
  };

  const isToday = value === formatDate(new Date());
  const isTomorrow = value === formatDate(addDays(new Date(), 1));

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => goDay(-1)}
        className="rounded-md border px-2 py-1 text-sm hover:bg-slate-100"
        aria-label="Previous day"
      >
        &larr;
      </button>
      <div className="flex items-center gap-2">
        <input
          type="date"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="rounded-md border px-3 py-1.5 text-sm"
        />
        {isToday && (
          <Badge className="bg-blue-100 text-blue-800 text-xs">Today</Badge>
        )}
        {isTomorrow && (
          <Badge className="bg-indigo-100 text-indigo-800 text-xs">Tomorrow</Badge>
        )}
      </div>
      <button
        onClick={() => goDay(1)}
        className="rounded-md border px-2 py-1 text-sm hover:bg-slate-100"
        aria-label="Next day"
      >
        &rarr;
      </button>
      <button
        onClick={() => onChange(formatDate(new Date()))}
        className="rounded-md border px-3 py-1 text-xs hover:bg-slate-100"
      >
        Today
      </button>
      <button
        onClick={() => onChange(formatDate(addDays(new Date(), 1)))}
        className="rounded-md border px-3 py-1 text-xs hover:bg-slate-100"
      >
        Tomorrow
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Print Schedule Helper
// ---------------------------------------------------------------------------

function printSchedule(data: KanbanScheduleResponse) {
  const w = window.open("", "_blank");
  if (!w) return;

  const rows = data.drivers
    .filter((d) => d.delivery_count > 0)
    .map(
      (d) => `
      <tr>
        <td style="padding:6px 12px;border:1px solid #ddd;font-weight:600">${d.name}</td>
        <td style="padding:6px 12px;border:1px solid #ddd">
          ${d.deliveries
            .map(
              (c, i) =>
                `${i + 1}. ${c.family_name || "—"} — ${c.cemetery_name || ""} ${c.service_time_display ? `@ ${c.service_time_display}` : ""}`,
            )
            .join("<br/>")}
        </td>
      </tr>`,
    )
    .join("");

  w.document.write(`
    <html><head><title>Schedule — ${data.date}</title>
    <style>body{font-family:system-ui;padding:24px}table{border-collapse:collapse;width:100%}th{text-align:left;padding:8px 12px;border:1px solid #ddd;background:#f1f5f9}@media print{button{display:none}}</style>
    </head><body>
    <h2>Funeral Vault Schedule — ${formatDisplayDate(data.date)}</h2>
    ${data.unscheduled.length > 0 ? `<p style="color:#b91c1c;font-weight:600">⚠ ${data.unscheduled.length} unscheduled order(s)</p>` : ""}
    <table><thead><tr><th>Driver</th><th>Deliveries</th></tr></thead><tbody>${rows}</tbody></table>
    <button onclick="window.print()" style="margin-top:16px;padding:8px 16px;cursor:pointer">Print</button>
    </body></html>
  `);
  w.document.close();
}

// ---------------------------------------------------------------------------
// Main Page Component
// ---------------------------------------------------------------------------

export default function FuneralSchedulingPage() {
  const [data, setData] = useState<KanbanScheduleResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState<string>("");
  const [configLoaded, setConfigLoaded] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [isMobile, setIsMobile] = useState(false);

  // Detect mobile
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  // Load config first to compute default date
  useEffect(() => {
    deliveryService
      .getKanbanConfig()
      .then((config) => {
        setSelectedDate(getDefaultDate(config));
        setConfigLoaded(true);
      })
      .catch(() => {
        // Extension might not be enabled — use tomorrow as fallback
        setSelectedDate(formatDate(addDays(new Date(), 1)));
        setConfigLoaded(true);
      });
  }, []);

  // Fetch schedule when date changes
  const fetchSchedule = useCallback(
    async (date: string, showLoading = true) => {
      if (!date) return;
      if (showLoading) setLoading(true);
      try {
        const result = await deliveryService.getKanbanSchedule(date);
        setData(result);
      } catch (err) {
        toast.error("Failed to load schedule");
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    if (configLoaded && selectedDate) {
      fetchSchedule(selectedDate);
    }
  }, [configLoaded, selectedDate, fetchSchedule]);

  // Poll every 60 seconds
  useEffect(() => {
    if (!selectedDate) return;
    pollRef.current = setInterval(() => {
      fetchSchedule(selectedDate, false);
    }, 60_000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [selectedDate, fetchSchedule]);

  // ---------------------------------------------------------------------------
  // Drag-and-drop handler
  // ---------------------------------------------------------------------------

  const handleDragEnd = useCallback(
    async (result: DropResult) => {
      if (!data || !result.destination) return;

      const { source, destination, draggableId } = result;
      const deliveryId = draggableId;

      // Same position — no-op
      if (
        source.droppableId === destination.droppableId &&
        source.index === destination.index
      ) {
        return;
      }

      // Optimistic update
      const prevData = structuredClone(data);
      const newData = structuredClone(data);

      // Remove card from source
      let movedCard: KanbanCard | undefined;
      if (source.droppableId === UNSCHEDULED_DROPPABLE) {
        movedCard = newData.unscheduled.splice(source.index, 1)[0];
      } else {
        const srcLane = newData.drivers.find(
          (d) => d.driver_id === source.droppableId,
        );
        if (srcLane) {
          movedCard = srcLane.deliveries.splice(source.index, 1)[0];
          srcLane.delivery_count = srcLane.deliveries.length;
        }
      }

      if (!movedCard) return;

      // Insert card at destination
      if (destination.droppableId === UNSCHEDULED_DROPPABLE) {
        movedCard.status = "pending";
        newData.unscheduled.splice(destination.index, 0, movedCard);
      } else {
        const destLane = newData.drivers.find(
          (d) => d.driver_id === destination.droppableId,
        );
        if (destLane) {
          movedCard.status = "scheduled";
          destLane.deliveries.splice(destination.index, 0, movedCard);
          destLane.delivery_count = destLane.deliveries.length;
        }
      }

      setData(newData);

      // Fire API call
      try {
        await deliveryService.assignKanban({
          delivery_id: deliveryId,
          driver_id:
            destination.droppableId === UNSCHEDULED_DROPPABLE
              ? null
              : destination.droppableId,
          date: selectedDate,
          sequence: destination.index + 1,
        });
      } catch {
        // Revert on failure
        setData(prevData);
        toast.error("Failed to update assignment");
      }
    },
    [data, selectedDate],
  );

  // ---------------------------------------------------------------------------
  // Conflict detection — overlapping delivery windows within a driver lane
  // ---------------------------------------------------------------------------

  const conflicts = useMemo(() => {
    if (!data) return new Set<string>();
    const conflictIds = new Set<string>();

    for (const lane of data.drivers) {
      for (let i = 0; i < lane.deliveries.length; i++) {
        for (let j = i + 1; j < lane.deliveries.length; j++) {
          const a = lane.deliveries[i];
          const b = lane.deliveries[j];
          // Both need service times to conflict
          if (a.service_time && b.service_time && a.service_time === b.service_time) {
            conflictIds.add(a.delivery_id);
            conflictIds.add(b.delivery_id);
          }
          // Window overlap check
          if (
            a.required_window_start &&
            a.required_window_end &&
            b.required_window_start &&
            b.required_window_end
          ) {
            if (
              a.required_window_start < b.required_window_end &&
              a.required_window_end > b.required_window_start
            ) {
              conflictIds.add(a.delivery_id);
              conflictIds.add(b.delivery_id);
            }
          }
        }
      }
    }
    return conflictIds;
  }, [data]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (!configLoaded) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading scheduler...</p>
      </div>
    );
  }

  const config = data?.config ?? {
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

  return (
    <div className="flex h-full flex-col gap-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Funeral Vault Scheduling
          </h1>
          {selectedDate && (
            <p className="text-sm text-muted-foreground">
              {formatDisplayDate(selectedDate)}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <DateSelector value={selectedDate} onChange={setSelectedDate} />
          {data && (
            <button
              onClick={() => printSchedule(data)}
              className="rounded-md border px-3 py-1.5 text-sm hover:bg-slate-100"
            >
              Print Schedule
            </button>
          )}
        </div>
      </div>

      {/* Conflict warning */}
      {conflicts.size > 0 && (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-800">
          <strong>Scheduling conflict:</strong> {conflicts.size} deliveries have
          overlapping time windows within the same driver.
        </div>
      )}

      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <p className="text-muted-foreground">Loading schedule...</p>
        </div>
      ) : !data ? (
        <div className="flex h-64 items-center justify-center">
          <p className="text-muted-foreground">
            No schedule data. The Funeral Kanban extension may not be enabled.
          </p>
        </div>
      ) : isMobile ? (
        /* ---- Mobile list view fallback ---- */
        <MobileView data={data} config={config} />
      ) : (
        /* ---- Desktop Kanban board ---- */
        <DragDropContext onDragEnd={handleDragEnd}>
          <div className="flex min-h-0 flex-1 gap-4 overflow-x-auto pb-4">
            {/* Unscheduled pool */}
            <div className="flex w-72 shrink-0 flex-col">
              <div className="flex items-center justify-between rounded-t-lg border border-b-0 border-slate-200 bg-slate-100 px-3 py-2">
                <span className="text-sm font-semibold text-slate-800">
                  Unscheduled
                </span>
                <Badge variant="secondary" className="text-xs">
                  {data.unscheduled.length}
                </Badge>
              </div>
              <Droppable droppableId={UNSCHEDULED_DROPPABLE} direction="vertical">
                {(provided, snapshot) => (
                  <div
                    ref={provided.innerRef}
                    {...provided.droppableProps}
                    className={cn(
                      "flex min-h-[200px] flex-1 flex-col gap-2 overflow-y-auto rounded-b-lg border border-t-0 p-2 transition-colors",
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
            {data.drivers.map((lane) => (
              <div key={lane.driver_id} className="flex w-72 shrink-0 flex-col">
                <DriverLane lane={lane} config={config} />
              </div>
            ))}

            {data.drivers.length === 0 && (
              <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
                No active drivers found. Add drivers in Delivery &amp; Logistics settings.
              </div>
            )}
          </div>
        </DragDropContext>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mobile List View Fallback
// ---------------------------------------------------------------------------

interface MobileViewProps {
  data: KanbanScheduleResponse;
  config: KanbanConfig;
}

function MobileView({ data, config }: MobileViewProps) {
  return (
    <div className="space-y-6">
      {/* Unscheduled */}
      {data.unscheduled.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-700">
            Unscheduled ({data.unscheduled.length})
          </h3>
          <div className="space-y-2">
            {data.unscheduled.map((card) => (
              <MobileCard key={card.delivery_id} card={card} config={config} />
            ))}
          </div>
        </div>
      )}

      {/* Driver sections */}
      {data.drivers
        .filter((d) => d.delivery_count > 0)
        .map((lane) => (
          <div key={lane.driver_id}>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-700">
              {lane.name}
              <Badge variant="secondary" className="text-xs">
                {lane.delivery_count}
              </Badge>
            </h3>
            <div className="space-y-2">
              {lane.deliveries.map((card, idx) => (
                <MobileCard
                  key={card.delivery_id}
                  card={card}
                  config={config}
                  sequence={idx + 1}
                />
              ))}
            </div>
          </div>
        ))}

      {data.unscheduled.length === 0 &&
        data.drivers.every((d) => d.delivery_count === 0) && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No funeral vault deliveries for this date.
          </p>
        )}
    </div>
  );
}

interface MobileCardProps {
  card: KanbanCard;
  config: KanbanConfig;
  sequence?: number;
}

function MobileCard({ card, config, sequence }: MobileCardProps) {
  return (
    <Card
      className={cn(
        "p-3",
        card.is_critical && "border-red-400 bg-red-50",
        card.is_warning && !card.is_critical && "border-amber-400 bg-amber-50",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          {sequence && (
            <span className="mr-2 text-xs font-bold text-slate-400">
              #{sequence}
            </span>
          )}
          {config.card_show_family_name && card.family_name && (
            <span className="text-sm font-semibold">{card.family_name}</span>
          )}
        </div>
        {config.card_show_service_time && card.service_time_display && (
          <Badge
            variant="outline"
            className={cn(
              "shrink-0 text-xs",
              card.is_critical
                ? "border-red-400 text-red-700"
                : card.is_warning
                  ? "border-amber-400 text-amber-700"
                  : "",
            )}
          >
            {card.service_time_display}
          </Badge>
        )}
      </div>
      <div className="mt-1 space-y-0.5 text-xs text-slate-600">
        {config.card_show_cemetery && card.cemetery_name && (
          <div>Cemetery: {card.cemetery_name}</div>
        )}
        {config.card_show_funeral_home && card.funeral_home_name && (
          <div>FH: {card.funeral_home_name}</div>
        )}
        {config.card_show_vault_type && card.vault_type && (
          <div>Vault: {card.vault_type}</div>
        )}
      </div>
    </Card>
  );
}
