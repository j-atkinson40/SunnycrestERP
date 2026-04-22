/**
 * AncillaryPanel v2 — 3-day rolling window + floating orders queue.
 *
 * Shows funeral-service-related orders that don't involve a cemetery burial
 * (drop-offs, pickups, supply deliveries). Scheduled orders are shown in a
 * rolling 3-day window with day sub-sections. Floating orders (no hard date)
 * appear in a separate holding queue below.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Package, X } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
      <div className="h-px flex-1 bg-border-subtle" />
      <span className="text-[10px] font-semibold uppercase tracking-wider text-content-subtle">
        {formatDayLabel(dateStr)}
      </span>
      <div className="h-px flex-1 bg-border-subtle" />
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
        className="text-[10px] text-content-subtle hover:text-content-base underline focus-ring-brass"
      >
        Move
      </button>
      {open && (
        <div className="absolute right-0 top-full z-20 mt-1 w-36 rounded-lg border border-border-subtle bg-surface-raised shadow-level-2">
          {otherDates.map((d) => (
            <button
              key={d}
              onClick={() => {
                onMove(d);
                setOpen(false);
              }}
              className="block w-full px-3 py-2 text-left text-xs text-content-base hover:bg-brass-subtle focus-ring-brass"
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
    <div className="rounded-lg border border-border-subtle bg-surface-elevated p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-semibold text-content-strong leading-tight">
          {card.funeral_home_name || "Unknown"}
        </span>
        <Badge variant="outline" className="shrink-0 text-[10px]">
          {card.order_type_label}
        </Badge>
      </div>
      {card.product_summary && (
        <p className="text-xs text-content-base">{card.product_summary}</p>
      )}
      {card.deceased_name && (
        <p className="text-xs text-content-muted">{card.deceased_name}</p>
      )}

      <div className="flex items-center gap-2 pt-1">
        <div className="relative">
          <button
            onClick={() => setShowDriverDropdown(!showDriverDropdown)}
            className="flex items-center gap-1 rounded border border-border-base bg-surface-sunken px-2.5 py-1 text-xs font-medium text-content-base transition-colors duration-quick ease-settle hover:bg-surface-elevated focus-ring-brass"
          >
            Assign to Driver
            <ChevronDown className="h-3 w-3" aria-hidden="true" />
          </button>
          {showDriverDropdown && (
            <div className="absolute left-0 top-full z-20 mt-1 w-48 rounded-lg border border-border-subtle bg-surface-raised shadow-level-2">
              {drivers.length === 0 ? (
                <div className="px-3 py-2 text-xs text-content-subtle">No drivers available</div>
              ) : (
                drivers.map((d) => (
                  <button
                    key={d.driver_id}
                    onClick={() => {
                      onAssign(card.delivery_id, d.driver_id);
                      setShowDriverDropdown(false);
                    }}
                    className="block w-full px-3 py-2 text-left text-xs text-content-base hover:bg-brass-subtle focus-ring-brass"
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
          className="rounded border border-border-base bg-surface-sunken px-2.5 py-1 text-xs font-medium text-content-base transition-colors duration-quick ease-settle hover:bg-surface-elevated focus-ring-brass"
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
    <div className="rounded-lg border border-border-subtle bg-surface-elevated p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-semibold text-content-strong leading-tight">
          {card.funeral_home_name || "Unknown"}
        </span>
        {/* Phase II Batch 1b — "Pickup" badge migrated from violet to
            info. Violet was ad-hoc (not in DL §3 palette); info
            semantic matches "awaiting / in progress" meaning. */}
        <Badge variant="info" className="shrink-0 text-[10px]">
          Pickup
        </Badge>
      </div>
      {card.product_summary && (
        <p className="text-xs text-content-base">{card.product_summary}</p>
      )}
      {card.deceased_name && (
        <p className="text-xs text-content-muted">{card.deceased_name}</p>
      )}
      {card.pickup_expected_by && (
        <p className={cn(
          "text-xs",
          overdue ? "text-status-warning font-medium" : "text-content-muted",
        )}>
          Expected: {formatTime(card.pickup_expected_by)}
          {overdue && " (overdue)"}
        </p>
      )}

      <div className="flex items-center justify-between pt-1">
        {!confirming ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setConfirming(true)}
            className="gap-1"
          >
            <Check className="h-3.5 w-3.5" aria-hidden="true" />
            Picked Up
          </Button>
        ) : (
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() => {
                onConfirmPickup(card.delivery_id);
                setConfirming(false);
              }}
            >
              Confirm
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirming(false)}
            >
              Cancel
            </Button>
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
    <div className="rounded-lg border border-border-subtle bg-surface-elevated p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-semibold text-content-strong leading-tight">
          {card.funeral_home_name || "Unknown"}
        </span>
        <Badge variant="outline" className="shrink-0 text-[10px]">
          {card.order_type_label}
        </Badge>
      </div>
      {card.product_summary && (
        <p className="text-xs text-content-base">{card.product_summary}</p>
      )}
      {card.deceased_name && (
        <p className="text-xs text-content-muted">{card.deceased_name}</p>
      )}

      <div className="flex items-center justify-between pt-1">
        {!confirming ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setConfirming(true)}
            className="gap-1"
          >
            <Check className="h-3.5 w-3.5" aria-hidden="true" />
            Delivered
          </Button>
        ) : (
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() => {
                onConfirmDelivered(card.delivery_id);
                setConfirming(false);
              }}
            >
              Confirm
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirming(false)}
            >
              Cancel
            </Button>
          </div>
        )}

        <div className="flex items-center gap-2">
          <div className="relative">
            <button
              onClick={() => setShowReassign(!showReassign)}
              className="text-[10px] text-content-subtle hover:text-content-base underline focus-ring-brass"
            >
              Reassign
            </button>
            {showReassign && (
              <div className="absolute right-0 top-full z-20 mt-1 w-48 rounded-lg border border-border-subtle bg-surface-raised shadow-level-2">
                {drivers.map((d) => (
                  <button
                    key={d.driver_id}
                    onClick={() => {
                      onReassign(card.delivery_id, d.driver_id);
                      setShowReassign(false);
                    }}
                    className="block w-full px-3 py-2 text-left text-xs text-content-base hover:bg-brass-subtle focus-ring-brass"
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
    <div className="rounded-lg border border-status-info bg-status-info-muted p-3 space-y-2">
      <p className="text-xs font-medium text-status-info">Funeral home pickup</p>
      <div className="space-y-1.5">
        <label className="text-[10px] text-content-muted">Expected by:</label>
        <input
          type="time"
          value={time}
          onChange={(e) => setTime(e.target.value)}
          className="block w-full rounded border border-border-base bg-surface-raised px-2 py-1 text-xs text-content-base focus-visible:border-brass focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brass/30"
        />
      </div>
      <div className="space-y-1.5">
        <label className="text-[10px] text-content-muted">Contact:</label>
        <input
          type="text"
          value={contact}
          onChange={(e) => setContact(e.target.value)}
          className="block w-full rounded border border-border-base bg-surface-raised px-2 py-1 text-xs text-content-base focus-visible:border-brass focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brass/30"
        />
      </div>
      <div className="flex gap-2 pt-1">
        <Button
          size="sm"
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
        >
          Confirm as Pickup
        </Button>
        <Button variant="outline" size="sm" onClick={onCancel}>
          Cancel
        </Button>
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
    <div className="rounded-lg border border-dashed border-border-base bg-surface-sunken/80 p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-semibold text-content-strong leading-tight">
          {card.funeral_home_name || "Unknown"}
        </span>
        <div className="flex items-center gap-1">
          <Badge variant="outline" className="shrink-0 text-[10px]">
            {card.order_type_label}
          </Badge>
          <Badge variant="warning" className="shrink-0 text-[10px]">
            Floating
          </Badge>
        </div>
      </div>
      {card.product_summary && (
        <p className="text-xs text-content-base">{card.product_summary}</p>
      )}
      {card.deceased_name && (
        <p className="text-xs text-content-muted">{card.deceased_name}</p>
      )}
      {card.ancillary_soft_target_date && (
        <p className="text-[10px] text-content-subtle">
          Soft target: {formatShortDate(card.ancillary_soft_target_date)}
        </p>
      )}

      {/* Combined driver + date picker for assign */}
      {!showAssign && !showPickupDate && (
        <div className="flex items-center gap-2 pt-1">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowAssign(true)}
          >
            Assign
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowPickupDate(true)}
          >
            Mark as Pickup
          </Button>
        </div>
      )}

      {showAssign && (
        <div className="rounded border border-status-info bg-status-info-muted p-2 space-y-2">
          <p className="text-[10px] font-medium text-status-info">Assign to driver + date</p>
          <select
            value={selectedDriver}
            onChange={(e) => setSelectedDriver(e.target.value)}
            className="block w-full rounded border border-border-base bg-surface-raised px-2 py-1 text-xs text-content-base focus-visible:border-brass focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brass/30"
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
            className="block w-full rounded border border-border-base bg-surface-raised px-2 py-1 text-xs text-content-base focus-visible:border-brass focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brass/30"
          >
            {windowDates.map((d) => (
              <option key={d} value={d}>
                {formatDayLabel(d)} ({formatShortDate(d)})
              </option>
            ))}
          </select>
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() => {
                if (!selectedDriver) {
                  toast.error("Select a driver");
                  return;
                }
                onAssignFloating(card.delivery_id, selectedDriver, selectedDate);
                setShowAssign(false);
              }}
            >
              Assign
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowAssign(false)}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}

      {showPickupDate && (
        <div className="rounded border border-status-info bg-status-info-muted p-2 space-y-2">
          <p className="text-[10px] font-medium text-status-info">Choose pickup date</p>
          <select
            value={pickupDate}
            onChange={(e) => setPickupDate(e.target.value)}
            className="block w-full rounded border border-border-base bg-surface-raised px-2 py-1 text-xs text-content-base focus-visible:border-brass focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brass/30"
          >
            {windowDates.map((d) => (
              <option key={d} value={d}>
                {formatDayLabel(d)} ({formatShortDate(d)})
              </option>
            ))}
          </select>
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() => {
                onFloatingMarkPickup(card.delivery_id, pickupDate);
                setShowPickupDate(false);
              }}
            >
              Confirm
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowPickupDate(false)}
            >
              Cancel
            </Button>
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
      <div className="flex items-center justify-between border-b border-border-subtle px-4 py-3">
        <div>
          <h3 className="text-sm font-bold text-content-strong">Ancillary Orders</h3>
          <p className="text-[11px] text-content-muted">
            {dateRange}
            {floatingCount > 0 && (
              <span className="ml-1 text-status-warning">
                + {floatingCount} floating
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {unresolvedCount > 0 && (
            <span className="rounded-full bg-status-warning-muted px-1.5 py-0.5 text-[10px] font-semibold text-status-warning">
              {unresolvedCount}
            </span>
          )}
          <button
            onClick={onToggleCollapse}
            className="rounded p-1 transition-colors duration-quick ease-settle hover:bg-surface-elevated focus-ring-brass"
            aria-label="Collapse ancillary panel"
          >
            <ChevronDown className="h-4 w-4 text-content-muted rotate-90" aria-hidden="true" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-4">
        {loading && !data ? (
          <div className="flex items-center justify-center py-8">
            <p className="text-xs text-content-subtle">Loading...</p>
          </div>
        ) : !hasAnyData ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <Package className="h-6 w-6 mb-2 text-content-subtle" aria-hidden="true" />
            <p className="text-xs text-content-subtle">No ancillary orders</p>
          </div>
        ) : (
          <>
            {/* ── SCHEDULED SECTION ── */}

            {/* Group 1: Needs Action */}
            {data!.needs_action.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <h4 className="text-[10px] font-bold uppercase tracking-wider text-content-muted">
                    Needs Action
                  </h4>
                  <Badge variant="error" className="text-[10px] px-1.5 py-0">
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
                  <h4 className="text-[10px] font-bold uppercase tracking-wider text-content-muted">
                    Awaiting Pickup
                  </h4>
                  <Badge variant="info" className="text-[10px] px-1.5 py-0">
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
                  <h4 className="text-[10px] font-bold uppercase tracking-wider text-content-muted">
                    With Drivers
                  </h4>
                  <Badge variant="info" className="text-[10px] px-1.5 py-0">
                    {data!.stats.assigned}
                  </Badge>
                </div>
                {data!.assigned_groups.map((group) => (
                  <div key={group.driver_id} className="space-y-1.5">
                    <p className="text-xs font-semibold text-content-base">
                      {group.driver_name}{" "}
                      <span className="font-normal text-content-subtle">
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
                  className="flex w-full items-center justify-between rounded-lg bg-surface-sunken px-3 py-1.5 text-[11px] font-medium text-content-muted transition-colors duration-quick ease-settle hover:bg-surface-elevated hover:text-content-strong focus-ring-brass"
                >
                  <span>Show completed ({data!.completed.length})</span>
                  <span>{showCompleted ? "\u25B4" : "\u25BE"}</span>
                </button>
                {showCompleted && (
                  <div className="space-y-0.5 pt-1">
                    {data!.completed.map((card) => (
                      <div key={card.delivery_id} className="flex items-center gap-2 rounded px-2 py-1 text-[11px] text-content-subtle">
                        <Check className="h-3 w-3 text-status-success shrink-0" aria-hidden="true" />
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
              <div className="space-y-2 border-t border-status-warning/30 pt-3">
                <div className="flex items-center gap-2">
                  <h4 className="text-[10px] font-bold uppercase tracking-wider text-status-warning">
                    Floating Orders
                  </h4>
                  {data!.floating.length > 0 && (
                    <Badge variant="warning" className="text-[10px] px-1.5 py-0">
                      {data!.floating.length}
                    </Badge>
                  )}
                </div>
                <p className="text-[10px] text-content-subtle">
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
                      className="flex w-full items-center justify-between rounded-lg bg-status-warning-muted px-3 py-1.5 text-[11px] font-medium text-status-warning transition-colors duration-quick ease-settle hover:brightness-95 focus-ring-brass"
                    >
                      <span>Completed floating ({data!.floating_completed.length})</span>
                      <span>{showFloatingCompleted ? "\u25B4" : "\u25BE"}</span>
                    </button>
                    {showFloatingCompleted && (
                      <div className="space-y-0.5 pt-1">
                        {data!.floating_completed.map((card) => (
                          <div key={card.delivery_id} className="flex items-center gap-2 rounded px-2 py-1 text-[11px] text-content-subtle">
                            <Check className="h-3 w-3 text-status-success shrink-0" aria-hidden="true" />
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
      className="fixed bottom-20 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2 rounded-full bg-surface-raised border border-border-base px-4 py-2 shadow-level-2 transition-colors duration-quick ease-settle hover:bg-surface-elevated focus-ring-brass"
    >
      <Package className="h-4 w-4 text-content-muted" aria-hidden="true" />
      <span className="text-xs font-medium text-content-base">Ancillary</span>
      {unresolvedCount > 0 && (
        <span className="rounded-full bg-status-warning-muted px-1.5 py-0.5 text-[10px] font-semibold text-status-warning">
          {unresolvedCount}
        </span>
      )}
      {floatingCount > 0 && (
        <span className="text-[10px] text-status-warning">
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
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="absolute bottom-0 left-0 right-0 max-h-[70vh] overflow-y-auto rounded-t-2xl bg-surface-raised shadow-level-3 animate-in slide-in-from-bottom duration-200">
        <div className="sticky top-0 flex items-center justify-between border-b border-border-subtle bg-surface-raised px-4 py-3">
          <h3 className="text-sm font-bold text-content-strong">Ancillary Orders</h3>
          <button
            onClick={onClose}
            className="rounded p-1 transition-colors duration-quick ease-settle hover:bg-surface-elevated focus-ring-brass"
            aria-label="Close drawer"
          >
            <X className="h-5 w-5 text-content-muted" aria-hidden="true" />
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
