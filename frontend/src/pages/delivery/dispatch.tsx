import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { deliveryService } from "@/services/delivery-service";
import { getApiErrorMessage } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import type {
  DeliveryListItem,
  DeliveryRoute,
  DeliveryStats,
  Driver,
  Vehicle,
  Carrier,
  RouteCreate,
} from "@/types/delivery";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
  return (
    <Badge className={colors[type] || ""}>
      {labels[type] || type}
    </Badge>
  );
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

function fmtDate(d: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString();
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

export default function DispatchPage() {
  const { hasPermission } = useAuth();
  const canDispatch = hasPermission("delivery.dispatch");
  const canCreate = hasPermission("delivery.create");

  // State
  const [stats, setStats] = useState<DeliveryStats | null>(null);
  const [unscheduled, setUnscheduled] = useState<DeliveryListItem[]>([]);
  const [unscheduledTotal, setUnscheduledTotal] = useState(0);
  const [routes, setRoutes] = useState<DeliveryRoute[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [carriers, setCarriers] = useState<Carrier[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [routeDate, setRouteDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [typeFilter, setTypeFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");

  // Create route dialog
  const [showCreateRoute, setShowCreateRoute] = useState(false);
  const [newRouteDriverId, setNewRouteDriverId] = useState("");
  const [newRouteVehicleId, setNewRouteVehicleId] = useState("");
  const [creatingRoute, setCreatingRoute] = useState(false);

  // Create delivery dialog
  const [showCreateDelivery, setShowCreateDelivery] = useState(false);
  const [newDeliveryType, setNewDeliveryType] = useState("funeral_vault");
  const [newDeliveryAddress, setNewDeliveryAddress] = useState("");
  const [newDeliveryPriority, setNewDeliveryPriority] = useState("normal");
  const [newDeliveryDate, setNewDeliveryDate] = useState("");
  const [newDeliveryCarrierId, setNewDeliveryCarrierId] = useState("");
  const [newDeliveryWeight, setNewDeliveryWeight] = useState("");
  const [newDeliveryInstructions, setNewDeliveryInstructions] = useState("");
  const [creatingDelivery, setCreatingDelivery] = useState(false);

  // Assign to route dialog
  const [assignDelivery, setAssignDelivery] = useState<DeliveryListItem | null>(null);
  const [assignRouteId, setAssignRouteId] = useState("");
  const [assigning, setAssigning] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [statsRes, unschedRes, routesRes, driversRes, vehiclesRes, carriersRes] =
        await Promise.all([
          deliveryService.getStats(),
          deliveryService.getDeliveries(1, 100, {
            unscheduled_only: true,
            delivery_type: typeFilter || undefined,
          }),
          deliveryService.getRoutes(1, 50, { route_date: routeDate }),
          deliveryService.getDrivers(1, 100, true),
          deliveryService.getVehicles(1, 100, true),
          deliveryService.getCarriers(1, 100, true),
        ]);
      setStats(statsRes);
      setUnscheduled(unschedRes.items);
      setUnscheduledTotal(unschedRes.total);
      setRoutes(routesRes.items);
      setDrivers(driversRes.items);
      setVehicles(vehiclesRes.items);
      setCarriers(carriersRes.items);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [routeDate, typeFilter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreateRoute = async () => {
    if (!newRouteDriverId) return;
    try {
      setCreatingRoute(true);
      const payload: RouteCreate = {
        driver_id: newRouteDriverId,
        vehicle_id: newRouteVehicleId || undefined,
        route_date: routeDate,
      };
      await deliveryService.createRoute(payload);
      toast.success("Route created");
      setShowCreateRoute(false);
      setNewRouteDriverId("");
      setNewRouteVehicleId("");
      loadData();
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setCreatingRoute(false);
    }
  };

  const handleCreateDelivery = async () => {
    try {
      setCreatingDelivery(true);
      await deliveryService.createDelivery({
        delivery_type: newDeliveryType,
        delivery_address: newDeliveryAddress || undefined,
        priority: newDeliveryPriority,
        requested_date: newDeliveryDate || undefined,
        carrier_id: newDeliveryCarrierId || undefined,
        weight_lbs: newDeliveryWeight || undefined,
        special_instructions: newDeliveryInstructions || undefined,
      });
      toast.success("Delivery created");
      setShowCreateDelivery(false);
      setNewDeliveryAddress("");
      setNewDeliveryWeight("");
      setNewDeliveryInstructions("");
      loadData();
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setCreatingDelivery(false);
    }
  };

  const handleAssignToRoute = async () => {
    if (!assignDelivery || !assignRouteId) return;
    try {
      setAssigning(true);
      await deliveryService.addStop(assignRouteId, assignDelivery.id);
      toast.success("Delivery added to route");
      setAssignDelivery(null);
      setAssignRouteId("");
      loadData();
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setAssigning(false);
    }
  };

  // Filter unscheduled
  const filteredUnscheduled = unscheduled.filter((d) => {
    if (priorityFilter && d.priority !== priorityFilter) return false;
    return true;
  });

  if (loading && !stats) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading dispatch board...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dispatch</h1>
          <p className="text-sm text-muted-foreground">Build routes and assign deliveries</p>
        </div>
        <div className="flex gap-2">
          {canCreate && (
            <Button variant="outline" onClick={() => setShowCreateDelivery(true)}>
              New Delivery
            </Button>
          )}
          {canDispatch && (
            <Button onClick={() => setShowCreateRoute(true)}>New Route</Button>
          )}
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Card className="p-3 text-center">
            <p className="text-2xl font-bold">{stats.total_deliveries}</p>
            <p className="text-xs text-muted-foreground">Total Deliveries</p>
          </Card>
          <Card className="p-3 text-center">
            <p className="text-2xl font-bold">{stats.pending}</p>
            <p className="text-xs text-muted-foreground">Pending</p>
          </Card>
          <Card className="p-3 text-center">
            <p className="text-2xl font-bold">{stats.active_routes}</p>
            <p className="text-xs text-muted-foreground">Active Routes</p>
          </Card>
          <Card className="p-3 text-center">
            <p className="text-2xl font-bold">{stats.completed_today}</p>
            <p className="text-xs text-muted-foreground">Completed Today</p>
          </Card>
        </div>
      )}

      {/* Date Picker */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Label>Date</Label>
          <Input
            type="date"
            value={routeDate}
            onChange={(e) => setRouteDate(e.target.value)}
            className="w-44"
          />
        </div>
        <div className="flex items-center gap-2">
          <Label>Type</Label>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="rounded-md border bg-background px-3 py-2 text-sm"
          >
            <option value="">All Types</option>
            <option value="funeral_vault">Funeral Vault</option>
            <option value="precast">Precast</option>
            <option value="redi_rock">Redi-Rock</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <Label>Priority</Label>
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="rounded-md border bg-background px-3 py-2 text-sm"
          >
            <option value="">All</option>
            <option value="urgent">Urgent</option>
            <option value="high">High</option>
            <option value="normal">Normal</option>
            <option value="low">Low</option>
          </select>
        </div>
      </div>

      {/* Two-panel layout */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Left: Unscheduled Deliveries */}
        <div>
          <h2 className="mb-3 text-lg font-semibold">
            Unscheduled ({unscheduledTotal})
          </h2>
          <div className="space-y-2">
            {filteredUnscheduled.length === 0 ? (
              <Card className="p-4 text-center text-sm text-muted-foreground">
                No unscheduled deliveries
              </Card>
            ) : (
              filteredUnscheduled.map((d) => (
                <Card key={d.id} className="p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        {typeBadge(d.delivery_type)}
                        {priorityBadge(d.priority)}
                        {d.carrier_name && (
                          <Badge variant="outline" className="text-xs">
                            {d.carrier_name}
                          </Badge>
                        )}
                      </div>
                      <p className="mt-1 text-sm font-medium">
                        <Link
                          to={`/delivery/deliveries/${d.id}`}
                          className="hover:underline"
                        >
                          {d.customer_name || "No Customer"}
                        </Link>
                      </p>
                      <p className="truncate text-xs text-muted-foreground">
                        {d.delivery_address || "No address"}
                      </p>
                      <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                        <span>Requested: {fmtDate(d.requested_date)}</span>
                        {d.weight_lbs && <span>{d.weight_lbs} lbs</span>}
                      </div>
                    </div>
                    {canDispatch && routes.length > 0 && !d.carrier_id && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setAssignDelivery(d);
                          setAssignRouteId(routes[0]?.id || "");
                        }}
                      >
                        Assign
                      </Button>
                    )}
                  </div>
                </Card>
              ))
            )}
          </div>
        </div>

        {/* Right: Routes for Date */}
        <div>
          <h2 className="mb-3 text-lg font-semibold">
            Routes for {new Date(routeDate + "T12:00:00").toLocaleDateString()}
          </h2>
          <div className="space-y-3">
            {routes.length === 0 ? (
              <Card className="p-4 text-center text-sm text-muted-foreground">
                No routes for this date.{" "}
                {canDispatch && (
                  <button
                    onClick={() => setShowCreateRoute(true)}
                    className="text-primary hover:underline"
                  >
                    Create one
                  </button>
                )}
              </Card>
            ) : (
              routes.map((route) => (
                <Card key={route.id} className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <Link
                        to={`/delivery/routes/${route.id}`}
                        className="font-medium hover:underline"
                      >
                        {route.driver_name || "Unassigned Driver"}
                      </Link>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        {route.vehicle_name && <span>{route.vehicle_name}</span>}
                        <span>{route.total_stops} stops</span>
                      </div>
                    </div>
                    {statusBadge(route.status)}
                  </div>

                  {/* Stop list */}
                  {route.stops.length > 0 && (
                    <div className="mt-3 space-y-1.5 border-l-2 border-muted pl-3">
                      {route.stops.map((stop, i) => (
                        <div key={stop.id} className="flex items-center gap-2 text-sm">
                          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium">
                            {i + 1}
                          </span>
                          <span className="min-w-0 flex-1 truncate">
                            {stop.delivery?.customer_name || stop.delivery?.delivery_address || "Delivery"}
                          </span>
                          {stop.delivery && typeBadge(stop.delivery.delivery_type)}
                          <Badge variant="outline" className="text-xs">
                            {stop.status}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Create Route Dialog */}
      <Dialog open={showCreateRoute} onOpenChange={setShowCreateRoute}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Route</DialogTitle>
            <DialogDescription>
              Create a new route for {new Date(routeDate + "T12:00:00").toLocaleDateString()}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>Driver *</Label>
              <select
                value={newRouteDriverId}
                onChange={(e) => setNewRouteDriverId(e.target.value)}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              >
                <option value="">Select a driver</option>
                {drivers.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.employee_name || d.employee_id}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>Vehicle</Label>
              <select
                value={newRouteVehicleId}
                onChange={(e) => setNewRouteVehicleId(e.target.value)}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              >
                <option value="">No vehicle</option>
                {vehicles.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name} {v.license_plate ? `(${v.license_plate})` : ""}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateRoute(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreateRoute}
              disabled={!newRouteDriverId || creatingRoute}
            >
              {creatingRoute ? "Creating..." : "Create Route"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Delivery Dialog */}
      <Dialog open={showCreateDelivery} onOpenChange={setShowCreateDelivery}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>New Delivery</DialogTitle>
            <DialogDescription>Create a delivery to schedule or assign to a carrier</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Type *</Label>
                <select
                  value={newDeliveryType}
                  onChange={(e) => setNewDeliveryType(e.target.value)}
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                >
                  <option value="funeral_vault">Funeral Vault</option>
                  <option value="precast">Precast</option>
                  <option value="redi_rock">Redi-Rock</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <Label>Priority</Label>
                <select
                  value={newDeliveryPriority}
                  onChange={(e) => setNewDeliveryPriority(e.target.value)}
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                >
                  <option value="low">Low</option>
                  <option value="normal">Normal</option>
                  <option value="high">High</option>
                  <option value="urgent">Urgent</option>
                </select>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Delivery Address</Label>
              <Input
                value={newDeliveryAddress}
                onChange={(e) => setNewDeliveryAddress(e.target.value)}
                placeholder="123 Main St, City, State"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Requested Date</Label>
                <Input
                  type="date"
                  value={newDeliveryDate}
                  onChange={(e) => setNewDeliveryDate(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label>Weight (lbs)</Label>
                <Input
                  type="number"
                  value={newDeliveryWeight}
                  onChange={(e) => setNewDeliveryWeight(e.target.value)}
                  placeholder="Optional"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Carrier (optional — for third-party delivery)</Label>
              <select
                value={newDeliveryCarrierId}
                onChange={(e) => setNewDeliveryCarrierId(e.target.value)}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              >
                <option value="">Own Fleet</option>
                {carriers.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.carrier_type === "third_party" ? "3rd Party" : "Own Fleet"})
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>Special Instructions</Label>
              <textarea
                value={newDeliveryInstructions}
                onChange={(e) => setNewDeliveryInstructions(e.target.value)}
                rows={2}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                placeholder="Optional notes for the driver"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDelivery(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateDelivery} disabled={creatingDelivery}>
              {creatingDelivery ? "Creating..." : "Create Delivery"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Assign to Route Dialog */}
      <Dialog open={!!assignDelivery} onOpenChange={(open) => !open && setAssignDelivery(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Assign to Route</DialogTitle>
            <DialogDescription>
              Assign "{assignDelivery?.customer_name || "delivery"}" to a route
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Label>Select Route</Label>
            <select
              value={assignRouteId}
              onChange={(e) => setAssignRouteId(e.target.value)}
              className="w-full rounded-md border bg-background px-3 py-2 text-sm"
            >
              {routes.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.driver_name || "Unassigned"} — {r.total_stops} stops
                </option>
              ))}
            </select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAssignDelivery(null)}>
              Cancel
            </Button>
            <Button onClick={handleAssignToRoute} disabled={!assignRouteId || assigning}>
              {assigning ? "Assigning..." : "Add to Route"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
