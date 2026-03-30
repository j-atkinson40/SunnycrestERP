import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Plus, Trash2 } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { deliveryService } from "@/services/delivery-service";
import apiClient from "@/lib/api-client";
import { getApiErrorMessage } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { getDeliveryTypeBadgeClass, getDeliveryTypeName } from "@/lib/delivery-types";
import type { Delivery, DeliveryEvent } from "@/types/delivery";

type ExceptionReason = "weather" | "access_issue" | "family_request" | "equipment_failure" | "other";

interface ExceptionItem {
  reason: ExceptionReason;
  notes: string;
}

const EXCEPTION_REASONS: { value: ExceptionReason; label: string }[] = [
  { value: "weather", label: "Weather conditions" },
  { value: "access_issue", label: "Access issue" },
  { value: "family_request", label: "Family request" },
  { value: "equipment_failure", label: "Equipment failure" },
  { value: "other", label: "Other" },
];

function statusBadge(status: string) {
  const map: Record<string, { className: string; label: string }> = {
    pending: { className: "bg-gray-100 text-gray-800", label: "Pending" },
    scheduled: { className: "bg-blue-100 text-blue-800", label: "Scheduled" },
    in_transit: { className: "bg-yellow-100 text-yellow-800", label: "In Transit" },
    arrived: { className: "bg-indigo-100 text-indigo-800", label: "Arrived" },
    setup: { className: "bg-purple-100 text-purple-800", label: "Setup" },
    completed: { className: "bg-green-100 text-green-800", label: "Completed" },
    cancelled: { className: "", label: "Cancelled" },
    failed: { className: "", label: "Failed" },
  };
  const info = map[status];
  if (info) return <Badge className={info.className}>{info.label}</Badge>;
  return <Badge variant="outline">{status}</Badge>;
}

function priorityBadge(priority: string) {
  switch (priority) {
    case "urgent":
      return <Badge variant="destructive">Urgent</Badge>;
    case "high":
      return <Badge className="bg-red-100 text-red-800">High</Badge>;
    case "normal":
      return <Badge variant="outline">Normal</Badge>;
    case "low":
      return <Badge variant="secondary">Low</Badge>;
    default:
      return <Badge variant="outline">{priority}</Badge>;
  }
}

function sourceBadge(source: string | null) {
  const map: Record<string, { className: string; label: string }> = {
    driver: { className: "bg-blue-100 text-blue-800", label: "Driver" },
    dispatch_manual: { className: "bg-gray-100 text-gray-800", label: "Dispatch" },
    carrier_sms: { className: "bg-orange-100 text-orange-800", label: "Carrier SMS" },
    carrier_portal: { className: "bg-orange-100 text-orange-800", label: "Carrier Portal" },
    system: { className: "bg-gray-100 text-gray-800", label: "System" },
  };
  if (!source) return null;
  const info = map[source];
  if (info) return <Badge className={info.className}>{info.label}</Badge>;
  return <Badge variant="outline">{source}</Badge>;
}

function fmtDateTime(d: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleString();
}

function fmtDate(d: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString();
}

