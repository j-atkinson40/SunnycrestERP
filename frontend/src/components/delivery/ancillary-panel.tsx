/**
 * AncillaryPanel v2 — 3-day rolling window + floating orders queue.
 *
 * Shows funeral-service-related orders that don't involve a cemetery burial
 * (drop-offs, pickups, supply deliveries). Scheduled orders are shown in a
 * rolling 3-day window with day sub-sections. Floating orders (no hard date)
 * appear in a separate holding queue below.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import api from "@/lib/api-client";
import type {
  AncillaryCard,
  AncillaryAvailableDriver,
  AncillaryDayGroup,
  AncillaryOrdersResponse,
} from "@/types/delivery";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface AncillaryPanelProps {
  anchorDate: string;
  /** The 3 delivery-day dates (computed by scheduling board via getNextDeliveryDay) */
  windowDates: string[];
  collapsed: boolean;
  onToggleCollapse: () => void;
}

// ---------------------------------------------------------------------------
// Date helpers
// ---------------------------------------------------------------------------

function formatTime(isoStr: string | null): string {
  if (!isoStr) return "";
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  } catch {
    return "";
  }
}

function isOverdue(expectedBy: string | null): boolean {
  if (!expectedBy) return false;
  return new Date(expectedBy) < new Date();
}

