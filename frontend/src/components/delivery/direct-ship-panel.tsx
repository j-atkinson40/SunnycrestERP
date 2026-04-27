/**
 * DirectShipPanel — side panel for direct ship orders on the Scheduling Board.
 *
 * Direct ship orders are shipped by Wilbert directly to the funeral home.
 * Status flow: Pending → Ordered from Wilbert → Shipped → Done.
 * Shows a 7-day lookahead window, not a single date.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Mailbox, X } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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

// Phase II Batch 1b — helper internals migrated to DESIGN_LANGUAGE
// status tokens. Overdue is error-family (fatal-urgent); within 2
// days is warning-family (attention-urgent); within 5 days is
// warning-family (soft attention); otherwise muted. Approved per
// session spec item #4 — keep helper structure, migrate internals.
function getUrgencyClass(neededBy: string | null): string {
  if (!neededBy) return "text-content-muted";
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const target = new Date(neededBy + "T00:00:00");
  const diffDays = Math.ceil((target.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));

  if (diffDays <= 0) return "text-status-error font-bold";
  if (diffDays <= 2) return "text-status-warning font-bold";
  if (diffDays <= 5) return "text-status-warning";
  return "text-content-muted";
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
    <div className="rounded-lg border border-border-subtle bg-surface-elevated p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-semibold text-content-strong leading-tight">
          {card.funeral_home_name || "Unknown"}
        </span>
        <Badge variant="outline" className="shrink-0 text-[10px]">
          {card.delivery_type === "merchandise" ? "Merchandise" :
            card.delivery_type === "memorial_item" ? "Memorial Item" : "Direct Ship"}
        </Badge>
      </div>
      {card.product_summary && (
        <p className="text-xs text-content-base">{card.product_summary}</p>
      )}
      {card.deceased_name && (
        <p className="text-xs text-content-muted">{card.deceased_name}</p>
      )}
      {card.needed_by && (
        <p className={cn("text-xs", getUrgencyClass(card.needed_by))}>
          Needed by: {formatNeededBy(card.needed_by)}
          {isNeededByUrgent(card.needed_by) && " \u26A0\uFE0F"}
        </p>
      )}

      {!showForm ? (
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowForm(true)}
          className="mt-1 gap-1"
        >
          <Check className="h-3.5 w-3.5" aria-hidden="true" />
          Mark as Ordered from Wilbert
        </Button>
      ) : (
        <div className="mt-1 rounded border border-status-info bg-status-info-muted p-2.5 space-y-2">
          <p className="text-xs font-medium text-status-info">Order placed with Wilbert</p>
          <div className="space-y-1.5">
            <label className="text-[10px] text-content-muted">Wilbert order/reference number:</label>
            <input
              type="text"
              value={orderNumber}
              onChange={(e) => setOrderNumber(e.target.value)}
              className="block w-full rounded border border-border-base bg-surface-raised px-2 py-1 text-xs text-content-base focus-visible:border-accent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent/30"
              placeholder="Optional"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] text-content-muted">Notes:</label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="block w-full rounded border border-border-base bg-surface-raised px-2 py-1 text-xs text-content-base focus-visible:border-accent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent/30"
              placeholder="Optional"
            />
          </div>
          <div className="flex gap-2 pt-1">
            <Button
              size="sm"
              onClick={() => {
                onMarkOrdered(card.delivery_id, orderNumber, notes);
                setShowForm(false);
              }}
            >
              Confirm — Mark as Ordered
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowForm(false)}
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
    <div className="rounded-lg border border-border-subtle bg-surface-elevated p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-semibold text-content-strong leading-tight">
          {card.funeral_home_name || "Unknown"}
        </span>
        <Badge variant="outline" className="shrink-0 text-[10px]">
          {card.delivery_type === "merchandise" ? "Merchandise" :
            card.delivery_type === "memorial_item" ? "Memorial Item" : "Direct Ship"}
        </Badge>
      </div>
      {card.product_summary && (
        <p className="text-xs text-content-base">{card.product_summary}</p>
      )}
      {card.deceased_name && (
        <p className="text-xs text-content-muted">{card.deceased_name}</p>
      )}
      {card.wilbert_order_number && (
        <p className="text-[11px] text-content-subtle">Order #: {card.wilbert_order_number}</p>
      )}
      {card.needed_by && (
        <p className={cn("text-xs", getUrgencyClass(card.needed_by))}>
          Needed by: {formatNeededBy(card.needed_by)}
          {isNeededByUrgent(card.needed_by) && " \u26A0\uFE0F"}
        </p>
      )}

      {!confirming ? (
        <Button
          variant="outline"
          size="sm"
          onClick={() => setConfirming(true)}
          className="mt-1 gap-1"
        >
          <Check className="h-3.5 w-3.5" aria-hidden="true" />
          Mark as Shipped
        </Button>
      ) : (
        <div className="mt-1 rounded border border-status-success bg-status-success-muted p-2 space-y-2">
          <p className="text-xs text-status-success">
            Mark as shipped to {card.funeral_home_name}?
          </p>
          <p className="text-[10px] text-content-muted">
            Wilbert will handle delivery from here.
          </p>
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() => {
                onMarkShipped(card.delivery_id);
                setConfirming(false);
              }}
            >
              Yes — Mark Shipped
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirming(false)}
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
    <div className="rounded-lg border border-border-subtle bg-surface-sunken p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-semibold text-content-base leading-tight">
          {card.funeral_home_name || "Unknown"}
        </span>
        <Badge variant="outline" className="shrink-0 text-[10px]">
          {card.delivery_type === "merchandise" ? "Merchandise" :
            card.delivery_type === "memorial_item" ? "Memorial Item" : "Direct Ship"}
        </Badge>
      </div>
      {card.product_summary && (
        <p className="text-xs text-content-muted">{card.product_summary}</p>
      )}
      {card.deceased_name && (
        <p className="text-xs text-content-subtle">{card.deceased_name}</p>
      )}
      <p className="text-[11px] text-content-subtle">
        Shipped {formatShippedTime(card.marked_shipped_at)}
      </p>

      {suggestDone && !confirming && (
        <p className="text-[11px] text-status-warning">
          Shipped {daysShipped} days ago — likely delivered
        </p>
      )}

      {!confirming ? (
        <Button
          variant="outline"
          size="sm"
          onClick={() => setConfirming(true)}
          className="mt-1 gap-1"
        >
          <Check className="h-3.5 w-3.5" aria-hidden="true" />
          Done
        </Button>
      ) : (
        <div className="mt-1 rounded border border-border-subtle bg-surface-elevated p-2 space-y-2">
          <p className="text-xs text-content-base">Mark as complete?</p>
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() => {
                onMarkDone(card.delivery_id);
                setConfirming(false);
              }}
            >
              Yes — Done
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirming(false)}
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
    <div className="flex flex-col border-t border-border-subtle">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border-subtle px-4 py-3">
        <div>
          <h3 className="text-sm font-bold text-content-strong">Direct Ship</h3>
          <p className="text-[11px] text-content-muted">Orders due within 7 days</p>
        </div>
        <button
          onClick={onToggleCollapse}
          className="rounded p-1 transition-colors duration-quick ease-settle hover:bg-surface-elevated focus-ring-accent"
          aria-label="Collapse direct ship panel"
        >
          <ChevronDown className="h-4 w-4 text-content-muted -rotate-180" aria-hidden="true" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-4">
        {loading && !data ? (
          <div className="flex items-center justify-center py-6">
            <p className="text-xs text-content-subtle">Loading...</p>
          </div>
        ) : !data || data.stats.total === 0 ? (
          <div className="flex flex-col items-center justify-center py-6 text-center">
            <Mailbox className="h-6 w-6 mb-2 text-content-subtle" aria-hidden="true" />
            <p className="text-xs text-content-subtle">No direct ship orders</p>
          </div>
        ) : (
          <>
            {/* Group 1: Needs to be Ordered */}
            {data.needs_ordering.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <h4 className="text-[10px] font-bold uppercase tracking-wider text-content-muted">
                    Needs to be Ordered
                  </h4>
                  <Badge variant="error" className="text-[10px] px-1.5 py-0">
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
                  <h4 className="text-[10px] font-bold uppercase tracking-wider text-content-muted">
                    Ordered from Wilbert
                  </h4>
                  <Badge variant="info" className="text-[10px] px-1.5 py-0">
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
                  <h4 className="text-[10px] font-bold uppercase tracking-wider text-content-muted">
                    Shipped
                  </h4>
                  <Badge variant="success" className="text-[10px] px-1.5 py-0">
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
                  className="flex w-full items-center justify-between rounded-lg bg-surface-sunken px-3 py-1.5 text-[11px] font-medium text-content-muted transition-colors duration-quick ease-settle hover:bg-surface-elevated hover:text-content-strong focus-ring-accent"
                >
                  <span>Show completed ({data.completed.length})</span>
                  <span>{showCompleted ? "\u25B4" : "\u25BE"}</span>
                </button>
                {showCompleted && (
                  <div className="space-y-0.5 pt-1">
                    {data.completed.map((card) => (
                      <div key={card.delivery_id} className="flex items-center gap-2 rounded px-2 py-1 text-[11px] text-content-subtle">
                        <Check className="h-3 w-3 text-status-success shrink-0" aria-hidden="true" />
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
      className="fixed bottom-8 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2 rounded-full bg-surface-raised border border-border-base px-4 py-2 shadow-level-2 transition-colors duration-quick ease-settle hover:bg-surface-elevated focus-ring-accent"
    >
      <Mailbox className="h-4 w-4 text-content-muted" aria-hidden="true" />
      <span className="text-xs font-medium text-content-base">Direct Ship</span>
      {unresolvedCount > 0 && (
        <span className="rounded-full bg-status-info-muted px-1.5 py-0.5 text-[10px] font-semibold text-status-info">
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
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="absolute bottom-0 left-0 right-0 max-h-[70vh] overflow-y-auto rounded-t-2xl bg-surface-raised shadow-level-3 animate-in slide-in-from-bottom duration-200">
        <div className="sticky top-0 flex items-center justify-between border-b border-border-subtle bg-surface-raised px-4 py-3">
          <h3 className="text-sm font-bold text-content-strong">Direct Ship Orders</h3>
          <button
            onClick={onClose}
            className="rounded p-1 transition-colors duration-quick ease-settle hover:bg-surface-elevated focus-ring-accent"
            aria-label="Close drawer"
          >
            <X className="h-5 w-5 text-content-muted" aria-hidden="true" />
          </button>
        </div>
        <div className="px-1 pb-8">
          <DirectShipPanel collapsed={false} onToggleCollapse={onClose} />
        </div>
      </div>
    </div>
  );
}
