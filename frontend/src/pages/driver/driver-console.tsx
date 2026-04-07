import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/contexts/auth-context";
import apiClient from "@/lib/api-client";
import type { SalesOrder } from "@/types/sales";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  Truck,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Package,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtDate(d: string | null) {
  if (!d) return "\u2014";
  return new Date(d).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function fmtTime(d: string | null) {
  if (!d) return null;
  // Handle time-only strings like "14:00" or full ISO dates
  const date = d.includes("T") ? new Date(d) : new Date(`2000-01-01T${d}`);
  if (isNaN(date.getTime())) return d;
  return date.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

function todayStr() {
  return new Date().toISOString().split("T")[0];
}

function statusLabel(status: string): string {
  switch (status) {
    case "shipped":
      return "Delivered";
    case "processing":
      return "In Production";
    default:
      return status.charAt(0).toUpperCase() + status.slice(1);
  }
}

function statusBadge(status: string) {
  switch (status) {
    case "processing":
      return (
        <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
          In Production
        </Badge>
      );
    case "confirmed":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
          Confirmed
        </Badge>
      );
    case "shipped":
    case "delivered":
      return (
        <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
          Delivered
        </Badge>
      );
    case "completed":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Completed
        </Badge>
      );
    default:
      return <Badge variant="outline">{statusLabel(status)}</Badge>;
  }
}

// ---------------------------------------------------------------------------
// Section header (collapsible)
// ---------------------------------------------------------------------------

