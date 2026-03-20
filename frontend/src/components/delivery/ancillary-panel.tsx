/**
 * AncillaryPanel — side panel for ancillary orders on the Scheduling Board.
 *
 * Shows funeral-service-related orders that don't involve a cemetery burial
 * (drop-offs, pickups, supply deliveries). Grouped into three status sections
 * plus a collapsible completed section.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import api from "@/lib/api-client";
import type {
  AncillaryCard,
  AncillaryDriverGroup,
  AncillaryAvailableDriver,
  AncillaryOrdersResponse,
} from "@/types/delivery";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface AncillaryPanelProps {
  dateStr: string;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
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

function formatCompletedTime(isoStr: string | null): string {
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

function formatPanelDate(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00");
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

// ---------------------------------------------------------------------------
// NeedsActionCard
// ---------------------------------------------------------------------------

function NeedsActionCard({
  card,
  drivers,
  onAssign,
  onMarkPickup,
}: {
  card: AncillaryCard;
  drivers: AncillaryAvailableDriver[];
  onAssign: (deliveryId: string, driverId: string) => void;
  onMarkPickup: (deliveryId: string) => void;
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
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AwaitingPickupCard
// ---------------------------------------------------------------------------

function AwaitingPickupCard({
  card,
  onConfirmPickup,
}: {
  card: AncillaryCard;
  onConfirmPickup: (deliveryId: string) => void;
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
          &#9742; Pickup
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
          overdue ? "text-amber-600 font-medium animate-pulse" : "text-slate-500",
        )}>
          Expected: {formatTime(card.pickup_expected_by)}
          {overdue && " \u26A0\uFE0F"}
        </p>
      )}

      {!confirming ? (
        <button
          onClick={() => setConfirming(true)}
          className="mt-1 rounded border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100 transition-colors"
        >
          &#10003; Picked Up
        </button>
      ) : (
        <div className="mt-1 rounded border border-emerald-200 bg-emerald-50 p-2 space-y-2">
          <p className="text-xs text-emerald-700">
            Confirm pickup by {card.funeral_home_name}?
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => {
                onConfirmPickup(card.delivery_id);
                setConfirming(false);
              }}
              className="rounded bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-700"
            >
              Yes, mark as picked up
            </button>
            <button
              onClick={() => setConfirming(false)}
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
// AssignedCard
// ---------------------------------------------------------------------------

function AssignedCard({
  card,
  drivers,
  onConfirmDelivered,
  onReassign,
}: {
  card: AncillaryCard;
  drivers: AncillaryAvailableDriver[];
  onConfirmDelivered: (deliveryId: string) => void;
  onReassign: (deliveryId: string, driverId: string) => void;
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
            &#10003; Delivered
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
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// MarkPickupModal (inline form)
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
          placeholder="Optional"
        />
      </div>
      <div className="space-y-1.5">
        <label className="text-[10px] text-slate-500">Contact:</label>
        <input
          type="text"
          value={contact}
          onChange={(e) => setContact(e.target.value)}
          className="block w-full rounded border px-2 py-1 text-xs"
          placeholder="Optional"
        />
      </div>
      <div className="flex gap-2 pt-1">
        <button
          onClick={() => {
            // Build ISO timestamp if time was given
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
// Main AncillaryPanel
// ---------------------------------------------------------------------------

export function AncillaryPanel({ dateStr, collapsed, onToggleCollapse }: AncillaryPanelProps) {
  const [data, setData] = useState<AncillaryOrdersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [pickupFormId, setPickupFormId] = useState<string | null>(null);
  const [showCompleted, setShowCompleted] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Fetch data
  const fetchData = useCallback(async (showLoading = true) => {
    if (!dateStr) return;
    if (showLoading) setLoading(true);
    try {
      const resp = await api.get<AncillaryOrdersResponse>(
        "/api/v1/extensions/funeral-kanban/ancillary",
        { params: { date: dateStr, include_completed: true } },
      );
      setData(resp.data);
    } catch {
      // Silent fail on poll
    } finally {
      setLoading(false);
    }
  }, [dateStr]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Poll every 60s
  useEffect(() => {
    pollRef.current = setInterval(() => fetchData(false), 60_000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [fetchData]);

  // Actions
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

  const unresolvedCount = data?.stats.unresolved ?? 0;
  const drivers = data?.available_drivers ?? [];

  // ── Collapsed tab ──
  if (collapsed) {
    return (
      <button
        onClick={onToggleCollapse}
        className="fixed right-0 top-1/2 -translate-y-1/2 z-30 flex items-center gap-1.5 rounded-l-lg border border-r-0 bg-white px-2 py-3 shadow-md hover:bg-slate-50 transition-colors"
        style={{ writingMode: "vertical-lr" }}
      >
        <span className="text-xs font-medium text-slate-600">&#9664; Ancillary</span>
        {unresolvedCount > 0 && (
          <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700"
            style={{ writingMode: "horizontal-tb" }}
          >
            {unresolvedCount}
          </span>
        )}
      </button>
    );
  }

  return (
    <div className="flex h-full w-80 shrink-0 flex-col border-l border-slate-200 bg-slate-50/50">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div>
          <h3 className="text-sm font-bold text-slate-900">Ancillary Orders</h3>
          <p className="text-[11px] text-slate-500">{formatPanelDate(dateStr)}</p>
        </div>
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

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-4">
        {loading && !data ? (
          <div className="flex items-center justify-center py-8">
            <p className="text-xs text-slate-400">Loading...</p>
          </div>
        ) : !data || data.stats.total === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="text-2xl mb-2">&#128230;</div>
            <p className="text-xs text-slate-400">No ancillary orders for this date</p>
          </div>
        ) : (
          <>
            {/* Group 1: Needs Action */}
            {data.needs_action.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Needs Action
                  </h4>
                  <Badge variant="destructive" className="text-[10px] px-1.5 py-0">
                    {data.needs_action.length}
                  </Badge>
                </div>
                {data.needs_action.map((card) =>
                  pickupFormId === card.delivery_id ? (
                    <MarkPickupInline
                      key={card.delivery_id}
                      deliveryId={card.delivery_id}
                      onConfirm={handleMarkPickup}
                      onCancel={() => setPickupFormId(null)}
                    />
                  ) : (
                    <NeedsActionCard
                      key={card.delivery_id}
                      card={card}
                      drivers={drivers}
                      onAssign={handleAssign}
                      onMarkPickup={(id) => setPickupFormId(id)}
                    />
                  ),
                )}
              </div>
            )}

            {/* Group 2: Awaiting Pickup */}
            {data.awaiting_pickup.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Awaiting Pickup
                  </h4>
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-violet-300 text-violet-600">
                    {data.awaiting_pickup.length}
                  </Badge>
                </div>
                {data.awaiting_pickup.map((card) => (
                  <AwaitingPickupCard
                    key={card.delivery_id}
                    card={card}
                    onConfirmPickup={handleConfirmPickup}
                  />
                ))}
              </div>
            )}

            {/* Group 3: With Drivers */}
            {data.assigned_groups.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    With Drivers
                  </h4>
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-blue-300 text-blue-600">
                    {data.stats.assigned}
                  </Badge>
                </div>
                {data.assigned_groups.map((group) => (
                  <div key={group.driver_id} className="space-y-1.5">
                    <p className="text-xs font-semibold text-slate-700">
                      {group.driver_name}{" "}
                      <span className="font-normal text-slate-400">
                        ({group.item_count} item{group.item_count !== 1 ? "s" : ""})
                      </span>
                    </p>
                    {group.items.map((card) => (
                      <AssignedCard
                        key={card.delivery_id}
                        card={card}
                        drivers={drivers}
                        onConfirmDelivered={handleConfirmDelivered}
                        onReassign={handleReassign}
                      />
                    ))}
                  </div>
                ))}
              </div>
            )}

            {/* Completed toggle */}
            {data.completed.length > 0 && (
              <div className="space-y-1">
                <button
                  onClick={() => setShowCompleted(!showCompleted)}
                  className="flex w-full items-center justify-between rounded-lg bg-slate-100 px-3 py-1.5 text-[11px] font-medium text-slate-500 hover:bg-slate-200 transition-colors"
                >
                  <span>Show completed ({data.completed.length})</span>
                  <span>{showCompleted ? "\u25B4" : "\u25BE"}</span>
                </button>
                {showCompleted && (
                  <div className="space-y-0.5 pt-1">
                    {data.completed.map((card) => (
                      <div key={card.delivery_id} className="flex items-center gap-2 rounded px-2 py-1 text-[11px] text-slate-400">
                        <span className="text-emerald-500">&#10003;</span>
                        <span className="flex-1 truncate">
                          {card.funeral_home_name} — {card.product_summary || card.order_type_label}
                          {card.deceased_name ? ` — ${card.deceased_name}` : ""}
                        </span>
                        <span className="shrink-0">{formatCompletedTime(card.completed_at)}</span>
                      </div>
                    ))}
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
// Mobile Drawer variant
// ---------------------------------------------------------------------------

export function AncillaryMobilePill({
  dateStr,
  unresolvedCount,
  onClick,
}: {
  dateStr: string;
  unresolvedCount: number;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="fixed bottom-20 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2 rounded-full bg-white border border-slate-300 px-4 py-2 shadow-lg hover:bg-slate-50 transition-colors"
    >
      <span className="text-sm">&#128230;</span>
      <span className="text-xs font-medium text-slate-700">Ancillary Orders</span>
      {unresolvedCount > 0 && (
        <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">
          {unresolvedCount}
        </span>
      )}
    </button>
  );
}

export function AncillaryDrawer({
  dateStr,
  open,
  onClose,
}: {
  dateStr: string;
  open: boolean;
  onClose: () => void;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/20" onClick={onClose} />
      {/* Drawer */}
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
          <AncillaryPanel dateStr={dateStr} collapsed={false} onToggleCollapse={onClose} />
        </div>
      </div>
    </div>
  );
}
