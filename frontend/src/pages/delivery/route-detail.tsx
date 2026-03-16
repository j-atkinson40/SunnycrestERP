import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { deliveryService } from "@/services/delivery-service";
import { getApiErrorMessage } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import type { DeliveryRoute, DeliveryListItem } from "@/types/delivery";

function routeStatusBadge(status: string) {
  const map: Record<string, { className: string; label: string }> = {
    draft: { className: "bg-gray-100 text-gray-800", label: "Draft" },
    dispatched: { className: "bg-blue-100 text-blue-800", label: "Dispatched" },
    in_progress: { className: "bg-yellow-100 text-yellow-800", label: "In Progress" },
    completed: { className: "bg-green-100 text-green-800", label: "Completed" },
    cancelled: { className: "", label: "Cancelled" },
  };
  const info = map[status];
  if (info) return <Badge className={info.className}>{info.label}</Badge>;
  return <Badge variant="outline">{status}</Badge>;
}

function stopStatusBadge(status: string) {
  const map: Record<string, { className: string; label: string }> = {
    pending: { className: "bg-gray-100 text-gray-800", label: "Pending" },
    en_route: { className: "bg-blue-100 text-blue-800", label: "En Route" },
    arrived: { className: "bg-indigo-100 text-indigo-800", label: "Arrived" },
    in_progress: { className: "bg-yellow-100 text-yellow-800", label: "In Progress" },
    completed: { className: "bg-green-100 text-green-800", label: "Completed" },
    skipped: { className: "bg-red-100 text-red-800", label: "Skipped" },
  };
  const info = map[status];
  if (info) return <Badge className={info.className}>{info.label}</Badge>;
  return <Badge variant="outline">{status}</Badge>;
}

function typeBadge(type: string) {
  const colors: Record<string, string> = {
    funeral_vault: "bg-purple-100 text-purple-800",
    precast: "bg-blue-100 text-blue-800",
    redi_rock: "bg-orange-100 text-orange-800",
  };
  const labels: Record<string, string> = {
    funeral_vault: "Vault",
    precast: "Precast",
    redi_rock: "Redi-Rock",
  };
  return <Badge className={colors[type] || ""}>{labels[type] || type}</Badge>;
}

