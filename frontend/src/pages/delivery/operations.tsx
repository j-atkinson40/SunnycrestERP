import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { deliveryService } from "@/services/delivery-service";
import { getApiErrorMessage } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { getDeliveryTypeBadgeClass, getDeliveryTypeName } from "@/lib/delivery-types";
import type {
  DeliveryRoute,
  DeliveryStats,
} from "@/types/delivery";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

function stopStatusDot(status: string) {
  const colors: Record<string, string> = {
    pending: "bg-gray-400",
    en_route: "bg-blue-500",
    arrived: "bg-indigo-500",
    in_progress: "bg-yellow-500",
    completed: "bg-green-500",
    skipped: "bg-red-400",
  };
  return (
    <span
      className={`inline-block h-2.5 w-2.5 rounded-full ${colors[status] || "bg-gray-300"}`}
      title={status}
    />
  );
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

export default function OperationsPage() {
  const [stats, setStats] = useState<DeliveryStats | null>(null);
  const [routes, setRoutes] = useState<DeliveryRoute[]>([]);
  const [loading, setLoading] = useState(true);
  const [routeDate, setRouteDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [statusFilter, setStatusFilter] = useState("");

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [statsRes, routesRes] = await Promise.all([
        deliveryService.getStats(),
        deliveryService.getRoutes(1, 50, {
          route_date: routeDate,
          route_status: statusFilter || undefined,
        }),
      ]);
      setStats(statsRes);
      setRoutes(routesRes.items);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [routeDate, statusFilter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Auto-refresh every 30s
  useEffect(() => {
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, [loadData]);

  if (loading && !stats) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading operations board...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Daily Operations</h1>
          <p className="text-sm text-muted-foreground">
            Live view — auto-refreshes every 30s
          </p>
        </div>
        <Button variant="outline" onClick={loadData} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh"}
        </Button>
      </div>

      {/* Stats Row */}
      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          <Card className="p-3 text-center">
            <p className="text-xl font-bold">{stats.total_deliveries}</p>
            <p className="text-xs text-muted-foreground">Total</p>
          </Card>
          <Card className="p-3 text-center">
            <p className="text-xl font-bold">{stats.pending}</p>
            <p className="text-xs text-muted-foreground">Pending</p>
          </Card>
          <Card className="p-3 text-center">
            <p className="text-xl font-bold">{stats.scheduled}</p>
            <p className="text-xs text-muted-foreground">Scheduled</p>
          </Card>
          <Card className="p-3 text-center">
            <p className="text-xl font-bold">{stats.in_transit}</p>
            <p className="text-xs text-muted-foreground">In Transit</p>
          </Card>
          <Card className="p-3 text-center">
            <p className="text-xl font-bold">{stats.completed_today}</p>
            <p className="text-xs text-muted-foreground">Completed</p>
          </Card>
          <Card className="p-3 text-center">
            <p className="text-xl font-bold">{stats.active_routes}</p>
            <p className="text-xs text-muted-foreground">Active Routes</p>
          </Card>
          <Card className="p-3 text-center">
            <p className="text-xl font-bold">{stats.available_drivers}</p>
            <p className="text-xs text-muted-foreground">Drivers</p>
          </Card>
        </div>
      )}

      {/* Filters */}
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
          <Label>Status</Label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-md border bg-background px-3 py-2 text-sm"
          >
            <option value="">All</option>
            <option value="draft">Draft</option>
            <option value="dispatched">Dispatched</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
          </select>
        </div>
      </div>

      {/* Route Cards */}
      {routes.length === 0 ? (
        <Card className="p-8 text-center text-muted-foreground">
          No routes found for this date.
        </Card>
      ) : (
        <div className="space-y-4">
          {routes.map((route) => {
            const completedStops = route.stops.filter(
              (s) => s.status === "completed",
            ).length;
            const progress =
              route.stops.length > 0
                ? Math.round((completedStops / route.stops.length) * 100)
                : 0;

            return (
              <Card key={route.id} className="p-4">
                {/* Route Header */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Link
                      to={`/delivery/routes/${route.id}`}
                      className="text-lg font-semibold hover:underline"
                    >
                      {route.driver_name || "Unassigned Driver"}
                    </Link>
                    {routeStatusBadge(route.status)}
                  </div>
                  <div className="flex items-center gap-3 text-sm text-muted-foreground">
                    {route.vehicle_name && <span>{route.vehicle_name}</span>}
                    <span>
                      {completedStops}/{route.stops.length} stops
                    </span>
                  </div>
                </div>

                {/* Progress bar */}
                <div className="mt-2 h-1.5 rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-green-500 transition-all"
                    style={{ width: `${progress}%` }}
                  />
                </div>

                {/* Stops Timeline */}
                {route.stops.length > 0 && (
                  <div className="mt-3 space-y-2">
                    {route.stops.map((stop, i) => {
                      const isCarrier = !!stop.delivery?.carrier_id;
                      return (
                        <div
                          key={stop.id}
                          className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm ${
                            stop.status === "completed"
                              ? "bg-green-50 dark:bg-green-950/20"
                              : stop.status === "in_progress"
                                ? "bg-yellow-50 dark:bg-yellow-950/20"
                                : ""
                          }`}
                        >
                          {stopStatusDot(stop.status)}
                          <span className="w-5 text-xs font-medium text-muted-foreground">
                            {i + 1}
                          </span>
                          <span className="min-w-0 flex-1">
                            <Link
                              to={`/delivery/deliveries/${stop.delivery_id}`}
                              className="hover:underline"
                            >
                              {stop.delivery?.customer_name ||
                                stop.delivery?.delivery_address ||
                                "Delivery"}
                            </Link>
                          </span>
                          {stop.delivery && <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${getDeliveryTypeBadgeClass(stop.delivery.delivery_type)}`}>{getDeliveryTypeName(stop.delivery.delivery_type)}</span>}
                          {isCarrier && (
                            <Badge variant="outline" className="text-xs">
                              {stop.delivery?.carrier_name || "Carrier"}
                            </Badge>
                          )}
                          {stop.estimated_arrival && (
                            <span className="text-xs text-muted-foreground">
                              ETA {new Date(stop.estimated_arrival).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                            </span>
                          )}
                          {stop.driver_notes && (
                            <span className="text-xs italic text-muted-foreground" title={stop.driver_notes}>
                              📝
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