export default function DeliveryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { hasPermission } = useAuth();
  const canEdit = hasPermission("delivery.edit");
  const canDispatch = hasPermission("delivery.dispatch");

  const [delivery, setDelivery] = useState<Delivery | null>(null);
  const [events, setEvents] = useState<DeliveryEvent[]>([]);
  const [loading, setLoading] = useState(true);

  // Status update dialog
  const [showStatusDialog, setShowStatusDialog] = useState(false);
  const [newStatus, setNewStatus] = useState("");
  const [statusNotes, setStatusNotes] = useState("");
  const [updatingStatus, setUpdatingStatus] = useState(false);

  // Exception confirmation flow (shown when completing a delivery)
  const [showExceptionConfirm, setShowExceptionConfirm] = useState(false);
  const [showExceptionForm, setShowExceptionForm] = useState(false);
  const [exceptions, setExceptions] = useState<ExceptionItem[]>([
    { reason: "other", notes: "" },
  ]);
  const [submittingComplete, setSubmittingComplete] = useState(false);

  const loadData = useCallback(async () => {
    if (!id) return;
    try {
      setLoading(true);
      const [del, evts] = await Promise.all([
        deliveryService.getDelivery(id),
        deliveryService.getDeliveryEvents(id),
      ]);
      setDelivery(del);
      setEvents(evts);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleStatusUpdate = async () => {
    if (!delivery || !newStatus) return;

    // Intercept "completed" → show exception confirmation flow
    if (newStatus === "completed") {
      setShowStatusDialog(false);
      setShowExceptionConfirm(true);
      return;
    }

    try {
      setUpdatingStatus(true);
      if (delivery.carrier_id) {
        await deliveryService.updateCarrierStatus(delivery.id, newStatus, statusNotes || undefined);
      } else {
        await deliveryService.updateDelivery(delivery.id, { status: newStatus });
      }
      toast.success(`Status updated to ${newStatus}`);
      setShowStatusDialog(false);
      setStatusNotes("");
      loadData();
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setUpdatingStatus(false);
    }
  };

  const handleCompleteNoExceptions = async () => {
    if (!delivery) return;
    setSubmittingComplete(true);
    try {
      await apiClient.post(`/delivery/${delivery.id}/complete`, {
        completed_at: new Date().toISOString(),
        exceptions: [],
      });
      toast.success("Delivery marked complete");
      setShowExceptionConfirm(false);
      loadData();
    } catch (err) {
      toast.error(getApiErrorMessage(err) ?? "Failed to complete delivery");
    } finally {
      setSubmittingComplete(false);
    }
  };

  const handleCompleteWithExceptions = async () => {
    if (!delivery) return;
    const valid = exceptions.filter((e) => e.reason);
    if (valid.length === 0) return;
    setSubmittingComplete(true);
    try {
      await apiClient.post(`/delivery/${delivery.id}/complete`, {
        completed_at: new Date().toISOString(),
        exceptions: valid,
      });
      toast.success("Delivery completed — exception flagged for tonight's invoice review");
      setShowExceptionForm(false);
      setShowExceptionConfirm(false);
      setExceptions([{ reason: "other", notes: "" }]);
      loadData();
    } catch (err) {
      toast.error(getApiErrorMessage(err) ?? "Failed to complete delivery");
    } finally {
      setSubmittingComplete(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading delivery...</p>
      </div>
    );
  }

  if (!delivery) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-destructive">Delivery not found</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Link to="/delivery/history" className="text-sm text-muted-foreground hover:underline">
              Deliveries
            </Link>
            <span className="text-muted-foreground">/</span>
            <h1 className="text-2xl font-bold">
              {delivery.customer_name || "Delivery"}
            </h1>
          </div>
          <div className="mt-1 flex items-center gap-2">
            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${getDeliveryTypeBadgeClass(delivery.delivery_type)}`}>{getDeliveryTypeName(delivery.delivery_type)}</span>
            {statusBadge(delivery.status)}
            {priorityBadge(delivery.priority)}
          </div>
        </div>
        {(canEdit || canDispatch) && (
          <Button
            variant="outline"
            onClick={() => {
              setNewStatus(delivery.status);
              setShowStatusDialog(true);
            }}
          >
            Update Status
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Main Info */}
        <div className="space-y-6 lg:col-span-2">
          <Card className="p-4">
            <h2 className="mb-3 font-semibold">Delivery Details</h2>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
              <div>
                <dt className="text-muted-foreground">Address</dt>
                <dd>{delivery.delivery_address || "—"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Requested Date</dt>
                <dd>{fmtDate(delivery.requested_date)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Time Window</dt>
                <dd>
                  {delivery.required_window_start && delivery.required_window_end
                    ? `${delivery.required_window_start} – ${delivery.required_window_end}`
                    : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Weight</dt>
                <dd>{delivery.weight_lbs ? `${delivery.weight_lbs} lbs` : "—"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Scheduled At</dt>
                <dd>{fmtDateTime(delivery.scheduled_at)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Completed At</dt>
                <dd>{fmtDateTime(delivery.completed_at)}</dd>
              </div>
            </dl>
            {delivery.special_instructions && (
              <div className="mt-3 rounded-md bg-muted/50 p-3 text-sm">
                <p className="font-medium">Special Instructions</p>
                <p className="text-muted-foreground">{delivery.special_instructions}</p>
              </div>
            )}
          </Card>

          {/* Carrier Info */}
          {delivery.carrier_id && (
            <Card className="p-4">
              <h2 className="mb-3 font-semibold">Third-Party Carrier</h2>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
                <div>
                  <dt className="text-muted-foreground">Carrier</dt>
                  <dd>{delivery.carrier_name || delivery.carrier_id}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Tracking Reference</dt>
                  <dd>{delivery.carrier_tracking_reference || "—"}</dd>
                </div>
              </dl>
            </Card>
          )}

          {/* Event Timeline */}
          <Card className="p-4">
            <h2 className="mb-3 font-semibold">Event Timeline</h2>
            {events.length === 0 ? (
              <p className="text-sm text-muted-foreground">No events recorded yet.</p>
            ) : (
              <div className="space-y-3">
                {events.map((evt) => (
                  <div key={evt.id} className="flex items-start gap-3 border-l-2 border-muted pl-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{evt.event_type}</span>
                        {sourceBadge(evt.source)}
                      </div>
                      {evt.notes && (
                        <p className="mt-0.5 text-xs text-muted-foreground">{evt.notes}</p>
                      )}
                    </div>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {fmtDateTime(evt.created_at)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <Card className="p-4">
            <h3 className="mb-2 text-sm font-semibold">Metadata</h3>
            <dl className="space-y-2 text-sm">
              <div>
                <dt className="text-muted-foreground">Created</dt>
                <dd>{fmtDateTime(delivery.created_at)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Modified</dt>
                <dd>{fmtDateTime(delivery.modified_at)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Order</dt>
                <dd>
                  {delivery.order_id ? (
                    <Link to={`/ar/orders/${delivery.order_id}`} className="text-primary hover:underline">
                      {delivery.order_id.slice(0, 8)}...
                    </Link>
                  ) : (
                    "—"
                  )}
                </dd>
              </div>
            </dl>
          </Card>

          {delivery.delivery_lat && delivery.delivery_lng && (
            <Card className="p-4">
              <h3 className="mb-2 text-sm font-semibold">Location</h3>
              <p className="text-xs text-muted-foreground">
                {delivery.delivery_lat}, {delivery.delivery_lng}
              </p>
            </Card>
          )}
        </div>
      </div>

      {/* Exception confirmation — "Was everything delivered as planned?" */}
      <Dialog open={showExceptionConfirm} onOpenChange={setShowExceptionConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-green-600" />
              Mark Delivery Complete
            </DialogTitle>
            <DialogDescription>
              Was everything delivered as planned?
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2 py-2">
            <Button
              size="lg"
              onClick={handleCompleteNoExceptions}
              disabled={submittingComplete}
            >
              <CheckCircle2 className="w-4 h-4 mr-2" />
              Yes, all complete
            </Button>
            <Button
              size="lg"
              variant="outline"
              onClick={() => {
                setShowExceptionConfirm(false);
                setShowExceptionForm(true);
              }}
            >
              <AlertTriangle className="w-4 h-4 mr-2 text-amber-500" />
              Report an issue
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Exception form */}
      <Dialog open={showExceptionForm} onOpenChange={setShowExceptionForm}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-500" />
              Report Delivery Exception
            </DialogTitle>
            <DialogDescription>
              Describe what could not be completed. This will be flagged on tonight's draft invoice for review.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-1">
            {exceptions.map((ex, idx) => (
              <div key={idx} className="rounded-md border p-3 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Issue {exceptions.length > 1 ? idx + 1 : ""}</span>
                  {exceptions.length > 1 && (
                    <button
                      onClick={() => setExceptions((prev) => prev.filter((_, i) => i !== idx))}
                      className="text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Reason</Label>
                  <select
                    value={ex.reason}
                    onChange={(e) =>
                      setExceptions((prev) =>
                        prev.map((item, i) =>
                          i === idx ? { ...item, reason: e.target.value as ExceptionReason } : item
                        )
                      )
                    }
                    className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                  >
                    {EXCEPTION_REASONS.map((r) => (
                      <option key={r.value} value={r.value}>{r.label}</option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Notes (optional)</Label>
                  <input
                    type="text"
                    value={ex.notes}
                    onChange={(e) =>
                      setExceptions((prev) =>
                        prev.map((item, i) =>
                          i === idx ? { ...item, notes: e.target.value } : item
                        )
                      )
                    }
                    placeholder="e.g. High winds prevented tent setup"
                    className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                  />
                </div>
              </div>
            ))}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setExceptions((prev) => [...prev, { reason: "other", notes: "" }])}
            >
              <Plus className="w-4 h-4 mr-1" /> Add another issue
            </Button>
          </div>
          <Separator />
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowExceptionForm(false);
                setShowExceptionConfirm(true);
              }}
            >
              Back
            </Button>
            <Button onClick={handleCompleteWithExceptions} disabled={submittingComplete}>
              Submit & Complete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Status Update Dialog */}
      <Dialog open={showStatusDialog} onOpenChange={setShowStatusDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Update Delivery Status</DialogTitle>
            <DialogDescription>Change the status of this delivery</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>New Status</Label>
              <select
                value={newStatus}
                onChange={(e) => setNewStatus(e.target.value)}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              >
                <option value="pending">Pending</option>
                <option value="scheduled">Scheduled</option>
                <option value="in_transit">In Transit</option>
                <option value="arrived">Arrived</option>
                <option value="setup">Setup</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
                <option value="failed">Failed</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>Notes (optional)</Label>
              <textarea
                value={statusNotes}
                onChange={(e) => setStatusNotes(e.target.value)}
                rows={2}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                placeholder="Reason for status change"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowStatusDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleStatusUpdate} disabled={updatingStatus}>
              {updatingStatus ? "Updating..." : "Update Status"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