function fmtTime(d: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function fmtDateTime(d: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleString();
}

export default function RouteDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { hasPermission } = useAuth();
  const canEdit = hasPermission("routes.edit");

  const [route, setRoute] = useState<DeliveryRoute | null>(null);
  const [loading, setLoading] = useState(true);

  // Add stop
  const [showAddStop, setShowAddStop] = useState(false);
  const [unscheduled, setUnscheduled] = useState<DeliveryListItem[]>([]);
  const [selectedDeliveryId, setSelectedDeliveryId] = useState("");
  const [addingStop, setAddingStop] = useState(false);

  // Status update
  const [updatingStatus, setUpdatingStatus] = useState(false);

  const loadRoute = useCallback(async () => {
    if (!id) return;
    try {
      setLoading(true);
      const r = await deliveryService.getRoute(id);
      setRoute(r);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadRoute();
  }, [loadRoute]);

  const loadUnscheduled = async () => {
    try {
      const res = await deliveryService.getDeliveries(1, 50, { unscheduled_only: true });
      setUnscheduled(res.items);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    }
  };

  const handleAddStop = async () => {
    if (!id || !selectedDeliveryId) return;
    try {
      setAddingStop(true);
      await deliveryService.addStop(id, selectedDeliveryId);
      toast.success("Stop added");
      setShowAddStop(false);
      setSelectedDeliveryId("");
      loadRoute();
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setAddingStop(false);
    }
  };

  const handleRemoveStop = async (stopId: string) => {
    if (!id) return;
    try {
      await deliveryService.removeStop(id, stopId);
      toast.success("Stop removed");
      loadRoute();
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    }
  };

  const handleStatusChange = async (newStatus: string) => {
    if (!route) return;
    try {
      setUpdatingStatus(true);
      await deliveryService.updateRoute(route.id, { status: newStatus });
      toast.success(`Route status updated to ${newStatus}`);
      loadRoute();
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setUpdatingStatus(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading route...</p>
      </div>
    );
  }

  if (!route) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-destructive">Route not found</p>
      </div>
    );
  }

  const completedStops = route.stops.filter((s) => s.status === "completed").length;
  const progress = route.stops.length > 0 ? Math.round((completedStops / route.stops.length) * 100) : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Link to="/delivery/operations" className="text-sm text-muted-foreground hover:underline">
              Operations
            </Link>
            <span className="text-muted-foreground">/</span>
            <h1 className="text-2xl font-bold">
              {route.driver_name || "Unassigned"}'s Route
            </h1>
          </div>
          <div className="mt-1 flex items-center gap-2">
            {routeStatusBadge(route.status)}
            <span className="text-sm text-muted-foreground">
              {new Date(route.route_date + "T12:00:00").toLocaleDateString()}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          {canEdit && route.status === "draft" && (
            <Button onClick={() => handleStatusChange("dispatched")} disabled={updatingStatus}>
              Dispatch
            </Button>
          )}
          {canEdit && route.status === "dispatched" && (
            <Button variant="outline" onClick={() => handleStatusChange("draft")} disabled={updatingStatus}>
              Back to Draft
            </Button>
          )}
          {canEdit && (
            <Button
              variant="outline"
              onClick={() => {
                loadUnscheduled();
                setShowAddStop(true);
              }}
            >
              Add Stop
            </Button>
          )}
        </div>
      </div>

      {/* Route Info */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {/* Progress */}
          <Card className="p-4">
            <div className="flex items-center justify-between text-sm">
              <span>{completedStops} of {route.stops.length} stops completed</span>
              <span className="font-medium">{progress}%</span>
            </div>
            <div className="mt-2 h-2 rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-green-500 transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
          </Card>

          {/* Stops */}
          <Card className="p-4">
            <h2 className="mb-3 font-semibold">Stops ({route.stops.length})</h2>
            {route.stops.length === 0 ? (
              <p className="text-sm text-muted-foreground">No stops on this route yet.</p>
            ) : (
              <div className="space-y-3">
                {route.stops.map((stop, i) => (
                  <div
                    key={stop.id}
                    className={`rounded-lg border p-3 ${
                      stop.status === "completed"
                        ? "border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950/20"
                        : stop.status === "in_progress"
                          ? "border-yellow-200 bg-yellow-50 dark:border-yellow-900 dark:bg-yellow-950/20"
                          : ""
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-muted text-sm font-medium">
                          {i + 1}
                        </span>
                        <div>
                          <div className="flex items-center gap-2">
                            <Link
                              to={`/delivery/deliveries/${stop.delivery_id}`}
                              className="font-medium hover:underline"
                            >
                              {stop.delivery?.customer_name ||
                                stop.delivery?.delivery_address ||
                                "Delivery"}
                            </Link>
                            {stop.delivery && typeBadge(stop.delivery.delivery_type)}
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {stop.delivery?.delivery_address || "No address"}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {stopStatusBadge(stop.status)}
                        {canEdit && route.status === "draft" && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleRemoveStop(stop.id)}
                          >
                            Remove
                          </Button>
                        )}
                      </div>
                    </div>
                    <div className="mt-2 flex gap-4 text-xs text-muted-foreground">
                      <span>ETA: {fmtTime(stop.estimated_arrival)}</span>
                      <span>Actual: {fmtTime(stop.actual_arrival)}</span>
                      {stop.driver_notes && <span className="italic">Note: {stop.driver_notes}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <Card className="p-4">
            <h3 className="mb-2 text-sm font-semibold">Route Info</h3>
            <dl className="space-y-2 text-sm">
              <div>
                <dt className="text-muted-foreground">Driver</dt>
                <dd>{route.driver_name || "—"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Vehicle</dt>
                <dd>{route.vehicle_name || "—"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Date</dt>
                <dd>{new Date(route.route_date + "T12:00:00").toLocaleDateString()}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Total Mileage</dt>
                <dd>{route.total_mileage ? `${route.total_mileage} mi` : "—"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Started</dt>
                <dd>{fmtDateTime(route.started_at)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Completed</dt>
                <dd>{fmtDateTime(route.completed_at)}</dd>
              </div>
            </dl>
          </Card>

          {route.notes && (
            <Card className="p-4">
              <h3 className="mb-2 text-sm font-semibold">Notes</h3>
              <p className="text-sm text-muted-foreground">{route.notes}</p>
            </Card>
          )}
        </div>
      </div>

      {/* Add Stop Dialog */}
      <Dialog open={showAddStop} onOpenChange={setShowAddStop}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Stop</DialogTitle>
            <DialogDescription>Select an unscheduled delivery to add to this route</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            {unscheduled.length === 0 ? (
              <p className="text-sm text-muted-foreground">No unscheduled deliveries available.</p>
            ) : (
              <select
                value={selectedDeliveryId}
                onChange={(e) => setSelectedDeliveryId(e.target.value)}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              >
                <option value="">Select a delivery</option>
                {unscheduled.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.customer_name || "No customer"} — {d.delivery_address || "No address"} ({d.delivery_type})
                  </option>
                ))}
              </select>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddStop(false)}>
              Cancel
            </Button>
            <Button onClick={handleAddStop} disabled={!selectedDeliveryId || addingStop}>
              {addingStop ? "Adding..." : "Add Stop"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