function SectionHeader({
  title,
  count,
  icon: Icon,
  open,
  onToggle,
}: {
  title: string;
  count: number;
  icon: React.ComponentType<{ className?: string }>;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      onClick={onToggle}
      className="flex w-full items-center justify-between rounded-lg bg-muted/50 px-3 py-3 text-left dark:bg-muted/30"
    >
      <div className="flex items-center gap-2">
        <Icon className="h-5 w-5 text-muted-foreground" />
        <span className="text-base font-semibold">{title}</span>
        <Badge variant="secondary" className="text-xs">
          {count}
        </Badge>
      </div>
      {open ? (
        <ChevronDown className="h-5 w-5 text-muted-foreground" />
      ) : (
        <ChevronRight className="h-5 w-5 text-muted-foreground" />
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Order Card
// ---------------------------------------------------------------------------

function OrderCard({
  order,
  onMarkDelivered,
  onReportIssue,
  showDeliverButton,
}: {
  order: SalesOrder;
  onMarkDelivered: (id: string) => void;
  onReportIssue: (id: string) => void;
  showDeliverButton: boolean;
}) {
  // Primary product from first line
  const primaryProduct =
    order.lines?.[0]?.product_name || order.lines?.[0]?.description || "\u2014";

  return (
    <Card className="overflow-hidden border border-border">
      <div className="p-4 space-y-3">
        {/* Header row */}
        <div className="flex items-center justify-between">
          <span className="font-mono text-sm text-muted-foreground">
            {order.number}
          </span>
          {statusBadge(order.status)}
        </div>

        {/* Customer */}
        <p className="text-base font-semibold leading-tight">
          {order.customer_name || "Unknown Customer"}
        </p>

        <hr className="border-border" />

        {/* Details */}
        <div className="space-y-1.5 text-sm">
          {order.deceased_name && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Deceased</span>
              <span className="font-medium">{order.deceased_name}</span>
            </div>
          )}
          {order.cemetery_name && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Cemetery</span>
              <span className="text-right font-semibold text-base leading-tight">
                {order.cemetery_name}
              </span>
            </div>
          )}
          {(order.scheduled_date || order.required_date) && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Burial</span>
              <span className="font-medium">
                {fmtDate(order.scheduled_date || order.required_date)}
                {order.service_time && (
                  <span className="ml-1 text-base font-semibold">
                    @ {fmtTime(order.service_time)}
                  </span>
                )}
              </span>
            </div>
          )}
          <div className="flex justify-between">
            <span className="text-muted-foreground">Vault</span>
            <span className="font-medium">{primaryProduct}</span>
          </div>
          {order.ship_to_address && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Address</span>
              <span className="text-right text-xs max-w-[60%]">
                {order.ship_to_address}
              </span>
            </div>
          )}
        </div>

        {/* Notes */}
        {order.notes && (
          <p className="text-xs text-muted-foreground italic border-l-2 border-yellow-400 pl-2">
            {order.notes}
          </p>
        )}

        <hr className="border-border" />

        {/* Action buttons */}
        <div className="flex flex-col gap-2">
          {showDeliverButton && (
            <Button
              size="lg"
              className="w-full min-h-[48px] bg-green-600 hover:bg-green-700 text-white text-base font-semibold"
              onClick={() => onMarkDelivered(order.id)}
            >
              <CheckCircle2 className="mr-2 h-5 w-5" />
              Mark Delivered
            </Button>
          )}
          <Button
            variant="outline"
            size="lg"
            className="w-full min-h-[48px] text-base"
            onClick={() => onReportIssue(order.id)}
          >
            <AlertTriangle className="mr-2 h-5 w-5" />
            Report Issue
          </Button>
        </div>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function DriverConsolePage() {
  const { user } = useAuth();
  const [orders, setOrders] = useState<SalesOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [useConsoleEndpoint, setUseConsoleEndpoint] = useState(false);

  // Section open state
  const [scheduledOpen, setScheduledOpen] = useState(true);
  const [readyOpen, setReadyOpen] = useState(true);
  const [completedOpen, setCompletedOpen] = useState(false);

  // Report issue modal
  const [issueOrderId, setIssueOrderId] = useState<string | null>(null);
  const [issueText, setIssueText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // --------------------------------------------------
  // Data fetching
  // --------------------------------------------------

  const fetchOrders = useCallback(async () => {
    setLoading(true);
    try {
      // Try driver console endpoint first (requires DeliveryRoute chain)
      try {
        const res = await apiClient.get("/driver/console/deliveries");
        if (res.data && Array.isArray(res.data) && res.data.length > 0) {
          setOrders(res.data);
          setUseConsoleEndpoint(true);
          return;
        }
      } catch {
        // Console endpoint not available, fall through
      }

      // Fallback: fetch today's orders from sales endpoint
      const res = await apiClient.get("/sales/orders", {
        params: {
          status: "processing,confirmed,shipped,delivered,completed",
          per_page: 50,
        },
      });

      const data = res.data?.items ?? res.data ?? [];
      setOrders(Array.isArray(data) ? data : []);
      setUseConsoleEndpoint(false);
    } catch (err) {
      console.error("Failed to load deliveries", err);
      toast.error("Failed to load deliveries");
      setOrders([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  // --------------------------------------------------
  // Categorize orders
  // --------------------------------------------------

  const today = todayStr();

  const scheduled = orders.filter((o) => {
    const date = o.scheduled_date || o.required_date || "";
    const dateStr = date.split("T")[0];
    return (
      dateStr === today &&
      (o.status === "processing" || o.status === "confirmed")
    );
  });

  const ready = orders.filter(
    (o) => o.status === "shipped" || o.status === "delivered",
  );

  const completed = orders.filter((o) => {
    if (o.status !== "completed") return false;
    // Show completed within last 7 days
    const completedAt = o.completed_at || o.modified_at || "";
    if (!completedAt) return true;
    const diff =
      Date.now() - new Date(completedAt).getTime();
    return diff < 7 * 24 * 60 * 60 * 1000;
  });

  const remaining = scheduled.length + ready.length;

  // --------------------------------------------------
  // Actions
  // --------------------------------------------------

  const markDelivered = async (orderId: string) => {
    try {
      if (useConsoleEndpoint) {
        await apiClient.patch(
          `/driver/console/deliveries/${orderId}/status`,
          { status: "delivered" },
        );
      } else {
        await apiClient.patch(`/sales/orders/${orderId}`, {
          status: "shipped",
          shipped_date: todayStr(),
        });
      }
      toast.success("Marked as delivered");
      fetchOrders();
    } catch (err) {
      console.error("Failed to update delivery status", err);
      toast.error("Failed to update status");
    }
  };

  const submitIssue = async () => {
    if (!issueOrderId || !issueText.trim()) return;
    setSubmitting(true);
    try {
      await apiClient.patch(`/sales/orders/${issueOrderId}`, {
        notes: `DRIVER EXCEPTION: ${issueText.trim()}`,
      });
      toast.success("Issue reported");
      setIssueOrderId(null);
      setIssueText("");
      fetchOrders();
    } catch (err) {
      console.error("Failed to report issue", err);
      toast.error("Failed to report issue");
    } finally {
      setSubmitting(false);
    }
  };

  // --------------------------------------------------
  // Render
  // --------------------------------------------------

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur px-3 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold flex items-center gap-2">
              <Truck className="h-6 w-6" />
              Today's Deliveries
            </h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {new Date().toLocaleDateString("en-US", {
                weekday: "long",
                month: "long",
                day: "numeric",
                year: "numeric",
              })}
            </p>
          </div>
          <Badge
            variant="secondary"
            className="text-lg px-3 py-1 font-semibold"
          >
            {remaining}
          </Badge>
        </div>
        {user && (
          <p className="text-xs text-muted-foreground mt-1">
            {user.first_name ? `${user.first_name} ${user.last_name}` : user.email}
          </p>
        )}
      </div>

      {/* Content */}
      <div className="px-3 py-4 space-y-4 pb-24">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
            <Package className="h-10 w-10 animate-pulse mb-3" />
            <p>Loading deliveries...</p>
          </div>
        ) : orders.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
            <CheckCircle2 className="h-12 w-12 mb-3 text-green-500" />
            <p className="text-lg font-medium">No deliveries today</p>
            <p className="text-sm mt-1">Check back later for new orders.</p>
          </div>
        ) : (
          <>
            {/* Scheduled Today */}
            <div className="space-y-3">
              <SectionHeader
                title="Scheduled Today"
                count={scheduled.length}
                icon={Clock}
                open={scheduledOpen}
                onToggle={() => setScheduledOpen((v) => !v)}
              />
              {scheduledOpen &&
                scheduled.map((order) => (
                  <OrderCard
                    key={order.id}
                    order={order}
                    onMarkDelivered={markDelivered}
                    onReportIssue={(id) => setIssueOrderId(id)}
                    showDeliverButton
                  />
                ))}
              {scheduledOpen && scheduled.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No orders scheduled for today.
                </p>
              )}
            </div>

            {/* Ready to Deliver */}
            <div className="space-y-3">
              <SectionHeader
                title="Ready to Deliver"
                count={ready.length}
                icon={Truck}
                open={readyOpen}
                onToggle={() => setReadyOpen((v) => !v)}
              />
              {readyOpen &&
                ready.map((order) => (
                  <OrderCard
                    key={order.id}
                    order={order}
                    onMarkDelivered={markDelivered}
                    onReportIssue={(id) => setIssueOrderId(id)}
                    showDeliverButton
                  />
                ))}
              {readyOpen && ready.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No orders ready for delivery.
                </p>
              )}
            </div>

            {/* Completed */}
            <div className="space-y-3">
              <SectionHeader
                title="Completed"
                count={completed.length}
                icon={CheckCircle2}
                open={completedOpen}
                onToggle={() => setCompletedOpen((v) => !v)}
              />
              {completedOpen &&
                completed.map((order) => (
                  <OrderCard
                    key={order.id}
                    order={order}
                    onMarkDelivered={markDelivered}
                    onReportIssue={(id) => setIssueOrderId(id)}
                    showDeliverButton={false}
                  />
                ))}
              {completedOpen && completed.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No completed deliveries this week.
                </p>
              )}
            </div>
          </>
        )}
      </div>

      {/* Report Issue Dialog */}
      <Dialog
        open={issueOrderId !== null}
        onOpenChange={(open) => {
          if (!open) {
            setIssueOrderId(null);
            setIssueText("");
          }
        }}
      >
        <DialogContent className="max-w-[92vw] rounded-lg">
          <DialogHeader>
            <DialogTitle>Report Issue</DialogTitle>
          </DialogHeader>
          <div className="py-2">
            <textarea
              className="w-full min-h-[120px] rounded-md border border-input bg-background px-3 py-2 text-base placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="Describe the issue (e.g., wrong vault, access blocked, grave not ready)..."
              value={issueText}
              onChange={(e) => setIssueText(e.target.value)}
              autoFocus
            />
          </div>
          <DialogFooter className="flex-col gap-2 sm:flex-col">
            <Button
              size="lg"
              className="w-full min-h-[48px] text-base"
              variant="destructive"
              disabled={!issueText.trim() || submitting}
              onClick={submitIssue}
            >
              {submitting ? "Submitting..." : "Submit Issue"}
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="w-full min-h-[48px] text-base"
              onClick={() => {
                setIssueOrderId(null);
                setIssueText("");
              }}
            >
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