function formatDayLabel(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00");
  const today = new Date();
  const todayStr = today.toISOString().split("T")[0];
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const tomorrowStr = tomorrow.toISOString().split("T")[0];

  if (dateStr === todayStr) return "Today";
  if (dateStr === tomorrowStr) return "Tomorrow";
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

function formatShortDate(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatHeaderDateRange(windowDates: string[]): string {
  if (windowDates.length === 0) return "";
  const first = new Date(windowDates[0] + "T12:00:00");
  const last = new Date(windowDates[windowDates.length - 1] + "T12:00:00");
  const f = first.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  const l = last.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  return `${f} \u2013 ${l}`;
}

// ---------------------------------------------------------------------------
// DaySectionHeader
// ---------------------------------------------------------------------------

function DaySectionHeader({ dateStr }: { dateStr: string }) {
  return (
    <div className="flex items-center gap-2 pt-1 pb-0.5">
      <div className="h-px flex-1 bg-slate-200" />
      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
        {formatDayLabel(dateStr)}
      </span>
      <div className="h-px flex-1 bg-slate-200" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// MoveDropdown — shift scheduled orders between days in the window
// ---------------------------------------------------------------------------

function MoveDropdown({
  currentDate,
  windowDates,
  onMove,
}: {
  currentDate: string | null;
  windowDates: string[];
  onMove: (newDate: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const otherDates = windowDates.filter((d) => d !== currentDate);

  if (otherDates.length === 0) return null;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="text-[10px] text-slate-400 hover:text-slate-600 underline"
      >
        Move
      </button>
      {open && (
        <div className="absolute right-0 top-full z-20 mt-1 w-36 rounded-lg border bg-white shadow-lg">
          {otherDates.map((d) => (
            <button
              key={d}
              onClick={() => {
                onMove(d);
                setOpen(false);
              }}
              className="block w-full px-3 py-2 text-left text-xs text-slate-700 hover:bg-slate-50"
            >
              {formatDayLabel(d)} ({formatShortDate(d)})
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// NeedsActionCard
// ---------------------------------------------------------------------------

function NeedsActionCard({
  card,
  drivers,
  windowDates,
  onAssign,
  onMarkPickup,
  onMove,
}: {
  card: AncillaryCard;
  drivers: AncillaryAvailableDriver[];
  windowDates: string[];
  onAssign: (deliveryId: string, driverId: string) => void;
  onMarkPickup: (deliveryId: string) => void;
  onMove: (deliveryId: string, newDate: string) => void;
}) {
  const [showDriverDropdown, setShowDriverDropdown] = useState(false);

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-semibold text-slate-900 leading-tight">
          {card.funeral_home_name || "Unknown"}
        </span>
        <Badge variant="outline" className="shrink-0 text-[10px] border-slate-300 text-slate-600">
          {card.order_type_label}
        </Badge>
      </div>
      {card.product_summary && (
        <p className="text-xs text-slate-600">{card.product_summary}</p>
      )}
      {card.deceased_name && (
        <p className="text-xs text-slate-500">{card.deceased_name}</p>
      )}

      <div className="flex items-center gap-2 pt-1">
        <div className="relative">
          <button
            onClick={() => setShowDriverDropdown(!showDriverDropdown)}
            className="rounded border border-slate-300 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 transition-colors"
          >
            Assign to Driver &#9662;
          </button>
          {showDriverDropdown && (
            <div className="absolute left-0 top-full z-20 mt-1 w-48 rounded-lg border bg-white shadow-lg">
              {drivers.length === 0 ? (
                <div className="px-3 py-2 text-xs text-slate-400">No drivers available</div>
              ) : (
                drivers.map((d) => (
                  <button
                    key={d.driver_id}
                    onClick={() => {
                      onAssign(card.delivery_id, d.driver_id);
                      setShowDriverDropdown(false);
                    }}
                    className="block w-full px-3 py-2 text-left text-xs text-slate-700 hover:bg-slate-50"
                  >
                    {d.name}
                  </button>
                ))
              )}
            </div>
          )}
        </div>
        <button
          onClick={() => onMarkPickup(card.delivery_id)}
          className="rounded border border-slate-300 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 transition-colors"
        >
          Mark as Pickup
        </button>
        <MoveDropdown
          currentDate={card.requested_date}
          windowDates={windowDates}
          onMove={(newDate) => onMove(card.delivery_id, newDate)}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AwaitingPickupCard
// ---------------------------------------------------------------------------

function AwaitingPickupCard({
  card,
  windowDates,
  onConfirmPickup,
  onMove,
}: {
  card: AncillaryCard;
  windowDates: string[];
  onConfirmPickup: (deliveryId: string) => void;
  onMove: (deliveryId: string, newDate: string) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const overdue = isOverdue(card.pickup_expected_by);

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-semibold text-slate-900 leading-tight">
          {card.funeral_home_name || "Unknown"}
        </span>
        <Badge variant="outline" className="shrink-0 text-[10px] border-violet-300 text-violet-600">
          Pickup
        </Badge>
      </div>
      {card.product_summary && (
        <p className="text-xs text-slate-600">{card.product_summary}</p>
      )}
      {card.deceased_name && (
        <p className="text-xs text-slate-500">{card.deceased_name}</p>
      )}
      {card.pickup_expected_by && (
        <p className={cn(
          "text-xs",
          overdue ? "text-amber-600 font-medium" : "text-slate-500",
        )}>
          Expected: {formatTime(card.pickup_expected_by)}
          {overdue && " (overdue)"}
        </p>
      )}

      <div className="flex items-center justify-between pt-1">
        {!confirming ? (
          <button
            onClick={() => setConfirming(true)}
            className="rounded border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100 transition-colors"
          >
            Picked Up
          </button>
        ) : (
          <div className="flex gap-2">
            <button
              onClick={() => {
                onConfirmPickup(card.delivery_id);
                setConfirming(false);
              }}
              className="rounded bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-700"
            >
              Confirm
            </button>
            <button
              onClick={() => setConfirming(false)}
              className="rounded border px-3 py-1 text-xs text-slate-600 hover:bg-slate-50"
            >
              Cancel
            </button>
          </div>
        )}
        <MoveDropdown
          currentDate={card.requested_date}
          windowDates={windowDates}
          onMove={(newDate) => onMove(card.delivery_id, newDate)}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AssignedCard
// ---------------------------------------------------------------------------

function AssignedCard({
  card,
  drivers,
  windowDates,
  onConfirmDelivered,
  onReassign,
  onMove,
}: {
  card: AncillaryCard;
  drivers: AncillaryAvailableDriver[];
  windowDates: string[];
  onConfirmDelivered: (deliveryId: string) => void;
  onReassign: (deliveryId: string, driverId: string) => void;
  onMove: (deliveryId: string, newDate: string) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [showReassign, setShowReassign] = useState(false);

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-semibold text-slate-900 leading-tight">
          {card.funeral_home_name || "Unknown"}
        </span>
        <Badge variant="outline" className="shrink-0 text-[10px] border-slate-300 text-slate-600">
          {card.order_type_label}
        </Badge>
      </div>
      {card.product_summary && (
        <p className="text-xs text-slate-600">{card.product_summary}</p>
      )}
      {card.deceased_name && (
        <p className="text-xs text-slate-500">{card.deceased_name}</p>
      )}

      <div className="flex items-center justify-between pt-1">
        {!confirming ? (
          <button
            onClick={() => setConfirming(true)}
            className="rounded border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100 transition-colors"
          >
            Delivered
          </button>
        ) : (
          <div className="flex gap-2">
            <button
              onClick={() => {
                onConfirmDelivered(card.delivery_id);
                setConfirming(false);
              }}
              className="rounded bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-700"
            >
              Confirm
            </button>
            <button
              onClick={() => setConfirming(false)}
              className="rounded border px-3 py-1 text-xs text-slate-600 hover:bg-slate-50"
            >
              Cancel
            </button>
          </div>
        )}

        <div className="flex items-center gap-2">
          <div className="relative">
            <button
              onClick={() => setShowReassign(!showReassign)}
              className="text-[10px] text-slate-400 hover:text-slate-600 underline"
            >
              Reassign
            </button>
            {showReassign && (
              <div className="absolute right-0 top-full z-20 mt-1 w-48 rounded-lg border bg-white shadow-lg">
                {drivers.map((d) => (
                  <button
                    key={d.driver_id}
                    onClick={() => {
                      onReassign(card.delivery_id, d.driver_id);
                      setShowReassign(false);
                    }}
                    className="block w-full px-3 py-2 text-left text-xs text-slate-700 hover:bg-slate-50"
                  >
                    {d.name}
                  </button>
                ))}
              </div>
            )}
          </div>
          <MoveDropdown
            currentDate={card.requested_date}
            windowDates={windowDates}
            onMove={(newDate) => onMove(card.delivery_id, newDate)}
          />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// MarkPickupInline
// ---------------------------------------------------------------------------

function MarkPickupInline({
  deliveryId,
  onConfirm,
  onCancel,
}: {
  deliveryId: string;
  onConfirm: (deliveryId: string, expectedBy: string | null, contact: string) => void;
  onCancel: () => void;
}) {
  const [time, setTime] = useState("");
  const [contact, setContact] = useState("");

  return (
    <div className="rounded-lg border border-violet-200 bg-violet-50 p-3 space-y-2">
      <p className="text-xs font-medium text-violet-700">Funeral home pickup</p>
      <div className="space-y-1.5">
        <label className="text-[10px] text-slate-500">Expected by:</label>
        <input
          type="time"
          value={time}
          onChange={(e) => setTime(e.target.value)}
          className="block w-full rounded border px-2 py-1 text-xs"
        />
      </div>
      <div className="space-y-1.5">
        <label className="text-[10px] text-slate-500">Contact:</label>
        <input
          type="text"
          value={contact}
          onChange={(e) => setContact(e.target.value)}
          className="block w-full rounded border px-2 py-1 text-xs"
        />
      </div>
      <div className="flex gap-2 pt-1">
        <button
          onClick={() => {
            let expectedBy: string | null = null;
            if (time) {
              const today = new Date();
              const [h, m] = time.split(":");
              today.setHours(parseInt(h, 10), parseInt(m, 10), 0, 0);
              expectedBy = today.toISOString();
            }
            onConfirm(deliveryId, expectedBy, contact);
          }}
          className="rounded bg-violet-600 px-3 py-1 text-xs font-medium text-white hover:bg-violet-700"
        >
          Confirm as Pickup
        </button>
        <button
          onClick={onCancel}
          className="rounded border px-3 py-1 text-xs text-slate-600 hover:bg-slate-50"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// FloatingCard — card in the floating queue
// ---------------------------------------------------------------------------

function FloatingCard({
  card,
  drivers,
  windowDates,
  onAssignFloating,
  onFloatingMarkPickup,
}: {
  card: AncillaryCard;
  drivers: AncillaryAvailableDriver[];
  windowDates: string[];
  onAssignFloating: (deliveryId: string, driverId: string, deliveryDate: string) => void;
  onFloatingMarkPickup: (deliveryId: string, deliveryDate: string) => void;
}) {
  const [showAssign, setShowAssign] = useState(false);
  const [selectedDriver, setSelectedDriver] = useState("");
  const [selectedDate, setSelectedDate] = useState(windowDates[0] || "");
  const [showPickupDate, setShowPickupDate] = useState(false);
  const [pickupDate, setPickupDate] = useState(windowDates[0] || "");

  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50/80 p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-semibold text-slate-900 leading-tight">
          {card.funeral_home_name || "Unknown"}
        </span>
        <div className="flex items-center gap-1">
          <Badge variant="outline" className="shrink-0 text-[10px] border-slate-300 text-slate-500">
            {card.order_type_label}
          </Badge>
          <Badge variant="outline" className="shrink-0 text-[10px] border-amber-300 text-amber-600 bg-amber-50">
            Floating
          </Badge>
        </div>
      </div>
      {card.product_summary && (
        <p className="text-xs text-slate-600">{card.product_summary}</p>
      )}
      {card.deceased_name && (
        <p className="text-xs text-slate-500">{card.deceased_name}</p>
      )}
      {card.ancillary_soft_target_date && (
        <p className="text-[10px] text-slate-400">
          Soft target: {formatShortDate(card.ancillary_soft_target_date)}
        </p>
      )}

      {/* Combined driver + date picker for assign */}
      {!showAssign && !showPickupDate && (
        <div className="flex items-center gap-2 pt-1">
          <button
            onClick={() => setShowAssign(true)}
            className="rounded border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 transition-colors"
          >
            Assign
          </button>
          <button
            onClick={() => setShowPickupDate(true)}
            className="rounded border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 transition-colors"
          >
            Mark as Pickup
          </button>
        </div>
      )}

      {showAssign && (
        <div className="rounded border border-blue-200 bg-blue-50 p-2 space-y-2">
          <p className="text-[10px] font-medium text-blue-700">Assign to driver + date</p>
          <select
            value={selectedDriver}
            onChange={(e) => setSelectedDriver(e.target.value)}
            className="block w-full rounded border px-2 py-1 text-xs"
          >
            <option value="">Select driver...</option>
            {drivers.map((d) => (
              <option key={d.driver_id} value={d.driver_id}>
                {d.name}
              </option>
            ))}
          </select>
          <select
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="block w-full rounded border px-2 py-1 text-xs"
          >
            {windowDates.map((d) => (
              <option key={d} value={d}>
                {formatDayLabel(d)} ({formatShortDate(d)})
              </option>
            ))}
          </select>
          <div className="flex gap-2">
            <button
              onClick={() => {
                if (!selectedDriver) {
                  toast.error("Select a driver");
                  return;
                }
                onAssignFloating(card.delivery_id, selectedDriver, selectedDate);
                setShowAssign(false);
              }}
              className="rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700"
            >
              Assign
            </button>
            <button
              onClick={() => setShowAssign(false)}
              className="rounded border px-3 py-1 text-xs text-slate-600 hover:bg-slate-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {showPickupDate && (
        <div className="rounded border border-violet-200 bg-violet-50 p-2 space-y-2">
          <p className="text-[10px] font-medium text-violet-700">Choose pickup date</p>
          <select
            value={pickupDate}
            onChange={(e) => setPickupDate(e.target.value)}
            className="block w-full rounded border px-2 py-1 text-xs"
          >
            {windowDates.map((d) => (
              <option key={d} value={d}>
                {formatDayLabel(d)} ({formatShortDate(d)})
              </option>
            ))}
          </select>
          <div className="flex gap-2">
            <button
              onClick={() => {
                onFloatingMarkPickup(card.delivery_id, pickupDate);
                setShowPickupDate(false);
              }}
              className="rounded bg-violet-600 px-3 py-1 text-xs font-medium text-white hover:bg-violet-700"
            >
              Confirm
            </button>
            <button
              onClick={() => setShowPickupDate(false)}
              className="rounded border px-3 py-1 text-xs text-slate-600 hover:bg-slate-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// DayGroupedCards — renders cards grouped by date within a status section
// ---------------------------------------------------------------------------

function DayGroupedCards({
  dayGroups,
  renderCard,
}: {
  dayGroups: AncillaryDayGroup[];
  renderCard: (card: AncillaryCard) => React.ReactNode;
}) {
  if (dayGroups.length === 0) return null;
  // If only one day, skip the sub-section header
  const skipHeaders = dayGroups.length === 1;

  return (
    <div className="space-y-1.5">
      {dayGroups.map((group) => (
        <div key={group.date} className="space-y-1.5">
          {!skipHeaders && <DaySectionHeader dateStr={group.date} />}
          {group.cards.map((card) => (
            <div key={card.delivery_id}>{renderCard(card)}</div>
          ))}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main AncillaryPanel
// ---------------------------------------------------------------------------

export function AncillaryPanel({
  anchorDate,
  windowDates,
  collapsed,
  onToggleCollapse,
}: AncillaryPanelProps) {
  const [data, setData] = useState<AncillaryOrdersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [pickupFormId, setPickupFormId] = useState<string | null>(null);
  const [showCompleted, setShowCompleted] = useState(false);
  const [showFloatingCompleted, setShowFloatingCompleted] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch data
  const fetchData = useCallback(async (showLoading = true) => {
    if (!anchorDate) return;
    if (showLoading) setLoading(true);
    try {
      const params: Record<string, string> = {
        date: anchorDate,
        include_completed: "true",
      };
      if (windowDates.length >= 3) {
        params.day1 = windowDates[0];
        params.day2 = windowDates[1];
        params.day3 = windowDates[2];
      }
      const resp = await api.get<AncillaryOrdersResponse>(
        "/api/v1/extensions/funeral-kanban/ancillary",
        { params },
      );
      setData(resp.data);
    } catch {
      // Silent fail on poll
    } finally {
      setLoading(false);
    }
  }, [anchorDate, windowDates]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Poll every 60s
  useEffect(() => {
    pollRef.current = setInterval(() => fetchData(false), 60_000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [fetchData]);

  // --- Actions ---

  const handleAssign = useCallback(async (deliveryId: string, driverId: string) => {
    try {
      await api.post(`/api/v1/extensions/funeral-kanban/ancillary/${deliveryId}/assign`, {
        driver_id: driverId,
      });
      toast.success("Assigned to driver");
      fetchData(false);
    } catch {
      toast.error("Failed to assign");
    }
  }, [fetchData]);

  const handleMarkPickup = useCallback(async (
    deliveryId: string,
    expectedBy: string | null,
    contact: string,
  ) => {
    try {
      await api.post(`/api/v1/extensions/funeral-kanban/ancillary/${deliveryId}/mark-pickup`, {
        expected_by: expectedBy,
        contact: contact || null,
      });
      toast.success("Marked as pickup");
      setPickupFormId(null);
      fetchData(false);
    } catch {
      toast.error("Failed to update");
    }
  }, [fetchData]);

  const handleConfirmPickup = useCallback(async (deliveryId: string) => {
    try {
      await api.post(`/api/v1/extensions/funeral-kanban/ancillary/${deliveryId}/confirm-pickup`, {});
      toast.success("Pickup confirmed");
      fetchData(false);
    } catch {
      toast.error("Failed to confirm");
    }
  }, [fetchData]);

  const handleConfirmDelivered = useCallback(async (deliveryId: string) => {
    try {
      await api.post(`/api/v1/extensions/funeral-kanban/ancillary/${deliveryId}/confirm-delivered`);
      toast.success("Delivery confirmed");
      fetchData(false);
    } catch {
      toast.error("Failed to confirm");
    }
  }, [fetchData]);

  const handleReassign = useCallback(async (deliveryId: string, driverId: string) => {
    try {
      await api.post(`/api/v1/extensions/funeral-kanban/ancillary/${deliveryId}/reassign`, {
        driver_id: driverId,
      });
      toast.success("Reassigned");
      fetchData(false);
    } catch {
      toast.error("Failed to reassign");
    }
  }, [fetchData]);

  const handleMove = useCallback(async (deliveryId: string, newDate: string) => {
    try {
      await api.post(`/api/v1/extensions/funeral-kanban/ancillary/${deliveryId}/move`, {
        new_date: newDate,
      });
      toast.success(`Moved to ${formatDayLabel(newDate)}`);
      fetchData(false);
    } catch {
      toast.error("Failed to move");
    }
  }, [fetchData]);

  const handleAssignFloating = useCallback(async (
    deliveryId: string,
    driverId: string,
    deliveryDate: string,
  ) => {
    try {
      await api.post(`/api/v1/extensions/funeral-kanban/ancillary/${deliveryId}/assign-floating`, {
        driver_id: driverId,
        delivery_date: deliveryDate,
      });
      toast.success("Floating order assigned");
      fetchData(false);
    } catch {
      toast.error("Failed to assign floating order");
    }
  }, [fetchData]);

  const handleFloatingMarkPickup = useCallback(async (
    deliveryId: string,
    deliveryDate: string,
  ) => {
    try {
      await api.post(`/api/v1/extensions/funeral-kanban/ancillary/${deliveryId}/floating-mark-pickup`, {
        delivery_date: deliveryDate,
      });
      toast.success("Floating order marked as pickup");
      fetchData(false);
    } catch {
      toast.error("Failed to update");
    }
  }, [fetchData]);

  const unresolvedCount = data?.stats.unresolved ?? 0;
  const floatingCount = data?.stats.floating_unresolved ?? 0;
  const drivers = data?.available_drivers ?? [];

  // ── Collapsed view ──
  if (collapsed) {
    return null; // Parent handles collapsed rendering
  }

  const dateRange = formatHeaderDateRange(windowDates);
  const hasAnyData = data && data.stats.total > 0;

  return (
    <div className="flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div>
          <h3 className="text-sm font-bold text-slate-900">Ancillary Orders</h3>
          <p className="text-[11px] text-slate-500">
            {dateRange}
            {floatingCount > 0 && (
              <span className="ml-1 text-amber-600">
                + {floatingCount} floating
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {unresolvedCount > 0 && (
            <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">
              {unresolvedCount}
            </span>
          )}
          <button
            onClick={onToggleCollapse}
            className="rounded p-1 hover:bg-slate-200 transition-colors"
            aria-label="Collapse ancillary panel"
          >
            <svg className="h-4 w-4 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="m15 18-6-6 6-6" />
            </svg>
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-4">
        {loading && !data ? (
          <div className="flex items-center justify-center py-8">
            <p className="text-xs text-slate-400">Loading...</p>
          </div>
        ) : !hasAnyData ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="text-2xl mb-2">&#128230;</div>
            <p className="text-xs text-slate-400">No ancillary orders</p>
          </div>
        ) : (
          <>
            {/* ── SCHEDULED SECTION ── */}

            {/* Group 1: Needs Action */}
            {data!.needs_action.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Needs Action
                  </h4>
                  <Badge variant="destructive" className="text-[10px] px-1.5 py-0">
                    {data!.needs_action.length}
                  </Badge>
                </div>
                <DayGroupedCards
                  dayGroups={data!.needs_action_by_day}
                  renderCard={(card) =>
                    pickupFormId === card.delivery_id ? (
                      <MarkPickupInline
                        deliveryId={card.delivery_id}
                        onConfirm={handleMarkPickup}
                        onCancel={() => setPickupFormId(null)}
                      />
                    ) : (
                      <NeedsActionCard
                        card={card}
                        drivers={drivers}
                        windowDates={windowDates}
                        onAssign={handleAssign}
                        onMarkPickup={(id) => setPickupFormId(id)}
                        onMove={handleMove}
                      />
                    )
                  }
                />
              </div>
            )}

            {/* Group 2: Awaiting Pickup */}
            {data!.awaiting_pickup.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Awaiting Pickup
                  </h4>
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-violet-300 text-violet-600">
                    {data!.awaiting_pickup.length}
                  </Badge>
                </div>
                <DayGroupedCards
                  dayGroups={data!.awaiting_pickup_by_day}
                  renderCard={(card) => (
                    <AwaitingPickupCard
                      card={card}
                      windowDates={windowDates}
                      onConfirmPickup={handleConfirmPickup}
                      onMove={handleMove}
                    />
                  )}
                />
              </div>
            )}

            {/* Group 3: With Drivers */}
            {data!.assigned_groups.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    With Drivers
                  </h4>
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-blue-300 text-blue-600">
                    {data!.stats.assigned}
                  </Badge>
                </div>
                {data!.assigned_groups.map((group) => (
                  <div key={group.driver_id} className="space-y-1.5">
                    <p className="text-xs font-semibold text-slate-700">
                      {group.driver_name}{" "}
                      <span className="font-normal text-slate-400">
                        ({group.item_count} item{group.item_count !== 1 ? "s" : ""})
                      </span>
                    </p>
                    <DayGroupedCards
                      dayGroups={group.items_by_day}
                      renderCard={(card) => (
                        <AssignedCard
                          card={card}
                          drivers={drivers}
                          windowDates={windowDates}
                          onConfirmDelivered={handleConfirmDelivered}
                          onReassign={handleReassign}
                          onMove={handleMove}
                        />
                      )}
                    />
                  </div>
                ))}
              </div>
            )}

            {/* Completed toggle */}
            {data!.completed.length > 0 && (
              <div className="space-y-1">
                <button
                  onClick={() => setShowCompleted(!showCompleted)}
                  className="flex w-full items-center justify-between rounded-lg bg-slate-100 px-3 py-1.5 text-[11px] font-medium text-slate-500 hover:bg-slate-200 transition-colors"
                >
                  <span>Show completed ({data!.completed.length})</span>
                  <span>{showCompleted ? "\u25B4" : "\u25BE"}</span>
                </button>
                {showCompleted && (
                  <div className="space-y-0.5 pt-1">
                    {data!.completed.map((card) => (
                      <div key={card.delivery_id} className="flex items-center gap-2 rounded px-2 py-1 text-[11px] text-slate-400">
                        <span className="text-emerald-500">&#10003;</span>
                        <span className="flex-1 truncate">
                          {card.funeral_home_name} — {card.product_summary || card.order_type_label}
                        </span>
                        <span className="shrink-0">{formatTime(card.completed_at)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ── FLOATING SECTION ── */}
            {(data!.floating.length > 0 || data!.floating_completed.length > 0) && (
              <div className="space-y-2 border-t border-amber-200 pt-3">
                <div className="flex items-center gap-2">
                  <h4 className="text-[10px] font-bold uppercase tracking-wider text-amber-600">
                    Floating Orders
                  </h4>
                  {data!.floating.length > 0 && (
                    <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-amber-300 text-amber-600 bg-amber-50">
                      {data!.floating.length}
                    </Badge>
                  )}
                </div>
                <p className="text-[10px] text-slate-400">
                  No hard delivery date — assign to schedule
                </p>

                {data!.floating.map((card) => (
                  <FloatingCard
                    key={card.delivery_id}
                    card={card}
                    drivers={drivers}
                    windowDates={windowDates}
                    onAssignFloating={handleAssignFloating}
                    onFloatingMarkPickup={handleFloatingMarkPickup}
                  />
                ))}

                {data!.floating_completed.length > 0 && (
                  <div className="space-y-1">
                    <button
                      onClick={() => setShowFloatingCompleted(!showFloatingCompleted)}
                      className="flex w-full items-center justify-between rounded-lg bg-amber-50 px-3 py-1.5 text-[11px] font-medium text-amber-600 hover:bg-amber-100 transition-colors"
                    >
                      <span>Completed floating ({data!.floating_completed.length})</span>
                      <span>{showFloatingCompleted ? "\u25B4" : "\u25BE"}</span>
                    </button>
                    {showFloatingCompleted && (
                      <div className="space-y-0.5 pt-1">
                        {data!.floating_completed.map((card) => (
                          <div key={card.delivery_id} className="flex items-center gap-2 rounded px-2 py-1 text-[11px] text-slate-400">
                            <span className="text-emerald-500">&#10003;</span>
                            <span className="flex-1 truncate">
                              {card.funeral_home_name} — {card.product_summary || card.order_type_label}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mobile Pill + Drawer
// ---------------------------------------------------------------------------

export function AncillaryMobilePill({
  unresolvedCount,
  floatingCount,
  onClick,
}: {
  unresolvedCount: number;
  floatingCount: number;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="fixed bottom-20 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2 rounded-full bg-white border border-slate-300 px-4 py-2 shadow-lg hover:bg-slate-50 transition-colors"
    >
      <span className="text-sm">&#128230;</span>
      <span className="text-xs font-medium text-slate-700">Ancillary</span>
      {unresolvedCount > 0 && (
        <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">
          {unresolvedCount}
        </span>
      )}
      {floatingCount > 0 && (
        <span className="text-[10px] text-amber-600">
          {floatingCount} floating
        </span>
      )}
    </button>
  );
}

export function AncillaryDrawer({
  anchorDate,
  windowDates,
  open,
  onClose,
}: {
  anchorDate: string;
  windowDates: string[];
  open: boolean;
  onClose: () => void;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0 bg-black/20" onClick={onClose} />
      <div className="absolute bottom-0 left-0 right-0 max-h-[70vh] overflow-y-auto rounded-t-2xl bg-white shadow-2xl animate-in slide-in-from-bottom duration-200">
        <div className="sticky top-0 flex items-center justify-between border-b bg-white px-4 py-3">
          <h3 className="text-sm font-bold text-slate-900">Ancillary Orders</h3>
          <button onClick={onClose} className="rounded p-1 hover:bg-slate-100">
            <svg className="h-5 w-5 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="px-1 pb-8">
          <AncillaryPanel
            anchorDate={anchorDate}
            windowDates={windowDates}
            collapsed={false}
            onToggleCollapse={onClose}
          />
        </div>
      </div>
    </div>
  );
}
