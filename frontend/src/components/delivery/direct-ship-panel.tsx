/**
 * DirectShipPanel — side panel for direct ship orders on the Scheduling Board.
 *
 * Direct ship orders are shipped by Wilbert directly to the funeral home.
 * Status flow: Pending → Ordered from Wilbert → Shipped → Done.
 * Shows a 7-day lookahead window, not a single date.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import api from "@/lib/api-client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DirectShipCard {
  delivery_id: string;
  delivery_type: string;
  funeral_home_name: string;
  product_summary: string;
  deceased_name: string;
  status: string;
  direct_ship_status: string;
  wilbert_order_number: string | null;
  direct_ship_notes: string | null;
  needed_by: string | null;
  marked_shipped_at: string | null;
  marked_shipped_by: string | null;
  completed_at: string | null;
  special_instructions: string | null;
  created_at: string | null;
}

interface DirectShipResponse {
  needs_ordering: DirectShipCard[];
  ordered: DirectShipCard[];
  shipped: DirectShipCard[];
  completed: DirectShipCard[];
  stats: {
    total: number;
    needs_ordering: number;
    ordered: number;
    shipped: number;
    completed: number;
    unresolved: number;
  };
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface DirectShipPanelProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getUrgencyClass(neededBy: string | null): string {
  if (!neededBy) return "text-slate-500";
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const target = new Date(neededBy + "T00:00:00");
  const diffDays = Math.ceil((target.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));

  if (diffDays <= 0) return "text-red-600 font-bold";
  if (diffDays <= 2) return "text-amber-600 font-bold";
  if (diffDays <= 5) return "text-amber-600";
  return "text-slate-500";
}

function formatNeededBy(neededBy: string | null): string {
  if (!neededBy) return "";
  const d = new Date(neededBy + "T12:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function isNeededByUrgent(neededBy: string | null): boolean {
  if (!neededBy) return false;
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const target = new Date(neededBy + "T00:00:00");
  const diffDays = Math.ceil((target.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  return diffDays <= 0;
}

function formatShippedTime(isoStr: string | null): string {
  if (!isoStr) return "";
  const d = new Date(isoStr);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) {
    return `today at ${d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}`;
  }
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" }) +
    ` at ${d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}`;
}

function daysSinceShipped(shippedAt: string | null): number {
  if (!shippedAt) return 0;
  const shipped = new Date(shippedAt);
  const now = new Date();
  return Math.floor((now.getTime() - shipped.getTime()) / (1000 * 60 * 60 * 24));
}

function formatCompletedLine(card: DirectShipCard): string {
  const parts = [card.funeral_home_name];
  if (card.product_summary) parts.push(card.product_summary);
  if (card.marked_shipped_at) {
    const d = new Date(card.marked_shipped_at);
    parts.push(`Shipped ${d.toLocaleDateString("en-US", { month: "short", day: "numeric" })}`);
  }
  if (card.completed_at) {
    const d = new Date(card.completed_at);
    parts.push(`Done ${d.toLocaleDateString("en-US", { month: "short", day: "numeric" })}`);
  }
  return parts.join(" \u2014 ");
}

// ---------------------------------------------------------------------------
// NeedsOrderingCard
// ---------------------------------------------------------------------------

function NeedsOrderingCard({
  card,
  onMarkOrdered,
}: {
  card: DirectShipCard;
  onMarkOrdered: (deliveryId: string, orderNumber: string, notes: string) => void;
}) {
  const [showForm, setShowForm] = useState(false);
  const [orderNumber, setOrderNumber] = useState("");
  const [notes, setNotes] = useState("");

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-semibold text-slate-900 leading-tight">
          {card.funeral_home_name || "Unknown"}
        </span>
        <Badge variant="outline" className="shrink-0 text-[10px] border-slate-300 text-slate-600">
          {card.delivery_type === "merchandise" ? "Merchandise" :
            card.delivery_type === "memorial_item" ? "Memorial Item" : "Direct Ship"}
        </Badge>
      </div>
      {card.product_summary && (
        <p className="text-xs text-slate-600">{card.product_summary}</p>
      )}
      {card.deceased_name && (
        <p className="text-xs text-slate-500">{card.deceased_name}</p>
      )}
      {card.needed_by && (
        <p className={cn("text-xs", getUrgencyClass(card.needed_by))}>
          Needed by: {formatNeededBy(card.needed_by)}
          {isNeededByUrgent(card.needed_by) && " \u26A0\uFE0F"}
        </p>
      )}

      {!showForm ? (
        <button
          onClick={() => setShowForm(true)}
          className="mt-1 rounded border border-blue-300 bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700 hover:bg-blue-100 transition-colors"
        >
          &#10003; Mark as Ordered from Wilbert
        </button>
      ) : (
        <div className="mt-1 rounded border border-blue-200 bg-blue-50 p-2.5 space-y-2">
          <p className="text-xs font-medium text-blue-700">Order placed with Wilbert</p>
          <div className="space-y-1.5">
            <label className="text-[10px] text-slate-500">Wilbert order/reference number:</label>
            <input
              type="text"
              value={orderNumber}
              onChange={(e) => setOrderNumber(e.target.value)}
              className="block w-full rounded border px-2 py-1 text-xs"
              placeholder="Optional"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] text-slate-500">Notes:</label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="block w-full rounded border px-2 py-1 text-xs"
              placeholder="Optional"
            />
          </div>
          <div className="flex gap-2 pt-1">
            <button
              onClick={() => {
                onMarkOrdered(card.delivery_id, orderNumber, notes);
                setShowForm(false);
              }}
              className="rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700"
            >
              Confirm — Mark as Ordered
            </button>
            <button
              onClick={() => setShowForm(false)}
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
// OrderedCard
// ---------------------------------------------------------------------------

function OrderedCard({
  card,
  onMarkShipped,
}: {
  card: DirectShipCard;
  onMarkShipped: (deliveryId: string) => void;
}) {
  const [confirming, setConfirming] = useState(false);

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-semibold text-slate-900 leading-tight">
          {card.funeral_home_name || "Unknown"}
        </span>
        <Badge variant="outline" className="shrink-0 text-[10px] border-slate-300 text-slate-600">
          {card.delivery_type === "merchandise" ? "Merchandise" :
            card.delivery_type === "memorial_item" ? "Memorial Item" : "Direct Ship"}
        </Badge>
      </div>
      {card.product_summary && (
        <p className="text-xs text-slate-600">{card.product_summary}</p>
      )}
      {card.deceased_name && (
        <p className="text-xs text-slate-500">{card.deceased_name}</p>
      )}
      {card.wilbert_order_number && (
        <p className="text-[11px] text-slate-400">Order #: {card.wilbert_order_number}</p>
      )}
      {card.needed_by && (
        <p className={cn("text-xs", getUrgencyClass(card.needed_by))}>
          Needed by: {formatNeededBy(card.needed_by)}
          {isNeededByUrgent(card.needed_by) && " \u26A0\uFE0F"}
        </p>
      )}

      {!confirming ? (
        <button
          onClick={() => setConfirming(true)}
          className="mt-1 rounded border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100 transition-colors"
        >
          &#10003; Mark as Shipped
        </button>
      ) : (
        <div className="mt-1 rounded border border-emerald-200 bg-emerald-50 p-2 space-y-2">
          <p className="text-xs text-emerald-700">
            Mark as shipped to {card.funeral_home_name}?
          </p>
          <p className="text-[10px] text-slate-500">
            Wilbert will handle delivery from here.
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => {
                onMarkShipped(card.delivery_id);
                setConfirming(false);
              }}
              className="rounded bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-700"
            >
              Yes — Mark Shipped
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
// ShippedCard
// ---------------------------------------------------------------------------

function ShippedCard({
  card,
  onMarkDone,
}: {
  card: DirectShipCard;
  onMarkDone: (deliveryId: string) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const daysShipped = daysSinceShipped(card.marked_shipped_at);
  const suggestDone = daysShipped >= 5;

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-semibold text-slate-700 leading-tight">
          {card.funeral_home_name || "Unknown"}
        </span>
        <Badge variant="outline" className="shrink-0 text-[10px] border-slate-300 text-slate-500">
          {card.delivery_type === "merchandise" ? "Merchandise" :
            card.delivery_type === "memorial_item" ? "Memorial Item" : "Direct Ship"}
        </Badge>
      </div>
      {card.product_summary && (
        <p className="text-xs text-slate-500">{card.product_summary}</p>
      )}
      {card.deceased_name && (
        <p className="text-xs text-slate-400">{card.deceased_name}</p>
      )}
      <p className="text-[11px] text-slate-400">
        Shipped {formatShippedTime(card.marked_shipped_at)}
      </p>

      {suggestDone && !confirming && (
        <p className="text-[11px] text-amber-600">
          Shipped {daysShipped} days ago — likely delivered
        </p>
      )}

      {!confirming ? (
        <button
          onClick={() => setConfirming(true)}
          className="mt-1 rounded border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors"
        >
          &#10003; Done
        </button>
      ) : (
        <div className="mt-1 rounded border border-slate-200 bg-white p-2 space-y-2">
          <p className="text-xs text-slate-700">Mark as complete?</p>
          <div className="flex gap-2">
            <button
              onClick={() => {
                onMarkDone(card.delivery_id);
                setConfirming(false);
              }}
              className="rounded bg-slate-700 px-3 py-1 text-xs font-medium text-white hover:bg-slate-800"
            >
              Yes — Done
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
// Main DirectShipPanel
// ---------------------------------------------------------------------------

export function DirectShipPanel({ collapsed, onToggleCollapse }: DirectShipPanelProps) {
  const [data, setData] = useState<DirectShipResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCompleted, setShowCompleted] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async (showLoading = true) => {
    if (showLoading) setLoading(true);
    try {
      const resp = await api.get<DirectShipResponse>(
        "/api/v1/extensions/funeral-kanban/direct-ship",
        { params: { include_completed: true } },
      );
      setData(resp.data);
    } catch {
      // Silent on poll
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    pollRef.current = setInterval(() => fetchData(false), 60_000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [fetchData]);

  // Actions
  const handleMarkOrdered = useCallback(async (deliveryId: string, orderNumber: string, notes: string) => {
    try {
      await api.post(`/api/v1/extensions/funeral-kanban/direct-ship/${deliveryId}/mark-ordered`, {
        wilbert_order_number: orderNumber || null,
        notes: notes || null,
      });
      toast.success("Marked as ordered from Wilbert");
      fetchData(false);
    } catch {
      toast.error("Failed to update");
    }
  }, [fetchData]);

  const handleMarkShipped = useCallback(async (deliveryId: string) => {
    try {
      await api.post(`/api/v1/extensions/funeral-kanban/direct-ship/${deliveryId}/mark-shipped`);
      toast.success("Marked as shipped");
      fetchData(false);
    } catch {
      toast.error("Failed to update");
    }
  }, [fetchData]);

  const handleMarkDone = useCallback(async (deliveryId: string) => {
    try {
      await api.post(`/api/v1/extensions/funeral-kanban/direct-ship/${deliveryId}/mark-done`);
      toast.success("Marked as done");
      fetchData(false);
    } catch {
      toast.error("Failed to update");
    }
  }, [fetchData]);

  // unresolvedCount exposed for parent components via props/callbacks if needed
  void (data?.stats.unresolved ?? 0);

  if (collapsed) {
    return null; // Collapse handled at the scheduling board level
  }

  return (
    <div className="flex flex-col border-t border-slate-200">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div>
          <h3 className="text-sm font-bold text-slate-900">Direct Ship</h3>
          <p className="text-[11px] text-slate-500">Orders due within 7 days</p>
        </div>
        <button
          onClick={onToggleCollapse}
          className="rounded p-1 hover:bg-slate-200 transition-colors"
          aria-label="Collapse direct ship panel"
        >
          <svg className="h-4 w-4 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="m18 15-6-6-6 6" />
          </svg>
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-4">
        {loading && !data ? (
          <div className="flex items-center justify-center py-6">
            <p className="text-xs text-slate-400">Loading...</p>
          </div>
        ) : !data || data.stats.total === 0 ? (
          <div className="flex flex-col items-center justify-center py-6 text-center">
            <div className="text-2xl mb-2">&#128236;</div>
            <p className="text-xs text-slate-400">No direct ship orders</p>
          </div>
        ) : (
          <>
            {/* Group 1: Needs to be Ordered */}
            {data.needs_ordering.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Needs to be Ordered
                  </h4>
                  <Badge variant="destructive" className="text-[10px] px-1.5 py-0">
                    {data.needs_ordering.length}
                  </Badge>
                </div>
                {data.needs_ordering.map((card) => (
                  <NeedsOrderingCard
                    key={card.delivery_id}
                    card={card}
                    onMarkOrdered={handleMarkOrdered}
                  />
                ))}
              </div>
            )}

            {/* Group 2: Ordered from Wilbert */}
            {data.ordered.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Ordered from Wilbert
                  </h4>
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-blue-300 text-blue-600">
                    {data.ordered.length}
                  </Badge>
                </div>
                {data.ordered.map((card) => (
                  <OrderedCard
                    key={card.delivery_id}
                    card={card}
                    onMarkShipped={handleMarkShipped}
                  />
                ))}
              </div>
            )}

            {/* Group 3: Shipped */}
            {data.shipped.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Shipped
                  </h4>
                  <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-emerald-300 text-emerald-600">
                    {data.shipped.length}
                  </Badge>
                </div>
                {data.shipped.map((card) => (
                  <ShippedCard
                    key={card.delivery_id}
                    card={card}
                    onMarkDone={handleMarkDone}
                  />
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
                        <span className="flex-1 truncate">{formatCompletedLine(card)}</span>
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
// Mobile Pill
// ---------------------------------------------------------------------------

export function DirectShipMobilePill({
  unresolvedCount,
  onClick,
}: {
  unresolvedCount: number;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="fixed bottom-8 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2 rounded-full bg-white border border-slate-300 px-4 py-2 shadow-lg hover:bg-slate-50 transition-colors"
    >
      <span className="text-sm">&#128236;</span>
      <span className="text-xs font-medium text-slate-700">Direct Ship</span>
      {unresolvedCount > 0 && (
        <span className="rounded-full bg-blue-100 px-1.5 py-0.5 text-[10px] font-semibold text-blue-700">
          {unresolvedCount}
        </span>
      )}
    </button>
  );
}

export function DirectShipDrawer({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0 bg-black/20" onClick={onClose} />
      <div className="absolute bottom-0 left-0 right-0 max-h-[70vh] overflow-y-auto rounded-t-2xl bg-white shadow-2xl animate-in slide-in-from-bottom duration-200">
        <div className="sticky top-0 flex items-center justify-between border-b bg-white px-4 py-3">
          <h3 className="text-sm font-bold text-slate-900">Direct Ship Orders</h3>
          <button onClick={onClose} className="rounded p-1 hover:bg-slate-100">
            <svg className="h-5 w-5 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="px-1 pb-8">
          <DirectShipPanel collapsed={false} onToggleCollapse={onClose} />
        </div>
      </div>
    </div>
  );
}
